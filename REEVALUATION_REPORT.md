# Aviation DMS Reevaluation Report

**Date:** 2026-11-24  
**Prepared by:** Chief of Staff  
**Scope:** Comprehensive reevaluation of 11 implementation areas based on change request workflow, audit processes, document management, fleet management, and integration requirements.

---

## Executive Summary

The Aviation DMS has a solid P0/P1 foundation with FastAPI backend, React/TypeScript frontend, and comprehensive RBAC. However, several critical gaps exist between the current implementation and the operational requirements defined by KFL's document control, audit, and fleet management processes. This report provides detailed findings and a phased implementation plan for all 11 reevaluation points.

---

## 1. Change Request Workflow — Separation of Duties & Manual Ownership

### Current State
- **ChangeRequest** model exists with states: `open → submitted → in_review → approved/rejected → implemented → closed`
- `ChangeRequests.tsx` page allows all roles with `document:read` to create/view; review/approve restricted to `document:update`/`document:approve`
- **SoD rule** enforced in `rbac.py`: proposer cannot approve/publish own change request
- **Document ownership** tracked via `documents.owner_id` but not linked to manual types (Operations, Quality, Safety, Security, Training, Maintenance)

### Gaps
| Requirement | Current | Gap |
|-------------|---------|-----|
| Manual-specific ownership | Generic `owner_id` | No mapping of doc_class → Head of Department |
| All roles except external can propose | `document:propose` on librarian, heads | ✅ Implemented |
| Manual owners edit drafts, HoQMS approves | Proposals by anyone; HoQMS reviews | Manual owners don't have special draft edit path |
| Propose→Review→Approve→Publish→Distribute | CR workflow exists | Distribution step separate; publish not gated by HoQMS |

### Recommendations
1. **Add `manual_owner_role` column to `documents` table** mapping:
   - `operations_manual` → `head_operations`
   - `safety_manual` → `head_safety`
   - `quality_manual` → `head_quality`
   - `security_manual` → `head_security`
   - `training_manual` → `head_training`
   - `maintenance_manual` → `head_maintenance`

2. **Introduce `draft_manual_versions` table** for manual owners to edit drafts directly (bypassing proposal engine), with HoQMS (`head_quality`) as sole approver/publisher.

3. **Enforce workflow gate**: `document:publish` permission only for `head_quality` on controlled manuals; `accountable_manager` retains executive override.

4. **Link CR to document class**: Auto-route CRs to correct manual owner based on `doc_class`.

---

## 2. Canonical User ID for u-quality (Librarian Cluster)

### Current State
- Migration `migrate_canonical_account_ids_v2()` promotes `u-quality` as canonical, merging `u-lib` and `u-records`
- `user_id_aliases` table preserves legacy IDs (`u-lib`, `u-quality`, `u-records`, `librarian`, `quality`, `records_custodian`)
- `ROLE_WORKSPACES` in `permissions.ts` shows `librarian` home as `/documents`; `head_quality` home as `/audit-dashboard`

### Finding
The canonical ID **`u-quality`** is already correctly established as the primary identity for the Quality/Librarian/Records cluster. The role `head_quality` is assigned to this canonical user.

### Action Required
- **Document this as canonical** in onboarding docs and `ROLE_WORKSPACES` — already correct.
- Ensure all invitation emails and setup tokens reference `u-quality` as the canonical actor for this cluster.

---

## 3. Audit Workflow — Head of Quality/Safety/Security Auditor Controls

### Current State
#### P1 Quality Audits (`quality_audits` table)
- Internal audits only; `auditor_id` assigned at creation
- Findings in `quality_audit_findings` with `severity` + `status`
- CARs in `corrective_actions` linked to findings/audits
- `QualityAudits.tsx` allows `safety:create` to create audits (too broad)

#### P3 External Audit Reports (`audit_reports` table) — **SS-KFL-SEP-2026 pattern**
- Audit engagements with `auditor_id` (must be `independent_auditor` role), `auditee_id`
- Findings in `audit_findings` with `level 1-4`, `area`, `due_date`, `closure_evidence`
- **Provenance import workflow** for historical audits: `audit_report_imports` → independent auditor verification → `audit_reports` + `audit_findings`
- `AuditReports.tsx` + `AuditReportImportWorkflow` component handle this

#### Auditor Controls Gap
| Role | P1 Quality Audits | P3 External Audits | Department-Specific Control |
|------|-------------------|---------------------|----------------------------|
| `head_quality` | Full CRUD | `audit_report:read`, `audit_finding:read/update/close` | ❌ No scoped dashboard |
| `head_safety` | `audit:read` only | `audit_finding:read/create/update` | ❌ No safety-specific audit view |
| `head_security` | `audit:read` only | `audit_finding:read/create/update` | ❌ No security-specific audit view |

### SS-KFL-SEP-2026 CAR/Findings Closure Workflow
**Implemented:**
- `audit_findings.status`: `open → in_progress → closed`
- Closure requires `closure_evidence` + `closed_by` + `closed_at` (enforced in `p3_routes.py:1137-1141`)
- `corrective_action_id` link to CARs (`corrective_actions` table)
- `audit_finding:close` permission required for closure

**Missing:**
- Automated escalation/reminders for overdue findings
- Head of Department approval before closure (currently any `audit_finding:close` holder can close)
- Findings dashboard filtered by `area` (Quality/Safety/Security) per role

### Recommendations
1. **Create department-scoped audit dashboards**:
   - `/audit-dashboard/quality` for `head_quality` (P1 + P3 quality findings)
   - `/audit-dashboard/safety` for `head_safety` (occurrence investigations + safety findings)
   - `/audit-dashboard/security` for `head_security` (security assessments + security findings)

2. **Add `department` column to `audit_findings`** (values: `quality`, `safety`, `security`) for filtering.

3. **Implement closure approval gate**: Finding closure requires both `audit_finding:close` AND matching department head role.

4. **Add overdue finding alerts** via `notifications` table with `entity_type=audit_finding`.

---

## 4. Document Editor Access Control — ROC, OpSpec, OEM Publications

### Current State
- `DocumentSelector` in `DocumentEditor.tsx` shows ALL documents from `/p0/documents`
- `DocumentEditorContent` loads content via `/p0/documents/{docId}/content`
- No filtering by `doc_class` or document type

### Document Classes in System (`DocClass` enum):
```
operations_manual, safety_manual, maintenance_manual, training_manual,
emergency_plan, sop, checklist, form, policy, procedure
```

### Documents That Should NOT Be Editable via Document Editor:
| Document Type | Reason | Current Protection |
|---------------|--------|-------------------|
| ROC (Remote Operator Certificate) | Regulatory certificate, not a controlled manual | None — reachable if created as document |
| OpSpec (Operations Specifications) | Regulatory authorization, appendices to ROC | None |
| OEM Publications | Vendor IP, reference only | None |
| Aircraft Insurance/Registration | Tracked in P2 AircraftInsurance page | Separate API, but could be created as document |

### Recommendations
1. **Add `document_category` enum** to `documents` table:
   - `controlled_manual` (editable via proposals)
   - `regulatory_certificate` (ROC, OpSpec — read-only, managed via ROC API)
   - `oem_publication` (reference only — read-only, uploaded as attachment)
   - `aircraft_record` (insurance, registration, CoA — managed via P2 Aircraft API)

2. **Filter `DocumentSelector` query**: `WHERE document_category = 'controlled_manual'`

3. **Enforce at API level**: `/p0/documents/{id}/content` PUT and proposal endpoints check `document_category`; reject if not `controlled_manual`.

4. **Migrate existing ROC/OpSpec/OEM documents** to correct category via seed script.

---

## 5. Submit Proposal Button — Document Editor Modal

### Current State (`DocumentEditor.tsx:786-898`)
- `<Dialog open={showSubmit && canPropose}>` with "Submit Proposal" button
- **High-fidelity manuals** (pdf2htmlEX output): Shows proposed changes from text selection overlay
- **Regular documents**: Shows auto-detected atomic changes from `proposalPreview` query
- **Validation**: Requires `hasChanges`, `selectedChangeSequences.length > 0` (regular) or `proposedChangeRanges.length > 0` (high-fidelity)

### Issues
1. **Button label** says "Submit Proposal" but creates **batch proposals** (one per atomic change) — confusing
2. **No manual owner routing**: Proposals go to generic review queue, not to manual owner → HoQMS
3. **Rationale/severity** captured but not linked to change request workflow
4. **High-fidelity manual warning** says "proposal submission is also disabled" but button remains enabled if `proposedChangeRanges.length > 0` — inconsistent

### Recommendations
1. **Rename button** → "Submit Change Proposals" (plural, reflects batch creation)
2. **Add routing field**: Auto-populate `reviewer_id` based on document's `manual_owner_role` (Head of Dept) and `approver_id` as `u-quality` (HoQMS)
3. **Create linked ChangeRequest** on submission with `change_request_id` on each proposal
4. **Disable for high-fidelity manuals** with clear banner: "Formatted manuals require manual review — use text selection to propose changes"
5. **Add "Save as Draft Proposal"** option for incomplete work

---

## 6. Multi-User Roles — u-flight-ops, u-reporter, u-auditor

### Current State
- `users` table: one row per `user_id` (unique)
- `user_roles` table: **many-to-many** (`user_id`, `role`) — supports multiple roles per user
- **But**: Invitation system (`auth_invite_email_outbox`, `auth_setup_tokens`) creates **one user per invite**
- `AuthInviteRequest` accepts single `username`/`email` → one account
- No "invite additional person to existing role" flow

### Roles That Need Multiple Individuals:
| Role | Current Constraint | Need |
|------|-------------------|------|
| `flight_ops_officer` | Single `u-flight-ops` user | Multiple officers per shift |
| `occurrence_reporter` | Single `u-reporter` user | All crew can report |
| `independent_auditor` | Single `u-auditor` user | Multiple auditors per engagement |

### Recommendations
1. **Add `role_invitation` flow**: POST `/auth/invites` with `role` + `email` → creates new user with that role assigned
2. **Allow multiple users per role**: Already supported by `user_roles` table — just need invitation UI
3. **Update `ROLE_WORKSPACES`**: Add `primaryPaths` for each role (already done)
4. **Invitation UI**: Admin page to "Invite User to Role" with email, role selector, optional department
5. **Landing page**: After invite acceptance, redirect to role-specific workspace (`ROLE_WORKSPACES[role].home`)

---

## 7. ROC Fleet Management — Aircraft Status Tags

### Current State (`ROCRegister.tsx`, `p1_models.py`)
- `aircraft.status`: `active`, `maintenance`, `retired` (free text, validated in `AircraftUpdate`)
- `AircraftInsurance.tsx` and `MaintenanceManagement` track separate records
- No unified status reflecting **Head of Maintenance** work/reports

### Required Tags (from requirement):
| Tag | Source | Logic |
|-----|--------|-------|
| `Grounded` | Maintenance records + safety occurrences | Open CARs, major findings, failed inspections |
| `Unserviceable` | Maintenance records | Due/overdue maintenance, failed checks |
| `Serviceable` | Maintenance + Insurance + ROC scope | All current, no open issues |
| `Standby` | Operations decision | Serviceable but not assigned to mission |
| `Deployed` | Mission status | Aircraft on active mission (`in_progress`) |

### Recommendations
1. **Add `operational_status` column to `aircraft` table** (enum: `grounded`, `unserviceable`, `serviceable`, `standby`, `deployed`)
2. **Compute status via background job** (or DB trigger) from:
   - `maintenance_records` (overdue → `unserviceable`)
   - `safety_actions`/`audit_findings` with `area=maintenance` + `status=open` → `grounded`
   - `missions` with `status=in_progress` + `aircraft_id` → `deployed`
   - `aircraft_insurance` + `aircraft_documents` expiry → affects `serviceable`
3. **Head of Maintenance** can override with justification (audit logged)
4. **Display as Badge** in `ROCRegister.tsx` aircraft table with color coding
5. **Add filter** on ROC page by operational status

---

## 8. Document Ingestion — Insurance, Registration, Licenses, Historical Authorizations

### Current State
- **Aircraft Insurance**: `/p2/aircraft/{id}/insurance` API + `AircraftInsurance.tsx` — manual entry
- **Aircraft Documents**: `/p2/aircraft/{id}/documents` API + same page — manual entry (types: `airworthiness_cert`, `registration`, `arc`, `noise_cert`, `radio_license`, `maintenance_release`)
- **Personnel Licenses**: `/p2/personnel/licenses` API + `PersonnelLicenses.tsx` — manual entry
- **Self-Service Upload**: `/p2/personnel/uploads/file` — crew upload credentials for verification
- **Historical Docs (Ops Authorizations)**: No dedicated flow; could use `/p0/documents` with `doc_class=policy`

### Auto-Population Gap
- **No OCR/extraction** from uploaded PDFs
- **No directory routing** based on document type
- **Manual data entry** for all fields

### Recommendations
1. **Add `document_source` column** to relevant tables: `uploaded`, `extracted`, `manual`
2. **Implement PDF text extraction** on upload (using `pdfplumber`/`pymupdf` already in stack):
   - Insurance: Extract policy number, insurer, coverage, dates
   - Registration: Extract registration mark, owner, issue/expiry
   - Licenses: Extract license number, type, holder, dates
   - Ops Authorizations: Extract auth number, scope, dates
3. **Auto-route to correct table/API** based on detected document type:
   - `insurance` → `aircraft_insurance` (match by aircraft registration in PDF)
   - `registration` → `aircraft_documents` (type=registration)
   - `license` → `personnel_licenses` (match by person_id from filename/metadata)
   - `authorization` → `documents` (doc_class=policy)
4. **Queue for verification**: Extracted data → `verification_status=pending` → Head of Maintenance/Quality verifies
5. **Directory structure** in storage: `uploads/insurance/`, `uploads/registration/`, `uploads/licenses/`, `uploads/authorizations/`

---

## 9. Risk Assessment & Mission Sheet — Replace with Provided PDFs

### Current State
- **RiskAssessments.tsx** + `RiskAssessmentCreate` model: SMS 5×5 matrix + OM §2.6 flight risk model
- **Missions.tsx** + `MissionCreate`: Flight log table with start/end times, battery cycles
- No PDF template rendering

### Provided PDFs Analysis

#### KFL_Drone_Risk_Assessment.pdf
**Structure:**
1. **Header**: Location/coordinates, Date, Project type, Drone type/model, PIC
2. **Hazards Table** (8 predefined + 2 custom):
   - Hazard | Risk | Mitigation in place | Score after mitigation (L×S)
   - Trees, Buildings, Human traffic, Wildlife, Manned aircraft, Strong winds, Communication towers, Electric poles
3. **Risk Matrix** (5×5 Likelihood × Severity)
4. **Flight Decision**: Overall residual risk → Proceed/Hold + conditions
5. **Sign-off**: Filed by PIC + Approved by Head of Safety + dates/signatures

#### KFL_Drone_Mission_Sheet.pdf
**Structure:**
1. **Header**: Location, Date, PIC name, Type of operation, KCAA OA reference, Drone type/model
2. **Flight Log** (11 rows): Flight no., Start, End, Total run, Battery number, Charge cycles
3. **Sign-off**: Filed by PIC + Signature + Date

### Implementation Plan
1. **Create PDF templates** in `backend/app/templates/` matching exact layout
2. **Add `render_risk_assessment_pdf(assessment_id)`** endpoint:
   - Map `RiskAssessment` fields → template placeholders
   - Predefined hazards as checklist; custom hazards from `mitigation_measures`
   - Risk matrix as static reference; computed score displayed
   - Signature fields for PIC + Head of Safety
3. **Add `render_mission_sheet_pdf(mission_id)`** endpoint:
   - Map `Mission` + `PostFlightReport` + `FlightRelease` data
   - Flight log rows from `PostFlightReport.battery_cycles` or manual entry
   - PIC signature field
3. **Integrate into UI**:
   - "Download Risk Assessment (PDF)" button on RiskAssessments page
   - "Download Mission Sheet (PDF)" button on Missions page (post-flight)
4. **Store rendered PDF** as `document_files` attachment for audit trail

---

## 10. Global Filter Bar — Document Search by Name, Doc ID, Keyword

### Current State
- **Per-page filters**: Each page implements own `search` + `statusFilter` state (see `ChangeRequests.tsx`, `AuditReports.tsx`, `QualityAudits.tsx`, `PersonnelLicenses.tsx`, etc.)
- **No global search**: No cross-entity search
- **Filter utilities** in `filters.ts` but not consistently used

### Current Search Capabilities by Page
| Page | Search Fields | Filter Fields |
|------|---------------|---------------|
| ChangeRequests | None (only status) | status |
| AuditReports | audit_number, scope, regulatory_basis | status |
| QualityAudits | audit_id, title, audit_type, scope | status |
| PersonnelLicenses | None (only status filter) | status |
| AircraftInsurance | None (aircraft selector only) | None |
| Documents (catalogue) | title, document_id | doc_class, status |

### Recommendations
1. **Add global search API**: `GET /api/search?q={query}&types=document,audit,license,aircraft,mission`
   - Searches: `documents.title`, `documents.document_id`, `audit_reports.audit_number`, `audit_findings.finding_number`, `personnel_licenses.license_number`, `aircraft.registration`, `missions.title`
   - Returns unified results with `type`, `id`, `title`, `subtitle`, `url`

2. **Global Filter Bar Component** (persistent in `AppShell`):
   - Search input with type-ahead
   - Quick filters: Document ID, Audit Number, License Number, Aircraft Reg
   - Recent searches dropdown

3. **Standardize per-page filters** using `filters.ts` utilities:
   - `filterBySearch(items, search, ['title', 'document_id', 'doc_class'])`
   - `filterByStatus(items, status)`
   - Consistent filter UI: status pills + search input

4. **Add column-specific filters** on tables (Doc ID, Title, Class, Status, Owner, Dates)

---

## 11. Zoho BugTracker Integration — Forms/Sheets Decommissioned

### Current State
- Zoho Forms and Zoho Sheets dual-write/pull integrations are decommissioned; `backend/app/feedback_sync.py` is removed.
- Zoho BugTracker remains the supported external issue tracker for feedback. Feedback creation still queues a BugTracker push, while the cron and webhook paths synchronize local status.
- BugTracker identifiers, URL, and sync state use `bugtracker_id`, `bugtracker_url`, and `bugtracker_sync_state`.
- Existing Forms/Sheets columns are retained only as legacy database fields so existing SQLite data can be upgraded without destructive column drops. The startup migration copies the prior sync state into `bugtracker_sync_state` once.
- OAuth refresh credentials are a valid configuration path; they are refreshed when an access token is not configured.

### Operational Requirements
- Keep the BugTracker project configuration and `cron_bugtracker_sync.py` / Docker copy in place.
- Staging Compose reads OAuth client ID, client secret, and refresh token from protected host-side secret files under `/opt/kfl-aviation-dms-staging/secrets/`; `.env.staging` contains file paths only, never the secret values.
- Do not add Zoho Forms or Zoho Sheets credentials, webhook routes, or synchronization code.
- Rotate any Zoho credentials exposed in prior conversations before using them for staging or production.

---

## Phased Implementation Plan

### Phase 1: Critical Fixes (Week 1-2) — COMPLETED
| # | Task | Owner | Status |
|---|------|-------|--------|
| 1 | Add `manual_owner_role`, `document_category` to `documents`; `operational_status` to `aircraft`; `department` to `audit_findings`; `bugtracker_id/url` to `feedback` | Backend | ✅ Done |
| 2 | Seed `manual_ownership` table + assign `manual_owner_role` to existing documents | Backend | ✅ Done |
| 3 | Filter DocumentEditor to `controlled_manual` only (backend + frontend) | Backend + Frontend | ✅ Done |
| 4 | Fix Submit Proposal button label + manual owner routing banner | Frontend | ✅ Done |
| 5 | Aircraft `operational_status` badges in ROCRegister + compute endpoint | Backend + Frontend | ✅ Done |
| 6 | Add `document:review` permission to department heads + librarian | Backend | ✅ Done |

### Phase 2: Audit & Multi-User Roles (Week 3-4) — COMPLETED
| # | Task | Owner | Status |
|---|------|-------|--------|
| 6 | Department-scoped audit dashboards (Quality/Safety/Security tabs) | Full-stack | ✅ Done |
| 7 | `department` field on `audit_findings` + closure gate by HoD | Backend | ✅ Done |
| 8 | Role invitation flow — `POST /auth/invites/role` for multiple users per role | Backend | ✅ Done |
| 9 | `document:review` permission for all department heads + librarian | Backend | ✅ Done |

### Phase 3: Document Ingestion & PDFs (Week 5-6) — COMPLETED
| # | Task | Owner | Status |
|---|------|-------|--------|
| 10 | PDF text extraction pipeline (`upload_ingestion.py`) for insurance/registration/licenses | Backend | ✅ Done |
| 11 | Auto-routing endpoints: `POST /ingest/document` + `POST /ingest/document/apply` | Backend | ✅ Done |
| 12 | Risk Assessment PDF template (`pdf_render.py`) matching provided KFL PDF | Backend | ✅ Done |
| 13 | Mission Sheet PDF template (`pdf_render.py`) matching provided KFL PDF | Backend | ✅ Done |
| 14 | PDF download endpoints: `GET /risk-assessments/{id}/pdf`, `GET /missions/{id}/pdf` | Backend | ✅ Done |

### Phase 4: Search & Zoho Migration (Week 7-8) — COMPLETED
| # | Task | Owner | Status |
|---|------|-------|--------|
| 15 | Global search API `GET /p0/search` across documents/audits/licenses/aircraft/missions | Backend | ✅ Done |
| 16 | FilterBar React component integrated into AppShell | Frontend | ✅ Done |
| 17 | Zoho BugTracker service (`bugtracker_sync.py`) replacing Forms+Sheets | Backend | ✅ Done |
| 18 | Feedback creation now syncs to BugTracker instead of Forms+Sheets | Backend | ✅ Done |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Manual owner routing breaks existing CRs | Medium | High | Migration script to backfill `manual_owner_role` on existing documents |
| PDF extraction accuracy varies | High | Medium | Human verification queue mandatory; confidence scoring |
| Zoho BugTracker API rate limits | Medium | Low | Batch sync with exponential backoff |
| Multi-user role invitation conflicts with canonical ID migration | Low | High | Test in staging with cloned DB first |
| Global search performance on large datasets | Medium | Medium | Add SQLite FTS5 virtual tables for searchable columns |

---

## Appendix: Key Files to Modify

### Backend
- `backend/app/database.py` — schema changes (manual_owner_role, operational_status, department on findings)
- `backend/app/rbac.py` — permissions for manual owners, department-scoped audit access
- `backend/app/p0_routes.py` — DocumentEditor content PUT/proposal validation
- `backend/app/p1_routes.py` — aircraft operational status computation
- `backend/app/p2_routes.py` — document ingestion endpoints
- `backend/app/p3_routes.py` — audit finding closure gate
- `backend/app/feedback_sync.py` — Zoho BugTracker sync replacement

### Frontend
- `frontend/src/pages/DocumentEditor.tsx` — proposal button, document selector filter
- `frontend/src/pages/ROCRegister.tsx` — operational status badges
- `frontend/src/pages/AuditDashboard.tsx` — department-scoped views
- `frontend/src/pages/ChangeRequests.tsx` — manual owner routing
- `frontend/src/pages/SelfServiceUpload.tsx` — ingestion UI
- `frontend/src/pages/RiskAssessments.tsx` — PDF download
- `frontend/src/pages/Missions.tsx` — PDF download
- `frontend/src/components/layout/AppShell.tsx` — Global FilterBar
- `frontend/src/components/ui/FilterBar.tsx` — new component

### Database Migrations Required
1. `ALTER TABLE documents ADD COLUMN manual_owner_role TEXT`
2. `ALTER TABLE documents ADD COLUMN document_category TEXT DEFAULT 'controlled_manual'`
3. `ALTER TABLE aircraft ADD COLUMN operational_status TEXT DEFAULT 'serviceable'`
4. `ALTER TABLE audit_findings ADD COLUMN department TEXT`
5. `ALTER TABLE feedback ADD COLUMN bugtracker_id TEXT, ADD COLUMN bugtracker_url TEXT`

---

## Sign-off

**Prepared by:** Chief of Staff  
**Review required by:** Head of Quality, Head of Safety, Head of Security, Head of Operations, Head of Maintenance  
**Target implementation start:** 2026-11-30