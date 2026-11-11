# Pre-Onboarding Workshop — Facilitator Guide

## Purpose

Facilitator guide for the pre-onboarding workshop. Covers session agenda, timed sections, discussion prompts, decision capture template, and exit criteria.

## Session Overview

| Parameter | Value |
|-----------|-------|
| Duration | 90 minutes |
| Participants | Records Custodian, Accountable Manager, Backend/IT Lead, System Administrator, Responsible Postholders, Independent Auditor |
| Facilitator | You |
| Location | In-person or video conference |
| Materials | Onboarding Readiness Checklist, Pilot Scope & Constraints, Pilot Onboarding Procedure |

## Agenda

| Time | Section | Lead | Output |
|------|---------|------|--------|
| 0:00–0:10 | Welcome and objectives | Facilitator | Shared understanding of pilot goals |
| 0:10–0:25 | Readiness gate review | Backend/IT Lead | Gate status confirmed or open items identified |
| 0:25–0:40 | Pilot scope and constraints | Accountable Manager | Scope acknowledged, constraints accepted |
| 0:40–0:55 | Retention and legal hold policy | Records Custodian | 36-month general / lifetime metadata confirmed |
| 0:55–1:10 | Off-host restore target | Accountable Manager | Destination and RPO/RTO discussed |
| 1:10–1:20 | Source-manual reconciliation | Responsible Postholders | DG Appendix 3 mapping path forward |
| 1:20–1:30 | Next steps and exit criteria | Facilitator | Action items assigned, go/no-go date set |

## Section Details

### 1. Welcome and Objectives (10 min)

State the purpose: confirm technical gates, confirm pilot scope, confirm retention policy, identify open items, set go/no-go date.

Emphasize: pilot does not authorize staging access, deployment, source-PDF upload, commit, or account invitation without separate authorization.

### 2. Readiness Gate Review (15 min)

Walk through each gate item in the Onboarding Readiness Checklist:

**Upload Safeguards (U1–U11):**
- Quota 30 GB configured
- Scanner endpoint `clamd:3310` provisioned and verified
- Timeouts 30s / max 60s
- P3 evidence max 10 MiB, import body max 5 MiB
- Validator isolation verified (UID 10002, read-only root, cap_drop ALL)
- ClamAV isolation verified (dropped caps, no-new-privileges, 1 GiB memory)

**Historical Audit Provenance (P1–P6):**
- Backdated report creation rejected
- Import requires system_admin; verification requires independent_auditor
- All duplicated metadata fields compared
- Evidence validated before write transaction; state rechecked under short lock
- Verifier UI displays all metadata fields

**Personnel Uploads (W1–W4):**
- File validation before write transaction
- Full row state rechecked under lock
- Self-review prohibited
- Rejection reason required

**Backup & Restore (B1–B3):**
- Manifest and schema validation implemented
- Active-data overlap refused
- Reconciliation is report-only

**Retention & Legal Hold (R1–R3):**
- RR-023: 36 months general retention
- RR-025: lifetime metadata retention
- Legal hold impose/release implemented
- No automatic disposition

**Operational Constraints (O1–O4):**
- Flight release disabled
- Staging untouched
- Source manuals preserved
- Identity map preserved (u-safety/security, Brian Swanya)

Ask: "Are there any gate items we cannot confirm? Record them as open items."

### 3. Pilot Scope and Constraints (15 min)

Review the Pilot Scope & Constraints document:

**In scope:** independent_auditor pilot account, provenance import workflow, personnel uploads, audit reports listing, backup validation

**Out of scope:** flight release, staging access, source-PDF upload through UI, automatic disposition, commit/push, account invitation beyond pilot, real audit import, off-host restore drill

Ask: "Does anyone object to any in-scope or out-of-scope item? Record objections."

### 4. Retention and Legal Hold Policy (15 min)

Confirm:
- RR-023: 36 months (3 years) retention for general operational records
- RR-025: lifetime retention for metadata records (audit trails, system logs, legal hold records)
- No automatic file disposition; records custodian classifies findings before any cleanup

Ask: "Records Custodian, do you confirm these retention values? Any record classes needing different treatment?"

### 5. Off-Host Restore Target (15 min)

Accountable Manager discusses:
- Authorized off-host destination
- Encryption, versioning, retention, access controls
- RPO/RTO objectives
- Acceptance criteria for restore drill

Ask: "What is the restore target? When can we schedule the restore drill?"

Record the target as an action item if not available during the session.

### 6. Source-Manual Reconciliation (10 min)

Responsible postholders discuss:
- DG Appendix 3 mapping discrepancy (five named checks vs "10 Appendix 3 checks")
- Manual version validation
- Source-to-rule mapping sign-off

Ask: "Who is responsible for reconciling the DG Appendix 3 discrepancy? What is the timeline?"

### 7. Next Steps and Exit Criteria (10 min)

Capture action items:

| Action | Owner | Due Date |
|--------|-------|----------|
| Provide off-host restore target | Accountable Manager | |
| Reconcile DG Appendix 3 mapping | Responsible Postholders | |
| Classify local missing/unmatched files | Records Custodian | |
| Validate reverse-proxy body limits under load | Backend/IT | |
| Schedule go/no-go review | Facilitator | |

Exit criteria for pilot go/no-go:
- All readiness gate items confirmed
- Off-host restore target provided
- Source-manual reconciliation complete
- Accountable Manager signs go/no-go

## Decision Capture Template

Use this table during the session:

| Decision | Proposed By | Supported By | Opposed By | Outcome |
|----------|-------------|--------------|------------|---------|
| | | | | |
| | | | | |

## Exit Criteria

The workshop is complete when:
1. All readiness gate items are confirmed or have assigned owners and due dates
2. Pilot scope and constraints are acknowledged by all participants
3. Retention policy (36 months general / lifetime metadata) is confirmed
4. Off-host restore target is identified or has a committed delivery date
5. Source-manual reconciliation path forward is identified
6. Go/no-go review date is set

## Escalation

If any critical gate item cannot be resolved during the workshop, escalate to the Accountable Manager and document as an open item in the readiness checklist.
