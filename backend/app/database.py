"""SQLite database schema and connection management for Aviation DMS."""
import aiosqlite
import os
import uuid
from datetime import datetime

DB_PATH = os.getenv("DMS_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "dms.db"))

SCHEMA = """
-- Users
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    password_hash TEXT,
    merged_into_user_id TEXT,
    onboarding_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- User roles (multi-role support)
CREATE TABLE IF NOT EXISTS user_roles (
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (user_id, role),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Stable aliases preserve historical actor IDs after verified account consolidation.
CREATE TABLE IF NOT EXISTS user_id_aliases (
    legacy_user_id TEXT PRIMARY KEY,
    canonical_user_id TEXT NOT NULL,
    merged_at TEXT NOT NULL,
    FOREIGN KEY (canonical_user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_user_id_aliases_canonical ON user_id_aliases(canonical_user_id);

-- Opaque, revocable browser sessions and one-time password setup tokens
CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    active_role TEXT,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at);

CREATE TABLE IF NOT EXISTS auth_setup_tokens (
    setup_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    invite_code TEXT,
    purpose TEXT NOT NULL DEFAULT 'setup',
    issued_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_auth_setup_user ON auth_setup_tokens(user_id);

CREATE TABLE IF NOT EXISTS auth_login_attempts (
    attempt_key TEXT PRIMARY KEY,
    failure_count INTEGER NOT NULL DEFAULT 0,
    window_started_at TEXT NOT NULL,
    locked_until TEXT
);

-- Documents
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    doc_class TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'S2',
    status TEXT NOT NULL DEFAULT 'draft',
    owner_id TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    current_version_id TEXT,
    kcaa_approval_required INTEGER NOT NULL DEFAULT 0,
    review_due_date TEXT,
    source_pdf_filename TEXT,
    source_sha256 TEXT,
    source_issue_revision TEXT,
    source_issued_date TEXT,
    approval_evidence_status TEXT,
    parent_document_id TEXT,
    parent_section_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- Document versions
CREATE TABLE IF NOT EXISTS document_versions (
    version_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_number TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft',
    content TEXT,
    change_summary TEXT,
    approved_by TEXT,
    approved_at TEXT,
    kcaa_approved INTEGER NOT NULL DEFAULT 0,
    kcaa_approved_by TEXT,
    kcaa_approved_at TEXT,
    published_at TEXT,
    kcaa_reference TEXT,
    kcaa_evidence_sha256 TEXT,
    kcaa_evidence_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS kcaa_approval_evidence (
    evidence_id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    reference TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_sha256 TEXT NOT NULL CHECK (length(file_sha256) = 64),
    file_size INTEGER NOT NULL CHECK (file_size > 0),
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'verified')),
    verified_by TEXT,
    verified_at TEXT,
    FOREIGN KEY (version_id) REFERENCES document_versions(version_id)
);
CREATE INDEX IF NOT EXISTS idx_kcaa_evidence_version ON kcaa_approval_evidence(version_id, status);

-- Change requests
CREATE TABLE IF NOT EXISTS change_requests (
    cr_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    change_type TEXT NOT NULL DEFAULT 'minor',
    status TEXT NOT NULL DEFAULT 'open',
    requester_id TEXT NOT NULL,
    reviewer_id TEXT,
    approver_id TEXT,
    reviewed_at TEXT,
    approved_at TEXT,
    rejected_at TEXT,
    rejection_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

-- Review comments
CREATE TABLE IF NOT EXISTS review_comments (
    comment_id TEXT PRIMARY KEY,
    cr_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (cr_id) REFERENCES change_requests(cr_id)
);

-- Distributions
CREATE TABLE IF NOT EXISTS distributions (
    distribution_id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'email',
    status TEXT NOT NULL DEFAULT 'pending',
    sent_at TEXT,
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (version_id) REFERENCES document_versions(version_id)
);

-- Retention rules
CREATE TABLE IF NOT EXISTS retention_rules (
    rule_id TEXT PRIMARY KEY,
    record_class TEXT NOT NULL,
    description TEXT,
    statutory_years INTEGER,
    kfl_policy_years INTEGER,
    trigger_event TEXT,
    disposal_method TEXT,
    classification TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- Legal holds
CREATE TABLE IF NOT EXISTS legal_holds (
    hold_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    imposed_by TEXT NOT NULL,
    imposed_at TEXT NOT NULL,
    released_by TEXT,
    released_at TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Audit events
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    details TEXT,
    timestamp TEXT NOT NULL
);

-- Compliance obligations
CREATE TABLE IF NOT EXISTS compliance_obligations (
    obligation_id TEXT PRIMARY KEY,
    reference TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    source TEXT,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    owner_id TEXT,
    evidence TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- Regulatory references
CREATE TABLE IF NOT EXISTS regulatory_references (
    ref_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    section TEXT,
    description TEXT,
    url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Occurrences (P1 Safety)
CREATE TABLE IF NOT EXISTS occurrences (
    occurrence_id TEXT PRIMARY KEY,
    serial_number TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    occurrence_type TEXT NOT NULL DEFAULT 'incident',
    severity TEXT NOT NULL DEFAULT 'minor',
    status TEXT NOT NULL DEFAULT 'reported',
    reporter_id TEXT,
    reporter_confidential INTEGER NOT NULL DEFAULT 0,
    location TEXT,
    occurred_at TEXT,
    reported_at TEXT NOT NULL,
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    mor_required INTEGER NOT NULL DEFAULT 0,
    mor_deadline TEXT,
    mor_submitted_at TEXT,
    mor_assessed_by TEXT,
    mor_assessed_at TEXT,
    mor_assessment_reason TEXT,
    followup_notes TEXT,
    effectiveness_confirmed INTEGER NOT NULL DEFAULT 0,
    no_new_hazards INTEGER NOT NULL DEFAULT 0,
    closed_by TEXT,
    closed_at TEXT,
    investigation_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- Hazards
CREATE TABLE IF NOT EXISTS hazards (
    hazard_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'operational',
    status TEXT NOT NULL DEFAULT 'identified',
    risk_level TEXT NOT NULL DEFAULT 'medium',
    likelihood TEXT,
    severity TEXT,
    mitigation TEXT,
    owner_id TEXT,
    identified_by TEXT,
    identified_at TEXT NOT NULL,
    reviewed_at TEXT,
    closed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Risk assessments
CREATE TABLE IF NOT EXISTS risk_assessments (
    assessment_id TEXT PRIMARY KEY,
    hazard_id TEXT,
    occurrence_id TEXT,
    mission_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    likelihood TEXT NOT NULL DEFAULT 'possible',
    severity TEXT NOT NULL DEFAULT 'minor',
    risk_level TEXT NOT NULL DEFAULT 'medium',
    risk_model TEXT NOT NULL DEFAULT 'sms_5x5',
    exposure TEXT,
    risk_score INTEGER,
    scrutiny_required INTEGER NOT NULL DEFAULT 0,
    flight_cancelled INTEGER NOT NULL DEFAULT 0,
    mitigation_measures TEXT,
    residual_risk TEXT,
    assessor_id TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Many-to-many link between risk assessments and hazards (supports multiple hazards per assessment)
CREATE TABLE IF NOT EXISTS risk_assessment_hazards (
    assessment_id TEXT NOT NULL,
    hazard_id TEXT NOT NULL,
    PRIMARY KEY (assessment_id, hazard_id),
    FOREIGN KEY (assessment_id) REFERENCES risk_assessments(assessment_id),
    FOREIGN KEY (hazard_id) REFERENCES hazards(hazard_id)
);
CREATE INDEX IF NOT EXISTS idx_risk_assessment_hazards_assessment ON risk_assessment_hazards(assessment_id);
CREATE INDEX IF NOT EXISTS idx_risk_assessment_hazards_hazard ON risk_assessment_hazards(hazard_id);

-- Investigations
CREATE TABLE IF NOT EXISTS investigations (
    investigation_id TEXT PRIMARY KEY,
    occurrence_id TEXT NOT NULL,
    investigator_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    findings TEXT,
    root_cause TEXT,
    recommendations TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Audit engagements (external/internal audits, e.g. SS-KFL-SEP 2026)
CREATE TABLE IF NOT EXISTS audit_reports (
    audit_id TEXT PRIMARY KEY,
    audit_number TEXT UNIQUE NOT NULL,
    audit_date TEXT NOT NULL,
    auditor_id TEXT NOT NULL,
    auditee_id TEXT NOT NULL,
    scope TEXT,
    regulatory_basis TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    evidence_file TEXT,
    evidence_sha256 TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (auditor_id) REFERENCES users(user_id),
    FOREIGN KEY (auditee_id) REFERENCES users(user_id)
);

-- Individual findings from an audit engagement
CREATE TABLE IF NOT EXISTS audit_findings (
    finding_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    finding_number TEXT NOT NULL,
    area TEXT NOT NULL,
    level INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    regulatory_reference TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    corrective_action_id TEXT,
    due_date TEXT,
    closed_at TEXT,
    closed_by TEXT,
    closure_evidence TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (audit_id) REFERENCES audit_reports(audit_id),
    FOREIGN KEY (corrective_action_id) REFERENCES corrective_actions(car_id)
);
CREATE INDEX IF NOT EXISTS idx_audit_findings_audit ON audit_findings(audit_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_status ON audit_findings(status);

-- Historical audit imports remain quarantined until an independent provenance review.
CREATE TABLE IF NOT EXISTS audit_report_imports (
    import_id TEXT PRIMARY KEY,
    audit_number TEXT NOT NULL,
    audit_date TEXT NOT NULL,
    source_auditor_id TEXT NOT NULL,
    source_auditor_name TEXT NOT NULL,
    auditee_id TEXT NOT NULL,
    scope TEXT,
    regulatory_basis TEXT,
    evidence_file TEXT NOT NULL,
    evidence_sha256 TEXT NOT NULL CHECK (length(evidence_sha256) = 64),
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    imported_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_verification'
        CHECK (status IN ('pending_verification', 'imported', 'rejected')),
    verified_by TEXT,
    verified_at TEXT,
    verification_notes TEXT,
    audit_id TEXT UNIQUE,
    FOREIGN KEY (source_auditor_id) REFERENCES users(user_id),
    FOREIGN KEY (auditee_id) REFERENCES users(user_id),
    FOREIGN KEY (imported_by) REFERENCES users(user_id),
    FOREIGN KEY (verified_by) REFERENCES users(user_id),
    FOREIGN KEY (audit_id) REFERENCES audit_reports(audit_id)
);
CREATE INDEX IF NOT EXISTS idx_audit_report_imports_status_created
    ON audit_report_imports(status, created_at DESC, import_id ASC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_report_imports_active_number
    ON audit_report_imports(audit_number) WHERE status IN ('pending_verification', 'imported');

-- Safety actions
CREATE TABLE IF NOT EXISTS safety_actions (
    action_id TEXT PRIMARY KEY,
    occurrence_id TEXT,
    hazard_id TEXT,
    investigation_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    action_type TEXT NOT NULL DEFAULT 'corrective',
    owner_id TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    evidence TEXT,
    verified_by TEXT,
    verified_at TEXT,
    effectiveness_check TEXT,
    closed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Safety reports
CREATE TABLE IF NOT EXISTS safety_reports (
    report_id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    period_start TEXT,
    period_end TEXT,
    generated_by TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
);

-- ROC Register
CREATE TABLE IF NOT EXISTS roc_register (
    roc_id TEXT PRIMARY KEY,
    roc_number TEXT NOT NULL,
    serial_number TEXT,
    kcaa_reference TEXT,
    issue_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    categories TEXT,
    bvlos_authorized INTEGER NOT NULL DEFAULT 0,
    night_authorized INTEGER NOT NULL DEFAULT 0,
    max_altitude_agl INTEGER,
    evlos_authorized INTEGER NOT NULL DEFAULT 0,
    dg_category TEXT,
    authorized_registrations TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- Aircraft / UAS Fleet
CREATE TABLE IF NOT EXISTS aircraft (
    aircraft_id TEXT PRIMARY KEY,
    registration TEXT NOT NULL UNIQUE,
    model TEXT NOT NULL,
    manufacturer TEXT,
    serial_number TEXT,
    roc_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    category TEXT,
    weight_class TEXT,
    max_takeoff_weight_kg REAL,
    acquired_date TEXT,
    opspec_authorized INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (roc_id) REFERENCES roc_register(roc_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_class ON documents(doc_class);
CREATE INDEX IF NOT EXISTS idx_versions_document ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_cr_document ON change_requests(document_id);
CREATE INDEX IF NOT EXISTS idx_cr_status ON change_requests(status);
CREATE INDEX IF NOT EXISTS idx_distributions_version ON distributions(version_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_occurrences_status ON occurrences(status);
CREATE INDEX IF NOT EXISTS idx_occurrences_type ON occurrences(occurrence_type);
CREATE INDEX IF NOT EXISTS idx_hazards_status ON hazards(status);
CREATE INDEX IF NOT EXISTS idx_safety_actions_status ON safety_actions(status);
CREATE INDEX IF NOT EXISTS idx_aircraft_registration ON aircraft(registration);
CREATE INDEX IF NOT EXISTS idx_aircraft_roc ON aircraft(roc_id);
-- Missions (P1 Phase 3 - Mission Workflow)
CREATE TABLE IF NOT EXISTS missions (
    mission_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    mission_type TEXT NOT NULL DEFAULT 'survey',
    status TEXT NOT NULL DEFAULT 'planned',
    priority TEXT NOT NULL DEFAULT 'normal',
    planned_date TEXT,
    location TEXT,
    aircraft_id TEXT,
    roc_id TEXT,
    rpas_pilot_id TEXT,
    visual_observer_id TEXT,
    dg_category TEXT,
    max_altitude_agl INTEGER,
    bvlos_required INTEGER NOT NULL DEFAULT 0,
    night_required INTEGER NOT NULL DEFAULT 0,
    risk_assessment_id TEXT,
    flight_plan_id TEXT,
    release_id TEXT,
    post_flight_report_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (aircraft_id) REFERENCES aircraft(aircraft_id),
    FOREIGN KEY (roc_id) REFERENCES roc_register(roc_id)
);

-- Flight Plans
CREATE TABLE IF NOT EXISTS flight_plans (
    plan_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    route_description TEXT,
    waypoints TEXT,
    max_altitude_agl INTEGER,
    estimated_duration_min INTEGER,
    fuel_battery_plan TEXT,
    weather_minima TEXT,
    contingency_plan TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(mission_id)
);

-- Flight Releases
CREATE TABLE IF NOT EXISTS flight_releases (
    release_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    released_by TEXT NOT NULL,
    released_at TEXT NOT NULL,
    pre_flight_checklist TEXT,
    weather_confirmed INTEGER NOT NULL DEFAULT 0,
    crew_confirmed INTEGER NOT NULL DEFAULT 0,
    aircraft_confirmed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'released',
    notes TEXT,
    created_at TEXT NOT NULL
);

-- Post-Flight Reports
CREATE TABLE IF NOT EXISTS post_flight_reports (
    report_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    actual_duration_min INTEGER,
    actual_max_altitude INTEGER,
    incidents TEXT,
    anomalies TEXT,
    battery_cycles INTEGER,
    flight_hours REAL,
    data_collected TEXT,
    submitted_by TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    status TEXT NOT NULL DEFAULT 'submitted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_missions_date ON missions(planned_date);
CREATE INDEX IF NOT EXISTS idx_flight_plans_mission ON flight_plans(mission_id);
CREATE INDEX IF NOT EXISTS idx_flight_releases_mission ON flight_releases(mission_id);
-- Quality Audits (P1 Phase 4)
CREATE TABLE IF NOT EXISTS quality_audits (
    audit_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    audit_type TEXT NOT NULL DEFAULT 'internal',
    scope TEXT,
    auditor_id TEXT NOT NULL,
    auditee_id TEXT,
    planned_date TEXT,
    actual_date TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    findings_count INTEGER NOT NULL DEFAULT 0,
    overall_result TEXT,
    report TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- Findings from the internal quality-audit programme (P1)
CREATE TABLE IF NOT EXISTS quality_audit_findings (
    finding_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    finding_type TEXT NOT NULL DEFAULT 'observation',
    description TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'minor',
    root_cause TEXT,
    evidence TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system',
    updated_by TEXT NOT NULL DEFAULT 'system',
    FOREIGN KEY (audit_id) REFERENCES quality_audits(audit_id)
);

-- Corrective Action Requests (CARs)
CREATE TABLE IF NOT EXISTS corrective_actions (
    car_id TEXT PRIMARY KEY,
    finding_id TEXT,
    audit_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    finding_level TEXT NOT NULL DEFAULT 'level_2',
    root_cause TEXT,
    corrective_action TEXT,
    preventive_action TEXT,
    owner_id TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    verification TEXT,
    verified_by TEXT,
    verified_at TEXT,
    closed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (finding_id) REFERENCES quality_audit_findings(finding_id),
    FOREIGN KEY (audit_id) REFERENCES quality_audits(audit_id)
);

CREATE INDEX IF NOT EXISTS idx_audits_status ON quality_audits(status);
CREATE INDEX IF NOT EXISTS idx_quality_findings_audit ON quality_audit_findings(audit_id);
CREATE INDEX IF NOT EXISTS idx_cars_status ON corrective_actions(status);
-- Dangerous Goods (P1 Phase 5)
CREATE TABLE IF NOT EXISTS dg_shipments (
    shipment_id TEXT PRIMARY KEY,
    dg_class TEXT NOT NULL,
    un_number TEXT,
    proper_shipping_name TEXT NOT NULL,
    quantity TEXT,
    packaging_type TEXT,
    shipper TEXT,
    consignee TEXT,
    mission_id TEXT,
    aircraft_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    acceptance_check_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(mission_id),
    FOREIGN KEY (aircraft_id) REFERENCES aircraft(aircraft_id)
);

CREATE TABLE IF NOT EXISTS dg_acceptance_checks (
    check_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL,
    checked_by TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    packaging_ok INTEGER NOT NULL DEFAULT 0,
    marking_ok INTEGER NOT NULL DEFAULT 0,
    labeling_ok INTEGER NOT NULL DEFAULT 0,
    documentation_ok INTEGER NOT NULL DEFAULT 0,
    compatibility_ok INTEGER NOT NULL DEFAULT 0,
    triple_packaging_ok INTEGER NOT NULL DEFAULT 1,
    no_leakage_visual_ok INTEGER NOT NULL DEFAULT 1,
    pic_weather_confirmed INTEGER NOT NULL DEFAULT 1,
    crew_layers_unopened_confirmed INTEGER NOT NULL DEFAULT 1,
    weight_within_limit_ok INTEGER NOT NULL DEFAULT 1,
    result TEXT NOT NULL DEFAULT 'pending',
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (shipment_id) REFERENCES dg_shipments(shipment_id)
);

CREATE TABLE IF NOT EXISTS dg_training_records (
    record_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    training_type TEXT NOT NULL,
    training_date TEXT NOT NULL,
    expiry_date TEXT,
    certificate_number TEXT,
    status TEXT NOT NULL DEFAULT 'valid',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dg_shipments_status ON dg_shipments(status);
CREATE INDEX IF NOT EXISTS idx_dg_acceptance_shipment ON dg_acceptance_checks(shipment_id);
-- Security Management (P1 Phase 6)
CREATE TABLE IF NOT EXISTS security_incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    incident_type TEXT NOT NULL DEFAULT 'unauthorized_access',
    severity TEXT NOT NULL DEFAULT 'minor',
    location TEXT,
    reported_by TEXT NOT NULL,
    reported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'reported',
    investigation_notes TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS security_assessments (
    assessment_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    assessment_type TEXT NOT NULL DEFAULT 'vulnerability',
    scope TEXT,
    assessor_id TEXT NOT NULL,
    findings TEXT,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'planned',
    planned_date TEXT,
    completed_date TEXT,
    report TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS security_training (
    training_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    training_type TEXT NOT NULL,
    training_date TEXT NOT NULL,
    expiry_date TEXT,
    certificate_number TEXT,
    status TEXT NOT NULL DEFAULT 'valid',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS training_records (
    record_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    training_category TEXT NOT NULL,
    training_type TEXT NOT NULL,
    training_date TEXT NOT NULL,
    expiry_date TEXT,
    certificate_number TEXT,
    status TEXT NOT NULL DEFAULT 'valid',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_security_incidents_status ON security_incidents(status);
CREATE INDEX IF NOT EXISTS idx_security_incidents_type ON security_incidents(incident_type);
CREATE INDEX IF NOT EXISTS idx_security_assessments_status ON security_assessments(status);
CREATE INDEX IF NOT EXISTS idx_dg_training_person ON dg_training_records(person_id);
CREATE INDEX IF NOT EXISTS idx_training_person ON training_records(person_id);

-- Outsourced Functions (P2 - QMS-06)
CREATE TABLE IF NOT EXISTS outsourced_functions (
    function_id TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    scope TEXT NOT NULL,
    contract_sla TEXT,
    applicable_requirements TEXT,
    assessment_date TEXT,
    audit_evidence TEXT,
    issues TEXT,
    actions TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- Maintenance Management (MAINT-01)
CREATE TABLE IF NOT EXISTS maintenance_records (
    record_id TEXT PRIMARY KEY,
    aircraft_registration TEXT NOT NULL,
    maintenance_type TEXT NOT NULL,
    description TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    performed_at TEXT NOT NULL,
    next_due TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_maintenance_aircraft ON maintenance_records(aircraft_registration);
CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance_records(status);

-- Safety KPIs / Objectives (P2 - SAF-08)
CREATE TABLE IF NOT EXISTS safety_kpis (
    kpi_id TEXT PRIMARY KEY,
    kpi_name TEXT NOT NULL,
    definition TEXT,
    target TEXT,
    period TEXT,
    current_value TEXT,
    evidence_source TEXT,
    trend TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- Security Review Meetings / KPIs (P2 - SEC-06)
CREATE TABLE IF NOT EXISTS security_reviews (
    review_id TEXT PRIMARY KEY,
    meeting_date TEXT NOT NULL,
    attendees TEXT,
    minutes TEXT,
    kpi_measures TEXT,
    audit_findings TEXT,
    inspection_results TEXT,
    corrective_actions TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

-- DG Responsibility Matrix (P2 - DG-12)
CREATE TABLE IF NOT EXISTS dg_responsibility_matrix (
    matrix_id TEXT PRIMARY KEY,
    project_or_route TEXT NOT NULL,
    operation_type TEXT,
    process_stage TEXT NOT NULL,
    responsible_role TEXT NOT NULL,
    escalation_contact TEXT,
    handover_point TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outsourced_status ON outsourced_functions(status);
CREATE INDEX IF NOT EXISTS idx_safety_kpi_status ON safety_kpis(status);
CREATE INDEX IF NOT EXISTS idx_security_review_date ON security_reviews(meeting_date);
CREATE INDEX IF NOT EXISTS idx_dg_matrix_project ON dg_responsibility_matrix(project_or_route);

CREATE TABLE IF NOT EXISTS notification_preferences (
    preference_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    email_enabled INTEGER NOT NULL DEFAULT 1,
    document_review_hours INTEGER NOT NULL DEFAULT 48,
    mor_deadline_hours INTEGER NOT NULL DEFAULT 24,
    car_due_days INTEGER NOT NULL DEFAULT 3,
    roc_expiry_days INTEGER NOT NULL DEFAULT 90,
    distribution_ack_days INTEGER NOT NULL DEFAULT 7,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    priority TEXT DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    sent_at TEXT,
    read_at TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL
);

-- Document proposals (section/line/word/illustration-level change suggestions)
CREATE TABLE IF NOT EXISTS document_proposals (
    proposal_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    change_request_id TEXT,
    change_set_id TEXT,
    proposal_type TEXT NOT NULL DEFAULT 'section',
    target_ref TEXT NOT NULL,
    section_number TEXT,
    section_heading TEXT,
    block_type TEXT,
    block_index INTEGER,
    anchor_id TEXT,
    context_before TEXT,
    context_after TEXT,
    original_text TEXT,
    proposed_text TEXT,
    original_excerpt_html TEXT,
    proposed_excerpt_html TEXT,
    change_fingerprint TEXT,
    change_sequence INTEGER,
    changed_token_count INTEGER,
    change_density REAL,
    grouping_reason TEXT,
    rationale TEXT,
    severity TEXT NOT NULL DEFAULT 'minor',
    status TEXT NOT NULL DEFAULT 'draft',
    proposer_id TEXT NOT NULL,
    reviewer_id TEXT,
    reviewed_at TEXT,
    disposition TEXT,
    applied_at TEXT,
    applied_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id),
    FOREIGN KEY (version_id) REFERENCES document_versions(version_id),
    FOREIGN KEY (change_request_id) REFERENCES change_requests(cr_id)
);

-- Document sections (for section-level targeting and navigation)
CREATE TABLE IF NOT EXISTS document_sections (
    section_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    section_number TEXT,
    heading TEXT NOT NULL,
    content_start_offset INTEGER,
    content_end_offset INTEGER,
    parent_section_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id),
    FOREIGN KEY (version_id) REFERENCES document_versions(version_id)
);

-- Document annotations (comments/highlights on specific locations)
CREATE TABLE IF NOT EXISTS document_annotations (
    annotation_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    annotation_type TEXT NOT NULL DEFAULT 'comment',
    target_ref TEXT NOT NULL,
    selected_text TEXT,
    content TEXT NOT NULL,
    author_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolved_by TEXT,
    resolved_at TEXT,
    parent_annotation_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id),
    FOREIGN KEY (version_id) REFERENCES document_versions(version_id)
);

-- Personnel licenses (crew/role qualifications and credentials)
CREATE TABLE IF NOT EXISTS personnel_licenses (
    license_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    license_type TEXT NOT NULL,
    license_number TEXT,
    issuing_authority TEXT,
    issued_date TEXT,
    expiry_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'valid',
    document_ref TEXT,
    aircraft_type TEXT,
    notes TEXT,
    verified_by TEXT,
    verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (person_id) REFERENCES users(user_id)
);

-- License renewal history
CREATE TABLE IF NOT EXISTS license_renewal_history (
    renewal_id TEXT PRIMARY KEY,
    license_id TEXT NOT NULL,
    previous_expiry TEXT,
    new_expiry TEXT NOT NULL,
    renewal_date TEXT NOT NULL,
    evidence_ref TEXT,
    renewed_by TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (license_id) REFERENCES personnel_licenses(license_id)
);

-- Personnel self-service uploads (credential documents)
CREATE TABLE IF NOT EXISTS personnel_uploads (
    upload_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    license_type TEXT NOT NULL,
    document_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    file_sha256 TEXT,
    content_type TEXT,
    verification_status TEXT NOT NULL DEFAULT 'pending',
    verified_by TEXT,
    verified_at TEXT,
    rejection_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (person_id) REFERENCES users(user_id)
);

-- Aircraft insurance policies
CREATE TABLE IF NOT EXISTS aircraft_insurance (
    insurance_id TEXT PRIMARY KEY,
    aircraft_id TEXT NOT NULL,
    insurance_type TEXT NOT NULL,
    policy_number TEXT,
    insurer TEXT NOT NULL,
    broker TEXT,
    coverage_amount REAL,
    currency TEXT NOT NULL DEFAULT 'USD',
    premium_amount REAL,
    premium_currency TEXT NOT NULL DEFAULT 'USD',
    start_date TEXT,
    expiry_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    document_ref TEXT,
    renewal_status TEXT NOT NULL DEFAULT 'not_started',
    renewal_notes TEXT,
    verified_by TEXT,
    verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (aircraft_id) REFERENCES aircraft(aircraft_id)
);

-- Insurance renewal history
CREATE TABLE IF NOT EXISTS insurance_renewal_history (
    renewal_id TEXT PRIMARY KEY,
    insurance_id TEXT NOT NULL,
    previous_expiry TEXT,
    new_expiry TEXT NOT NULL,
    renewal_date TEXT NOT NULL,
    evidence_ref TEXT,
    renewed_by TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (insurance_id) REFERENCES aircraft_insurance(insurance_id)
);

-- Aircraft documents (CoA, registration, ARC, noise cert, radio license, etc.)
CREATE TABLE IF NOT EXISTS aircraft_documents (
    doc_id TEXT PRIMARY KEY,
    aircraft_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_number TEXT,
    issuing_authority TEXT,
    issue_date TEXT,
    expiry_date TEXT,
    status TEXT NOT NULL DEFAULT 'valid',
    document_ref TEXT,
    notes TEXT,
    verified_by TEXT,
    verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (aircraft_id) REFERENCES aircraft(aircraft_id)
);

-- Indexes for new tables
CREATE INDEX IF NOT EXISTS idx_proposals_document ON document_proposals(document_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON document_proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_proposer ON document_proposals(proposer_id);
CREATE INDEX IF NOT EXISTS idx_annotations_document ON document_annotations(document_id);
CREATE INDEX IF NOT EXISTS idx_annotations_status ON document_annotations(status);
CREATE INDEX IF NOT EXISTS idx_personnel_licenses_person ON personnel_licenses(person_id);
CREATE INDEX IF NOT EXISTS idx_personnel_licenses_expiry ON personnel_licenses(expiry_date);
CREATE INDEX IF NOT EXISTS idx_personnel_licenses_status ON personnel_licenses(status);
CREATE INDEX IF NOT EXISTS idx_personnel_uploads_person_created ON personnel_uploads(person_id, created_at DESC, upload_id ASC);
CREATE INDEX IF NOT EXISTS idx_personnel_uploads_person_status_created ON personnel_uploads(person_id, verification_status, created_at DESC, upload_id ASC);
CREATE INDEX IF NOT EXISTS idx_personnel_uploads_status_created ON personnel_uploads(verification_status, created_at DESC, upload_id ASC);
CREATE INDEX IF NOT EXISTS idx_aircraft_insurance_aircraft ON aircraft_insurance(aircraft_id);
CREATE INDEX IF NOT EXISTS idx_aircraft_insurance_expiry ON aircraft_insurance(expiry_date);
CREATE INDEX IF NOT EXISTS idx_aircraft_insurance_status ON aircraft_insurance(status);
CREATE INDEX IF NOT EXISTS idx_aircraft_documents_aircraft ON aircraft_documents(aircraft_id);
CREATE INDEX IF NOT EXISTS idx_aircraft_documents_expiry ON aircraft_documents(expiry_date);
CREATE INDEX IF NOT EXISTS idx_aircraft_documents_status ON aircraft_documents(status);

CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at);

-- App Settings (configurable FDTL defaults)
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Crew Management
CREATE TABLE IF NOT EXISTS crew_members (
    crew_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    base TEXT NOT NULL DEFAULT 'Nairobi',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_crew_role ON crew_members(role);
CREATE INDEX IF NOT EXISTS idx_crew_status ON crew_members(status);

CREATE TABLE IF NOT EXISTS duty_records (
    duty_id TEXT PRIMARY KEY,
    crew_id TEXT NOT NULL,
    duty_start TEXT NOT NULL,
    duty_end TEXT NOT NULL,
    aircraft_reg TEXT,
    role TEXT NOT NULL,
    location TEXT,
    block_hours REAL,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_duty_crew ON duty_records(crew_id);
CREATE INDEX IF NOT EXISTS idx_duty_start ON duty_records(duty_start);

CREATE TABLE IF NOT EXISTS crew_qualifications (
    qual_id TEXT PRIMARY KEY,
    crew_id TEXT NOT NULL,
    qual_type TEXT NOT NULL,
    rating TEXT,
    issue_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'valid',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qual_crew ON crew_qualifications(crew_id);
CREATE INDEX IF NOT EXISTS idx_qual_expiry ON crew_qualifications(expiry_date);
"""

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


async def _install_mutation_audit_triggers(db: aiosqlite.Connection) -> None:
    """Record persisted table changes atomically without requiring custom SQLite functions."""
    stale_cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'audit_mutation_%'"
    )
    for row in await stale_cursor.fetchall():
        trigger_name = row["name"].replace('"', '""')
        await db.execute(f'DROP TRIGGER IF EXISTS "{trigger_name}"')
    tables_cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('audit_events', 'auth_sessions')"
    )
    table_names = [row["name"] for row in await tables_cursor.fetchall()]
    insert_actor_columns = (
        "created_by", "actor_id", "reported_by", "reporter_id", "assessor_id", "reviewed_by",
        "approved_by", "verified_by", "closed_by", "submitted_by", "resolved_by", "acknowledged_by",
        "identified_by", "imposed_by", "released_by", "uploaded_by", "requested_by", "assigned_by",
        "published_by", "accepted_by",
    )
    for table_name in table_names:
        escaped_table = table_name.replace('"', '""')
        info_cursor = await db.execute(f'PRAGMA table_info("{escaped_table}")')
        columns = await info_cursor.fetchall()
        column_names = {row["name"] for row in columns}
        primary_keys = sorted((row for row in columns if row["pk"]), key=lambda row: row["pk"])
        if not primary_keys:
            continue
        if len(primary_keys) == 1:
            key_expr = f'CAST(NEW."{primary_keys[0]["name"]}" AS TEXT)'
            old_key_expr = f'CAST(OLD."{primary_keys[0]["name"]}" AS TEXT)'
        else:
            key_expr = " || ':' || ".join(f'CAST(NEW."{row["name"]}" AS TEXT)' for row in primary_keys)
            old_key_expr = " || ':' || ".join(f'CAST(OLD."{row["name"]}" AS TEXT)' for row in primary_keys)
        available_insert_actors = [column for column in insert_actor_columns if column in column_names]
        new_actor = "COALESCE(" + ", ".join(f'NEW."{column}"' for column in available_insert_actors) + ", 'system')" if available_insert_actors else "'system'"
        updated_actor_column = "updated_by" if "updated_by" in column_names else ("actor_id" if "actor_id" in column_names else None)
        update_actor = f'COALESCE(NEW."{updated_actor_column}", \'system\')' if updated_actor_column else "'system'"
        deleted_actor_column = "deleted_by" if "deleted_by" in column_names else None
        old_actor = f'COALESCE(OLD."{deleted_actor_column}", \'system\')' if deleted_actor_column else "'system'"
        escaped_name = table_name.replace('"', '""')
        for operation, action in (("INSERT", "row_inserted"), ("UPDATE", "row_updated"), ("DELETE", "row_deleted")):
            trigger_name = f"audit_mutation_{table_name}_{operation.lower()}".replace('"', '""')
            entity_key_expr = old_key_expr if operation == "DELETE" else key_expr
            actor_expr = old_actor if operation == "DELETE" else (update_actor if operation == "UPDATE" else new_actor)
            sql = f'''CREATE TRIGGER IF NOT EXISTS "{trigger_name}"
                AFTER {operation} ON "{escaped_name}"
                BEGIN
                    INSERT INTO audit_events
                        (event_id, entity_type, entity_id, action, actor_id, details, timestamp)
                    VALUES
                        ('EVT-DB-' || lower(hex(randomblob(12))),
                         '{table_name.replace("'", "''")}',
                         {entity_key_expr},
                         '{action}',
                         {actor_expr},
                         '{{"source":"database_trigger","operation":"{operation.lower()}"}}',
                         strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
                END'''
            await db.execute(sql)


async def remove_shared_seed_passwords():
    """Invalidate identical shared seed hashes from older installations once."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM app_settings WHERE key = 'auth_shared_seed_hash_migration'")
        if await cursor.fetchone():
            return
        cursor = await db.execute(
            """SELECT password_hash FROM users
               WHERE password_hash IS NOT NULL
               GROUP BY password_hash HAVING COUNT(*) > 1"""
        )
        shared_hashes = [row["password_hash"] for row in await cursor.fetchall()]
        for shared_hash in shared_hashes:
            await db.execute("UPDATE users SET password_hash = NULL, updated_at = ? WHERE password_hash = ?", (datetime.now().isoformat(), shared_hash))
        await db.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("auth_shared_seed_hash_migration", "complete", datetime.now().isoformat()),
        )
        await db.commit()
    finally:
        await db.close()


# V1 identity groups are retained so existing databases and fresh seeds reach the
# same pre-v2 state before the owner-approved canonical-ID migration runs.
V1_VERIFIED_IDENTITY_GROUPS = {
    "u-admin": ("u-admin", "u-maintenance"),
    "u-lib": ("u-lib", "u-quality", "u-records"),
    "u-safety": ("u-safety", "u-security"),
    "u-ops": ("u-ops", "u-chief-pilot", "u-training"),
    "u-flight-ops": ("u-flight-ops", "u-dg"),
}


async def migrate_verified_identity_groups():
    """Merge owner-verified seeded accounts without rewriting historical actor references."""
    db = await get_db()
    now = datetime.now().isoformat()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute("SELECT value FROM app_settings WHERE key = 'auth_canonical_identity_migration'")
        if await cursor.fetchone():
            await db.rollback()
            return

        cursor = await db.execute("SELECT user_id, username, role, is_active FROM users")
        all_users = [dict(row) for row in await cursor.fetchall()]
        for user in all_users:
            await db.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", (user["user_id"], user["role"]))
            for historical_id in {user["user_id"], user["username"]}:
                alias_cursor = await db.execute(
                    "SELECT canonical_user_id FROM user_id_aliases WHERE legacy_user_id = ?", (historical_id,)
                )
                existing_alias = await alias_cursor.fetchone()
                if existing_alias and existing_alias["canonical_user_id"] not in (historical_id, user["user_id"]):
                    raise RuntimeError(f"Historical identity {historical_id} maps to multiple accounts")
                await db.execute(
                    "INSERT INTO user_id_aliases (legacy_user_id, canonical_user_id, merged_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(legacy_user_id) DO UPDATE SET canonical_user_id = excluded.canonical_user_id",
                    (historical_id, user["user_id"], now),
                )

        for canonical_id, member_ids in V1_VERIFIED_IDENTITY_GROUPS.items():
            placeholders = ",".join("?" for _ in member_ids)
            cursor = await db.execute(f"SELECT * FROM users WHERE user_id IN ({placeholders})", member_ids)
            members = [dict(row) for row in await cursor.fetchall()]
            if not members:
                continue
            canonical = next((member for member in members if member["user_id"] == canonical_id), None)
            if canonical is None:
                raise RuntimeError(f"Cannot consolidate verified identity group; canonical account {canonical_id} is missing")
            if not canonical["is_active"] and any(member["is_active"] for member in members if member["user_id"] != canonical_id):
                raise RuntimeError(f"Cannot consolidate verified identity group into inactive account {canonical_id}")

            hashes = {member["password_hash"] for member in members if member["password_hash"]}
            if len(hashes) > 1:
                raise RuntimeError(f"Cannot consolidate {canonical_id}: member accounts have different passwords; resolve credentials first")
            password_hash = next(iter(hashes), None)

            cursor = await db.execute(f"SELECT user_id, role FROM user_roles WHERE user_id IN ({placeholders})", member_ids)
            roles = {row["role"] for row in await cursor.fetchall()}
            roles.update(member["role"] for member in members)
            if not roles:
                raise RuntimeError(f"Cannot consolidate {canonical_id}: no authorized role assignments exist")

            existing_roles = await db.execute_fetchall(
                "SELECT role FROM user_roles WHERE user_id = ?", (canonical_id,)
            )
            if canonical["role"] not in {row["role"] for row in existing_roles}:
                await db.execute("UPDATE users SET role = ? WHERE user_id = ?", (sorted(roles)[0], canonical_id))
            await db.execute(
                "UPDATE users SET password_hash = COALESCE(password_hash, ?), updated_at = ? WHERE user_id = ?",
                (password_hash, now, canonical_id),
            )
            for role in roles:
                await db.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", (canonical_id, role))

            for member in members:
                legacy_id = member["user_id"]
                for historical_id in {legacy_id, member["username"]}:
                    alias_cursor = await db.execute(
                        "SELECT canonical_user_id FROM user_id_aliases WHERE legacy_user_id = ?", (historical_id,)
                    )
                    existing_alias = await alias_cursor.fetchone()
                    if existing_alias and existing_alias["canonical_user_id"] not in (historical_id, legacy_id, canonical_id):
                        raise RuntimeError(f"Identity alias {historical_id} is already assigned to another canonical user")
                    await db.execute(
                        "INSERT INTO user_id_aliases (legacy_user_id, canonical_user_id, merged_at) VALUES (?, ?, ?) "
                        "ON CONFLICT(legacy_user_id) DO UPDATE SET canonical_user_id = excluded.canonical_user_id",
                        (historical_id, canonical_id, now),
                    )
                if legacy_id != canonical_id:
                    await db.execute(
                        "UPDATE users SET is_active = 0, merged_into_user_id = ?, updated_at = ? WHERE user_id = ?",
                        (canonical_id, now, legacy_id),
                    )
                    await db.execute(
                        "UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE user_id = ?",
                        (now, legacy_id),
                    )
                    await db.execute(
                        "UPDATE auth_setup_tokens SET used_at = COALESCE(used_at, ?) WHERE user_id = ?",
                        (now, legacy_id),
                    )

        await db.execute(
            "UPDATE auth_sessions SET active_role = (SELECT role FROM users WHERE users.user_id = auth_sessions.user_id) "
            "WHERE active_role IS NULL AND revoked_at IS NULL"
        )
        await db.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES ('auth_canonical_identity_migration', 'complete', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = 'complete', updated_at = excluded.updated_at",
            (now,),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()




async def _user_foreign_key_columns(db):
    tables = await db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    result = []
    for row in tables:
        table_name = row["name"]
        foreign_keys = await db.execute_fetchall(f'PRAGMA foreign_key_list("{table_name}")')
        for foreign_key in foreign_keys:
            if foreign_key["table"] == "users":
                result.append((table_name, foreign_key["from"]))
    return result


async def _remap_user_foreign_keys(db, source_ids, canonical_id):
    # Auth/session and role tables are handled explicitly. Business foreign keys
    # point to the same verified person and follow the new canonical ID.
    excluded_tables = {"user_roles", "user_id_aliases", "auth_sessions", "auth_setup_tokens"}
    for table_name, column_name in await _user_foreign_key_columns(db):
        if table_name in excluded_tables:
            continue
        quoted_table = '"' + table_name.replace('"', '""') + '"'
        quoted_column = '"' + column_name.replace('"', '""') + '"'
        for source_id in source_ids:
            await db.execute(
                f"UPDATE {quoted_table} SET {quoted_column} = ? WHERE {quoted_column} = ?",
                (canonical_id, source_id),
            )


async def _ensure_canonical_aliases(db, alias_ids, canonical_id, allowed_targets, now):
    for alias_id in alias_ids:
        cursor = await db.execute(
            "SELECT canonical_user_id FROM user_id_aliases WHERE legacy_user_id = ?",
            (alias_id,),
        )
        existing = await cursor.fetchone()
        if existing and existing["canonical_user_id"] not in allowed_targets:
            raise RuntimeError(f"Identity alias {alias_id} already belongs to another canonical account")
        if existing:
            await db.execute(
                "UPDATE user_id_aliases SET canonical_user_id = ? WHERE legacy_user_id = ?",
                (canonical_id, alias_id),
            )
        else:
            await db.execute(
                "INSERT INTO user_id_aliases (legacy_user_id, canonical_user_id, merged_at) VALUES (?, ?, ?)",
                (alias_id, canonical_id, now),
            )


async def _promote_quality_canonical_account(db, now):
    member_ids = ("u-lib", "u-quality", "u-records")
    placeholders = ",".join("?" for _ in member_ids)
    rows = await db.execute_fetchall(
        f"SELECT * FROM users WHERE user_id IN ({placeholders})", member_ids
    )
    users = {row["user_id"]: dict(row) for row in rows}
    source = users.get("u-lib")
    canonical = users.get("u-quality")
    if not source or not canonical:
        raise RuntimeError("Cannot promote u-quality: both the prior canonical and target account must exist")
    if source["merged_into_user_id"] is not None or canonical["merged_into_user_id"] != "u-lib":
        raise RuntimeError("Cannot promote u-quality: account rows are not in the expected v1 state")
    if canonical["is_active"]:
        raise RuntimeError("Cannot promote u-quality: merged target account is unexpectedly active")

    password_hashes = {user["password_hash"] for user in users.values() if user.get("password_hash")}
    if len(password_hashes) > 1:
        raise RuntimeError("Cannot promote u-quality: account password hashes conflict")
    assigned_roles = {user["role"] for user in users.values()}
    role_rows = await db.execute_fetchall(
        f"SELECT role FROM user_roles WHERE user_id IN ({placeholders})", member_ids
    )
    assigned_roles.update(row["role"] for row in role_rows)
    expected_roles = {"head_quality", "librarian", "records_custodian"}
    if assigned_roles != expected_roles:
        raise RuntimeError("Cannot promote u-quality: assigned roles differ from the approved role set")
    if source["full_name"] != canonical["full_name"] or source["department"] != canonical["department"]:
        raise RuntimeError("Cannot promote u-quality: merged account profile fields conflict")

    # Keep login identifiers from the pre-v2 canonical account. Transfer the
    # former target identifiers to the inactive legacy row within this transaction.
    source_username, source_email = source["username"], source["email"]
    target_username, target_email = canonical["username"], canonical["email"]
    if source_username != target_username:
        temporary_username = f"__canonical_v2_{uuid.uuid4().hex}"
        await db.execute("UPDATE users SET username = ? WHERE user_id = 'u-quality'", (temporary_username,))
        await db.execute("UPDATE users SET username = ? WHERE user_id = 'u-lib'", (target_username,))
        await db.execute("UPDATE users SET username = ? WHERE user_id = 'u-quality'", (source_username,))
    if source_email != target_email:
        temporary_email = f"canonical-v2-{uuid.uuid4().hex}@invalid.invalid"
        await db.execute("UPDATE users SET email = ? WHERE user_id = 'u-quality'", (temporary_email,))
        await db.execute("UPDATE users SET email = ? WHERE user_id = 'u-lib'", (target_email,))
        await db.execute("UPDATE users SET email = ? WHERE user_id = 'u-quality'", (source_email,))

    password_hash = next(iter(password_hashes), None)
    await db.execute(
        """UPDATE users SET role = 'head_quality', is_active = ?, password_hash = ?,
                  onboarding_completed = ?, merged_into_user_id = NULL, updated_at = ?
           WHERE user_id = 'u-quality'""",
        (source["is_active"], password_hash, source["onboarding_completed"], now),
    )
    await db.execute(
        "UPDATE users SET is_active = 0, password_hash = NULL, merged_into_user_id = 'u-quality', updated_at = ? WHERE user_id = 'u-lib'",
        (now,),
    )
    await db.execute(
        "UPDATE users SET is_active = 0, password_hash = NULL, merged_into_user_id = 'u-quality', updated_at = ? WHERE user_id = 'u-records'",
        (now,),
    )
    await db.execute("DELETE FROM user_roles WHERE user_id = 'u-quality'")
    for role in sorted(expected_roles):
        await db.execute("INSERT INTO user_roles (user_id, role) VALUES ('u-quality', ?)", (role,))

    await _ensure_canonical_aliases(
        db,
        ("u-lib", "librarian", "u-quality", "quality", "u-records", "records_custodian"),
        "u-quality",
        {"u-lib", "u-quality"},
        now,
    )
    await _remap_user_foreign_keys(db, ("u-lib", "u-records"), "u-quality")
    await db.execute(
        "UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE user_id IN ('u-lib', 'u-quality', 'u-records')",
        (now,),
    )
    await db.execute(
        "UPDATE auth_setup_tokens SET used_at = COALESCE(used_at, ?) WHERE user_id IN ('u-lib', 'u-quality', 'u-records')",
        (now,),
    )


async def _promote_safety_security_canonical_account(db, now):
    old_id = "u-safety"
    canonical_id = "u-safety/security"
    cursor = await db.execute("SELECT * FROM users WHERE user_id IN (?, ?)", (old_id, "u-security"))
    users = {row["user_id"]: dict(row) for row in await cursor.fetchall()}
    canonical = users.get(old_id)
    security_alias = users.get("u-security")
    if not canonical:
        raise RuntimeError("Cannot promote u-safety/security: prior canonical account is missing")
    if await (await db.execute("SELECT 1 FROM users WHERE user_id = ?", (canonical_id,))).fetchone():
        raise RuntimeError("Cannot promote u-safety/security: target ID already exists")
    if security_alias and (security_alias["merged_into_user_id"] != old_id or security_alias["is_active"]):
        raise RuntimeError("Cannot promote u-safety/security: security alias is not in the expected v1 state")

    password_hashes = {user["password_hash"] for user in users.values() if user.get("password_hash")}
    if len(password_hashes) > 1:
        raise RuntimeError("Cannot promote u-safety/security: account password hashes conflict")
    assigned_roles = {user["role"] for user in users.values()}
    role_rows = await db.execute_fetchall(
        "SELECT role FROM user_roles WHERE user_id IN ('u-safety', 'u-security')"
    )
    assigned_roles.update(row["role"] for row in role_rows)
    expected_roles = {"head_safety", "head_security"}
    if assigned_roles != expected_roles:
        raise RuntimeError("Cannot promote u-safety/security: assigned roles differ from the approved role set")

    await _ensure_canonical_aliases(
        db,
        (canonical_id, "u-safety", "safety", "u-security", "security"),
        canonical_id,
        {old_id, canonical_id},
        now,
    )
    await _remap_user_foreign_keys(db, (old_id, "u-security"), canonical_id)
    await db.execute("UPDATE user_roles SET user_id = ? WHERE user_id = ?", (canonical_id, old_id))
    await db.execute(
        "UPDATE auth_sessions SET user_id = ?, revoked_at = COALESCE(revoked_at, ?) WHERE user_id = ?",
        (canonical_id, now, old_id),
    )
    await db.execute(
        "UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE user_id = 'u-security'",
        (now,),
    )
    await db.execute(
        "UPDATE auth_setup_tokens SET user_id = ?, used_at = COALESCE(used_at, ?) WHERE user_id = ?",
        (canonical_id, now, old_id),
    )
    await db.execute(
        "UPDATE auth_setup_tokens SET used_at = COALESCE(used_at, ?) WHERE user_id = 'u-security'",
        (now,),
    )
    await db.execute("UPDATE users SET user_id = ?, role = 'head_safety', updated_at = ? WHERE user_id = ?", (canonical_id, now, old_id))
    await db.execute(
        "UPDATE users SET is_active = 0, merged_into_user_id = ?, password_hash = NULL, updated_at = ? WHERE user_id = 'u-security'",
        (canonical_id, now),
    )


async def migrate_canonical_account_ids_v2():
    """Promote the owner-approved quality and safety canonical IDs transactionally."""
    db = await get_db()
    now = datetime.now().isoformat()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute("SELECT value FROM app_settings WHERE key = 'canonical_account_ids_migration_v2'")
        if await cursor.fetchone():
            await db.rollback()
            return
        present_accounts = await db.execute_fetchall(
            "SELECT user_id FROM users WHERE user_id IN ('u-lib', 'u-quality', 'u-records', 'u-safety', 'u-security')"
        )
        if not present_accounts:
            await db.rollback()
            return
        await db.execute("PRAGMA defer_foreign_keys = ON")
        await _promote_quality_canonical_account(db, now)
        await _promote_safety_security_canonical_account(db, now)
        await db.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES ('canonical_account_ids_migration_v2', 'complete', ?)",
            (now,),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


async def _table_columns(db, table_name):
    rows = await (await db.execute(f"PRAGMA table_info({table_name})")).fetchall()
    return {row["name"] for row in rows}


async def _audit_parent_exists(db, table, audit_id):
    cursor = await db.execute(f"SELECT 1 FROM {table} WHERE audit_id = ?", (audit_id,))
    return await cursor.fetchone() is not None


async def _create_external_audit_findings(db):
    await db.execute(
        """CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY,
            audit_id TEXT NOT NULL,
            finding_number TEXT NOT NULL,
            area TEXT NOT NULL,
            level INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            regulatory_reference TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            corrective_action_id TEXT,
            due_date TEXT,
            closed_at TEXT,
            closed_by TEXT,
            closure_evidence TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audit_reports(audit_id),
            FOREIGN KEY (corrective_action_id) REFERENCES corrective_actions(car_id)
        )"""
    )
    await db.execute("CREATE INDEX idx_audit_findings_audit ON audit_findings(audit_id)")
    await db.execute("CREATE INDEX idx_audit_findings_status ON audit_findings(status)")


async def _preserve_quality_finding(db, item):
    finding_id = item["finding_id"]
    audit_id = item["audit_id"]
    if not await _audit_parent_exists(db, "quality_audits", audit_id):
        raise RuntimeError(f"cannot classify legacy audit finding {finding_id}: no matching quality audit {audit_id}")
    if await _audit_parent_exists(db, "audit_reports", audit_id):
        raise RuntimeError(f"cannot classify legacy audit finding {finding_id}: audit_id exists in both audit systems")
    columns = ("finding_id", "audit_id", "finding_type", "description", "severity", "root_cause", "evidence", "status", "created_at", "updated_at")
    expected = tuple(item.get(column) for column in columns)
    existing = await (await db.execute(
        "SELECT finding_id, audit_id, finding_type, description, severity, root_cause, evidence, status, created_at, updated_at FROM quality_audit_findings WHERE finding_id = ?",
        (finding_id,),
    )).fetchone()
    if existing and tuple(existing) != expected:
        raise RuntimeError(f"cannot preserve legacy audit finding {finding_id}: conflicting quality finding id")
    if not existing:
        await db.execute(
            """INSERT INTO quality_audit_findings
               (finding_id, audit_id, finding_type, description, severity, root_cause, evidence, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""", expected,
        )


def _has_external_finding_shape(item) -> bool:
    return (
        all(item.get(column) not in (None, "") for column in ("finding_number", "area", "title"))
        and item.get("level") is not None
    )


def _is_defaulted_external_finding(item) -> bool:
    """Recognize P3 rows in a widened legacy table when P1 columns only hold defaults."""
    return (
        _has_external_finding_shape(item)
        and item.get("finding_type") == "observation"
        and item.get("severity") == "minor"
        and item.get("root_cause") is None
        and item.get("evidence") is None
    )


async def _migrate_legacy_quality_findings(db):
    columns = await _table_columns(db, "audit_findings")
    records = await (await db.execute("SELECT * FROM audit_findings ORDER BY finding_id")).fetchall()
    internal_columns = {"finding_id", "audit_id", "finding_type", "description", "severity", "status", "created_at", "updated_at"}
    if "finding_number" not in columns:
        if not internal_columns <= columns:
            if records:
                raise RuntimeError(f"cannot safely interpret legacy audit_findings rows: legacy columns are incomplete ({', '.join(sorted(columns))})")
            return True
        unexpected = columns - internal_columns - {"root_cause", "evidence"}
        for row in records:
            item = dict(row)
            if any(item.get(column) is not None for column in unexpected):
                raise RuntimeError(f"cannot safely migrate legacy audit finding {item['finding_id']}: unrecognized populated fields")
            await _preserve_quality_finding(db, item)
        return True

    # Some transitional installations widened the shared table and accepted both shapes.
    # Move quality rows first; external rows remain in audit_findings and are rebuilt below.
    if internal_columns <= columns:
        for row in records:
            item = dict(row)
            if item.get("finding_type") is None:
                continue
            quality_parent = await _audit_parent_exists(db, "quality_audits", item["audit_id"])
            external_parent = await _audit_parent_exists(db, "audit_reports", item["audit_id"])
            if _has_external_finding_shape(item):
                if external_parent and _is_defaulted_external_finding(item):
                    # External seed rows omitted P1-only columns, so table defaults must not
                    # reclassify them as internal quality findings during the split.
                    continue
                if not external_parent:
                    raise RuntimeError(
                        f"cannot classify legacy audit finding {item['finding_id']}: external finding shape has no audit report"
                    )
                raise RuntimeError(
                    f"cannot classify legacy audit finding {item['finding_id']}: external finding has non-defaulted P1 fields"
                )
            if quality_parent:
                await _preserve_quality_finding(db, item)
                await db.execute("DELETE FROM audit_findings WHERE finding_id = ?", (item["finding_id"],))
            elif not external_parent:
                raise RuntimeError(f"cannot classify legacy audit finding {item['finding_id']}: no matching audit parent")
            else:
                raise RuntimeError(f"cannot classify legacy audit finding {item['finding_id']}: internal fields conflict with external audit parent")
    return False


async def _rebuild_corrective_actions_finding_fk(db):
    fks = await (await db.execute("PRAGMA foreign_key_list(corrective_actions)")).fetchall()
    if any(row["table"] == "quality_audit_findings" and row["from"] == "finding_id" and row["to"] == "finding_id" for row in fks):
        return

    columns = await _table_columns(db, "corrective_actions")
    records = await (await db.execute("SELECT * FROM corrective_actions ORDER BY car_id")).fetchall()
    required = ("car_id", "title", "description", "owner_id", "created_at", "updated_at", "created_by", "updated_by")
    for row in records:
        item = dict(row)
        if any(item.get(column) is None for column in required):
            raise RuntimeError(f"cannot safely migrate corrective action {item.get('car_id')}: required field is missing")
        finding_id = item.get("finding_id")
        if finding_id and not await (await db.execute(
            "SELECT 1 FROM quality_audit_findings WHERE finding_id = ?", (finding_id,)
        )).fetchone():
            raise RuntimeError(
                f"cannot safely migrate corrective action {item['car_id']}: quality finding {finding_id} does not exist"
            )
        audit_id = item.get("audit_id")
        if audit_id and not await _audit_parent_exists(db, "quality_audits", audit_id):
            raise RuntimeError(
                f"cannot safely migrate corrective action {item['car_id']}: quality audit {audit_id} does not exist"
            )

    await db.execute(
        """CREATE TABLE corrective_actions__new (
            car_id TEXT PRIMARY KEY,
            finding_id TEXT,
            audit_id TEXT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            finding_level TEXT NOT NULL DEFAULT 'level_2',
            root_cause TEXT,
            corrective_action TEXT,
            preventive_action TEXT,
            owner_id TEXT NOT NULL,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            verification TEXT,
            verified_by TEXT,
            verified_at TEXT,
            closed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            updated_by TEXT NOT NULL,
            FOREIGN KEY (finding_id) REFERENCES quality_audit_findings(finding_id),
            FOREIGN KEY (audit_id) REFERENCES quality_audits(audit_id)
        )"""
    )
    copy_columns = (
        "car_id", "finding_id", "audit_id", "title", "description", "finding_level", "root_cause",
        "corrective_action", "preventive_action", "owner_id", "due_date", "status", "verification",
        "verified_by", "verified_at", "closed_at", "created_at", "updated_at", "created_by", "updated_by",
    )
    extra_columns = columns - set(copy_columns)
    for row in records:
        item = dict(row)
        if any(item.get(column) is not None for column in extra_columns):
            raise RuntimeError(f"cannot safely migrate corrective action {item['car_id']}: unrecognized populated fields")
    for row in records:
        item = dict(row)
        values = [item.get(column) for column in copy_columns]
        if "finding_level" not in columns:
            values[5] = "level_2"
        await db.execute(
            f"INSERT INTO corrective_actions__new ({', '.join(copy_columns)}) VALUES ({','.join('?' for _ in copy_columns)})",
            values,
        )
    await db.execute("DROP INDEX IF EXISTS idx_cars_status")
    await db.execute("DROP TABLE corrective_actions")
    await db.execute("ALTER TABLE corrective_actions__new RENAME TO corrective_actions")
    await db.execute("CREATE INDEX idx_cars_status ON corrective_actions(status)")


async def _rebuild_external_audit_findings(db):
    columns = await _table_columns(db, "audit_findings")
    if "finding_number" not in columns:
        return
    fks = await (await db.execute("PRAGMA foreign_key_list(audit_findings)")).fetchall()
    correct_audit_fk = any(row["table"] == "audit_reports" and row["from"] == "audit_id" and row["to"] == "audit_id" for row in fks)
    correct_car_fk = any(row["table"] == "corrective_actions" and row["from"] == "corrective_action_id" and row["to"] == "car_id" for row in fks)
    has_closure_evidence = "closure_evidence" in columns
    known_columns = {
        "finding_id", "audit_id", "finding_number", "area", "level", "title", "description",
        "regulatory_reference", "status", "corrective_action_id", "due_date", "closed_at", "closed_by",
        "closure_evidence", "created_at", "updated_at",
    }
    extra_columns = columns - known_columns
    if correct_audit_fk and correct_car_fk and has_closure_evidence and not extra_columns:
        return

    records = await (await db.execute("SELECT * FROM audit_findings ORDER BY finding_id")).fetchall()
    legacy_p1_columns = {"finding_type", "severity", "root_cause", "evidence"}
    unknown_extra_columns = extra_columns - legacy_p1_columns
    for row in records:
        item = dict(row)
        fid = item.get("finding_id")
        if any(item.get(column) is not None for column in unknown_extra_columns):
            raise RuntimeError(f"cannot safely migrate external audit finding {fid}: unrecognized populated fields")
        populated_p1_columns = any(item.get(column) is not None for column in extra_columns & legacy_p1_columns)
        if populated_p1_columns and not _is_defaulted_external_finding(item):
            raise RuntimeError(f"cannot safely migrate external audit finding {fid}: P1 fields contain non-defaulted data")
        mandatory = ("finding_id", "audit_id", "finding_number", "area", "level", "title", "description", "created_at", "updated_at")
        if any(item.get(column) is None for column in mandatory):
            raise RuntimeError(f"cannot safely migrate external audit finding {fid}: required field is missing")
        if not await _audit_parent_exists(db, "audit_reports", item["audit_id"]):
            raise RuntimeError(f"cannot safely migrate external audit finding {fid}: audit report {item['audit_id']} does not exist")
        car_id = item.get("corrective_action_id")
        if car_id:
            car = await (await db.execute("SELECT 1 FROM corrective_actions WHERE car_id = ?", (car_id,))).fetchone()
            if not car:
                raise RuntimeError(
                    f"cannot safely migrate external audit finding {fid}: corrective action {car_id} has no matching corrective_actions.car_id"
                )

    await db.execute("DROP INDEX IF EXISTS idx_audit_findings_audit")
    await db.execute("DROP INDEX IF EXISTS idx_audit_findings_status")
    await db.execute("ALTER TABLE audit_findings RENAME TO audit_findings__upgrade")
    await _create_external_audit_findings(db)
    for row in records:
        item = dict(row)
        values = tuple(item.get(key) for key in (
            "finding_id", "audit_id", "finding_number", "area", "level", "title", "description",
            "regulatory_reference", "status", "corrective_action_id", "due_date", "closed_at", "closed_by",
            "closure_evidence", "created_at", "updated_at",
        ))
        await db.execute(
            """INSERT INTO audit_findings
               (finding_id, audit_id, finding_number, area, level, title, description, regulatory_reference,
                status, corrective_action_id, due_date, closed_at, closed_by, closure_evidence, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values,
        )
    await db.execute("DROP TABLE audit_findings__upgrade")


async def migrate_audit_schema(db, *, manage_transaction=True):
    """Separate legacy audit records and validate all rebuilt audit foreign keys atomically."""
    if manage_transaction:
        await db.execute("PRAGMA foreign_keys = OFF")
        await db.execute("BEGIN IMMEDIATE")
    try:
        legacy_quality_table = await _migrate_legacy_quality_findings(db)
        await _rebuild_corrective_actions_finding_fk(db)
        if legacy_quality_table:
            await db.execute("DROP TABLE audit_findings")
            await _create_external_audit_findings(db)
        await _rebuild_external_audit_findings(db)
        for table in ("audit_findings", "corrective_actions"):
            violations = await (await db.execute(f"PRAGMA foreign_key_check({table})")).fetchall()
            if violations:
                raise RuntimeError(f"audit schema migration left invalid foreign keys in {table}: {tuple(violations[0])}")
        if manage_transaction:
            await db.commit()
    except Exception:
        if manage_transaction:
            await db.rollback()
        raise
    finally:
        if manage_transaction:
            await db.execute("PRAGMA foreign_keys = ON")


async def _ensure_unique_mission_lifecycle_indexes(db: aiosqlite.Connection) -> None:
    """Enforce one flight release and one post-flight report per mission.

    Existing duplicates are preserved and make startup fail closed for manual
    reconciliation; the migration never chooses or deletes a record silently.
    """
    for table_name, index_name in (
        ("flight_releases", "idx_flight_releases_mission_unique"),
        ("post_flight_reports", "idx_post_flight_reports_mission_unique"),
    ):
        duplicate = await (await db.execute(
            f"SELECT mission_id, COUNT(*) AS row_count FROM {table_name} "
            "GROUP BY mission_id HAVING COUNT(*) > 1 LIMIT 1"
        )).fetchone()
        if duplicate:
            raise RuntimeError(
                f"Cannot enforce one {table_name} row per mission: duplicate {table_name} rows "
                f"for mission {duplicate['mission_id']} ({duplicate['row_count']} rows); reconcile before startup"
            )
        await db.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name}(mission_id)"
        )


async def _ensure_unique_audit_report_index(db: aiosqlite.Connection) -> None:
    """Require non-null, unique audit IDs, stopping for reconciliation when invalid."""
    null_id = await (await db.execute(
        "SELECT 1 FROM audit_reports WHERE audit_id IS NULL LIMIT 1"
    )).fetchone()
    if null_id:
        raise RuntimeError(
            "Cannot enforce unique audit_reports.audit_id: NULL audit ID found; "
            "reconcile before startup"
        )
    duplicate = await (await db.execute(
        "SELECT audit_id, COUNT(*) AS row_count FROM audit_reports "
        "GROUP BY audit_id HAVING COUNT(*) > 1 LIMIT 1"
    )).fetchone()
    if duplicate:
        raise RuntimeError(
            "Cannot enforce unique audit_reports.audit_id: duplicate audit ID "
            f"{duplicate['audit_id']} ({duplicate['row_count']} rows); reconcile before startup"
        )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_reports_audit_id ON audit_reports(audit_id)"
    )


async def _add_column_if_missing(db, table_name: str, column_name: str, column_type: str) -> None:
    """Add a legacy migration column only when schema introspection shows it is absent."""
    columns = {
        row["name"]
        for row in await (await db.execute(f'PRAGMA table_info("{table_name}")')).fetchall()
    }
    if column_name not in columns:
        await db.execute(
            f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}'
        )


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await get_db()
    try:
        # executescript commits any pending transaction before executing its input;
        # start the transaction inside the script so all schema statements participate.
        await db.execute("PRAGMA foreign_keys = OFF")
        await db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA)
        # Parent-key uniqueness must exist before the audit migration checks rebuilt FKs.
        await _ensure_unique_audit_report_index(db)
        await _ensure_unique_mission_lifecycle_indexes(db)
        version_columns = {row["name"] for row in await (await db.execute("PRAGMA table_info(document_versions)")).fetchall()}
        if "kcaa_evidence_sha256" not in version_columns:
            await db.execute("ALTER TABLE document_versions ADD COLUMN kcaa_evidence_sha256 TEXT")
        if "kcaa_evidence_id" not in version_columns:
            await db.execute("ALTER TABLE document_versions ADD COLUMN kcaa_evidence_id TEXT")
        await migrate_audit_schema(db, manage_transaction=False)
        quality_finding_columns = {row["name"] for row in await (await db.execute("PRAGMA table_info(quality_audit_findings)")).fetchall()}
        for column in ("created_by", "updated_by"):
            if column not in quality_finding_columns:
                await db.execute(
                    f"ALTER TABLE quality_audit_findings ADD COLUMN {column} TEXT NOT NULL DEFAULT 'system'"
                )
        user_columns = {row["name"] for row in await (await db.execute("PRAGMA table_info(users)")).fetchall()}
        if "merged_into_user_id" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN merged_into_user_id TEXT")
        session_columns = {row["name"] for row in await (await db.execute("PRAGMA table_info(auth_sessions)")).fetchall()}
        if "active_role" not in session_columns:
            await db.execute("ALTER TABLE auth_sessions ADD COLUMN active_role TEXT")
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.close()

    # Migration: add new columns to existing tables
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        await _add_column_if_missing(db, "audit_reports", "evidence_sha256", "TEXT")
        # documents: kcaa_approval_required, review_due_date
        await _add_column_if_missing(db, "documents", "kcaa_approval_required", "INTEGER NOT NULL DEFAULT 0")
        await _add_column_if_missing(db, "documents", "review_due_date", "TEXT")
        # document_versions: kcaa_approved, kcaa_approved_by, kcaa_approved_at
        await _add_column_if_missing(db, "document_versions", "kcaa_approved", "INTEGER NOT NULL DEFAULT 0")
        await _add_column_if_missing(db, "document_versions", "kcaa_approved_by", "TEXT")
        await _add_column_if_missing(db, "document_versions", "kcaa_approved_at", "TEXT")
        # document_proposals: atomic proposal location and excerpt metadata
        proposal_columns = {
            "change_set_id": "TEXT",
            "section_number": "TEXT",
            "section_heading": "TEXT",
            "block_type": "TEXT",
            "block_index": "INTEGER",
            "anchor_id": "TEXT",
            "context_before": "TEXT",
            "context_after": "TEXT",
            "original_excerpt_html": "TEXT",
            "proposed_excerpt_html": "TEXT",
            "change_fingerprint": "TEXT",
            "change_sequence": "INTEGER",
            "changed_token_count": "INTEGER",
            "change_density": "REAL",
            "grouping_reason": "TEXT",
        }
        for column, column_type in proposal_columns.items():
            await _add_column_if_missing(db, "document_proposals", column, column_type)
        occurrence_columns = {
            "mor_assessed_by": "TEXT",
            "mor_assessed_at": "TEXT",
            "mor_assessment_reason": "TEXT",
            "followup_notes": "TEXT",
            "effectiveness_confirmed": "INTEGER NOT NULL DEFAULT 0",
            "no_new_hazards": "INTEGER NOT NULL DEFAULT 0",
            "closed_by": "TEXT",
            "closed_at": "TEXT",
        }
        for column, column_type in occurrence_columns.items():
            await _add_column_if_missing(db, "occurrences", column, column_type)
        doc_source_columns = {
            "source_pdf_filename": "TEXT",
            "source_sha256": "TEXT",
            "source_issue_revision": "TEXT",
            "source_issued_date": "TEXT",
            "approval_evidence_status": "TEXT",
            "parent_document_id": "TEXT",
            "parent_section_ref": "TEXT",
        }
        for column, column_type in doc_source_columns.items():
            await _add_column_if_missing(db, "documents", column, column_type)
        await _add_column_if_missing(db, "roc_register", "authorized_registrations", "TEXT")
        await _add_column_if_missing(db, "aircraft", "opspec_authorized", "INTEGER NOT NULL DEFAULT 0")
        await _add_column_if_missing(db, "personnel_uploads", "file_sha256", "TEXT")
        ra_columns = {
            "risk_model": "TEXT NOT NULL DEFAULT 'sms_5x5'",
            "exposure": "TEXT",
            "risk_score": "INTEGER",
            "scrutiny_required": "INTEGER NOT NULL DEFAULT 0",
            "flight_cancelled": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, column_type in ra_columns.items():
            await _add_column_if_missing(db, "risk_assessments", column, column_type)
        # Migration: create risk_assessment_hazards junction table for existing databases
        await db.execute(
            """CREATE TABLE IF NOT EXISTS risk_assessment_hazards (
                assessment_id TEXT NOT NULL,
                hazard_id TEXT NOT NULL,
                PRIMARY KEY (assessment_id, hazard_id),
                FOREIGN KEY (assessment_id) REFERENCES risk_assessments(assessment_id),
                FOREIGN KEY (hazard_id) REFERENCES hazards(hazard_id)
            )"""
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_risk_assessment_hazards_assessment ON risk_assessment_hazards(assessment_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_risk_assessment_hazards_hazard ON risk_assessment_hazards(hazard_id)"
        )
        # Migration: add missing columns to existing audit_findings table
        for column, column_type in (
            ("finding_number", "TEXT"),
            ("area", "TEXT"),
            ("level", "INTEGER"),
            ("title", "TEXT"),
            ("regulatory_reference", "TEXT"),
            ("corrective_action_id", "TEXT"),
            ("due_date", "TEXT"),
            ("closed_at", "TEXT"),
            ("closed_by", "TEXT"),
        ):
            await _add_column_if_missing(db, "audit_findings", column, column_type)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_findings_audit ON audit_findings(audit_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_findings_status ON audit_findings(status)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_findings_level ON audit_findings(level)"
        )
        await _add_column_if_missing(db, "corrective_actions", "finding_level", "TEXT NOT NULL DEFAULT 'level_2'")
        for col in (
            "triple_packaging_ok",
            "no_leakage_visual_ok",
            "pic_weather_confirmed",
            "crew_layers_unopened_confirmed",
            "weight_within_limit_ok",
        ):
            await _add_column_if_missing(db, "dg_acceptance_checks", col, "INTEGER NOT NULL DEFAULT 1")
        # Onboarding columns
        await _add_column_if_missing(db, "users", "onboarding_completed", "INTEGER NOT NULL DEFAULT 0")
        await _add_column_if_missing(db, "auth_setup_tokens", "purpose", "TEXT NOT NULL DEFAULT 'setup'")
        await _add_column_if_missing(db, "auth_setup_tokens", "invite_code", "TEXT")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_auth_setup_invite ON auth_setup_tokens(invite_code)")
        await db.commit()
    except Exception:
        if db.in_transaction:
            await db.rollback()
        raise
    finally:
        await db.close()

    # Seed data
    await seed_db()
    await remove_shared_seed_passwords()
    await migrate_verified_identity_groups()
    await migrate_canonical_account_ids_v2()
    await apply_catalogue_corrections()
    await repair_manual_content_assignment()

async def apply_catalogue_corrections():
    """Keep catalogue corrections idempotent without overwriting operational authorization."""
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        corrections = [
            ("DOC-006", "Security Management System Manual", "security_manual", "KFL Security Management System Manual v01.00"),
            ("DOC-007", "Dangerous Goods Manual", "dg_manual", "KFL Dangerous Goods Manual v01.00"),
            ("DOC-012", "Quality Management System Manual", "quality_manual", "KFL Quality Management System Manual v01.00"),
        ]
        for document_id, title, doc_class, description in corrections:
            await db.execute(
                """UPDATE documents
                   SET title = ?, doc_class = ?, description = ?,
                       kcaa_approval_required = 1, updated_at = ?, updated_by = ?
                   WHERE document_id = ?""",
                (title, doc_class, description, now, "system", document_id),
            )
        # Reconcile supplied approved PDFs and embedded OM sections (Phase 0)
        source_manifest = [
            (
                "DOC-001", "published", "KFL 2021 COMPANY ABCD.pdf",
                "92a2509879ca39aafd88e69a5a7cbfdfb536715753da674e27689b2929af07b3",
                "Issue 1 Rev 0", "2021-01-01", "verified_certificate_2021_07_23", None, None,
            ),
            (
                "DOC-002", "published", "KFL 2021 SAFETY.pdf",
                "46b8d26ee14e952899a03d287fceee1a4fe0be9c193cb47047fca37ea5d01f8f",
                "Issue 1 Rev 0", "2021-01-01", "verified_certificate_2021_07_23", None, None,
            ),
            (
                "DOC-006", "published", "KFL REVISED SECURITY MANUAL.pdf",
                "20efd7c392f8ffa0ab007b3f84a645709211bd9e62d252a71afb1dd11ba2bd03",
                "Issue 1 Rev 0", "2021-01-01", "verified_certificate_2021_07_23", None, None,
            ),
            (
                "DOC-012", "published", "KFL QUALITY.pdf",
                "82dc4d547aa0ac1d2f27c693aa91e7c81dfd3a27994c5069e6524c4fc0e6463e",
                "Issue 1 Rev 0", "2021-01-01", "verified_certificate_2021_07_23", None, None,
            ),
            (
                "DOC-007", "published", "DANGEROUS GOODS MANUAL KFL 01 may 2025.pdf",
                "90e06fac387de092a1144fdf598e93368068b6de5e978fa0bab315a89766b823",
                "Issue 01 Rev 00", "2024-05-01", "pending_letter", None, None,
            ),
            (
                "DOC-003", "published", None, None,
                "Manufacturer / OpSpec referenced", None, "oem_and_opspec_referenced", "DOC-001", "OM + OEM specifications",
            ),
            (
                "DOC-004", "published", "KFL 2021 COMPANY ABCD.pdf",
                "92a2509879ca39aafd88e69a5a7cbfdfb536715753da674e27689b2929af07b3",
                "Issue 1 Rev 0", "2021-01-01", "embedded_in_om_part_d", "DOC-001", "Part D",
            ),
            (
                "DOC-005", "published", "KFL 2021 COMPANY ABCD.pdf",
                "92a2509879ca39aafd88e69a5a7cbfdfb536715753da674e27689b2929af07b3",
                "Issue 1 Rev 0", "2021-01-01", "embedded_in_om_part_b", "DOC-001", "Part B",
            ),
        ]
        for (
            doc_id, status_val, pdf_name, sha256_val, issue_rev,
            issued_date, evidence_status, parent_doc, parent_sec,
        ) in source_manifest:
            await db.execute(
                """UPDATE documents
                   SET status = ?, source_pdf_filename = ?, source_sha256 = ?,
                       source_issue_revision = ?, source_issued_date = ?,
                       approval_evidence_status = ?, parent_document_id = ?,
                       parent_section_ref = ?, updated_at = ?, updated_by = ?
                   WHERE document_id = ?""",
                (
                    status_val, pdf_name, sha256_val, issue_rev, issued_date,
                    evidence_status, parent_doc, parent_sec, now, "system", doc_id,
                ),
            )
        # Synchronize signed 2021 KCAA certificate metadata on the 4 verified baseline versions
        for ver_id in ("VER-DOC-001", "VER-DOC-002", "VER-DOC-006", "VER-DOC-012"):
            await db.execute(
                """UPDATE document_versions
                   SET kcaa_approved = 1, kcaa_approved_by = 'KCAA',
                       kcaa_approved_at = '2021-07-23',
                       kcaa_reference = COALESCE(kcaa_reference, 'KCAA-CERT-2021-07-23')
                   WHERE version_id = ?""",
                (ver_id,),
            )
        await db.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("fdtl_validation_status", "configurable_application_defaults_pending_regulatory_clause_validation", now),
        )
        await db.commit()
    finally:
        await db.close()

async def repair_manual_content_assignment():
    """Repair the known QMS/security content reversal without changing HTML formatting."""
    db = await get_db()
    try:
        rows = {}
        for document_id in ("DOC-006", "DOC-012"):
            async with db.execute(
                "SELECT d.document_id, d.current_version_id, v.content FROM documents d JOIN document_versions v ON v.version_id = d.current_version_id WHERE d.document_id = ?",
                (document_id,),
            ) as cursor:
                row = await cursor.fetchone()
            if row:
                rows[document_id] = row

        security_row = rows.get("DOC-006")
        qms_row = rows.get("DOC-012")
        security_content = security_row["content"] if security_row else None
        qms_content = qms_row["content"] if qms_row else None
        if not security_content or not qms_content:
            return

        security_marker = security_content.upper()
        qms_marker = qms_content.upper()
        reversed_assignment = (
            "QUALITY MANAGEMENT SYSTEM" in security_marker
            and "SECURITY MANUAL" in qms_marker
        )
        if not reversed_assignment:
            return

        now = datetime.now().isoformat()
        await db.execute(
            "UPDATE document_versions SET content = ?, updated_at = ?, updated_by = ? WHERE version_id = ?",
            (qms_content, now, "system", rows["DOC-006"]["current_version_id"]),
        )
        await db.execute(
            "UPDATE document_versions SET content = ?, updated_at = ?, updated_by = ? WHERE version_id = ?",
            (security_content, now, "system", rows["DOC-012"]["current_version_id"]),
        )
        await db.commit()
    finally:
        await db.close()

async def seed_db():
    db = await get_db()
    try:
        # Check if already seeded
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        count = (await cursor.fetchone())[0]
        if count > 0:
            await _install_mutation_audit_triggers(db)
            await db.commit()
            return

        from datetime import datetime, timedelta
        now_dt = datetime.now()
        now = now_dt.isoformat()
        two_years = (now_dt + timedelta(days=730)).strftime('%Y-%m-%d')
        six_months = (now_dt + timedelta(days=180)).strftime('%Y-%m-%d')
        pw = None
        users = [
            ("u-admin", "admin", "admin@kfl.aero", "Mohamed Alsayed", "system_admin", "IT", now, now, pw),
            ("u-lib", "librarian", "librarian@kfl.aero", "Eric Otieno", "librarian", "Quality", now, now, pw),
            ("u-quality", "quality", "quality@kfl.aero", "Eric Otieno", "head_quality", "Quality", now, now, pw),
            ("u-safety", "safety", "safety@kfl.aero", "Brian Swanya", "head_safety", "Safety", now, now, pw),
            ("u-security", "security", "security@kfl.aero", "Brian Swanya", "head_security", "Security", now, now, pw),
            ("u-ops", "ops", "ops@kfl.aero", "Utana Kinuthia", "head_operations", "Operations", now, now, pw),
            ("u-chief-pilot", "chief_pilot", "chiefpilot@kfl.aero", "Utana Kinuthia", "chief_pilot", "Operations", now, now, pw),
            ("u-flight-ops", "flight_ops", "flightops@kfl.aero", "Emmanuel Koome", "flight_ops_officer", "Operations", now, now, pw),
            ("u-training", "training", "training@kfl.aero", "Utana Kinuthia", "head_training", "Training", now, now, pw),
            ("u-maintenance", "maintenance", "maintenance@kfl.aero", "Mohamed Alsayed", "head_maintenance", "Maintenance", now, now, pw),
            ("u-dg", "dg_coordinator", "dg@kfl.aero", "Emmanuel Koome", "dg_coordinator", "Operations", now, now, pw),
            ("u-reporter", "reporter", "reporter@kfl.aero", "Occurrence Reporter", "occurrence_reporter", "Safety", now, now, pw),
            ("u-auditor", "auditor", "auditor@kfl.aero", "Independent Auditor", "independent_auditor", "Quality", now, now, pw),
            ("u-records", "records_custodian", "records@kfl.aero", "Eric Otieno", "records_custodian", "Quality", now, now, pw),
            ("u-accountable", "accountable", "accountable@kfl.aero", "Cleopa Otieno", "accountable_manager", "Executive", now, now, pw),
        ]
        for u in users:
            await db.execute(
                "INSERT INTO users (user_id, username, email, full_name, role, department, is_active, password_hash, created_at, updated_at) VALUES (?,?,?,?,?,?,1,?,?,?)",
                (u[0], u[1], u[2], u[3], u[4], u[5], u[8], now, now),
            )
            await db.execute(
                "INSERT INTO user_roles (user_id, role) VALUES (?, ?)",
                (u[0], u[4]),
            )

        # Retention rules (22)
        retention_rules = [
            ("RR-001", "Safety Occurrence Reports", "Occurrence reports and investigation records", 5, 7, "Occurrence closure", "Secure archive then destroy", "S2"),
            ("RR-002", "Flight Operations Records", "Mission logs, flight plans, release forms", 3, 5, "Mission completion", "Secure archive then destroy", "S2"),
            ("RR-003", "Maintenance Records", "Aircraft maintenance logs and work orders", 5, 7, "Last entry date", "Secure archive then destroy", "S2"),
            ("RR-004", "Training Records", "Personnel training and competency records", 5, 7, "Last training date", "Secure archive then destroy", "S1"),
            ("RR-005", "Audit Records", "Internal and external audit reports", 5, 7, "Audit completion", "Secure archive then destroy", "S3"),
            ("RR-006", "Regulatory Correspondence", "KCAA correspondence and approvals", 10, 10, "Last correspondence", "Permanent archive", "S3"),
            ("RR-007", "ROC & Ops Specs", "ROC certificates and operations specifications", 10, 10, "Expiry date", "Permanent archive", "S3"),
            ("RR-008", "Document Control Records", "Document versions, change requests, distributions", 5, 7, "Document obsolescence", "Secure archive then destroy", "S1"),
            ("RR-009", "Personnel Records", "Employment and qualification records", 7, 7, "Employment termination", "Secure archive then destroy", "S3"),
            ("RR-010", "Dangerous Goods Records", "DG acceptance and transport records", 5, 7, "Transport completion", "Secure archive then destroy", "S2"),
            ("RR-011", "Security Records", "Security assessments and incident reports", 5, 7, "Incident closure", "Secure archive then destroy", "S3"),
            ("RR-012", "Insurance Records", "Insurance policies and claims", 7, 7, "Policy expiry", "Secure archive then destroy", "S2"),
            ("RR-013", "Financial Records", "Invoices, payments, financial statements", 7, 7, "Fiscal year end", "Secure archive then destroy", "S2"),
            ("RR-014", "Supplier Records", "Supplier evaluations and contracts", 5, 7, "Contract expiry", "Secure archive then destroy", "S1"),
            ("RR-015", "Emergency Response Records", "Emergency drill and response records", 5, 7, "Drill completion", "Secure archive then destroy", "S2"),
            ("RR-016", "Risk Assessments", "Risk assessment records and mitigations", 5, 7, "Assessment closure", "Secure archive then destroy", "S2"),
            ("RR-017", "Hazard Register", "Hazard identification and tracking records", 5, 7, "Hazard closure", "Secure archive then destroy", "S2"),
            ("RR-018", "Quality Audit Records", "Quality audit findings and CARs", 5, 7, "CAR closure", "Secure archive then destroy", "S2"),
            ("RR-019", "Delegation Register", "Delegation of authority records", 10, 10, "Role change", "Permanent archive", "S3"),
            ("RR-020", "Aircraft Register", "Aircraft registration and airworthiness records", 10, 10, "Aircraft deregistration", "Permanent archive", "S3"),
            ("RR-021", "Manual Index", "Manual and document index records", 5, 7, "Document obsolescence", "Secure archive then destroy", "S1"),
            ("RR-022", "Safety Reports", "Monthly/quarterly/annual safety reports", 5, 7, "Report period end", "Secure archive then destroy", "S2"),
            ("RR-023", "General Operational Records", "General business and operational records", 3, 3, "Record creation", "Secure archive then destroy", "S2"),
            ("RR-025", "Metadata Records", "Audit trail metadata, system logs, and legal hold records", -1, -1, "Record creation", "Permanent archive", "S3"),
        ]
        for r in retention_rules:
            await db.execute(
                "INSERT INTO retention_rules (rule_id, record_class, description, statutory_years, kfl_policy_years, trigger_event, disposal_method, classification, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], now, now, "admin", "admin"),
            )

        # Compliance obligations (14)
        obligations = [
            ("CO-001", "KCAA/OPS/2117/ROC/06", "ROC Validity", "ROC must be renewed before expiry", "KCAA", "2027-10-11", "open", "u-ops"),
            ("CO-002", "Reg 25", "Application Notice", "Submit ROC renewal application ≥90 days before expiry", "KCAA Regs 2025", "2027-07-13", "open", "u-ops"),
            ("CO-003", "SMS-004A", "MOR Reporting", "Mandatory Occurrence Reporting per KCAA CAA-AC-SMS004A", "KCAA", None, "open", "u-safety"),
            ("CO-004", "UAS Regs 2025", "UAS Registration", "All UAS must be registered with KCAA", "KCAA", None, "open", "u-ops"),
            ("CO-005", "UAS Regs 2025", "Remote Pilot Certification", "All RPICs must hold valid KCAA certification", "KCAA", None, "open", "u-ops"),
            ("CO-006", "UAS Regs 2025", "Operations Manual", "Approved operations manual must be current", "KCAA", None, "open", "u-lib"),
            ("CO-007", "UAS Regs 2025", "Maintenance Program", "Approved maintenance program must be followed", "KCAA", None, "open", "u-quality"),
            ("CO-008", "UAS Regs 2025", "Insurance", "Third-party liability insurance required", "KCAA", None, "open", "u-admin"),
            ("CO-009", "SMS-004A", "Safety Management System", "SMS must be implemented and maintained", "KCAA", None, "open", "u-safety"),
            ("CO-010", "UAS Regs 2025", "Dangerous Goods", "DG transport requires KCAA authorization", "KCAA", None, "open", "u-ops"),
            ("CO-011", "UAS Regs 2025", "Security Program", "Aviation security program must be implemented", "KCAA", None, "open", "u-safety"),
            ("CO-012", "Data Protection Act", "Data Protection", "ODPC registration and compliance", "Kenya DPA", None, "open", "u-admin"),
            ("CO-013", "KCAA", "Audit Program", "Annual internal audit program", "KCAA", None, "open", "u-quality"),
            ("CO-014", "KCAA", "Training Program", "Recurrent training program maintained", "KCAA", None, "open", "u-ops"),
        ]
        for o in obligations:
            await db.execute(
                "INSERT INTO compliance_obligations (obligation_id, reference, title, description, source, due_date, status, owner_id, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (o[0], o[1], o[2], o[3], o[4], o[5], o[6], o[7], now, now, "admin", "admin"),
            )

        # Regulatory references (27)
        refs = [
            ("RRF-001", "KCAA", "Civil Aviation (Unmanned Aircraft Systems) Regulations, 2020", "General", "UAS regulations", None),
            ("RRF-002", "KCAA", "Civil Aviation (Unmanned Aircraft Systems) Regulations, 2025", "General", "UAS regulations (LN 40)", None),
            ("RRF-003", "KCAA", "CAA-AC-SMS004A", "MOR", "Mandatory Occurrence Reporting Circular", None),
            ("RRF-004", "KCAA", "CAA-M-UAS001", "ROC", "UAS MIS - ROC approval process", None),
            ("RRF-005", "KCAA", "KCAA/OPS/2117/ROC/06", "ROC", "KFL ROC certificate", None),
            ("RRF-006", "KCAA", "Civil Aviation (Safety Management) Regulations, 2018", "SMS", "SMS regulations", None),
            ("RRF-007", "KCAA", "Civil Aviation (Security) Regulations, 2020", "Security", "Security regulations", None),
            ("RRF-008", "KCAA", "Civil Aviation (Dangerous Goods) Regulations", "DG", "DG transport regulations", None),
            ("RRF-009", "Kenya", "Data Protection Act, 2019", "Data", "Data protection", None),
            ("RRF-010", "KCAA", "Civil Aviation (Airworthiness) Regulations", "Airworthiness", "Airworthiness standards", None),
            ("RRF-011", "KCAA", "Civil Aviation (Personnel Licensing) Regulations", "Licensing", "Personnel licensing", None),
            ("RRF-012", "KCAA", "Civil Aviation (Operations) Regulations", "Operations", "Operations standards", None),
            ("RRF-013", "KCAA", "Civil Aviation (Aerodromes) Regulations", "Aerodromes", "Aerodrome standards", None),
            ("RRF-014", "KCAA", "Civil Aviation (Air Navigation Services) Regulations", "ANS", "ANS standards", None),
            ("RRF-015", "KCAA", "Civil Aviation (Environmental Protection) Regulations", "Environment", "Environmental standards", None),
            ("RRF-016", "ICAO", "Annex 1 - Personnel Licensing", "ICAO", "ICAO Annex 1", None),
            ("RRF-017", "ICAO", "Annex 6 - Operation of Aircraft", "ICAO", "ICAO Annex 6", None),
            ("RRF-018", "ICAO", "Annex 8 - Airworthiness", "ICAO", "ICAO Annex 8", None),
            ("RRF-019", "ICAO", "Annex 13 - Aircraft Accident Investigation", "ICAO", "ICAO Annex 13", None),
            ("RRF-020", "ICAO", "Annex 14 - Aerodromes", "ICAO", "ICAO Annex 14", None),
            ("RRF-021", "ICAO", "Annex 17 - Security", "ICAO", "ICAO Annex 17", None),
            ("RRF-022", "ICAO", "Annex 18 - Dangerous Goods", "ICAO", "ICAO Annex 18", None),
            ("RRF-023", "ICAO", "Annex 19 - Safety Management", "ICAO", "ICAO Annex 19", None),
            ("RRF-024", "KCAA", "KCAA Form ROC-001", "Forms", "ROC application form", None),
            ("RRF-025", "KCAA", "KCAA Form ROC-003", "Forms", "ROC amendment form", None),
            ("RRF-026", "KCAA", "KCAA Form ROC-005", "Forms", "ROC renewal form", None),
            ("RRF-027", "KCAA", "KCAA Form UAS-001", "Forms", "UAS registration form", None),
        ]
        for r in refs:
            await db.execute(
                "INSERT INTO regulatory_references (ref_id, source, title, section, description, url, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (r[0], r[1], r[2], r[3], r[4], r[5], now, now),
            )

        # Documents (baseline manuals + SOPs, checklists, forms, policies)
        # kcaa_approval_required=1 for regulated documents (DMS-05)
        # review_due_date: 2 years for manuals, 6 months for checklists/forms (DMS-07)
        docs = [
            ("DOC-001", "Operations Manual", "operations_manual", "S2", "published", "u-lib", "KFL Operations Manual v01.01", now, now, "u-lib", "u-lib", 1, two_years),
            ("DOC-002", "Safety Management Manual", "safety_manual", "S2", "published", "u-lib", "KFL Safety Management Manual v01.01", now, now, "u-lib", "u-lib", 1, two_years),
            ("DOC-003", "Maintenance Manual", "maintenance_manual", "S2", "published", "u-lib", "KFL Maintenance Manual v01.01", now, now, "u-lib", "u-lib", 1, two_years),
            ("DOC-004", "Training Manual", "training_manual", "S2", "published", "u-lib", "KFL Training Manual v01.01", now, now, "u-lib", "u-lib", 0, six_months),
            ("DOC-005", "Emergency Response Plan", "emergency_plan", "S2", "published", "u-lib", "KFL Emergency Response Plan v01.01", now, now, "u-lib", "u-lib", 1, two_years),
            ("DOC-006", "Security Management System Manual", "security_manual", "S3", "published", "u-security", "KFL Security Management System Manual v01.00", now, now, "u-lib", "u-lib", 1, two_years),
            ("DOC-007", "Dangerous Goods Manual", "dg_manual", "S3", "published", "u-dg", "KFL Dangerous Goods Manual v01.00", now, now, "u-lib", "u-lib", 1, two_years),
            ("DOC-008", "Pre-Flight Checklist - DJI M350 RTK", "checklist", "S1", "published", "u-ops", "Pre-flight inspection checklist for DJI M350 RTK", now, now, "u-lib", "u-lib", 0, six_months),
            ("DOC-009", "Pre-Flight Checklist - DJI Phantom 4 Pro", "checklist", "S1", "published", "u-ops", "Pre-flight inspection checklist for DJI Phantom 4 Pro", now, now, "u-lib", "u-lib", 0, six_months),
            ("DOC-010", "Flight Release Form", "form", "S2", "published", "u-ops", "KFL Flight Release Authorization Form", now, now, "u-lib", "u-lib", 0, six_months),
            ("DOC-011", "Occurrence Report Form", "form", "S2", "published", "u-safety", "Mandatory Occurrence Report Form", now, now, "u-lib", "u-lib", 0, six_months),
            ("DOC-012", "Quality Management System Manual", "quality_manual", "S2", "draft", "u-quality", "KFL Quality Management System Manual v01.00", now, now, "u-lib", "u-lib", 1, two_years),
            ("DOC-013", "Personnel Training Policy", "policy", "S1", "published", "u-training", "KFL Training and Competency Policy", now, now, "u-lib", "u-lib", 0, six_months),
            ("DOC-014", "ROC Application Form ROC-001", "form", "S3", "published", "u-ops", "KCAA Form ROC-001 - ROC Application", now, now, "u-lib", "u-lib", 0, six_months),
            ("DOC-015", "DG Acceptance Checklist", "checklist", "S3", "published", "u-dg", "Dangerous Goods Acceptance Inspection Checklist", now, now, "u-lib", "u-lib", 0, six_months),
        ]
        for d in docs:
            await db.execute(
                "INSERT INTO documents (document_id, title, doc_class, classification, status, owner_id, description, created_at, updated_at, created_by, updated_by, kcaa_approval_required, review_due_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                d,
            )
            ver_id = f"VER-{d[0]}"
            # Proper content per document instead of minimal placeholder
            doc_content_map = {
                "DOC-001": "# KFL Operations Manual v01.01\n\n## 1. Purpose\nThis manual establishes the standard operating procedures for all KFL UAS flight operations.\n\n## 2. Scope\nApplies to all remotely piloted aircraft systems operated under KFL ROC No. 06.\n\n## 3. Responsibilities\nThe Accountable Executive is responsible for overall compliance. The Head of Operations oversees daily flight activities.\n\n## 4. Procedures\n4.1 Pre-flight planning\n4.2 Flight execution\n4.3 Post-flight reporting\n\n## 5. Emergency Procedures\nFollow the Emergency Response Plan (DOC-005) in case of incident.\n\n---\nVersion 01.01.00",
                "DOC-002": "# KFL Safety Management Manual v01.01\n\n## 1. Safety Policy\nKFL is committed to maintaining the highest safety standards in all UAS operations.\n\n## 2. Safety Risk Management\nHazards are identified, assessed, and mitigated per the Safety Occurrence Reporting procedure.\n\n## 3. Safety Assurance\nInternal audits and reviews verify the effectiveness of safety controls.\n\n## 4. Safety Promotion\nAll personnel receive regular safety training and briefings.\n\n---\nVersion 01.01.00",
                "DOC-003": "# KFL Maintenance Manual v01.01\n\n## 1. Maintenance Philosophy\nAll KFL aircraft are maintained in accordance with manufacturer instructions and regulatory requirements.\n\n## 2. Maintenance Personnel\nThe Head of Maintenance oversees all maintenance activities. Only authorized personnel may perform maintenance.\n\n## 3. Maintenance Schedule\nRoutine inspections are conducted per the OEM maintenance manual for each aircraft model.\n\n## 4. Defect Management\nDefects are recorded, assessed, and rectified before the aircraft returns to service.\n\n---\nVersion 01.01.00",
                "DOC-004": "# KFL Training Manual v01.01\n\n## 1. Training Program\nAll remote pilots must complete initial and recurrent training before operating KFL aircraft.\n\n## 2. Initial Training\nIncludes ground school, flight training, and practical assessment.\n\n## 3. Recurrent Training\nConducted every 12 months for all active remote pilots.\n\n---\nVersion 01.01.00",
                "DOC-005": "# KFL Emergency Response Plan v01.01\n\n## 1. Emergency Categories\nAccident, serious incident, incident, and emergency deviation.\n\n## 2. Immediate Actions\nSecure the area, notify the Accountable Executive, and contact emergency services if required.\n\n## 3. Reporting\nAccidents are reported to KCAA within 24 hours. Serious incidents within 48 hours.\n\n---\nVersion 01.01.00",
                "DOC-006": "# KFL Security Management System Manual v01.00\n\n## 1. Security Policy\nKFL protects its aircraft, personnel, and data from unauthorized access.\n\n## 2. Access Control\nOnly authorized personnel may access the operations center and aircraft storage.\n\n## 3. Cyber Security\nAll systems are protected by firewalls and encryption.\n\n---\nVersion 01.00.00",
                "DOC-007": "# KFL Dangerous Goods Manual v01.00\n\n## 1. DG Policy\nDangerous goods are transported only in accordance with ICAO Technical Instructions and KCAA requirements.\n\n## 2. DG Categories\nCategory A and B dangerous goods are approved for transport under KFL ROC.\n\n## 3. Acceptance Checks\nAll DG shipments must pass acceptance checks before loading.\n\n---\nVersion 01.00.00",
                "DOC-008": "# Pre-Flight Checklist - DJI M350 RTK\n\n## 1. Pre-Flight\n- Inspect airframe for damage\n- Verify battery charge level\n- Check propeller condition\n- Confirm GPS signal\n- Verify return-to-home altitude\n\n## 2. Flight\n- Maintain visual line of sight\n- Monitor battery level\n- Observe altitude limits (400 ft AGL)\n\n---\nVersion 01.01.00",
                "DOC-009": "# Pre-Flight Checklist - DJI Phantom 4 Pro\n\n## 1. Pre-Flight\n- Inspect airframe for damage\n- Verify battery charge level\n- Check propeller condition\n- Confirm GPS signal\n- Verify return-to-home altitude\n\n## 2. Flight\n- Maintain visual line of sight\n- Monitor battery level\n- Observe altitude limits (400 ft AGL)\n\n---\nVersion 01.01.00",
                "DOC-010": "# KFL Flight Release Authorization Form\n\n## 1. Flight Details\nMission ID, date, location, aircraft, remote pilot.\n\n## 2. Pre-Flight Confirmations\n- Weather confirmed\n- Crew confirmed\n- Aircraft confirmed\n- Pre-flight checklist completed\n\n## 3. Release Authorization\nReleased by: __________  Date: __________\n\n---\nVersion 01.01.00",
                "DOC-011": "# KFL Mandatory Occurrence Report Form\n\n## 1. Occurrence Details\nSerial number, date, time, location, type, severity.\n\n## 2. Description\nDetailed description of the occurrence.\n\n## 3. Reporting\nMOR submitted to KCAA within required timelines.\n\n---\nVersion 01.01.00",
                "DOC-012": "# KFL Quality Management System Manual v01.00\n\n## 1. Purpose\nThis manual defines the KFL quality management system for SMS and operations.\n\n## 2. Audit Schedule\nAudits are conducted at least annually per the approved audit schedule.\n\n## 3. Findings\nFindings are documented and corrective actions are tracked to closure.\n\n---\nVersion 01.00.00",
                "DOC-013": "# KFL Training and Competency Policy\n\n## 1. Policy\nAll personnel must hold valid training and competency records for their assigned duties.\n\n## 2. Training Records\nRecords are maintained in the training management system.\n\n## 3. Competency Assessment\nCompetency is assessed before personnel are authorized to perform duties.\n\n---\nVersion 01.01.00",
                "DOC-014": "# KCAA Form ROC-001 - ROC Application\n\n## 1. Applicant Details\nOrganization name, address, contact person.\n\n## 2. Operation Details\nOperation type, area, altitude, aircraft models.\n\n## 3. Supporting Documents\nOperations Manual, Safety Management Manual, Maintenance Manual.\n\n---\nVersion 01.01.00",
                "DOC-015": "# KFL Dangerous Goods Acceptance Inspection Checklist\n\n## 1. Shipment Details\nShipment ID, DG class, UN number, shipper, consignee.\n\n## 2. Acceptance Checks\n- Packaging inspected\n- Marking and labeling verified\n- Documentation complete\n- State of charge verified (for batteries)\n\n## 3. Result\nAccepted / Rejected - Inspector signature: __________\n\n---\nVersion 01.01.00",
            }
            content_text = doc_content_map.get(d[0], f"# {d[1]}\\n\\nVersion 01.01.00")
            await db.execute(
                "INSERT INTO document_versions (version_id, document_id, version_number, state, content, kcaa_approved, kcaa_approved_by, kcaa_approved_at, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ver_id, d[0], "01.01.00", "published", content_text, 0, None, None, now, now, "u-lib", "u-lib"),
            )
            await db.execute(
                "UPDATE documents SET current_version_id = ? WHERE document_id = ?",
                (ver_id, d[0]),
            )

        # ROC register
        opspec_regs = ("5Y-0029A", "5Y-0030A", "5Y-0042A", "5Y-0164A", "5Y-0600A", "5Y-0601A", "5Y-0602A")
        await db.execute(
            """INSERT INTO roc_register (roc_id, roc_number, serial_number, kcaa_reference, issue_date, expiry_date, status, categories, bvlos_authorized, night_authorized, max_altitude_agl, evlos_authorized, dg_category, authorized_registrations, notes, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("ROC-001", "06", "0110", "KCAA/OPS/2117/ROC/06", "2026-10-12", "2027-10-11", "active", "A,B", 0, 0, 400, 1, "Division 6.2 Cat A&B", ",".join(opspec_regs), "EVLOS with qualified VO", now, now, "admin", "admin"),
        )

        # Aircraft / UAS master fleet (20 registrations), separate from the 7 OpSpec-authorized registrations
        aircraft = [
            ("AC-001", "5Y-0029A", "DJI M350 RTK", "DJI", "154820399", "ROC-001", "active", "Category A", "MTOW < 25kg", 7.5, "2024-03-15", "BVLOS capable", now, now, "u-maintenance", "u-maintenance"),
            ("AC-002", "5Y-0030A", "DJI Phantom 4 Pro", "DJI", "154820400", "ROC-001", "active", "Category A", "MTOW < 25kg", 1.4, "2024-02-20", "Visual line of sight", now, now, "u-maintenance", "u-maintenance"),
            ("AC-003", "5Y-0042A", "Tarot Iron Man 650", "Tarot", "TIM99762399", "ROC-001", "active", "Category B", "MTOW < 25kg", 5.0, "2024-01-10", "Heavy lift platform", now, now, "u-maintenance", "u-maintenance"),
            ("AC-004", "5Y-0043A", "Mavic Air 2", "DJI", "154820401", "ROC-001", "active", "Category A", "MTOW < 25kg", 0.57, "2024-04-05", "Compact survey", now, now, "u-maintenance", "u-maintenance"),
            ("AC-005", "5Y-0059A", "Skydio 2", "Skydio", "154820402", "ROC-001", "active", "Category A", "MTOW < 25kg", 0.8, "2024-05-12", "Autonomous flight", now, now, "u-maintenance", "u-maintenance"),
            ("AC-006", "5Y-0164A", "Phantom 4 Pro v2", "DJI", "154820403", "ROC-001", "active", "Category A", "MTOW < 25kg", 1.4, "2024-03-28", "Photogrammetry", now, now, "u-maintenance", "u-maintenance"),
            ("AC-007", "5Y-0366A", "Ebee X", "senseFly", "154820404", "ROC-001", "active", "Category A", "Fixed wing", 1.1, "2024-06-01", "Fixed wing mapping", now, now, "u-maintenance", "u-maintenance"),
            ("AC-008", "5Y-0496A", "Matrice 600 Pro", "DJI", "154820405", "ROC-001", "active", "Category B", "MTOW < 25kg", 9.5, "2024-02-14", "Heavy lift hexacopter", now, now, "u-maintenance", "u-maintenance"),
            ("AC-009", "5Y-0600A", "Mini 2", "DJI", "154820406", "ROC-001", "active", "Category A", "MTOW < 25kg", 0.25, "2024-07-10", "Micro drone", now, now, "u-maintenance", "u-maintenance"),
            ("AC-010", "5Y-0601A", "Mavic Air 2S", "DJI", "154820407", "ROC-001", "active", "Category A", "MTOW < 25kg", 0.6, "2024-08-15", "1-inch sensor survey", now, now, "u-maintenance", "u-maintenance"),
            ("AC-011", "5Y-0602A", "Matrice 350 RTK", "DJI", "154820408", "ROC-001", "active", "Category B", "MTOW < 25kg", 7.5, "2024-09-01", "Enterprise platform", now, now, "u-maintenance", "u-maintenance"),
            ("AC-012", "5Y-0685A", "FlyCart 30", "DJI", "154820409", "ROC-001", "active", "Category B", "Cargo delivery", 40.0, "2024-10-05", "Delivery drone", now, now, "u-maintenance", "u-maintenance"),
            ("AC-013", "5Y-0682A", "Matrice 4TD", "DJI", "154820410", "ROC-001", "active", "Category A", "MTOW < 25kg", 1.2, "2025-01-20", "Thermal imaging", now, now, "u-maintenance", "u-maintenance"),
            ("AC-014", "5Y-0820A", "Matrice 4E", "DJI", "154820411", "ROC-001", "active", "Category A", "MTOW < 25kg", 1.2, "2025-02-10", "Mapping platform", now, now, "u-maintenance", "u-maintenance"),
            ("AC-015", "5Y-0925A", "Matrice 4T", "DJI", "154820412", "ROC-001", "active", "Category A", "MTOW < 25kg", 1.2, "2025-03-05", "Thermal + zoom", now, now, "u-maintenance", "u-maintenance"),
            ("AC-016", "5Y-0926A", "Matrice 400 RTK", "DJI", "154820413", "ROC-001", "active", "Category B", "MTOW < 25kg", 6.5, "2025-04-12", "Enterprise platform", now, now, "u-maintenance", "u-maintenance"),
            ("AC-017", "5Y-0976A", "Mavic Pro", "DJI", "154820414", "ROC-001", "active", "Category A", "MTOW < 25kg", 0.74, "2024-01-30", "Legacy platform", now, now, "u-maintenance", "u-maintenance"),
            ("AC-018", "5Y-1352A", "Phantom 3", "DJI", "154820415", "ROC-001", "active", "Category A", "MTOW < 25kg", 1.2, "2024-02-25", "Legacy platform", now, now, "u-maintenance", "u-maintenance"),
            ("AC-019", "5Y-1353A", "DJI M350 RTK", "DJI", "154820416", "ROC-001", "active", "Category A", "MTOW < 25kg", 7.5, "2025-05-01", "Primary survey platform", now, now, "u-maintenance", "u-maintenance"),
            ("AC-021", "5Y-1355A", "eBee X", "senseFly", "154820418", "ROC-001", "active", "Category A", "Fixed wing", 1.1, "2025-07-01", "Fixed wing mapping", now, now, "u-maintenance", "u-maintenance"),
        ]
        for ac in aircraft:
            await db.execute(
                """INSERT INTO aircraft (aircraft_id, registration, model, manufacturer, serial_number, roc_id, status, opspec_authorized, category, weight_class, max_takeoff_weight_kg, acquired_date, notes, created_at, updated_at, created_by, updated_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (*ac[:7], 1 if ac[1] in opspec_regs else 0, *ac[7:]),
            )

        # App settings (configurable FDTL defaults)
        await db.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES (?,?,?)""",
            ("fdtl_max_duty_hours", "14", now),
        )
        await db.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES (?,?,?)""",
            ("fdtl_max_block_hours", "12", now),
        )
        await db.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES (?,?,?)""",
            ("fdtl_min_rest_hours", "10", now),
        )
        await db.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES (?,?,?)""",
            ("crew_currency_warning_days", "30", now),
        )

        await db.commit()
    finally:
        await db.close()

    db = await get_db()
    try:
        await _install_mutation_audit_triggers(db)
        await db.commit()
    finally:
        await db.close()
    print("Database seeded successfully")