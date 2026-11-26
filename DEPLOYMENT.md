# Aviation DMS — CI/CD Deployment Runbook

## Overview

Staging (shared `roc-dis` VM — bastion and staging are the same host) → Production (new OCI instance).

The pipeline builds and tests images on pushes to `main`; it does not deploy to a live environment on a code push. Staging deployment requires an explicit workflow dispatch approval. Production promotion requires separate staging and production approvals.

## Repositories & Secrets

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `CR_PAT` | Container registry personal access token (ghcr.io) |
| `BASTION_SSH_PRIVATE_KEY` | SSH key for the shared bastion/staging host (`roc-dis`, `145.241.152.126`) |
| `PRODUCTION_SSH_PRIVATE_KEY` | SSH key for production OCI instance |

The workflow pins the single `roc-dis` ED25519 fingerprint (`ROC_DIS_HOST_KEY_FINGERPRINT`) and verifies it against the bastion/staging host key before deploying. Since bastion and staging are the same VM, no separate staging host key or jump host is required.

### Environments

- **staging**: Manual workflow dispatch with `approve_staging=true`; bastion Caddy terminates public TLS
- **production**: Requires manual approval before deployment

## Workflow Triggers

### Push to `main`
```
push → build/publish images → backend/frontend checks; live environments remain unchanged
```

### Authorized staging dispatch (`workflow_dispatch`)
```bash
gh workflow run deploy.yml -f environment=staging -f approve_staging=true
```

Production promotion requires a separate dispatch with `environment=production`, `approve_staging=true`, and `approve_production=true`, after staging validation and the production backup preflight.

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `scripts/deploy-staging.sh <TAG>` | Deploy image to staging instance |
| `scripts/deploy-prod.sh <TAG>` | Deploy image to production (with pre-deploy backup) |
| `scripts/promote-to-production.sh <TAG>` | Promote staging-validated image to production |
| `scripts/configure-bugtracker-secrets.sh` | Prompt for and store protected Zoho BugTracker OAuth secret files on the host (paths only in `.env.staging`) |
| `scripts/verify-bugtracker-staging.sh` | Read-only check of BugTracker configuration, schema, and image contents; `--refresh-token-check` tests OAuth refresh only |
| `scripts/install-bugtracker-cron.sh` | Inspect (`--check`, default), install (`--install`), or remove (`--remove`) the scheduled BugTracker sync in `/etc/cron.d` |
| `scripts/test-bugtracker-create.sh` | `--check` (default), `--create`, `--cleanup` — proves the BugTracker create path with one labelled disposable feedback row |

### Zoho BugTracker scheduling

The backend image ships `/app/cron_bugtracker_sync.py`, but the container runs no cron daemon. The sync is scheduled from the host in `/etc/cron.d/kfl-aviation-dms-bugtracker-sync` and executes `docker exec <backend> python /app/cron_bugtracker_sync.py`.

`--install` schedules a job that **creates real BugTracker tickets** for pending feedback, so it is a deliberate, separately authorized action. Run `--check` first: it reports the schedule (if any), stale user-crontab entries, and how many feedback rows still lack a BugTracker ID, without changing anything. The installer removes obsolete user-crontab entries that point at a checkout path instead of the container, backing up the crontab first.

## Runtime Version Surfacing

Every deployment injects `DMS_RELEASE_TAG` (and `DMS_GIT_SHA` where available) into the backend container. The running build identity is observable without SSH:

- `GET /health` → `{"status": "ok", "version": {"name", "api_version", "release_tag", "git_sha"}}`
- `GET /api/p0/admin/observability` (system admin) → top-level `version` block with the same identity, rendered as the "Build version" tile in Admin → System Observability.

This makes the currently running release tag (`canonical-<git sha>-<timestamp>`) verifiable over HTTPS after every deployment; the deploy script's post-deploy smoke test should confirm the reported tag matches the requested `IMAGE_TAG`.

## Production Promotion Safety

Before any production deployment:

1. **Pre-deployment backup** — `full-stack-backup.sh` runs on production, creating a rollback candidate on the backup server (`10.20.173.120`)
2. **Image verification** — Manifest checked in registry before deployment
3. **Health checks** — All 5 containers must report healthy
4. **Smoke test** — Backend `/health` endpoint verified
5. **Rollback on failure** — If any service fails health check, compose is torn down

## Rollback Procedure

If production deployment fails:

```bash
# On production instance
cd /opt/kfl-aviation-dms-prod

# Redeploy previous image tag
./scripts/deploy-prod.sh <PREVIOUS_TAG>

# Or restore from backup candidate on backup server
# Verify backup candidate first:
python3 -m backup_validation verify --data-root <candidate> --confirm-isolated-candidate
```

## Staging / Production Data Separation

- Staging uses `dms_data` volume on the shared `roc-dis` VM (bastion + staging)
- Production uses separate `dms_data` volume on OCI instance
- **Never share volumes between environments**
- Staging database contains test data; production database is independent

## Feature Flags

New features are deployed to production with `CONTROLLED_DOCUMENT_SECURITY_ENABLED=false` (or equivalent), then enabled after Accountable Manager approval. This allows code deployment without activating unapproved features.

## Emergency Contacts

- Accountable Manager: Production go/no-go approval
- Records Custodian: Data classification and backup verification
- System Administrator: Deployment execution and rollback
