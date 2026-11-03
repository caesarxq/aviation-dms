# KFL Aviation DMS — Manual-Grounded Workflow Conformance Audit & Execution Report

**Date:** 2026-10-30  
**Repository:** `/Users/mohamedalsayed/Projects/aviation-dms`  
**Specification Revision:** `2026-10-30.1`  
**Verification Summary:** Backend `166 passed` (`pytest`), Frontend `92 passed` (`vitest`), Production bundle build succeeded (`tsc && vite build`).

---

## 1. Source Baseline & Provenance Manifest (Phase 0)

All six user-supplied KCAA-approved PDFs in `/Users/mohamedalsayed/.hermes/profiles/chief-of-staff/attachments/` were inspected and bound by SHA-256 to the DMS catalogue via `apply_catalogue_corrections()` (`backend/app/database.py:1187-1266`) and exposed via `GET /api/p1/workflow-rules` (`backend/app/p1_routes.py:1788-1840`).

| DMS ID | Controlled Title | Source File | SHA-256 | Issue / Rev / Date | Approval Evidence Status | Structural Mapping |
|---|---|---|---|---|---|---|
| `DOC-001` | Operations Manual (`OM-KFL`, Parts A–D) | `KFL 2021 COMPANY ABCD.pdf` | `92a2509879ca39aafd88e69a5a7cbfdfb536715753da674e27689b2929af07b3` | Issue 1, Rev 0, Jan 2021 | `verified_certificate_2021_07_23` (signed/stamped PDF p.4) | Standalone manual containing Part A (Gen/Ops), Part B (Abnormal/ERP/DARP), Part C (Route/Area), Part D (Training). |
| `DOC-002` | Safety Management Manual (`SMS-KFL`) | `KFL 2021 SAFETY.pdf` | `46b8d26ee14e952899a03d287fceee1a4fe0be9c193cb47047fca37ea5d01f8f` | Issue 1, Rev 0, Jan 2021 | `verified_certificate_2021_07_23` (signed/stamped PDF p.4) | Standalone manual. |
| `DOC-003` | Maintenance Manual | — | — | Manufacturer / OpSpec referenced | `oem_and_opspec_referenced` | Not a standalone manual; maps to `DOC-001` (`OM + OEM specifications`) and `ROC-001` OpSpec continued-airworthiness condition. |
| `DOC-004` | Training Manual | `KFL 2021 COMPANY ABCD.pdf` | `92a2509879ca39aafd88e69a5a7cbfdfb536715753da674e27689b2929af07b3` | Issue 1, Rev 0, Jan 2021 | `embedded_in_om_part_d` | Embedded in `DOC-001` (`parent_section_ref = "Part D"`). |
| `DOC-005` | Emergency Response Plan | `KFL 2021 COMPANY ABCD.pdf` | `92a2509879ca39aafd88e69a5a7cbfdfb536715753da674e27689b2929af07b3` | Issue 1, Rev 0, Jan 2021 | `embedded_in_om_part_b` | Embedded in `DOC-001` (`parent_section_ref = "Part B"` §§1.3–1.5, including DARP). |
| `DOC-006` | Security Management System Manual (`SEC-KFL`) | `KFL REVISED SECURITY MANUAL.pdf` | `20efd7c392f8ffa0ab007b3f84a645709211bd9e62d252a71afb1dd11ba2bd03` | Issue 1, Rev 0, Jan 2021 | `verified_certificate_2021_07_23` (signed/stamped PDF p.4) | Standalone manual. |
| `DOC-007` | Dangerous Goods Manual (`DGM-KFL`) | `DANGEROUS GOODS MANUAL KFL 01 may 2025.pdf` | `90e06fac387de092a1144fdf598e93368068b6de5e978fa0bab315a89766b823` | Issue 01, Rev 00, `2024-05-01` (internal header) | `pending_letter` (user-confirmed KCAA approval; separate approval letter to be linked when supplied) | Standalone manual; filename (`01 may 2025`) vs internal issue date (`01 May 2024`) and blank certificate page (PDF pp.4, 6) tracked explicitly. |
| `DOC-012` | Quality Management System Manual (`QM-KFL`) | `KFL QUALITY.pdf` | `82dc4d547aa0ac1d2f27c693aa91e7c81dfd3a27994c5069e6524c4fc0e6463e` | Issue 1, Rev 0, Jan 2021 | `verified_certificate_2021_07_23` (signed/stamped PDF p.3) | Standalone manual; synchronized from `draft` to `published` with `kcaa_approved = 1`. |
| `ROC-001` | ROC No. 06 & OpSpec (`KCAA/OPS/2117/ROC/06`) | `KFL ROC & OPSSPEC 2027.pdf` | `b892512dff83304a1b2e7e2b8b71ffcf29aca3f7538066869e20ebb9a378c4c8` | Issued `2026-10-12`, Expires `2027-10-11` | Signed/stamped ROC + OpSpec | Categories A & B; DG Division 6.2; ≤400 ft AGL; BVLOS No; Night No; EVLOS Yes with qualified VO; 7 listed registrations (`5Y-0029A`, `5Y-0030A`, `5Y-0042A`, `5Y-0164A`, `5Y-0600A`, `5Y-0601A`, `5Y-0602A`) kept separate from the **20-aircraft master fleet**. |

---

## 2. Conformance Audit Findings & Remediations Executed

### Workstream A — Controlled Documents, Change Requests, Distributions & QMS (`QM-KFL`, `OM-KFL §0.5`)

1. **[CRITICAL — REMEDIATED IN METADATA / OPEN FOR FULL PDF INGEST] Clean-install seed & catalogue metadata divergence**
   - **Audit Evidence:** `backend/app/database.py:1317-1365` seeded short markdown summaries with `kcaa_approved=0`, `DOC-012` marked `draft` while its version was `published`, and `DOC-003/004/005` presented as standalone manuals.
   - **Manual Basis:** `QM-KFL` §§3.1, 3.6; `OM-KFL` Part A §§0.5.2, 0.6.
   - **Remediation Executed:** `apply_catalogue_corrections()` (`backend/app/database.py:1187-1266`) records exact source PDF filenames, SHA-256 hashes, issue/revision dates, `approval_evidence_status`, `parent_document_id` / `parent_section_ref` for `DOC-003/004/005`, synchronizes `DOC-012` to `published`, and sets `kcaa_approved=1` (`2021-07-23`) on `VER-DOC-001`, `VER-DOC-002`, `VER-DOC-006`, and `VER-DOC-012` while keeping `DOC-007` at `approval_evidence_status = 'pending_letter'`.
   - **Test Coverage:** `tests/test_documents.py::TestDocumentVersioning::test_source_reconciliation_and_embedded_manual_mapping`.

2. **[HIGH — REMEDIATED] Draft version creation overwrote effective published content returned to readers**
   - **Audit Evidence:** `backend/app/p0_routes.py:304-323` selected `ORDER BY created_at DESC LIMIT 1` regardless of state, returning unapproved drafts as current content; `PATCH /versions/{id}/state` (`backend/app/p0_routes.py:277-289`) did not update `documents.current_version_id` or supersede prior published versions.
   - **Manual Basis:** `QM-KFL` §§3.12.3–3.12.5; `OM-KFL` Part A §§0.5.3–0.5.4.
   - **Remediation Executed:** `GET /api/p0/documents/{doc_id}/content` (`backend/app/p0_routes.py:309-338`) now resolves through `documents.current_version_id` (or latest `published` version) unless `include_draft=true` is explicitly requested; publishing a version (`backend/app/p0_routes.py:282-291`) atomically updates `documents.current_version_id` and marks prior published versions `obsolete`.
   - **Test Coverage:** `tests/test_documents.py::TestDocumentVersioning::test_draft_version_does_not_replace_effective_published_content`.

3. **[HIGH — REMEDIATED] P0 Change Request status updates bypassed review sequence and omitted audit events**
   - **Audit Evidence:** `backend/app/p0_routes.py:432-479` allowed direct transition from `open` to `approved` without `in_review`/`under_review` and did not call `log_audit_event`.
   - **Manual Basis:** `QM-KFL` §§3.1, 3.15; `OM-KFL` Part A §§0.5.1–0.5.6.
   - **Remediation Executed:** `update_change_request` (`backend/app/p0_routes.py:472-523`) enforces predecessor state transitions (`open/submitted -> in_review/under_review -> approved/rejected -> implemented/closed`) and logs an audit event on every status change.
   - **Test Coverage:** `tests/test_documents.py::TestDocumentVersioning::test_p0_change_request_cannot_skip_review_to_approved`.

4. **[HIGH — REMEDIATED] Distribution acknowledgements were not bound to the named recipient**
   - **Audit Evidence:** `backend/app/p0_routes.py:524-535` allowed any caller with `document:read` to acknowledge any distribution without recipient verification or 404 check.
   - **Manual Basis:** `QM-KFL` §§3.11–3.12; `OM-KFL` Part A §0.5.3.
   - **Remediation Executed:** `acknowledge_distribution` (`backend/app/p0_routes.py:567-590`) verifies the distribution exists (`404` if missing), enforces `actor == recipient_id` (or `distribution:manage` / `system_admin`), and logs an audit event.
   - **Test Coverage:** `tests/test_distributions.py::TestDistributions::test_non_recipient_cannot_acknowledge_other_holders_distribution`.

5. **[HIGH — REMEDIATED] QMS CAR/CAP lacked Level 1 (7d) / Level 2 (30d) timelines, CAP completeness gates, and independent auditor verification**
   - **Audit Evidence:** `backend/app/p1_routes.py:1413-1499` allowed CAR verification without `root_cause` or `corrective_action`, permitted owners to self-verify their own CARs, did not compute Level 1/Level 2 due dates, and omitted `safety:create`/`safety:update` from `head_quality` and `independent_auditor` (`backend/app/rbac.py:42-47, 89-92`).
   - **Manual Basis:** `QM-KFL` §§2.10.1–2.10.6, 2.11.
   - **Remediation Executed:** Added `finding_level` (`level_1` -> 7-day default deadline, `level_2` -> 30-day default deadline), required `root_cause`, `corrective_action`, and non-empty `verification` text before verification/closure, blocked self-verification (`actor == owner_id` returns `403`), and granted `head_quality` and `independent_auditor` audit/CAR management permissions (`backend/app/p1_routes.py:1413-1534`, `backend/app/rbac.py:43-47, 91-95`).
   - **Test Coverage:** `tests/test_manual_workflows.py::TestManualWorkflowControls::test_qms_car_level_deadlines_and_independent_auditor_closure`.

---

### Workstream B — SMS Occurrences, MOR 72-Hour Clock, Risk Models & Closure (`SMS-KFL §§2.2–2.6`, `OM-KFL §2.6`)

6. **[HIGH — REMEDIATED] MOR reportability and the 72-hour KCAA clock were editable at submission and not computed from `occurred_at`**
   - **Audit Evidence:** `OccurrenceCreate` accepted caller-supplied `mor_required`/`mor_deadline`; no dedicated Safety assessment endpoint calculated the 72-hour deadline from `occurred_at`.
   - **Manual Basis:** `SMS-KFL` §§2.2.3, 2.3 (Head of Safety assesses reportability; applicable MORs submitted within 72 hours of occurrence).
   - **Remediation Executed:** Removed reporter-supplied MOR flags from `OccurrenceCreate` (`backend/app/p1_models.py:23-31`), forced new occurrences to initialize with `mor_required=False, mor_deadline=None` (`backend/app/p1_routes.py:131-139`), and added `POST /api/p1/occurrences/{occ_id}/mor-assessment` (`backend/app/p1_routes.py:247-315`) requiring `safety:update`, validating `occurred_at`, computing `mor_deadline = occurred_at + 72 hours`, and recording `mor_assessed_by`, `mor_assessed_at`, `mor_assessment_reason`, and an audit event.
   - **Test Coverage:** `tests/test_occurrences.py::TestOccurrences::test_reporter_cannot_decide_mor_at_submission`, `test_head_safety_assessment_sets_72_hour_deadline_from_occurrence`, `test_reporter_cannot_assess_mor`, `test_reportable_occurrence_needs_time_to_start_mor_clock`.

7. **[HIGH — REMEDIATED] Occurrence closure could bypass follow-up effectiveness and no-new-hazard verification**
   - **Audit Evidence:** `PATCH /api/p1/occurrences/{occ_id}` (`backend/app/p1_routes.py:191-226`) allowed direct `status="closed"` without follow-up review.
   - **Manual Basis:** `SMS-KFL` §2.3.2 (Closure requires satisfactory follow-up demonstrating risk eliminated/reduced and no new hazards introduced; otherwise report remains Open).
   - **Remediation Executed:** Blocked `status="closed"` in `update_occurrence` (`backend/app/p1_routes.py:194-198`) and added `POST /api/p1/occurrences/{occ_id}/close` (`backend/app/p1_routes.py:318-373`) requiring `effectiveness_confirmed=True`, `no_new_hazards=True`, non-empty `followup_notes`, and KCAA submission/notification when `mor_required=True`.
   - **Test Coverage:** `tests/test_occurrences.py::TestOccurrences::test_occurrence_closure_requires_satisfactory_followup`.

8. **[HIGH — REMEDIATED] SMS 5×5 matrix (`SAF-07`) and OM §2.6 3-factor flight risk tool (`>20` scrutiny, `>25` cancel) were conflated and unvalidated**
   - **Audit Evidence:** `create_risk_assessment` (`backend/app/p1_routes.py:447-463`) stored arbitrary `risk_level` strings without checking 5×5 consistency or supporting the OM §2.6 exposure/score thresholds.
   - **Manual Basis:** `SMS-KFL` §2.6 (`SAF-07` 5×5 matrix); `OM-KFL` Part A §2.6 (probability, severity, exposure; score `>20` triggers additional scrutiny, `>25` cancels flight).
   - **Remediation Executed:** Added `risk_model` (`sms_5x5` vs `om_flight_26`), `exposure`, `risk_score`, `scrutiny_required`, and `flight_cancelled` to `risk_assessments` (`backend/app/p1_routes.py:447-538`). `sms_5x5` rejects contradictory ratings (`400`), while `om_flight_26` enforces `>20` (`scrutiny_required=True`) and `>25` (`flight_cancelled=True, status='cancelled'`).
   - **Test Coverage:** `tests/test_risk_assessments.py::TestRiskAssessments::test_sms_5x5_rejects_contradictory_risk_level`, `test_om_flight_risk_tool_thresholds_20_and_25`.

---

### Workstream C — Mission Planning, Flight Release, 20-Aircraft Fleet & ROC/OpSpec Gates (`OM-KFL §§2.3.1, 2.6, 3.2–3.5`, `ROC-001`)

9. **[CRITICAL — REMEDIATED] Flight plan approval and flight release used `safety:update` instead of operational authority and did not enforce ROC/OpSpec or aircraft-authorization gates**
   - **Audit Evidence:** `approve_flight_plan` and `create_flight_release` (`backend/app/p1_routes.py:1062-1100`) checked `safety:update` (excluding `head_operations` and `chief_pilot` while allowing `head_safety`), did not verify that the flight plan was approved or linked to the mission, and did not check `ROC-001` limits (≤400 ft AGL, BVLOS No, Night No, 7 OpSpec-listed registrations vs 20-aircraft fleet). Additionally, `_check_mission_eligibility` (`backend/app/p1_routes.py:101`) failed to recognize `status='active'` insurance policies created via `/api/p2/aircraft/{id}/insurance`.
   - **Manual Basis:** `OM-KFL` Part A §§2.3.1, 2.6, 3.2–3.5; `KFL ROC & OPSSPEC 2027.pdf`.
   - **Remediation Executed:**
     - Preserved all **20 aircraft rows** in `aircraft` while marking the **7 OpSpec-listed registrations** (`5Y-0029A`, `5Y-0030A`, `5Y-0042A`, `5Y-0164A`, `5Y-0600A`, `5Y-0601A`, `5Y-0602A`) with `opspec_authorized = 1` (`backend/app/database.py:1254-1264`).
     - Added `flight:release` permission to `head_operations`, `chief_pilot`, `accountable_manager`, and `system_admin` (`backend/app/rbac.py:24-66`).
     - Updated `approve_flight_plan` and `create_flight_release` (`backend/app/p1_routes.py:1137-1239`) to require `flight:release`, verify mission/plan linkage and `plan.status == 'approved'`, enforce `ROC-001` altitude (`<= 400 ft AGL`), BVLOS (`False`), and night (`False`) limits, block release for fleet aircraft where `opspec_authorized == 0`, and block release when linked `risk_assessment` has `flight_cancelled` (`>25`) or unapproved scrutiny/Medium-High risk (`>20`).
   - **Test Coverage:** `tests/test_missions.py::TestMissionStateTransitions::test_master_fleet_preserves_20_aircraft_and_7_opspec_authorized`, `test_flight_release_enforces_delegated_role_opspec_and_om_gates`.

---

### Workstream D — Dangerous Goods & Aviation Security (`DGM-KFL §§2.1–2.8, §3.1, Appendix 3`, `SEC-KFL §§3.9–3.10, Ch. 7`)

10. **[CRITICAL — REMEDIATED] DG shipments allowed out-of-scope classes, direct PATCH to `accepted`, and post-acceptance edits without re-verification**
    - **Audit Evidence:** `create_dg_shipment` and `update_dg_shipment` (`backend/app/p1_routes.py:1502-1565`) accepted any `dg_class` string, allowed `PATCH {"status": "accepted"}` without an acceptance check, and kept `status="accepted"` when quantity/packaging changed.
    - **Manual Basis:** `DGM-KFL` §§2.1–2.8, §3.1, Appendix 3; `ROC-001` OpSpec (DG Division 6.2 only).
    - **Remediation Executed:** Enforced Division 6.2 scope validation on create/update, blocked `status="accepted"` on `PATCH /api/p1/dg-shipments/{id}`, reset `status` to `"pending"` if material shipment fields change after acceptance, and extended `POST /api/p1/dg-acceptance-checks` (`backend/app/p1_routes.py:1536-1688`) with Appendix 3 checks (`triple_packaging_ok`, `no_leakage_visual_ok`, `pic_weather_confirmed`, `crew_layers_unopened_confirmed`, `weight_within_limit_ok`).
    - **Test Coverage:** `tests/test_manual_workflows.py::TestManualWorkflowControls::test_dg_shipment_enforces_division_6_2_and_blocks_patch_acceptance_bypass`.

11. **[HIGH — REMEDIATED] Security-Sensitive Information (SSI) was exposed to all `safety:read` roles while `head_security` lacked update permission**
    - **Audit Evidence:** `backend/app/rbac.py:53-56` omitted `safety:update` from `head_security`, blocking the Head of Security from updating security incidents; `list_security_incidents` (`backend/app/p1_routes.py:1658-1676`) returned raw `investigation_notes` to all roles with `safety:read`.
    - **Manual Basis:** `SEC-KFL` §§3.9–3.10, Chapter 7 (Head of Security controls SSI access; delegates to Head of Safety in absence).
    - **Remediation Executed:** Granted `safety:update`, `security:read_sensitive`, and `security:manage` to `head_security` (and `security:read_sensitive` to `head_safety` as designated alternate per `SEC-KFL` §3.9, plus `accountable_manager` and `system_admin`), and masked `investigation_notes` as `"[SSI REDACTED]"` for callers without `security:read_sensitive` (`backend/app/p1_routes.py:1760-1785`).
    - **Test Coverage:** `tests/test_manual_workflows.py::TestManualWorkflowControls::test_security_incident_head_security_update_and_ssi_masking`.

---

## 3. Clause-to-Rule-to-Test Traceability Matrix

| Manual Clause | Workflow Requirement | Rule Version | API Command / Route | Authorized Role(s) | Required Evidence | Test ID | Audit Event |
|---|---|---|---|---|---|---|---|
| `QM-KFL` §§3.1, 3.6; `OM-KFL` §0.5 | Source provenance, effective version pointer, and embedded manual mapping | `2026-10-30.1` | `GET /api/p0/documents`, `GET /api/p0/documents/{id}/content`, `PATCH /api/p0/versions/{id}/state` | `librarian`, `head_quality`, `accountable_manager`, `system_admin` | SHA-256 hash, certificate date (`2021-07-23`) or `pending_letter`, `current_version_id` | `test_documents.py::test_draft_version_does_not_replace_effective_published_content`, `test_source_reconciliation_and_embedded_manual_mapping` | `document_version:state_changed` |
| `QM-KFL` §§3.1, 3.15 | Change request must pass review before approval (SoD) | `2026-10-30.1` | `PATCH /api/p0/change-requests/{cr_id}` | `head_quality`, `accountable_manager`, `system_admin` | `in_review`/`under_review` state, `requester_id != actor` | `test_documents.py::test_p0_change_request_cannot_skip_review_to_approved` | `change_request:status_*` |
| `QM-KFL` §§3.11–3.12; `OM-KFL` §0.5.3 | Holder-bound distribution acknowledgement | `2026-10-30.1` | `POST /api/p0/distributions/{dist_id}/acknowledge` | Named `recipient_id`, `librarian`, `system_admin` | Matching `actor == recipient_id` | `test_distributions.py::test_non_recipient_cannot_acknowledge_other_holders_distribution` | `distribution:acknowledged` |
| `SMS-KFL` §§2.2.3, 2.3 | Safety MOR reportability assessment & 72h clock from `occurred_at` | `2026-10-30.1` | `POST /api/p1/occurrences/{occ_id}/mor-assessment` | `head_safety`, `system_admin` | `rationale`, `occurred_at` (when `mor_required=True`) | `test_occurrences.py::test_head_safety_assessment_sets_72_hour_deadline_from_occurrence`, `test_reporter_cannot_assess_mor` | `occurrence:mor_assessed` |
| `SMS-KFL` §2.3.2 | Guarded occurrence closure after satisfactory follow-up & no new hazards | `2026-10-30.1` | `POST /api/p1/occurrences/{occ_id}/close` | `head_safety`, `system_admin` | `effectiveness_confirmed=True`, `no_new_hazards=True`, `followup_notes` | `test_occurrences.py::test_occurrence_closure_requires_satisfactory_followup` | `occurrence:closed` |
| `SMS-KFL` §2.6 (`SAF-07`) vs `OM-KFL` Part A §2.6 | Separate SMS 5×5 matrix and OM 3-factor flight risk tool (`>20` scrutiny, `>25` cancel) | `2026-10-30.1` | `POST /api/p1/risk-assessments` | `head_safety`, `head_operations`, `chief_pilot`, `system_admin` | `risk_model`, `likelihood`, `severity`, `exposure`/`risk_score` | `test_risk_assessments.py::test_sms_5x5_rejects_contradictory_risk_level`, `test_om_flight_risk_tool_thresholds_20_and_25` | — |
| `OM-KFL` §§2.3.1, 3.2–3.5; `ROC-001` OpSpec | Operational flight plan approval, 20-aircraft fleet preservation, 7-aircraft OpSpec release gate, ≤400 ft AGL, no BVLOS/night | `2026-10-30.1` | `PATCH /api/p1/flight-plans/{id}/approve`, `POST /api/p1/flight-releases` | `head_operations`, `chief_pilot`, `accountable_manager`, `system_admin` | Approved plan, 3 confirmations, checklist, `opspec_authorized=1`, `<=400 ft AGL`, approved risk | `test_missions.py::test_master_fleet_preserves_20_aircraft_and_7_opspec_authorized`, `test_flight_release_enforces_delegated_role_opspec_and_om_gates` | `flight_plan:approved`, `flight_release:released` |
| `DGM-KFL` §§2.1–2.8, §3.1, App. 3; `ROC-001` | Division 6.2 scope, Appendix 3 acceptance checks, no PATCH bypass, post-edit invalidation | `2026-10-30.1` | `POST /api/p1/dg-shipments`, `PATCH /api/p1/dg-shipments/{id}`, `POST /api/p1/dg-acceptance-checks` | `dg_coordinator`, `head_safety`, `head_operations`, `system_admin` | Division 6.2 class, 10 Appendix 3 checks true | `test_manual_workflows.py::test_dg_shipment_enforces_division_6_2_and_blocks_patch_acceptance_bypass` | `dg_acceptance_check:accepted/rejected` |
| `SEC-KFL` §§3.9–3.10, Ch. 7 | Head of Security incident management & SSI need-to-know masking | `2026-10-30.1` | `GET /api/p1/security-incidents`, `PATCH /api/p1/security-incidents/{id}` | `head_security`, `head_safety` (alternate), `accountable_manager`, `system_admin` | `security:read_sensitive` permission for unmasked `investigation_notes` | `test_manual_workflows.py::test_security_incident_head_security_update_and_ssi_masking` | — |
| `QM-KFL` §§2.10.1–2.10.6 | Level 1 (7d) / Level 2 (30d) CAR deadlines, CAP completeness, and independent auditor verification | `2026-10-30.1` | `POST /api/p1/corrective-actions`, `POST /api/p1/corrective-actions/{id}/verify`, `PATCH /api/p1/corrective-actions/{id}` | `head_quality`, `independent_auditor`, `system_admin` | `root_cause`, `corrective_action`, `verification`, `actor != owner_id` | `test_manual_workflows.py::test_qms_car_level_deadlines_and_independent_auditor_closure` | `corrective_action:verified` |

---

## 4. Remaining Production Blockers & External Evidence Gates

1. **DGM-KFL Separate Approval Letter (`DOC-007`) — Pending User Supply:**
   - `DOC-007` is recorded as KCAA-approved per user confirmation with `approval_evidence_status = "pending_letter"` and `source_issued_date = "2024-05-01"` (matching internal header Issue 01 Rev 00, 01 May 2024 despite the May 2025 filename). Link the approval letter reference and date to `VER-DOC-007` once provided.
2. **Authority Coverage for the Remaining 13 Master-Fleet Aircraft (`aircraft.opspec_authorized = 0`):**
   - All **20 aircraft rows** are preserved in the master fleet register. Only the **7 registrations** printed on `KFL ROC & OPSSPEC 2027.pdf` (`5Y-0029A`, `5Y-0030A`, `5Y-0042A`, `5Y-0164A`, `5Y-0600A`, `5Y-0601A`, `5Y-0602A`) have `opspec_authorized = 1`. Flight release fails closed (`400`) for the other 13 registrations until an updated OpSpec or KCAA authorization addendum is linked.
3. **Aircraft-Specific OEM Maintenance Manuals & KCAA-Approved Checklists:**
   - `DOC-003` is mapped to `OM + OEM specifications` (`ROC-001` requires continued airworthiness per manufacturer specifications). Per-model OEM maintenance schedules and KCAA-approved aircraft checklists must be linked before enabling automated return-to-service gates.
4. **FDTL Numerical Limits Validation (`14h duty / 12h block / 10h rest`) — User-Confirmed Provisional Flag:**
   - Per user confirmation, the current `14h / 12h / 10h` values are retained and flagged in `app_settings` (`fdtl_validation_status`), `GET /api/p1/duty-records/fdtl-validation`, and `GET /api/p1/workflow-rules` as `configurable_application_defaults_pending_regulatory_clause_validation` (`binding_gate_active = false`) until mapped to a specific KCAA UAS regulatory clause and signed off by the Head of Operations.
5. **Production Authentication (`DEV_MODE` vs JWT/OIDC):**
   - Pre-existing uncommitted auth changes in `backend/app/p0_routes.py` were preserved untouched per workspace rules; before production cutover, ensure `login` does not return `password_hash`, issues a signed JWT/session token, and disables `DEV_MODE` header fallback.
