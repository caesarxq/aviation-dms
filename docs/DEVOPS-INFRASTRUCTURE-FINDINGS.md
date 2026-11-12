# Aviation DMS — DevOps Infrastructure Findings

**Date:** 2026-11-12
**Status:** In progress
**Scope:** CI/CD, branch protection, secrets, restore drill, IaC

---

## 1. GitHub Secrets — NOT CONFIGURED (Critical)

No secrets are configured in the `caesarxq/aviation-dms` repository. The CI/CD pipeline cannot execute without them.

### Required Secrets

| Secret | Purpose | How to Set |
|--------|---------|------------|
| `STAGING_SSH_PRIVATE_KEY` | SSH key for staging instance via bastion | `gh secret set STAGING_SSH_PRIVATE_KEY < ~/.ssh/id_ed25519` |
| `PRODUCTION_SSH_PRIVATE_KEY` | SSH key for production instance via bastion | `gh secret set PRODUCTION_SSH_PRIVATE_KEY < ~/.ssh/id_ed25519` |
| `BASTION_SSH_PRIVATE_KEY` | SSH key for bastion host (ProxyJump) | `gh secret set BASTION_SSH_PRIVATE_KEY < ~/.ssh/id_ed25519` |
| `CR_PAT` | Container registry PAT for ghcr.io (write:packages) | `gh secret set CR_PAT` (prompt) |
| `PROD_HOST` | Production hostname for deployment | `gh secret set PROD_HOST roc.kfl.ke` |

### Commands to Run

```bash
# Authenticate first (already done)
gh auth status

# Set all five secrets (SSH keys via file redirect, others via prompt)
gh secret set STAGING_SSH_PRIVATE_KEY < ~/.ssh/id_ed25519
gh secret set PRODUCTION_SSH_PRIVATE_KEY < ~/.ssh/id_ed25519
gh secret set BASTION_SSH_PRIVATE_KEY < ~/.ssh/id_ed25519
gh secret set CR_PAT
gh secret set PROD_HOST roc.kfl.ke

# Verify
gh secret list --repo caesarxq/aviation-dms
```

**Note:** SSH private keys are passed via file redirect (`<`) so their contents are never echoed to the terminal. `CR_PAT` and `PROD_HOST` will prompt interactively.

---

## 2. Branch Protection — UNAVAILABLE (Critical)

GitHub branch protection rules require GitHub Pro or a public repository. The `caesarxq/aviation-dms` repository is on a free plan with a private repo.

### Current State
- `main` branch has **no protection** — anyone with write access can push directly
- No required PR reviews, no status checks, no enforcement

### Mitigation (Without GitHub Pro)

| Practice | Implementation |
|----------|---------------|
| Code review | All changes go through PR review manually before merge |
| Status checks | CI workflow runs on push; failures visible in PR checks |
| No direct pushes | Team agreement: no direct pushes to `main` |
| Deploy approval | Production promotion requires `approve_production=true` in workflow_dispatch |

### Recommendation
Upgrade to GitHub Pro or make the repository public to enable native branch protection. Until then, enforce through team convention and CI visibility.

---

## 3. CI/CD Workflow — FIXED (was High, now resolved)

### Problem (Before)
Tests ran **after** deploying to staging:
```
build → deploy staging → test staging → promote to production
```
Bad code could reach the staging environment before tests caught it.

### Fix (After)
Tests now run **before** staging deployment:
```
build → test-backend + test-frontend (parallel) → deploy-staging → promote-to-production
```

- `test-backend`: runs `pytest -x -q` in backend/
- `test-frontend`: runs `npm test -- --run` and `npx tsc --noEmit` in frontend/
- Both test jobs must pass before `deploy-staging` can run
- `graphify-extract` runs in parallel with tests (no blocking)
- `deploy-staging` needs both test jobs to succeed
- `promote-to-production` needs `deploy-staging` to succeed

### Commit
`c2541e4` — Fix CI/CD: tests now gate staging deployment

---

## 4. Off-Host Restore Drill — INCOMPLETE (Medium)

### Current State
- Backup server: `10.20.173.120` with 3 verified backup candidates
- `backup_validation.py` exists and can validate manifests read-only
- Daily cron backup: `0 2 * * *` on `10.20.4.234`
- Full-stack backup: `backend/scripts/full-stack-backup.sh` verified end-to-end

### Missing
- No Accountable Manager-approved RPO/RTO targets
- No authorized off-host destination with encryption/versioning/retention/access controls
- No complete off-host restore drill executed
- No documented restore acceptance criteria

### Steps to Complete

1. **Accountable Manager** approves recovery objectives (RPO=2 days, RTO=5 hours proposed)
2. **System Administrator** provisions off-host destination with encryption/versioning/retention/access controls
3. **Backend/IT** runs `backup_validation.py create-manifest` on a backup copy
4. **System Administrator** restores to isolated target on `10.20.173.120`
5. **Backend/IT** runs `backup_validation.py verify --confirm-isolated-candidate`
6. **Accountable Manager** records successful restore and approves go/no-go

### Commands (reference)

```bash
# Create manifest on isolated backup copy
(cd backend && python -m app.backup_validation create-manifest \
  --data-root "$BACKUP_COPY" --confirm-isolated-candidate)

# Verify restore candidate
(cd backend && python -m app.backup_validation verify \
  --data-root "$RESTORE_CANDIDATE" --confirm-isolated-candidate)
```

---

## 5. Infrastructure as Code — NOT IMPLEMENTED (Medium)

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

### Recommendation
When OCI credentials are available, reintroduce Terraform with:
- Import existing production instance into Terraform state
- Define staging and bastion as managed resources
- Store `terraform.tfvars` as a GitHub secret (never commit)
- Apply through CI/CD with plan/apply separation

---

## 6. Summary of All Actions Taken

| Action | Status | Commit |
|--------|--------|--------|
| Caddy reload on bastion (`roc.kfl.ke` → production) | ✅ Done | — |
| Staging deployment on `10.20.4.234` | ✅ Done | — |
| Production deployment on `10.20.1.69` | ✅ Done | — |
| Fix `database.py` indentation bug | ✅ Done | `3465d73` |
| Fix staging port conflicts (8000→8001, 8080→8081) | ✅ Done | `3465d73` |
| Remove Terraform infrastructure | ✅ Done | `386e99b` |
| Add CHANGELOG, ADRs, threat model, retention, DR | ✅ Done | `a561b35` |
| Remove staging subdomain → `stage.kfl.ke` | ✅ Done | `b034d0d` |
| Fix staging compose for `0.0.0.0` binding | ✅ Done | `a030ad8` |
| Fix production `DMS_TRUSTED_FRONTEND_IP` | ✅ Done | `7efecd8` |
| Fix production SMTP to match staging | ✅ Done | `208c2a1` |
| Remove `https_proxy` from prod compose | ✅ Done | `7efecd8` |
| Reduce clamd CPUs to 1.0 | ✅ Done | `7efecd8` |
| Fix CI/CD: tests gate staging deployment | ✅ Done | `c2541e4` |
| Add Graphify to CI and CONTRIBUTING | ✅ Done | `ce48a37`, `46b9ffe` |
| Add proactive Graphify method to CONTRIBUTING | ✅ Done | `46b9ffe` |
| **GitHub secrets configuration** | ⏳ User action | — |
| **Branch protection** | ⚠️ GitHub Free limitation | — |
| **Off-host restore drill** | 📋 Pending AM approval | — |
| **Infrastructure as Code** | 📋 Pending OCI credentials | — |

---

## Next Steps (Priority Order)

1. **Configure GitHub secrets** (5 secrets) — enables CI/CD pipeline
2. **Accountable Manager approves RPO/RTO** — enables restore drill
3. **Execute off-host restore drill** — validates backup/recovery
4. **Reintroduce Terraform** (when OCI credentials available) — IaC for reproducibility
5. **Upgrade GitHub plan or make repo public** — enables branch protection
