"""P1 Pydantic models."""
from pydantic import BaseModel
from typing import Optional
from enum import Enum


class OccurrenceType(str, Enum):
    accident = "accident"
    serious_incident = "serious_incident"
    incident = "incident"
    hazard = "hazard"
    near_miss = "near_miss"


class OccurrenceSeverity(str, Enum):
    catastrophic = "catastrophic"
    hazardous = "hazardous"
    major = "major"
    minor = "minor"
    negligible = "negligible"


class OccurrenceCreate(BaseModel):
    title: str
    description: str
    occurrence_type: str = "incident"
    severity: str = "minor"
    reporter_confidential: bool = False
    location: Optional[str] = None
    occurred_at: Optional[str] = None
    mor_required: bool = False
    mor_deadline: Optional[str] = None


class OccurrenceUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    occurrence_type: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    occurred_at: Optional[str] = None
    mor_required: Optional[bool] = None
    mor_deadline: Optional[str] = None
    mor_submitted_at: Optional[str] = None


class OccurrenceResponse(BaseModel):
    occurrence_id: str
    serial_number: Optional[str] = None
    title: str
    description: str
    occurrence_type: str
    severity: str
    status: str
    reporter_id: Optional[str] = None
    reporter_confidential: bool = False
    location: Optional[str] = None
    occurred_at: Optional[str] = None
    reported_at: str
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    mor_required: bool = False
    mor_deadline: Optional[str] = None
    mor_submitted_at: Optional[str] = None
    investigation_id: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class HazardCreate(BaseModel):
    title: str
    description: str
    category: str = "operational"
    risk_level: str = "medium"
    likelihood: Optional[str] = None
    severity: Optional[str] = None
    mitigation: Optional[str] = None
    owner_id: Optional[str] = None


class HazardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    likelihood: Optional[str] = None
    severity: Optional[str] = None
    mitigation: Optional[str] = None
    owner_id: Optional[str] = None


class HazardResponse(BaseModel):
    hazard_id: str
    title: str
    description: str
    category: str
    status: str
    risk_level: str
    likelihood: Optional[str] = None
    severity: Optional[str] = None
    mitigation: Optional[str] = None
    owner_id: Optional[str] = None
    identified_by: Optional[str] = None
    identified_at: str
    reviewed_at: Optional[str] = None
    closed_at: Optional[str] = None
    created_at: str
    updated_at: str


class RiskAssessmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    hazard_id: Optional[str] = None
    occurrence_id: Optional[str] = None
    mission_id: Optional[str] = None
    likelihood: str = "possible"
    severity: str = "minor"
    risk_level: str = "medium"
    mitigation_measures: Optional[str] = None
    residual_risk: Optional[str] = None


class RiskAssessmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    likelihood: Optional[str] = None
    severity: Optional[str] = None
    risk_level: Optional[str] = None
    mitigation_measures: Optional[str] = None
    residual_risk: Optional[str] = None
    status: Optional[str] = None
    reviewed_by: Optional[str] = None


class RiskAssessmentResponse(BaseModel):
    assessment_id: str
    hazard_id: Optional[str] = None
    occurrence_id: Optional[str] = None
    mission_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    likelihood: str
    severity: str
    risk_level: str
    mitigation_measures: Optional[str] = None
    residual_risk: Optional[str] = None
    assessor_id: str
    assessed_at: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InvestigationCreate(BaseModel):
    occurrence_id: str
    investigator_id: str
    findings: Optional[str] = None
    root_cause: Optional[str] = None
    recommendations: Optional[str] = None


class InvestigationUpdate(BaseModel):
    status: Optional[str] = None
    findings: Optional[str] = None
    root_cause: Optional[str] = None
    recommendations: Optional[str] = None
    completed_at: Optional[str] = None


class InvestigationResponse(BaseModel):
    investigation_id: str
    occurrence_id: str
    investigator_id: str
    status: str
    findings: Optional[str] = None
    root_cause: Optional[str] = None
    recommendations: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str


class SafetyActionCreate(BaseModel):
    title: str
    description: str
    action_type: str = "corrective"
    owner_id: str
    due_date: Optional[str] = None
    occurrence_id: Optional[str] = None
    hazard_id: Optional[str] = None
    investigation_id: Optional[str] = None


class SafetyActionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    action_type: Optional[str] = None
    owner_id: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    evidence: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    effectiveness_check: Optional[str] = None
    closed_at: Optional[str] = None


class SafetyActionResponse(BaseModel):
    action_id: str
    occurrence_id: Optional[str] = None
    hazard_id: Optional[str] = None
    investigation_id: Optional[str] = None
    title: str
    description: str
    action_type: str
    owner_id: str
    due_date: Optional[str] = None
    status: str
    evidence: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    effectiveness_check: Optional[str] = None
    closed_at: Optional[str] = None
    created_at: str
    updated_at: str


class SafetyTrendsResponse(BaseModel):
    occurrences_by_type: dict = {}
    occurrences_by_severity: dict = {}
    safety_actions_by_status: dict = {}
    hazards_by_risk_level: dict = {}
    occurrences_last_30_days: int = 0


class ROCRegisterCreate(BaseModel):
    roc_number: str
    serial_number: Optional[str] = None
    kcaa_reference: Optional[str] = None
    issue_date: str
    expiry_date: str
    categories: Optional[str] = None
    bvlos_authorized: bool = False
    night_authorized: bool = False
    max_altitude_agl: Optional[int] = None
    evlos_authorized: bool = False
    dg_category: Optional[str] = None
    notes: Optional[str] = None


class ROCRegisterUpdate(BaseModel):
    roc_number: Optional[str] = None
    serial_number: Optional[str] = None
    kcaa_reference: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    categories: Optional[str] = None
    bvlos_authorized: Optional[bool] = None
    night_authorized: Optional[bool] = None
    max_altitude_agl: Optional[int] = None
    evlos_authorized: Optional[bool] = None
    dg_category: Optional[str] = None
    notes: Optional[str] = None


class ROCRegisterResponse(BaseModel):
    roc_id: str
    roc_number: str
    serial_number: Optional[str] = None
    kcaa_reference: Optional[str] = None
    issue_date: str
    expiry_date: str
    status: str
    categories: Optional[str] = None
    bvlos_authorized: bool = False
    night_authorized: bool = False
    max_altitude_agl: Optional[int] = None
    evlos_authorized: bool = False
    dg_category: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class AircraftCreate(BaseModel):
    registration: str
    model: str
    manufacturer: Optional[str] = None
    serial_number: Optional[str] = None
    roc_id: Optional[str] = None
    category: Optional[str] = None
    weight_class: Optional[str] = None
    max_takeoff_weight_kg: Optional[float] = None
    acquired_date: Optional[str] = None
    notes: Optional[str] = None


class AircraftUpdate(BaseModel):
    registration: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    serial_number: Optional[str] = None
    roc_id: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    weight_class: Optional[str] = None
    max_takeoff_weight_kg: Optional[float] = None
    acquired_date: Optional[str] = None
    notes: Optional[str] = None


class AircraftResponse(BaseModel):
    aircraft_id: str
    registration: str
    model: str
    manufacturer: Optional[str] = None
    serial_number: Optional[str] = None
    roc_id: Optional[str] = None
    status: str
    category: Optional[str] = None
    weight_class: Optional[str] = None
    max_takeoff_weight_kg: Optional[float] = None
    acquired_date: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

# --- Mission Workflow (P1 Phase 3) ---
class MissionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    mission_type: str = "survey"
    priority: str = "normal"
    planned_date: Optional[str] = None
    location: Optional[str] = None
    aircraft_id: Optional[str] = None
    roc_id: Optional[str] = None
    rpas_pilot_id: Optional[str] = None
    visual_observer_id: Optional[str] = None
    dg_category: Optional[str] = None
    max_altitude_agl: Optional[int] = None
    bvlos_required: bool = False
    night_required: bool = False

class MissionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    mission_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    planned_date: Optional[str] = None
    location: Optional[str] = None
    aircraft_id: Optional[str] = None
    roc_id: Optional[str] = None
    rpas_pilot_id: Optional[str] = None
    visual_observer_id: Optional[str] = None
    dg_category: Optional[str] = None
    max_altitude_agl: Optional[int] = None
    bvlos_required: Optional[bool] = None
    night_required: Optional[bool] = None
    risk_assessment_id: Optional[str] = None

class MissionResponse(BaseModel):
    mission_id: str
    title: str
    description: Optional[str] = None
    mission_type: str
    status: str
    priority: str
    planned_date: Optional[str] = None
    location: Optional[str] = None
    aircraft_id: Optional[str] = None
    roc_id: Optional[str] = None
    rpas_pilot_id: Optional[str] = None
    visual_observer_id: Optional[str] = None
    dg_category: Optional[str] = None
    max_altitude_agl: Optional[int] = None
    bvlos_required: bool = False
    night_required: bool = False
    risk_assessment_id: Optional[str] = None
    flight_plan_id: Optional[str] = None
    release_id: Optional[str] = None
    post_flight_report_id: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

class FlightPlanCreate(BaseModel):
    mission_id: str
    route_description: Optional[str] = None
    waypoints: Optional[str] = None
    max_altitude_agl: Optional[int] = None
    estimated_duration_min: Optional[int] = None
    fuel_battery_plan: Optional[str] = None
    weather_minima: Optional[str] = None
    contingency_plan: Optional[str] = None

class FlightPlanResponse(BaseModel):
    plan_id: str
    mission_id: str
    route_description: Optional[str] = None
    waypoints: Optional[str] = None
    max_altitude_agl: Optional[int] = None
    estimated_duration_min: Optional[int] = None
    fuel_battery_plan: Optional[str] = None
    weather_minima: Optional[str] = None
    contingency_plan: Optional[str] = None
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

class FlightReleaseCreate(BaseModel):
    mission_id: str
    plan_id: str
    pre_flight_checklist: Optional[str] = None
    weather_confirmed: bool = False
    crew_confirmed: bool = False
    aircraft_confirmed: bool = False
    notes: Optional[str] = None

class FlightReleaseResponse(BaseModel):
    release_id: str
    mission_id: str
    plan_id: str
    released_by: str
    released_at: str
    pre_flight_checklist: Optional[str] = None
    weather_confirmed: bool = False
    crew_confirmed: bool = False
    aircraft_confirmed: bool = False
    status: str
    notes: Optional[str] = None
    created_at: str

class PostFlightReportCreate(BaseModel):
    mission_id: str
    actual_duration_min: Optional[int] = None
    actual_max_altitude: Optional[int] = None
    incidents: Optional[str] = None
    anomalies: Optional[str] = None
    battery_cycles: Optional[int] = None
    flight_hours: Optional[float] = None
    data_collected: Optional[str] = None

class PostFlightReportResponse(BaseModel):
    report_id: str
    mission_id: str
    actual_duration_min: Optional[int] = None
    actual_max_altitude: Optional[int] = None
    incidents: Optional[str] = None
    anomalies: Optional[str] = None
    battery_cycles: Optional[int] = None
    flight_hours: Optional[float] = None
    data_collected: Optional[str] = None
    submitted_by: str
    submitted_at: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    status: str
    created_at: str
    updated_at: str

# --- Quality Audit & CAR (P1 Phase 4) ---
class QualityAuditCreate(BaseModel):
    title: str
    audit_type: str = "internal"
    scope: Optional[str] = None
    auditor_id: str
    auditee_id: Optional[str] = None
    planned_date: Optional[str] = None

class QualityAuditUpdate(BaseModel):
    title: Optional[str] = None
    audit_type: Optional[str] = None
    scope: Optional[str] = None
    auditee_id: Optional[str] = None
    planned_date: Optional[str] = None
    actual_date: Optional[str] = None
    status: Optional[str] = None
    overall_result: Optional[str] = None
    report: Optional[str] = None

class QualityAuditResponse(BaseModel):
    audit_id: str
    title: str
    audit_type: str
    scope: Optional[str] = None
    auditor_id: str
    auditee_id: Optional[str] = None
    planned_date: Optional[str] = None
    actual_date: Optional[str] = None
    status: str
    findings_count: int = 0
    overall_result: Optional[str] = None
    report: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

class AuditFindingCreate(BaseModel):
    audit_id: str
    finding_type: str = "observation"
    description: str
    severity: str = "minor"
    root_cause: Optional[str] = None
    evidence: Optional[str] = None

class AuditFindingResponse(BaseModel):
    finding_id: str
    audit_id: str
    finding_type: str
    description: str
    severity: str
    root_cause: Optional[str] = None
    evidence: Optional[str] = None
    status: str
    created_at: str
    updated_at: str

class CorrectiveActionCreate(BaseModel):
    title: str
    description: str
    finding_id: Optional[str] = None
    audit_id: Optional[str] = None
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    preventive_action: Optional[str] = None
    owner_id: str
    due_date: Optional[str] = None

class CorrectiveActionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    preventive_action: Optional[str] = None
    owner_id: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    verification: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    closed_at: Optional[str] = None

class CorrectiveActionResponse(BaseModel):
    car_id: str
    finding_id: Optional[str] = None
    audit_id: Optional[str] = None
    title: str
    description: str
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    preventive_action: Optional[str] = None
    owner_id: str
    due_date: Optional[str] = None
    status: str
    verification: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    closed_at: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

# --- Dangerous Goods (P1 Phase 5) ---
class DGShipmentCreate(BaseModel):
    dg_class: str
    proper_shipping_name: str
    un_number: Optional[str] = None
    quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    mission_id: Optional[str] = None
    aircraft_id: Optional[str] = None
    notes: Optional[str] = None

class DGShipmentUpdate(BaseModel):
    dg_class: Optional[str] = None
    proper_shipping_name: Optional[str] = None
    un_number: Optional[str] = None
    quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    mission_id: Optional[str] = None
    aircraft_id: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class DGShipmentResponse(BaseModel):
    shipment_id: str
    dg_class: str
    un_number: Optional[str] = None
    proper_shipping_name: str
    quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    mission_id: Optional[str] = None
    aircraft_id: Optional[str] = None
    status: str
    acceptance_check_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

class DGAcceptanceCheckCreate(BaseModel):
    shipment_id: str
    packaging_ok: bool = False
    marking_ok: bool = False
    labeling_ok: bool = False
    documentation_ok: bool = False
    compatibility_ok: bool = False
    notes: Optional[str] = None

class DGAcceptanceCheckResponse(BaseModel):
    check_id: str
    shipment_id: str
    checked_by: str
    checked_at: str
    packaging_ok: bool
    marking_ok: bool
    labeling_ok: bool
    documentation_ok: bool
    compatibility_ok: bool
    result: str
    notes: Optional[str] = None
    created_at: str

class DGTrainingRecordCreate(BaseModel):
    person_id: str
    training_type: str
    training_date: str
    expiry_date: Optional[str] = None
    certificate_number: Optional[str] = None

class DGTrainingRecordResponse(BaseModel):
    record_id: str
    person_id: str
    training_type: str
    training_date: str
    expiry_date: Optional[str] = None
    certificate_number: Optional[str] = None
    status: str
    created_at: str
    updated_at: str

# --- Security Management (P1 Phase 6) ---
class SecurityIncidentCreate(BaseModel):
    title: str
    description: str
    incident_type: str = "unauthorized_access"
    severity: str = "minor"
    location: Optional[str] = None

class SecurityIncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    incident_type: Optional[str] = None
    severity: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    investigation_notes: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None

class SecurityIncidentResponse(BaseModel):
    incident_id: str
    title: str
    description: str
    incident_type: str
    severity: str
    location: Optional[str] = None
    reported_by: str
    reported_at: str
    status: str
    investigation_notes: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    created_at: str
    updated_at: str

class SecurityAssessmentCreate(BaseModel):
    title: str
    assessment_type: str = "vulnerability"
    scope: Optional[str] = None
    assessor_id: str
    planned_date: Optional[str] = None

class SecurityAssessmentUpdate(BaseModel):
    title: Optional[str] = None
    assessment_type: Optional[str] = None
    scope: Optional[str] = None
    findings: Optional[str] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None
    planned_date: Optional[str] = None
    completed_date: Optional[str] = None
    report: Optional[str] = None

class SecurityAssessmentResponse(BaseModel):
    assessment_id: str
    title: str
    assessment_type: str
    scope: Optional[str] = None
    assessor_id: str
    findings: Optional[str] = None
    risk_level: str
    status: str
    planned_date: Optional[str] = None
    completed_date: Optional[str] = None
    report: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

class SecurityTrainingCreate(BaseModel):
    person_id: str
    training_type: str
    training_date: str
    expiry_date: Optional[str] = None
    certificate_number: Optional[str] = None

class SecurityTrainingResponse(BaseModel):
    training_id: str
    person_id: str
    training_type: str
    training_date: str
    expiry_date: Optional[str] = None
    certificate_number: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


class TrainingRecordCreate(BaseModel):
    person_id: str
    training_category: str
    training_type: str
    training_date: str
    expiry_date: Optional[str] = None
    certificate_number: Optional[str] = None
    notes: Optional[str] = None


class TrainingRecordResponse(BaseModel):
    record_id: str
    person_id: str
    training_category: str
    training_type: str
    training_date: str
    expiry_date: Optional[str] = None
    certificate_number: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: str
    updated_at: str


# --- P2 Models ---
class OutsourcedFunctionCreate(BaseModel):
    provider_name: str
    scope: str
    contract_sla: Optional[str] = None
    applicable_requirements: Optional[str] = None
    assessment_date: Optional[str] = None
    audit_evidence: Optional[str] = None
    issues: Optional[str] = None
    actions: Optional[str] = None

class OutsourcedFunctionUpdate(BaseModel):
    provider_name: Optional[str] = None
    scope: Optional[str] = None
    contract_sla: Optional[str] = None
    applicable_requirements: Optional[str] = None
    assessment_date: Optional[str] = None
    audit_evidence: Optional[str] = None
    issues: Optional[str] = None
    actions: Optional[str] = None
    status: Optional[str] = None

class OutsourcedFunctionResponse(BaseModel):
    function_id: str
    provider_name: str
    scope: str
    contract_sla: Optional[str] = None
    applicable_requirements: Optional[str] = None
    assessment_date: Optional[str] = None
    audit_evidence: Optional[str] = None
    issues: Optional[str] = None
    actions: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

class SafetyKPICreate(BaseModel):
    kpi_name: str
    definition: Optional[str] = None
    target: Optional[str] = None
    period: Optional[str] = None
    current_value: Optional[str] = None
    evidence_source: Optional[str] = None
    trend: Optional[str] = None

class SafetyKPIUpdate(BaseModel):
    kpi_name: Optional[str] = None
    definition: Optional[str] = None
    target: Optional[str] = None
    period: Optional[str] = None
    current_value: Optional[str] = None
    evidence_source: Optional[str] = None
    trend: Optional[str] = None
    status: Optional[str] = None

class SafetyKPIResponse(BaseModel):
    kpi_id: str
    kpi_name: str
    definition: Optional[str] = None
    target: Optional[str] = None
    period: Optional[str] = None
    current_value: Optional[str] = None
    evidence_source: Optional[str] = None
    trend: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

class SecurityReviewCreate(BaseModel):
    meeting_date: str
    attendees: Optional[str] = None
    minutes: Optional[str] = None
    kpi_measures: Optional[str] = None
    audit_findings: Optional[str] = None
    inspection_results: Optional[str] = None
    corrective_actions: Optional[str] = None

class SecurityReviewUpdate(BaseModel):
    meeting_date: Optional[str] = None
    attendees: Optional[str] = None
    minutes: Optional[str] = None
    kpi_measures: Optional[str] = None
    audit_findings: Optional[str] = None
    inspection_results: Optional[str] = None
    corrective_actions: Optional[str] = None
    status: Optional[str] = None

class SecurityReviewResponse(BaseModel):
    review_id: str
    meeting_date: str
    attendees: Optional[str] = None
    minutes: Optional[str] = None
    kpi_measures: Optional[str] = None
    audit_findings: Optional[str] = None
    inspection_results: Optional[str] = None
    corrective_actions: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str

class DGResponsibilityMatrixCreate(BaseModel):
    project_or_route: str
    operation_type: Optional[str] = None
    process_stage: str
    responsible_role: str
    escalation_contact: Optional[str] = None
    handover_point: Optional[str] = None

class DGResponsibilityMatrixUpdate(BaseModel):
    project_or_route: Optional[str] = None
    operation_type: Optional[str] = None
    process_stage: Optional[str] = None
    responsible_role: Optional[str] = None
    escalation_contact: Optional[str] = None
    handover_point: Optional[str] = None
    status: Optional[str] = None

class DGResponsibilityMatrixResponse(BaseModel):
    matrix_id: str
    project_or_route: str
    operation_type: Optional[str] = None
    process_stage: str
    responsible_role: str
    escalation_contact: Optional[str] = None
    handover_point: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str
