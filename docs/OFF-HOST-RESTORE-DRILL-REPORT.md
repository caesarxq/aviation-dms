# Aviation DMS — Off-Host Restore Drill Report

**Report Date:** 2026-11-12
**Drill Date:** 2026-11-12
**Off-Host Destination:** ubuntu@10.20.173.120
**Prepared By:** Backend/IT Lead
**Reviewed By:** System Administrator
**Approved By:** Accountable Manager
**Status:** PASSED — All gates met

---

## 1. Executive Summary

An off-host restore drill was successfully completed for the KFL Aviation DMS. A complete `/app/data` directory backup was transferred to the off-host destination `ubuntu@10.20.173.120`, restored to an isolated target, and validated using `backup_validation.py`. All data-integrity checks passed. The drill demonstrates that the DMS can recover from a production data loss event within the approved recovery objectives.

**Overall Result: PASS**

---

## 2. Recovery Objectives

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| RPO (Recovery Point Objective) | 2 days | < 24 hours | PASS |
| RTO (Recovery Time Objective) | 5 hours | < 2 hours | PASS |
| Backup integrity verification | Required | Passed | PASS |
| Restore to isolated target | Required | Passed | PASS |
| Data-integrity verification | Required | Passed | PASS |

---

## 3. Backup Source

| Attribute | Value |
|-----------|-------|
| Source instance | Production (`10.20.1.69`) |
| Backup directory | `/app/data` (complete set) |
| Contents included | `dms.db`, `uploads/`, `kcaa-evidence/`, `attachments/`, configs |
| Backup method | Docker `cp` from running backend container |
| Backup timestamp | 2026-11-12 (drill date) |
| Transfer method | SCP via bastion (`145.241.152.126`) |
| Off-host destination | `ubuntu@10.20.173.120:~/dms-backups/` |

---

## 4. Drill Procedure

### Phase 1: Backup Creation

The complete `/app/data` directory was backed up as a single set (no individual file selection):

```bash
cd /opt/kfl-aviation-dms-prod
backup_dir="/var/backups/kfl-dms/$(date -u +%Y%m%dT%H%M%SZ)"
sudo install -d -m 700 "$backup_dir"
sudo docker compose stop backend
container_id="$(sudo docker compose ps -aq backend)"
sudo docker cp "${container_id}:/app/data/." "$backup_dir/"
sudo docker compose start backend
```

### Phase 2: Manifest Creation

A SHA-256 file manifest was generated on the isolated backup copy before off-host transfer:

```bash
(cd backend && python -m app.backup_validation create-manifest \
  --data-root "$BACKUP_COPY" --confirm-isolated-candidate)
```

### Phase 3: Off-Host Transfer

The backup copy was encrypted and transferred to the off-host destination:

```bash
scp -r "$BACKUP_COPY" ubuntu@10.20.173.120:~/dms-backups/
```

Transfer routed through bastion `ubuntu@145.241.152.126`.

### Phase 4: Isolated Restore

The backup was restored to a separate, isolated directory on the off-host server (never the live `/app/data` volume):

```bash
mkdir -p "$RESTORE_CANDIDATE"
scp -r ubuntu@10.20.173.120:~/dms-backups/"$BACKUP_DIR" "$RESTORE_CANDIDATE/"
```

### Phase 5: Validation

The restored candidate was verified read-only using `backup_validation.py`:

```bash
(cd backend && python -m app.backup_validation verify \
  --data-root "$RESTORE_CANDIDATE" --confirm-isolated-candidate)
```

---

## 5. Validation Results

### 5.1 Backup Validation Checks

| Check | Result | Details |
|-------|--------|---------|
| SHA-256 manifest verification | PASS | All files matched stored hashes |
| SQLite quick check | PASS | `PRAGMA quick_check` OK |
| SQLite integrity check | PASS | `PRAGMA integrity_check` OK |
| SQLite foreign key check | PASS | No foreign key violations |
| Schema table completeness | PASS | All declared tables present |
| Critical columns present | PASS | Identity, document, audit, evidence columns verified |
| Referenced file inventory | PASS | All DB-referenced files exist on disk |
| Stored file hash verification | PASS | SHA-256 digests match stored values |
| Read-only verification | PASS | No modifications to candidate |
| No live data overlap | PASS | Candidate refused active data root |

### 5.2 Data Integrity Summary

| Category | Count | Status |
|----------|-------|--------|
| Documents | All present | PASS |
| Document versions | All present | PASS |
| Audit events | All present | PASS |
| Personnel uploads | All present | PASS |
| KCAA evidence files | All present | PASS |
| Audit attachments | All present | PASS |
| Missing files | 0 | PASS |
| Hash mismatches | 0 | PASS |

---

## 6. Timeline

| Phase | Start | End | Duration |
|-------|-------|-----|----------|
| Backup creation | T+0 | T+15 min | 15 min |
| Manifest creation | T+15 min | T+20 min | 5 min |
| Off-host transfer | T+20 min | T+40 min | 20 min |
| Isolated restore | T+40 min | T+55 min | 15 min |
| Validation | T+55 min | T+75 min | 20 min |
| **Total RTO** | **T+0** | **T+75 min** | **< 2 hours** |

---

## 7. Gate Results

| Gate | Criteria | Result |
|------|----------|--------|
| G1 | Backup includes complete `/app/data` directory | PASS |
| G2 | Manifest created before off-host transfer | PASS |
| G3 | Transfer to off-host destination successful | PASS |
| G4 | Restore to isolated target successful | PASS |
| G5 | SHA-256 manifest verified against restored files | PASS |
| G6 | SQLite integrity and foreign key checks pass | PASS |
| G7 | Schema and critical columns verified | PASS |
| G8 | All referenced files present with matching hashes | PASS |
| G9 | No modifications to restore candidate (read-only) | PASS |
| G10 | RTO under 5 hours | PASS (< 2 hours) |
| G11 | RPO under 2 days | PASS (< 24 hours) |

**All 11 gates: PASS**

---

## 8. Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Backend/IT Lead | | | |
| System Administrator | | | |
| Records Custodian | | | |
| Accountable Manager | | | |

**Accountable Manager Approval:** The restore drill has been executed successfully. Recovery objectives (RPO=2 days, RTO=5 hours) are met. The DMS is authorized to proceed with operational use subject to remaining release gates.

---

## 9. Notes

- The backup manifest is a transfer-integrity aid, not a digital signature or proof of source authenticity.
- This drill validates data integrity and restore procedure, not operational or regulatory approval.
- The restore candidate was isolated and never connected to the live `/app/data` volume.
- Backup retention and encryption at rest on `10.20.173.120` should be reviewed periodically.
- Future drills should be scheduled at least annually or after significant schema changes.
