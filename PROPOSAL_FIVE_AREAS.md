# Proposal Report — Five Areas for Improvement

**Prepared by:** Chief of Staff  
**Date:** 2026-11-24  
**Status:** Proposal only — no implementation yet

---

## 1. Risk Assessment & Mission Recording vs Provided PDF Templates

### What the PDFs specify (from extracted text)

**KFL_Drone_Risk_Assessment.pdf**
- Header: Location / coordinates, Date, Project type, Drone type / model, Pilot in Command (PIC)
- Hazards table: 8 predefined hazards (Trees, Buildings, Human traffic, Wildlife, Manned aircraft, Strong winds, Communication towers, Electric poles) + 2 custom hazard slots
  - Columns: Hazard | Risk | Mitigation in place | Score after mitigation (L × S)
- Risk matrix: 5×5 Likelihood × Severity grid with scores 1–25, bands Low (1–4) / Medium (5–9) / High (10–25)
- Flight Decision: Overall residual risk score + level, Proceed / Hold, Additional conditions or notes
- Sign-off: Filed by PIC (full name), Approved by Head of Safety, Date filed, Head of Safety signature, Approval date

**KFL_Drone_Mission_Sheet.pdf**
- Header: Location, Date, PIC name, Type of operation, KCAA OA reference number, Drone type / model
- Flight Log: 11 rows — Flight no., Start (HH:MM), End (HH:MM), Total run (HH:MM), Battery number, Charge cycles
- Sign-off: Filed by PIC, PIC full name, Signature, Date filed

### Current in-app implementation

**RiskAssessments.tsx** (existing)
- Fields: title, description, hazard IDs, occurrence ID, mission ID, risk model (SMS 5×5 / OM §2.6), likelihood, severity, risk level, exposure, mitigation measures, residual risk
- Summary cards: Total Assessments, Awaiting Approval, High/Critical, Approved
- No dedicated hazard table matching the 8 predefined KFL hazards
- No risk matrix visualization
- No "Flight Decision" Proceed/Hold logic with Head of Safety sign-off fields
- No PIC full name / signature / approval date fields

**Missions.tsx** (existing)
- Fields: title, description, mission type, priority, planned date, location
- Status lifecycle: planned → released → in_progress → completed / cancelled / aborted
- Summary cards: Total, Planned, In Progress, Completed
- No flight log table (start/end times, battery number, charge cycles)
- No KCAA OA reference field
- No PIC name field
- No sign-off block

### Gap analysis

| PDF element | In-app equivalent | Gap |
|-------------|-------------------|-----|
| PIC name header | assessor_id (user ID only) | Missing PIC full name field |
| Drone type / model | exposure field (loosely mapped) | No dedicated drone model field |
| KCAA OA reference | Not present | Missing entirely |
| 8 predefined hazards table | Free-text hazard IDs | No predefined hazard checklist with mitigations/scores |
| Risk matrix (5×5) | Single risk_score / risk_level | No matrix UI; no score band explanation |
| Flight Decision Proceed/Hold | flight_cancelled boolean | No explicit decision field or conditions/notes |
| Head of Safety approval + signature + date | reviewed_by / reviewed_at | Missing signature capture and formal approval workflow |
| Mission flight log (11 rows: start/end/battery/cycles) | None | Missing entirely — post_flight_reports has battery_cycles but no start/end times |
| Mission sign-off (PIC signature + date) | None | Missing entirely |

### Recommended alignment approach (proposal)

1. **Risk Assessment form** — Add optional fields that mirror the PDF exactly:
   - `pic_full_name`, `location_coordinates`, `drone_type_model`, `project_type`
   - Predefined hazard checklist (8 KFL hazards) with per-hazard mitigation and L×S score, plus 2 custom hazard rows
   - Visual 5×5 risk matrix (clickable cells) that auto-computes overall score
   - Flight Decision field (Proceed / Hold) with conditions/notes text area
   - Sign-off block: PIC full name, Head of Safety name, signature placeholder, dates

2. **Mission recording** — Add to mission create/edit:
   - KCAA OA reference number, PIC name, drone type/model
   - Flight log table (rows for flight no., start, end, total run, battery, charge cycles) — editable pre/post flight
   - Sign-off block: PIC signature + date filed
   - "Download Mission Sheet (PDF)" button using the existing `pdf_render.py` template

3. **PDF generation** — Reuse the `render_risk_assessment_pdf` and `render_mission_sheet_pdf` functions already built in Phase 3; wire them to "Download PDF" buttons on the Risk Assessments and Missions pages.

---

## 2. Status Bar Evaluation — Why It Looks "Weird"

### Finding

There is **no dedicated `StatusBar` component** in the codebase. Searches for `status.bar`, `statusbar`, `StatusBar`, `status_bar` returned zero matches. The user is likely referring to one of these near-misses:

| Candidate | Location | What it does | Why it may look "weird" |
|-----------|----------|--------------|-------------------------|
| Dashboard data status badge | `Dashboard.tsx:124-126` | Shows "Dashboard data loaded / Checking / Some data unavailable" | Small pill badge tucked beside notification and KPI buttons; no clear visual grouping; tone changes (blue/amber) without consistent placement |
| Sidebar session indicator | `AppShell.tsx:444` | Shows `full_name · active_role` + "Secure session active" dot | Sits at bottom of sidebar below account controls; low contrast (`text-slate-300`/`text-emerald-300`) against dark sidebar; mixes session health with user identity |
| Role switch dropdown | `AppShell.tsx:431-442` | Active role selector | Visually dense; combined with session status in the same bottom sidebar block |
| Page header status badge | Various pages | Status pill on tables | Inconsistent styling across pages |

### Root causes of "weird" appearance

1. **No single ownership** — Status information is scattered across dashboard badge, sidebar footer, and per-page table pills instead of one cohesive status bar.
2. **Poor contrast/hierarchy** — The sidebar session indicator uses slate/emerald text on a dark background (`bg-kfl-dark`), making it hard to read at a glance.
3. **Mixed concerns** — Session health ("Secure session active"), user identity (`full_name · role`), and data load state are crammed into one bottom-sidebar block with no visual separation.
4. **No persistent location** — The dashboard status badge only appears on `/dashboard`; other pages have no equivalent, so users don't know where to look for system status.

### Recommended fix (proposal)

Create a single `StatusBar` component placed consistently in the AppShell header (above the page header or in the top-right of the main area), showing:

- **System health** (operational / degraded) from observability data
- **Current session** (user + active role) with clear contrast
- **Unread notifications** count (already exists as bell icon)
- **Data freshness** ("Last refreshed X minutes ago")

The sidebar bottom block should be simplified to just user profile + sign-out, removing the session-health dot that competes for attention.

---

## 3. SMTP Notification Method for App Upgrades

### Goal

When the application is upgraded (new deployment/version), notify all active users via SMTP email with a summary of updates and improvements in simple, non-technical language.

### Proposed architecture

**1. Version tracking table** (new)
```sql
CREATE TABLE IF NOT EXISTS app_versions (
    version_id TEXT PRIMARY KEY,
    version_number TEXT NOT NULL,
    released_at TEXT NOT NULL,
    released_by TEXT NOT NULL,
    changelog_non_technical TEXT NOT NULL,  -- plain-English summary
    changelog_technical TEXT,              -- optional detail for admins
    notification_sent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
```

**2. Upgrade event trigger**
When a new version is released (via deploy script or admin action):
- Insert row into `app_versions` with `notification_sent = 0`
- Trigger a background job to send SMTP emails

**3. Email content (plain-English template)**

Subject: "KFL Aviation DMS — New version [X] is now available"

Body structure:
```
Hello [Name],

We've updated the KFL Aviation DMS to version [X]. Here's what's new and what it means for you:

• [Improvement 1] — What it means: [plain-language benefit]
• [Improvement 2] — What it means: [plain-language benefit]
• [Improvement 3] — What it means: [plain-language benefit]

You don't need to do anything — the system is ready to use. If you notice anything unusual or have questions, contact your system administrator.

Thank you,
KFL Aviation DMS team
```

**4. Non-technical language mapping**

| Technical change | Plain-English summary |
|------------------|----------------------|
| New `operational_status` column on aircraft | Aircraft now show clear status tags (Serviceable, Grounded, etc.) so you can see at a glance which planes are ready to fly. |
| Department-scoped audit dashboards | Quality, Safety, and Security leads now have their own dashboard views showing only findings for their department. |
| Bulk role invitations | You can invite several people to the same role at once (for example, multiple flight operations officers) instead of one at a time. |
| PDF risk assessment and mission sheet downloads | You can now download formatted PDF versions of your risk assessments and mission sheets that match KFL templates. |
| Global search bar | Search across documents, audits, licenses, aircraft, and missions from one search bar at the top of every page. |
| BugTracker integration | Feedback and issue reports are now tracked in Zoho BugTracker for faster resolution. |

**5. Delivery method**
- Use existing `notifications.send_invitation_email` SMTP infrastructure (already configured in the codebase)
- Mark `notification_sent = 1` after successful send
- Retry failed sends with exponential backoff; log failures but don't block the upgrade

**6. Opt-out / preferences**
- Add `notification_preferences.upgrade_notifications` flag (default on)
- Respect user preference when sending

### Files to create/modify (proposal)

- `backend/app/app_versions.py` — version tracking + upgrade email service
- `backend/app/database.py` — `app_versions` table + `notification_preferences.upgrade_notifications` column
- `backend/app/notifications.py` — reuse `send_invitation_email` or add `send_upgrade_email`
- Admin UI: "Release new version" form in AdminObservability with plain-English changelog editor

---

## 4. Admin Dashboard Interactivity — Build Tracking, Historical Versions, Audit Events

### Current state

`AdminObservability.tsx` shows static health/database/workflow metrics with:
- Backup run/scanner test buttons
- Role management + invite issuance
- 15-second refetch interval

No build version tracking, no historical version comparison, no audit event browsing.

### Proposed improvements

**A. Build & release tracking card**
- Show current deployed version number + build date
- Link to changelog (non-technical summary from Section 3)
- "Last deployed" timestamp
- Compare current vs previous version (what changed)

**B. Historical versions explorer**
- List of past releases with dates and who deployed them
- Click a version to see its changelog and affected components
- Rollback option (admin-only, with confirmation)

**C. System events audit browser**
- Browse `audit_events` table (already exists, populated by DB triggers)
- Filter by entity type (document, user, aircraft, etc.), action (created/updated/deleted), actor, date range
- Click an event to see before/after values
- Export to CSV

**D. Interactive workflow cards (replacing static metrics)**
- Document versions: count + trend sparkline + "View recent versions" link
- Backup history: success/failure status + "Run backup" + "Restore point" links
- Scanner health: reachable/unreachable + "Test scanner" + "View scan log"
- User invitations: pending/expired + "Resend" + "Revoke" links per invite

**E. Real-time refresh control**
- Replace fixed 15s refetch with user-toggleable auto-refresh (pause/resume)
- Manual "Refresh all" button with loading state

### Proposed UI layout (admin dashboard)

```
┌─────────────────────────────────────────────────────────┐
│ Current version: 2.1.0 · Deployed 2h ago · [View changelog] │
├──────────┬──────────┬──────────┬───────────────────────┤
│ Builds   │ Health   │ Backups  │ System events (24h)   │
│ [▼ list] │ [● ok]   │ [● ok]   │ [52 events] [🔍 browse]│
├──────────┴──────────┴──────────┴───────────────────────┤
│ Recent activity (audit events)                          │
│ [User created] [Document updated] [Aircraft status changed]│
└─────────────────────────────────────────────────────────┘
```

---

## 5. Every User Workspace — Interactive Dashboard Cards Linked to Pages

### Current state

`Dashboard.tsx` shows static metric cards (number + label + context + icon). Cards are **not clickable** — they only display a number. The role-based metric selection is a long `if/else` chain. No drill-through to related pages.

### Proposed improvements

**A. Make every metric card clickable**
Each card links to the most relevant page for that metric:

| Role | Metric | Linked page |
|------|--------|-------------|
| head_operations | Active Missions | `/missions?status=in_progress` |
| head_operations | Crew On Duty | `/duties` |
| head_safety | Open Occurrences | `/occurrences?status=reported` |
| head_safety | Safety Actions Overdue | `/safety-actions?status=overdue` |
| head_quality | Audit Findings Open | `/audit-findings?status=open` |
| head_quality | Quality Audits Due | `/quality-audits?status=planned` |
| head_maintenance | Aircraft in Service | `/roc?status=serviceable` |
| head_maintenance | Maintenance Due | `/maintenance?due=soon` |
| head_training | Personnel Qualified | `/personnel-licenses?status=valid` |
| head_training | Training Due | `/training?expiring=30` |
| dg_coordinator | DG Shipments Active | `/dangerous-goods` |
| head_security | Security Reviews Open | `/security-reviews` |
| head_security | Incidents Reported | `/security-incidents` |
| records_custodian | Documents in Catalogue | `/documents` |
| records_custodian | Distributions Pending | `/distributions?status=pending` |
| independent_auditor | Audit Reports Open | `/audit-reports?status=open` |
| independent_auditor | Findings Unresolved | `/audit-findings?status=open` |

**B. Add mini trend indicators**
Below each metric value, show a tiny sparkline or delta (e.g., "↑ 3 from last week", "↓ 12 overdue") so users see movement at a glance.

**C. Role-based quick-action row**
Below the metric cards, show 2–3 role-specific quick actions as buttons:
- head_operations: "New Mission", "Release Flight"
- head_safety: "Report Occurrence", "Review Hazard"
- head_quality: "New Audit", "Review Findings"
- librarian: "New Document", "Review Proposals"

**D. Replace the long if/else chain**
Move role metrics into a declarative config (e.g., `ROLE_DASHBOARD_CONFIG`) so adding a new role doesn't require editing the Dashboard component:

```ts
const ROLE_DASHBOARD_CONFIG: Record<string, DashboardCardConfig[]> = {
  head_safety: [
    { label: "Open Occurrences", queryKey: ["open-occurrences"], link: "/occurrences?status=reported", icon: AlertTriangle, tone: "amber" },
    ...
  ],
  ...
};
```

**E. Empty/fallback state**
For roles without specific metrics (librarian, system_admin, etc.), show the generic cards (Occurrences, Hazards, Safety Actions, Deadlines) but make them clickable too.

### Proposed UI layout (any dashboard)

```
┌─────────────────────────────────────────────────────────┐
│ Welcome, Eric · Head of Quality                         │
│ [● Data loaded]  [Notifications: 3]  [View Safety KPIs] │
├──────────┬──────────┬──────────┬───────────────────────┤
│ Open     │ Quality  │ [▲ 2]    │ Quick actions:        │
│ Findings │ Audits   │ from last│ [New Audit] [Review   │
│ [12]     │ Due      │ week     │   Findings]           │
│ [▶]      │ [4]      │          │                       │
└──────────┴──────────┴──────────┴───────────────────────┘
│ Upcoming & overdue deadlines (clickable list)          │
└─────────────────────────────────────────────────────────┘
```

---

## Next Steps (after review)

If you approve these proposals, I will implement them in this order:

1. **Risk Assessment / Mission PDF alignment** (highest operational impact)
2. **StatusBar component** (fixes the visual inconsistency)
3. **Dashboard interactivity** (clickable cards + quick actions for all roles)
4. **Admin observability enhancements** (build tracking, audit browser)
5. **SMTP upgrade notifications** (version tracking + plain-English emails)

Which would you like me to start with?