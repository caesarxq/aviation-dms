# Aviation DMS — Disaster Recovery

**Version:** 1.0
**Date:** 2026-11-12
**Owner:** Backend/IT Lead and System Administrator
**Approval Status:** Draft — awaiting Accountable Manager approval of recovery objectives
**Classification:** Internal — operational procedure

---

## 1. Purpose

This document defines the disaster recovery (DR) procedure for the KFL Aviation DMS. It covers backup creation, off-host transfer, isolated restore, validation, and the go/no-go decision for operational use.

A successful backup or restore test does **not** constitute operational or regulatory approval. The Accountable Manager must approve recovery objectives and accept the restore drill before the DMS is considered operationally ready.

---

## 2. Recovery Objectives (Pending Approval)

| Metric | Target | Status |
|--------|--------|--------|
| RPO (Recovery Point Objective) | 2 days | Proposed — pending Accountable Manager approval |
| RTO (Recovery Time Objective) | 5 hours | Proposed — pending Accountable Manager approval |
| Backup frequency | Daily at 02:00 UTC | Planned systemd timer; not active |
| Backup location | Dedicated encrypted Restic repository on an approved off-host target | Destination/key/host identity not configured |
| Off-host encryption | Required | Restic design prepared; no production Restic installation/configuration |

These targets are **proposed values** and must be approved by the Accountable Manager before operational go/no-go.

---

## 3. Backup Scope

A complete backup includes the entire `/app/data` directory as one set:

- `dms.db` — consistent SQLite online backup (do not raw-copy the live DB)
- `uploads/` — personnel credential files
- `kcaa-evidence/` — KCAA approval evidence PDFs
- `attachments/` — P3 audit evidence attachments
- `document_files/` — source document files and generated extracts

Do not include `.env`, SMTP/bootstrap secrets, SSH keys, TLS private keys, runtime environment values, or Docker images. Versioned configuration and image identifiers are recoverable from Git and the container registry.

**Never copy only `dms.db`.** A consistent backup requires the complete directory.

---

## 4. Backup Procedure

### 4.1 Create Backup (Production Instance)

```bash
sudo /opt/kfl-aviation-dms-prod/scripts/full-stack-backup-prod.sh
```

This command is usable only after the production helper's Restic repository, dedicated encrypted staging mount and root-owned OCI encryption attestation, password file, dedicated SSH identity, and pinned host key are configured. It uses SQLite's online backup API and candidate verification; it does not stop or restart the backend. It fails closed and does not prune remote snapshots.

### 4.2 Candidate Manifest and Verification

`full-stack-backup-prod.sh` creates the SHA-256 manifest and validates the isolated candidate before Restic transfer. Do not manually edit the candidate or manifest. For a separately restored candidate, run the read-only verifier:

```bash
(cd backend && python -m app.backup_validation verify \
  --data-root "$RESTORE_CANDIDATE" --confirm-isolated-candidate)
```

The manifest verifies transfer integrity but is **not** a digital signature or proof of source authenticity.

### 4.3 Transfer to Off-Host Storage

The configured Restic SFTP repository must be encrypted, access-controlled, and verified against a pinned SSH host key before any scheduled backup is enabled. The previously reported `10.20.173.120` destination remains a candidate until its host identity, access controls, capacity, encryption, and isolated restore path are re-verified.

---

## 5. Restore Procedure

### 5.1 Isolate the Restore Target

The restore must target a **separate, isolated** directory — never the live `/app/data` volume. The validator refuses candidates overlapping active development data.

### 5.2 Restore from Backup

Restore the complete directory to an isolated staging volume:

```bash
# On isolated restore target
mkdir -p "$RESTORE_CANDIDATE"
# Copy from off-host backup server via bastion
```

### 5.3 Verify the Restore Candidate

Verify the restored candidate read-only:

```bash
(cd backend && python -m app.backup_validation verify \
  --data-root "$RESTORE_CANDIDATE" --confirm-isolated-candidate)
```

The verifier checks:
- SHA-256 manifest against every file
- SQLite quick check, integrity check, foreign key check
- All tables declared by the current application schema
- Critical columns for identity, document, audit, and evidence tables
- Referenced files exist
- Stored file hashes match

Exit code `0` = data integrity checks passed. Exit code `2` = blocker found.

### 5.4 Exercise Representative Reads

After verification, exercise representative reads against the restored candidate:
- `PRAGMA integrity_check`
- Confirm KCAA evidence and upload files are present
- Read sample documents, users, and audit events

Record the restore result and timestamp.

---

## 6. Off-Host Restore Drill

A genuine off-host drill requires all of the following before it is considered complete:

1. **Accountable Manager** approves recovery objectives (RPO/RTO) and acceptance criteria
2. **Infrastructure** supplies an authorized off-host destination with encryption, versioning, retention, and access controls
3. **Complete source backup** exists (full `/app/data` directory)
4. **Separate isolated restore target** is provisioned
5. **Restore drill is executed** and validated using `backup_validation.py verify`
6. **Owner records** the successful restore result

The owner-reported `OFF-HOST-RESTORE-DRILL-REPORT.md` records a prior manual drill as passed. The production-specific helper and systemd units are now installed, but the timer remains disabled; Restic, the remote repository/credentials, a pinned SSH identity, the dedicated encrypted staging mount/attestation, and retention approvals are not configured. No backup was run. The prior report also predates `document_files/` reference validation. Treat it as owner-reported manual evidence, not proof of a recurring production backup or full current data-scope validation. Repeat an isolated restore after configuration.

---

## 7. Rollback Procedure

### 7.1 Application Rollback

If a production deployment fails:

1. Choose a new `DMS_RELEASE_TAG` (never reuse a tag)
2. Build once, record backend/frontend image IDs and digests
3. Retain previous tagged images
4. Roll back by restoring the prior tag in the deployment `.env`
5. Run `docker compose up -d --no-build`

Roll back the application image only when the schema remains backward compatible.

### 7.2 Database Rollback (Non-Reversible Migration)

For a migration that cannot be reversed safely:
1. Restore the verified pre-release backup
2. Follow the controlled recovery procedure
3. **Never delete or rewrite audit history** to make rollback appear clean

---

## 8. Roles and Responsibilities

| Role | Responsibility |
|------|----------------|
| **Accountable Manager** | Approves recovery objectives (RPO/RTO), accepts restore drill, gives final go/no-go |
| **Records Custodian** | Owns retention/legal hold basis, classifies findings, approves disposition |
| **Backend/IT Lead** | Implements backup/restore, runs validation, monitors scanner freshness |
| **System Administrator** | Provisions the backup target and encrypted staging mount, enables the systemd timer after approval, manages off-host transfer, provisions restore targets |
| **Responsible Postholders** | Validate source mappings and delegations for their function |

---

## 9. Open Items (Block Operational Go/No-Go)

| Item | Owner | Required For |
|------|-------|--------------|
| Accountable Manager-approved RPO/RTO targets | Accountable Manager | Recovery planning |
| Authorized off-host destination with encryption/versioning/retention | System Administrator | Off-host backup |
| Complete off-host restore drill | System Administrator + Accountable Manager | Operational go/no-go |
| Backup encryption at rest and in transit | Backend/IT Lead | Off-host storage security |
| Documented restore acceptance criteria | Accountable Manager | Drill sign-off |

---

## 10. Testing Schedule

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Backup creation (systemd timer; planned, not enabled) | Daily at 02:00 UTC after approval | System Administrator |
| Backup manifest creation | After each backup | Backend/IT Lead |
| Restore drill | Before go/no-go, then annually | System Administrator + Accountable Manager |
| ClamAV signature freshness check | Daily | Backend/IT Lead |
| Recovery objective review | Annually | Accountable Manager |
