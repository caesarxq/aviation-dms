"""SQLite database schema and connection management for Aviation DMS."""
import aiosqlite
import os
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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

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

-- Audit Findings
CREATE TABLE IF NOT EXISTS audit_findings (
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
    FOREIGN KEY (audit_id) REFERENCES quality_audits(audit_id)
);

-- Corrective Action Requests (CARs)
CREATE TABLE IF NOT EXISTS corrective_actions (
    car_id TEXT PRIMARY KEY,
    finding_id TEXT,
    audit_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
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
    FOREIGN KEY (finding_id) REFERENCES audit_findings(finding_id),
    FOREIGN KEY (audit_id) REFERENCES quality_audits(audit_id)
);

CREATE INDEX IF NOT EXISTS idx_audits_status ON quality_audits(status);
CREATE INDEX IF NOT EXISTS idx_findings_audit ON audit_findings(audit_id);
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

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()

    # Migration: add new columns to existing tables
    db = await get_db()
    try:
        # documents: kcaa_approval_required, review_due_date
        try:
            await db.execute("ALTER TABLE documents ADD COLUMN kcaa_approval_required INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass  # Column already exists
        try:
            await db.execute("ALTER TABLE documents ADD COLUMN review_due_date TEXT")
        except Exception:
            pass  # Column already exists
        # document_versions: kcaa_approved, kcaa_approved_by, kcaa_approved_at
        try:
            await db.execute("ALTER TABLE document_versions ADD COLUMN kcaa_approved INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE document_versions ADD COLUMN kcaa_approved_by TEXT")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE document_versions ADD COLUMN kcaa_approved_at TEXT")
        except Exception:
            pass
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
            try:
                await db.execute(f"ALTER TABLE document_proposals ADD COLUMN {column} {column_type}")
            except Exception:
                pass
        await db.commit()
    finally:
        await db.close()

    # Seed data
    await seed_db()
    await apply_catalogue_corrections()
    await repair_manual_content_assignment()

async def apply_catalogue_corrections():
    """Keep controlled-document catalogue metadata aligned with the approved manual names."""
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
            return

        from datetime import datetime, timedelta
        now_dt = datetime.now()
        now = now_dt.isoformat()
        two_years = (now_dt + timedelta(days=730)).strftime('%Y-%m-%d')
        six_months = (now_dt + timedelta(days=180)).strftime('%Y-%m-%d')
        users = [
            ("u-admin", "admin", "admin@kfl.aero", "Mohamed Alsayed", "system_admin", "IT", now, now),
            ("u-lib", "librarian", "librarian@kfl.aero", "Eric Otieno", "librarian", "Quality", now, now),
            ("u-quality", "quality", "quality@kfl.aero", "Eric Otieno", "head_quality", "Quality", now, now),
            ("u-safety", "safety", "safety@kfl.aero", "Brian Swanya", "head_safety", "Safety", now, now),
            ("u-security", "security", "security@kfl.aero", "Brian Swanya", "head_security", "Security", now, now),
            ("u-ops", "ops", "ops@kfl.aero", "Utana Kinuthia", "head_operations", "Operations", now, now),
            ("u-chief-pilot", "chief_pilot", "chiefpilot@kfl.aero", "Utana Kinuthia", "chief_pilot", "Operations", now, now),
            ("u-flight-ops", "flight_ops", "flightops@kfl.aero", "Emmanuel Koome", "flight_ops_officer", "Operations", now, now),
            ("u-training", "training", "training@kfl.aero", "Utana Kinuthia", "head_training", "Training", now, now),
            ("u-maintenance", "maintenance", "maintenance@kfl.aero", "Mohamed Alsayed", "head_maintenance", "Maintenance", now, now),
            ("u-dg", "dg_coordinator", "dg@kfl.aero", "Emmanuel Koome", "dg_coordinator", "Operations", now, now),
            ("u-reporter", "reporter", "reporter@kfl.aero", "Occurrence Reporter", "occurrence_reporter", "Safety", now, now),
            ("u-auditor", "auditor", "auditor@kfl.aero", "Independent Auditor", "independent_auditor", "Quality", now, now),
            ("u-records", "records_custodian", "records@kfl.aero", "Eric Otieno", "records_custodian", "Quality", now, now),
            ("u-accountable", "accountable", "accountable@kfl.aero", "Cleopa Otieno", "accountable_manager", "Executive", now, now),
        ]
        for u in users:
            await db.execute(
                "INSERT INTO users (user_id, username, email, full_name, role, department, is_active, created_at, updated_at) VALUES (?,?,?,?,?,?,1,?,?)",
                (u[0], u[1], u[2], u[3], u[4], u[5], now, now),
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
        await db.execute(
            """INSERT INTO roc_register (roc_id, roc_number, serial_number, kcaa_reference, issue_date, expiry_date, status, categories, bvlos_authorized, night_authorized, max_altitude_agl, evlos_authorized, dg_category, notes, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("ROC-001", "06", "0110", "KCAA/OPS/2117/ROC/06", "2026-10-12", "2027-10-11", "active", "A,B", 0, 0, 400, 1, "Division 6.2 Cat A&B", "EVLOS with qualified VO", now, now, "admin", "admin"),
        )

        # Aircraft / UAS Fleet (21 aircraft from registry)
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
                """INSERT INTO aircraft (aircraft_id, registration, model, manufacturer, serial_number, roc_id, status, category, weight_class, max_takeoff_weight_kg, acquired_date, notes, created_at, updated_at, created_by, updated_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ac,
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
    print("Database seeded successfully")