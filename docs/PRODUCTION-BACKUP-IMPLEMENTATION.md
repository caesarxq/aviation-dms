# Production DMS Backup Helper and Schedule

## Purpose and current gate

The production deployment preflight requires `/opt/kfl-aviation-dms-prod/scripts/full-stack-backup-prod.sh`. This helper creates a validated DMS data candidate and stores it in an encrypted Restic SFTP repository. It never initializes a new remote repository automatically, never prunes snapshots, and fails closed when the production volume, password-file permissions, SSH identity, pinned host key, or Restic repository is unavailable.

The helper and systemd units are implemented in this branch. The production host was inspected: it has volume `kfl-aviation-dms-prod_dms_data` mounted at `/app/data`, but lacks Restic, a backup SSH identity, a pinned host key for the reported off-host host, and an active DMS timer. Therefore the timer must remain disabled until the requirements below are provisioned and verified.

## Backup scope

- `dms.db`, copied with SQLite's online backup API rather than raw file copy.
- `uploads/`, `kcaa-evidence/`, `attachments/`, and `document_files/` including generated `extracts/`.
- The candidate manifest records file paths, sizes, and SHA-256 hashes. Validation checks SQLite integrity/schema, existing upload/evidence references, document-file references, and generated extract references.
- Unknown top-level entries, symlinks, special files, missing referenced files, size/hash mismatches, or an unaccepted candidate abort the run before off-host upload.
- The helper records host/volume/image metadata only. It excludes `.env`, SMTP/bootstrap secrets, SSH keys, TLS private keys, runtime environment values, and Docker images; configuration and image digests are recoverable from Git and the registry.

The application validator and candidate creator now include `document_files/` and verify `document_files` and `section_extractions` references. Keep these checks in sync when new file roots or file-reference tables are added.

## Encryption and off-host prerequisites

1. Confirm and authorize the off-host destination; `10.20.173.120` is a candidate from prior documentation, not currently verified from production.
2. Install Restic on production. Configure a dedicated SFTP identity at `/etc/kfl-aviation-dms-prod/backup-secrets/backup_ssh_key`, owner `root:root`, mode `0600`.
3. Obtain the destination's SSH host-key fingerprint through a trusted channel and install a pinned `known_hosts` file at `/etc/kfl-aviation-dms-prod/backup-secrets/backup_known_hosts`. The helper requires `StrictHostKeyChecking=yes`; do not use `ssh-keyscan` output as trust by itself.
4. Initialize the Restic repository once, manually, only after verifying the destination. Store the repository password in `/etc/kfl-aviation-dms-prod/backup-secrets/restic_password`, owner `root:root`, mode `0600`. Never put it in an environment value, command argument, log, or Git.
5. Verify the host staging filesystem is encrypted at rest and has capacity for a full candidate. Staging is created with restrictive permissions; it is removed after each run.
6. Create `/etc/kfl-aviation-dms-prod/backup.env` from `deploy/systemd/backup.env.example`; it contains non-secret paths and the Restic repository URL only. Protect it as `root:root`, mode `0640`.

No helper or timer should be enabled until the off-host repository, encryption, staging protection, and restore access are verified.

## Schedule and retention

`deploy/systemd/kfl-aviation-dms-backup.service` is a hardened oneshot service. `deploy/systemd/kfl-aviation-dms-backup.timer` schedules it daily at 02:00 UTC with persistent catch-up and a randomized delay. The installer reloads systemd but intentionally does not enable or start the timer.

There is no automatic Restic `forget` or `prune` in the helper. The Records Custodian must approve how the policy's 36-month and lifetime record classes apply to full backup snapshots and legal holds before pruning is implemented. The Accountable Manager must approve RPO/RTO. The current DR document proposes RPO 2 days and RTO 5 hours; a successful daily schedule would target at most 24 hours of data loss only if every scheduled run succeeds.

## Install and activate

Install files on the production host from a trusted checkout/archive:

```bash
sudo ./scripts/install-prod-backup-helper.sh /path/to/aviation-dms-checkout
```

The installer installs the helper and unit files and reloads systemd; it does not start/restart application services or enable the timer. After prerequisites are provisioned:

1. Run the helper once manually and verify the Restic snapshot ID.
2. Restore that snapshot to an isolated target; run `python -m app.backup_validation verify --data-root <candidate> --confirm-isolated-candidate` and inspect the report.
3. Record the restore result and owner-approved RPO/RTO/retention.
4. Enable `kfl-aviation-dms-backup.timer`; verify `systemctl list-timers` and monitor the first scheduled success.
5. Keep production deployment fail-closed until the pre-deployment helper completes successfully.

The prior owner-reported restore report describes a manual drill; it does not establish an active recurring production schedule. Repeat an isolated restore with the expanded `document_files/` coverage before treating the current backup path as verified.
