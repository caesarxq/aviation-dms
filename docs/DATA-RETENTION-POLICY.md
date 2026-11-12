# Aviation DMS — Data Retention Policy

**Version:** 1.0
**Date:** 2026-11-12
**Owner:** Records Custodian
**Approval Status:** Draft — awaiting Records Custodian and Accountable Manager approval
**Classification:** Internal — operational policy

---

## 1. Purpose

This policy establishes retention periods, legal hold procedures, and disposition rules for records managed by the KFL Aviation DMS. It applies to all data stored in the DMS database (`/app/data/dms.db`) and associated file roots (`/app/data/uploads/`, `/app/data/kcaa-evidence/`, `/app/data/attachments/`).

This policy does **not** constitute operational or regulatory approval. Retention periods are application defaults pending Records Custodian approval and accountable-postholder sign-off.

---

## 2. Scope

### In Scope
- Controlled documents and versions (`documents`, `document_versions`)
- Document proposals and change requests (`document_proposals`, `change_requests`)
- Distributions and acknowledgements (`distributions`)
- Audit events (`audit_events`)
- Safety occurrences and related records (`occurrences`, `investigations`, `risk_assessments`, `corrective_actions`, `safety_actions`)
- Personnel credentials and uploads (`personnel_uploads`, `personnel_licenses`)
- Aircraft records (`aircraft`, `aircraft_insurance`, `maintenance_records`)
- Mission and flight records (`missions`, `flight_plans`, `flight_releases`)
- Dangerous goods records (`dg_shipments`, `dg_acceptance_checks`)
- Security incidents (`security_incidents`)
- Audit reports and provenance imports (`audit_reports`, `audit_report_imports`, `audit_findings`, `extractions`)
- Retention rules and legal holds (`retention_rules`, `legal_holds`)
- File storage roots: uploads, KCAA evidence, audit attachments

### Out of Scope
- Physical paper records (handled under separate KFL records management procedures)
- Email and chat records outside the DMS
- System logs and infrastructure monitoring data (retained under separate IT policy)

---

## 3. Retention Rules

### Seeded Retention Rules

| Rule ID | Record Type | Retention Period | Start Event | Disposition |
|---------|-------------|-----------------|-------------|-------------|
| RR-023 | General operational records | 36 months (3 years) | Record creation or last update | Secure destruction after Records Custodian approval |
| RR-025 | Metadata records (audit trails, system logs, legal hold records) | Lifetime | Record creation | No automatic disposition; permanent retention |

### Rule Application

Retention rules are applied at the record level, not the file level. File disposition is **not automatic** — `upload_reconciliation.py` is report-only and never deletes or repairs files. Any file disposition requires:

1. Records Custodian classification of the finding
2. Accountable Manager approval of disposition targets
3. Documented DB/path cross-check
4. Independent verification that no legal hold applies

---

## 4. Legal Holds

### Legal Hold Lifecycle

| Phase | Action | Owner | System Support |
|-------|--------|-------|----------------|
| Impose | Records Custodian imposes a legal hold on specific records | Records Custodian | `POST /api/p0/legal-holds` — prevents disposition of held records |
| Review | Periodic review of active holds | Records Custodian | `GET /api/p0/legal-holds` — list active holds |
| Release | Records Custodian releases a hold when no longer required | Records Custodian | `PATCH /api/p0/legal-holds/{id}/release` — lifts disposition prevention |
| Audit | Verify no held records were dispositioned | Accountable Manager | `audit_events` — all hold actions logged |

### Hold Effects
- Records under legal hold are exempt from RR-023 disposition
- Hold applies to both database rows and associated file storage
- Hold release requires explicit Records Custodian action
- All hold impose/release actions are audited with actor, timestamp, and affected record IDs

---

## 5. Disposition Procedure

Disposition (secure destruction) of records past their retention period follows this procedure:

1. **Inventory**: Run `upload_reconciliation.py` against an isolated candidate to identify records past retention
2. **Classification**: Records Custodian classifies each finding (retain, dispose, or hold)
3. **Approval**: Accountable Manager approves disposition targets
4. **Legal hold check**: Verify no active legal hold applies to any record marked for disposition
5. **Execution**: Secure deletion of database rows and associated files
6. **Documentation**: Record disposition decision, actor, date, and affected record IDs in `audit_events`

**No automatic disposition occurs.** `upload_reconciliation.py` never deletes, repairs, or imports records. It is report-only.

---

## 6. Storage Roots and File Retention

| Storage Root | Contents | Retention | Disposition Gate |
|--------------|----------|-----------|------------------|
| `/app/data/uploads/` | Personnel credential uploads | RR-023 (36 months) | Records Custodian + legal hold check |
| `/app/data/kcaa-evidence/` | KCAA approval evidence PDFs | RR-025 (lifetime) | No automatic disposition |
| `/app/data/attachments/` | P3 audit evidence attachments | RR-025 (lifetime) | No automatic disposition |

Files are never deleted in place. Disposition creates an immutable audit record before deletion.

---

## 7. Backup and Retention Interaction

Backups are full `/app/data` directory copies, not incremental. Backup retention follows the same rules as the live data:

- Backup copies retained for the same period as the source records
- Backup restoration tested via isolated restore drill (see Disaster Recovery)
- Backup manifests (SHA-256) verify transfer integrity before off-host storage

---

## 8. Exceptions

Exceptions to this policy require:
1. Written request to the Records Custodian
2. Accountable Manager approval
3. Documentation in `audit_events` with rationale and effective dates
4. Periodic review (at least annually)

---

## 9. Policy Review

This policy is reviewed:
- Annually by the Records Custodian
- When new record types are added to the DMS
- When regulatory requirements change (KCAA, ICAO Annex 19)
- After any legal hold or disposition event

**Approvers:** Records Custodian (policy owner), Accountable Manager (final approval)

---

## 10. Open Items

| Item | Owner | Status |
|------|-------|--------|
| Records Custodian formal approval of RR-023 and RR-025 | Records Custodian | Pending |
| Legal hold impose/release workflow tested end-to-end | Records Custodian | Pending |
| Disposition procedure exercised in drill | Records Custodian + Accountable Manager | Pending |
| File-level retention vs row-level retention clarified | Records Custodian | Pending |
