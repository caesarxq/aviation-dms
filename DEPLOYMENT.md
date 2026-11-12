# Aviation DMS — CI/CD Deployment Runbook

## Overview

Staging is `10.20.4.234` (`stage.kfl.ke`); production is `10.20.1.69` (`roc.kfl.ke`). Caddy on bastion `145.241.152.126` terminates TLS and forwards to private instance ports.

The checked-in workflow is designed to:
1. Run backend/frontend tests and build Docker images for pull requests; PR builds are not published and do not deploy.
2. On a push to `main`, wait for both test jobs and build multi-platform images; it does not change either live environment.
3. Deploy to staging only for an explicit `workflow_dispatch` with `approve_staging=true`.
4. Run production promotion only for an explicit `workflow_dispatch` with `environment=production`, `approve_staging=true`, and `approve_production=true`.

Production promotion additionally requires the production-specific backup helper described below. No deployment is authorized by this runbook alone.

## Repositories & Secrets

### GitHub Actions Secrets Required

| Secret | Description |
|--------|-------------|
| `CR_PAT` | Container registry personal access token (ghcr.io) |
| `STAGING_SSH_PRIVATE_KEY` | SSH key for staging instance (`10.20.4.234`) |
| `PRODUCTION_SSH_PRIVATE_KEY` | SSH key for production OCI instance |
| `BASTION_SSH_PRIVATE_KEY` | SSH key for bastion (`145.241.152.126`) |

### Environments

- **staging**: Explicit deployment via workflow dispatch with `approve_staging=true`
- **production**: Explicit dispatch with both approval inputs; production backup preflight also required. The GitHub `production` environment has no configured reviewer rule, so these inputs are single-operator attestations, not independent approval.

## Workflow Triggers

### Pull request to `main`
```
pull_request → backend tests + frontend tests + multi-platform image build + Graphify (image build is not published; no deployment)
```

### Push to `main`
```
push → backend/frontend tests → multi-platform image build/push (no deployment)
```

### Manual staging dispatch (`workflow_dispatch`)
```bash
gh workflow run deploy.yml -f environment=staging -f approve_staging=true
```

### Manual production dispatch (`workflow_dispatch`)
```bash
gh workflow run deploy.yml \
  -f environment=production \
  -f approve_staging=true \
  -f approve_production=true
```

This builds a new tag from the selected `main` revision and deploys it to staging before production. Both approval flags are required. There is no `image_tag` input for selecting an already-built image.

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `scripts/deploy-staging.sh <TAG>` | Deploy image to staging instance |
| `scripts/deploy-prod.sh <TAG>` | Deploy image to production (with pre-deploy backup) |
| `scripts/promote-to-production.sh <TAG>` | Operator-only SSH wrapper; see its explicit approval/key-path requirements |

`promote-to-production.sh` is not the GitHub workflow path. If run manually, it requires `PRODUCTION_APPROVED=true`, `BASTION_SSH_KEY_FILE` and `PRODUCTION_SSH_KEY_FILE`, plus registry authentication on both the local Docker client and production host. Do not place key or token values on the command line.

## Production Promotion Safety

Before any production deployment:

1. **Explicit authorization** — use the production workflow input gate; do not promote during routine pushes.
2. **Production-specific backup** — `/opt/kfl-aviation-dms-prod/scripts/full-stack-backup-prod.sh` must be executable and must complete successfully before images are pulled or containers changed. The existing staging backup script is not a substitute.
3. **Image verification** — deploy the image tag built by the same workflow run and validated on staging.
4. **Health checks** — backend, upload-validator, ClamAV, and frontend must report healthy; backend `/health` is checked inside the container.
5. **Failure behavior** — the deployment does not run `docker compose down`. On health failure it attempts to return to the previous recorded image tag; investigate schema compatibility and backup status before any manual recovery.

**Current gate:** the production helper and systemd service/timer are installed, and the units pass `systemd-analyze verify`; the timer is deliberately disabled. The host has no Restic package, backup SSH identity, pinned host key, or `/etc/kfl-aviation-dms-prod/backup.env`; the staging path is not a dedicated encrypted mount and has no root-owned OCI encryption attestation. No external failure alert is configured and no backup was run. The production data persists in Docker volume `kfl-aviation-dms-prod_dms_data`, but persistence is not backup. Verify the off-host destination, separate encrypted staging mount, approved retention/RPO/RTO, failure alert, and isolated restore before enabling the timer or allowing a production deployment. The owner-reported prior drill remains separate evidence and is not proof of a recurring schedule.

## Rollback Procedure

If production deployment fails:

```bash
# On production instance
cd /opt/kfl-aviation-dms-prod

# Redeploy a previous image tag only after confirming backup and schema compatibility.
sudo ./scripts/deploy-prod.sh <PREVIOUS_TAG>

# Or restore from backup candidate on backup server
# Verify backup candidate first:
python3 -m backup_validation verify --data-root <candidate> --confirm-isolated-candidate
```

## Staging / Production Data Separation

- Staging uses `dms_data` volume on `10.20.4.234`; host ports are `8001` and `8081`.
- Production uses a separate `dms_data` volume on `10.20.1.69`; host ports are `8000` and `8080`.
- Both Compose files bind application ports to all host interfaces; OCI ingress must restrict them to the bastion/private VCN. Public direct access to application ports is not intended.
- The Compose Caddy service is profile-gated (`local-https`) and is not started on OCI hosts; bastion Caddy is the TLS entry point.
- **Never share volumes between environments**
- Staging database contains test data; production database is independent

## Feature Flags

New features are deployed to production with `CONTROLLED_DOCUMENT_SECURITY_ENABLED=false` (or equivalent), then enabled after Accountable Manager approval. This allows code deployment without activating unapproved features.

## Emergency Contacts

- Accountable Manager: Production go/no-go approval
- Records Custodian: Data classification and backup verification
- System Administrator: Deployment execution and rollback
