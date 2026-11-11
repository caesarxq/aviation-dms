# Aviation DMS — CI/CD Deployment Runbook

## Overview

Staging (cloud instance `10.20.4.234`) → Production (new OCI instance).

The pipeline:
1. Builds Docker images on push to `main`
2. Deploys to staging automatically
3. Runs E2E + security tests on staging
4. **Pauses for manual approval** before production
5. Deploys the same validated image tag to production

## Repositories & Secrets

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `CR_PAT` | Container registry personal access token (ghcr.io) |
| `STAGING_SSH_PRIVATE_KEY` | SSH key for staging instance (`10.20.4.234`) |
| `PRODUCTION_SSH_PRIVATE_KEY` | SSH key for production OCI instance |
| `BASTION_SSH_PRIVATE_KEY` | SSH key for bastion (`145.241.152.126`) |

### Environments

- **staging**: Automatic deployment on push to `main`
- **production**: Requires manual approval before deployment

## Workflow Triggers

### Push to `main`
```
push → build → deploy staging → test staging → PAUSE (approve production) → deploy production
```

### Manual dispatch (`workflow_dispatch`)
```bash
gh workflow run deploy.yml \
  -f environment=production \
  -f image_tag=canonical-v7-feature-20261112 \
  -f approve_production=true
```

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `scripts/deploy-staging.sh <TAG>` | Deploy image to staging instance |
| `scripts/deploy-prod.sh <TAG>` | Deploy image to production (with pre-deploy backup) |
| `scripts/promote-to-production.sh <TAG>` | Promote staging-validated image to production |

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

- Staging uses `dms_data` volume on `10.20.4.234`
- Production uses separate `dms_data` volume on OCI instance
- **Never share volumes between environments**
- Staging database contains test data; production database is independent

## Feature Flags

New features are deployed to production with `CONTROLLED_DOCUMENT_SECURITY_ENABLED=false` (or equivalent), then enabled after Accountable Manager approval. This allows code deployment without activating unapproved features.

## Emergency Contacts

- Accountable Manager: Production go/no-go approval
- Records Custodian: Data classification and backup verification
- System Administrator: Deployment execution and rollback
