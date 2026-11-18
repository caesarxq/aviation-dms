# Aviation DMS — CI/CD Deployment Runbook

## Overview

Staging (cloud instance `10.20.4.234`) → Production (new OCI instance).

The pipeline builds and tests images on pushes to `main`; it does not deploy to a live environment on a code push. Staging deployment requires an explicit workflow dispatch approval. Production promotion is disabled and the production job exits before SSH or deployment.

## Repositories & Secrets

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `CR_PAT` | Container registry personal access token (ghcr.io) |
| `STAGING_SSH_PRIVATE_KEY` | SSH key for staging instance (`10.20.4.234`) |
| `BASTION_SSH_PRIVATE_KEY` | SSH key for bastion (`145.241.152.126`) |

The workflow pins the single `roc-dis` ED25519 SHA256 fingerprint and requires both the public bastion address and private staging address to present that exact key.

### Environments

- **staging**: Manual workflow dispatch with `approve_staging=true`; bastion Caddy terminates public TLS
- **production**: Disabled in the workflow until production backup, host-key, and deployment-path gates are reviewed and implemented

## Workflow Triggers

### Push to `main`
```
push → build/publish images → backend/frontend checks; live environments remain unchanged
```

### Authorized staging dispatch (`workflow_dispatch`)
```bash
gh workflow run deploy.yml -f environment=staging -f approve_staging=true
```

Cloud staging binds the backend to `10.20.4.234:8001` and the frontend to `10.20.4.234:8081`. Before pulling images, the deploy script validates those exact mappings, requires no published ports on the validator and ClamAV services, and requires both email-delivery flags to remain false. The owner confirmed that `10.20.4.234` is the private address of the same `roc-dis` VM used as the public bastion. The workflow treats this as one shared host identity, pins its ED25519 fingerprint, and checks both address paths against it; this is not separation between two hosts.

Before a staging deployment, create and validate a fresh data-only backup on a dedicated encrypted staging mount with a root-owned OCI encryption attestation. The current `~/dms-backups` directory is on the backup host's root filesystem and is not an eligible staging mount. Do not use the legacy `backend/scripts/full-stack-backup.sh`: it includes secret files and prunes older backups.

Production promotion is disabled in the workflow until the production-specific backup, host-key, and deployment-path gates are reviewed and implemented.

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `scripts/deploy-staging.sh <TAG>` | Deploy image to staging instance |
| `scripts/deploy-prod.sh <TAG>` | Legacy production deploy script; do not use until production backup gates are closed |
| `scripts/promote-to-production.sh <TAG>` | Operator SSH wrapper; not invoked by the disabled production workflow |

## Production Promotion Safety

The production GitHub job currently exits before any production SSH or deployment action. No production readiness or container-health claim is made. Do not use the legacy deploy scripts; they do not meet the required production-specific backup, host-key, health-check, and rollback gates. Re-enable promotion only after those controls are implemented and independently reviewed.

## Rollback Procedure

Production rollback is not authorized through the legacy deploy script. Keep the live stack and data intact; use an approved recovery procedure only after the production backup and isolated-restore gates are closed.

The `scripts/deploy-prod.sh` script is legacy and must not be used until the production backup workflow is replaced and independently reviewed.

## Staging / Production Data Separation

- Staging uses `dms_data` volume on `10.20.4.234`
- Production uses separate `dms_data` volume on `10.20.1.69`; the environment example binds host ports `8000/8080` to that private address. Base Compose defaults to loopback if the binding IP is omitted.
- **Never share volumes between environments**
- Staging database contains test data; production database is independent

## Feature Flags

New features are deployed to production with `CONTROLLED_DOCUMENT_SECURITY_ENABLED=false` (or equivalent), then enabled after Accountable Manager approval. This allows code deployment without activating unapproved features.

## Emergency Contacts

- Accountable Manager: Production go/no-go approval
- Records Custodian: Data classification and backup verification
- System Administrator: Deployment execution and rollback
