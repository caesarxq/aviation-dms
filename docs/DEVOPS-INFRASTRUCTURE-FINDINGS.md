# Aviation DMS — DevOps Infrastructure Findings

**Updated:** 2026-11-12
**Status:** Draft PR #1 open; production backup helper and disabled systemd units installed; no DMS backup or application deployment performed
**Scope:** CI/CD, branch protection, secrets, reverse proxy, backups, IaC

---

## 1. Verified GitHub Configuration

- Repository visibility is `PUBLIC`.
- Actions secret names were confirmed configured: `BASTION_SSH_PRIVATE_KEY`, `STAGING_SSH_PRIVATE_KEY`, `PRODUCTION_SSH_PRIVATE_KEY`, `CR_PAT`, and `PROD_HOST`. Values were not read or recorded.
- The updated workflow uses the private production address directly; `PROD_HOST` is no longer required by that workflow.
- Public `main` contains SMTP password assignments in three tracked environment examples. Sanitized Zoho examples are prepared locally, but their edits are excluded from this PR because the deletion diff would repeat the old credential publicly. Treat it as exposed, rotate it, then handle history cleanup as a separately authorized operation.

Never put credential values in issues, chat, workflow logs, or committed examples. Pass registry credentials to `docker login --password-stdin`; store runtime secrets in protected host-side files.

---

## 2. Branch Protection — PR-ONLY, ZERO APPROVALS, ADMIN ENFORCEMENT ON

The owner selected zero required approvals with PR checks enforced. GitHub now requires a pull request, enforces rules for administrators, and retains strict required checks (`Build Docker images`, `Run backend tests`, `Run frontend tests`). No approval vote is required. The repository has one collaborator.

The `production` environment is not configured (only `staging` exists, with no protection rules). The workflow's two boolean inputs are single-operator attestations, not independent review.

The draft PR adds a `pull_request` trigger and a non-publishing image build. Its required backend, frontend, and image-build checks have run successfully on PR events; staging and production jobs were skipped. The workflow change is not yet in `main`. Do not bypass the protected branch if a future required check is missing; diagnose the trigger first.

---

## 3. CI/CD and Runtime Configuration — REMEDIATION PREPARED

### Verified staging deployment failure

Run `43227041924` completed with backend tests, frontend tests, and image build passing; staging failed while creating the `https_proxy` container. The Docker daemon reported that `/opt/kfl-aviation-dms-staging/Caddyfile.staging` was a directory where a file mount was expected. Both public HTTPS sites returned HTTP 200 during a later read-only check; no deployment was run during this evaluation.

### Draft PR #1 changes

- Added PR triggers; tests run before image build, and PRs do not publish images or deploy.
- Staging now syncs the Compose files and deploy script, pulls the tested GHCR images, uses `--no-build`, passes the registry credential through stdin, and excludes the containerized proxy that caused the mount failure. A staging deployment requires `workflow_dispatch` with `approve_staging=true`; pushes to `main` do not change live environments.
- Corrected Compose port merging: staging config now renders only `8001`/`8081`, not both those ports and base `8000`/`8080`. Production renders `8000`/`8080`. Caddy is profile-gated for local standalone use; OCI uses bastion Caddy.
- Corrected trusted proxy IPs to the exact bastion private peer address and changed Caddy forwarding to `{remote_host}`, which supplies a parseable IP to the rate limiter.
- Production deployment now fails closed unless a production-specific backup helper exists and succeeds; it no longer tears down the running stack on health failure.
- The production-specific helper and systemd service/timer are now installed at the expected paths on `roc-app`; `systemd-analyze verify` passed. The timer is disabled. The host lacks Restic, the backup SSH identity, pinned off-host host key, `/etc/kfl-aviation-dms-prod/backup.env`, a dedicated encrypted staging mount, and the staging encryption attestation; no backup was run. The candidate off-host target and OCI-managed volume policies were not independently verified.
- Production SMTP source is `/run/secrets/smtp_pass` on host `/run` tmpfs. Its contents were not read or changed. After approval, permissions were hardened to `root:10001` `0440`; the backend can read it. The running container has `NOTIFICATION_ENABLED=true` but no `SMTP_PASS_FILE` value; the app then falls back to `SMTP_PASS`, which I did not inspect. A direct test of the new Zoho credential for `info@kfl.ke` was accepted and the owner-provided screenshot confirms receipt, but production is not switched to it. The `/run` path may not survive reboot.
- Prepared Zoho SMTP examples using `SMTP_PASS_SECRET_FILE` and no password value; those files are excluded from this PR until the public secret-bearing diff can be handled safely.
- Fixed the isolated-database harness for `test_seed_audit_findings.py` and removed that file from CI exclusions.

### Verification run

- Backend suite: `571 passed, 1 skipped` (Python 3.11; one existing warning).
- Staging and production Compose render/validation passed; rendered host ports match their intended values and Caddy is absent from default OCI service sets.
- Deployment shell scripts pass `bash -n`; workflow YAML parses; `git diff --check` passes.
- Staging and production application containers were not deployed or restarted. The production helper files and disabled units were installed; no backup was run.

---

## 4. Off-Host Restore Drill — OWNER-REPORTED COMPLETE

### Current State
- The owner reports a successful off-host drill to `10.20.173.120`; see `docs/OFF-HOST-RESTORE-DRILL-REPORT.md`.
- The report records RPO under 24 hours (target: 2 days) and RTO under 2 hours (target: 5 hours), based on owner-supplied drill evidence.
- This evaluation did not independently rerun the drill or inspect backup contents.
- The production-specific helper now exists at `/opt/kfl-aviation-dms-prod/scripts/full-stack-backup-prod.sh`, but its encrypted remote repository is not configured and its timer is disabled. The owner-reported drill is not independently tied to the current production database/volume or the added `document_files/` validation.

---

## 5. Infrastructure as Code — MANUAL OCI STATE

### Current State
- Terraform directory removed (was not applied, contained uncommitted OCIDs)
- Production instance `10.20.1.69` created manually via OCI Console
- Staging instance `10.20.4.234` exists as cloud VM
- Bastion `145.241.152.126` runs Caddy for TLS termination
- All infrastructure state is manual, not versioned

### Risk
- No reproducible infrastructure definition
- Disaster recovery requires manual recreation
- Configuration drift between environments possible
- OCIDs and network details not in version control

Terraform was removed at the owner's direction. Keep OCI changes manual until there is an approved IaC approach and a safe import plan; do not reintroduce the removed configuration as a drive-by fix.

---

## 6. Current State and Remaining Gates

- `stage.kfl.ke` and `roc.kfl.ke` returned HTTP 200 at the time of this evaluation; public TCP probes for ports `111`, `8000`, `8001`, `8080`, and `8081` were closed/filtered.
- Recent Actions runs failed at staging deployment; image builds and backend/frontend tests passed.
- Branch protection requires strict PR checks, zero approval votes, and applies to administrators. The `pull_request` workflow is published; required checks passed on current PR head `6d49b7d`.
- Production promotion remains blocked: the production-specific helper and systemd units are installed, but the timer is disabled. Restic, repository credentials, pinned SSH identity/host key, dedicated encrypted staging mount/attestation, retention approval, an external failure-alert route, and an isolated restore are still missing; no backup was run.
- PR #1 remains draft with the reviewed backup fixes pushed and required checks passing. No production application deployment or restart occurred.

---

## Next Steps (Priority Order)

1. Complete production SMTP rotation after the backup gate; decide separately whether to remediate public repository history.
2. Keep PR #1 in draft until the remaining production backup gates and owner approvals are satisfied; merge only after they close.
3. Do not deploy staging until the explicit workflow input is authorized; then validate the four service health checks and HTTPS endpoint.
4. Provision the dedicated encrypted staging volume, verify the off-host target and host key, approve recovery/retention targets, then run and restore a manual backup before enabling the timer or production promotion.
5. Public TCP probes show ports `111`, `8000`, `8001`, `8080`, and `8081` closed/filtered. Confirm the OCI NSG/security-list rules match that intent; UDP/111 was not tested.
