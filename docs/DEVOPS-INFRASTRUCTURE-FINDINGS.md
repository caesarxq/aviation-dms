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
| `CR_PAT` | Container registry PAT for ghcr.io (write:packages) | `gh secret set CR_PAT` (prompt) |
| `PROD_HOST` | Production hostname for deployment | `gh secret set PROD_HOST roc.kfl.ke` |
| `BASTION_SSH_PRIVATE_KEY` | SSH key for bastion host (shared bastion/staging VM) | `gh secret set BASTION_SSH_PRIVATE_KEY < ~/.ssh/id_ed25519` |

### Commands to Run

```bash
# Authenticate first (already done)
gh auth status

# Set secrets (SSH key via file redirect, others via prompt)
gh secret set BASTION_SSH_PRIVATE_KEY < ~/.ssh/id_ed25519
gh secret set CR_PAT
gh secret set PROD_HOST roc.kfl.ke

# Verify
gh secret list --repo caesarxq/aviation-dms
```

**Note:** SSH private key is passed via file redirect (`<`) so its contents are never echoed to the terminal. `CR_PAT` and `PROD_HOST` will prompt interactively.

**Staging deploy:** Uses a self-hosted GitHub Actions runner on the shared bastion/staging VM (`roc-dis`). No `STAGING_SSH_PRIVATE_KEY` or `STAGING_HOST` secret needed — deploy commands run locally on the runner.

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
| Deploy approval | Production promotion is disabled in the workflow pending backup, host-key, and deployment-path gates |

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

## 4. Off-Host Restore Drill — COMPLETE (Medium)

### Current State
- Backup server: `10.20.173.120` with verified backup candidates
- `backup_validation.py` exists and validates manifests read-only
- Daily cron backup: `0 2 * * *` on backup host `10.20.173.120`
- Full-stack backup: `backend/scripts/full-stack-backup.sh` verified end-to-end
- **Off-host restore drill completed** — see `docs/OFF-HOST-RESTORE-DRILL-REPORT.md`
- All 11 DR gates passed (backup creation, manifest, off-host transfer, isolated restore, SHA-256 verification, SQLite integrity, foreign key checks, schema completeness, file inventory, hash matching, read-only verification)
- RPO: < 24 hours (target: 2 days) — PASS
- RTO: < 2 hours (target: 5 hours) — PASS

---

## 5. Infrastructure as Code — NOT IMPLEMENTED (Medium)

### Current State
- Terraform directory removed (was not applied, contained uncommitted OCIDs)
- Production instance `10.20.1.69` created manually via OCI Console
- Staging runs on shared bastion/staging VM `roc-dis` (`145.241.152.126`), backend on `127.0.0.1:8000`
- Bastion `145.241.152.126` runs Caddy for TLS termination and staging reverse-proxy
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
| Staging deployment on shared bastion/staging VM `roc-dis` (`145.241.152.126`) | ✅ Done | — |
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
| **Off-host restore drill** | ✅ Complete | `docs/OFF-HOST-RESTORE-DRILL-REPORT.md` |
| **Infrastructure as Code** | 📋 Pending OCI credentials | — |

---

## Next Steps (Priority Order)

1. **Configure GitHub secrets** (5 secrets) — enables CI/CD pipeline
2. **Accountable Manager signs off on drill report** — final go/no-go for operational use
3. **Reintroduce Terraform** (when OCI credentials available) — IaC for reproducibility
4. **Upgrade GitHub plan or make repo public** — enables branch protection
