export interface User {
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  role: string;
  department: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Document {
  document_id: string;
  title: string;
  doc_class: string;
  classification: string;
  status: string;
  owner_id: string;
  description: string | null;
  tags: string | null;
  current_version_id: string | null;
  kcaa_approval_required: boolean;
  review_due_date: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface DocumentVersion {
  version_id: string;
  document_id: string;
  version_number: string;
  state: string;
  content: string | null;
  change_summary: string | null;
  approved_by: string | null;
  approved_at: string | null;
  kcaa_approved: number;
  kcaa_approved_by: string | null;
  kcaa_approved_at: string | null;
  published_at: string | null;
  kcaa_reference: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface Occurrence {
  occurrence_id: string;
  serial_number: string | null;
  title: string;
  description: string;
  occurrence_type: string;
  severity: string;
  status: string;
  reporter_id: string | null;
  reporter_confidential: boolean;
  location: string | null;
  occurred_at: string | null;
  reported_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  mor_required: boolean;
  mor_deadline: string | null;
  mor_submitted_at: string | null;
  investigation_id: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface Hazard {
  hazard_id: string;
  title: string;
  description: string;
  category: string;
  status: string;
  risk_level: string;
  likelihood: string | null;
  severity: string | null;
  mitigation: string | null;
  owner_id: string | null;
  identified_by: string | null;
  identified_at: string;
  reviewed_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SafetyAction {
  action_id: string;
  occurrence_id: string | null;
  hazard_id: string | null;
  investigation_id: string | null;
  title: string;
  description: string;
  action_type: string;
  owner_id: string;
  due_date: string | null;
  status: string;
  evidence: string | null;
  verified_by: string | null;
  verified_at: string | null;
  effectiveness_check: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RiskAssessment {
  assessment_id: string;
  hazard_ids: string[];
  occurrence_id: string | null;
  mission_id: string | null;
  title: string;
  description: string | null;
  likelihood: string;
  severity: string;
  risk_level: string;
  risk_model: string;
  exposure: string | null;
  risk_score: number | null;
  scrutiny_required: boolean;
  flight_cancelled: boolean;
  mitigation_measures: string | null;
  residual_risk: string | null;
  assessor_id: string;
  can_approve_for_current_user?: boolean;
  assessed_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface RiskAssessmentSummary {
  total: number;
  draft: number;
  scrutiny_required: number;
  approved: number;
  cancelled: number;
  high_or_critical: number;
}

export interface Investigation {
  investigation_id: string;
  occurrence_id: string;
  investigator_id: string;
  status: string;
  findings: string | null;
  root_cause: string | null;
  recommendations: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SafetyAction {
  action_id: string;
  occurrence_id: string | null;
  hazard_id: string | null;
  investigation_id: string | null;
  title: string;
  description: string;
  action_type: string;
  owner_id: string;
  due_date: string | null;
  status: string;
  evidence: string | null;
  verified_by: string | null;
  verified_at: string | null;
  effectiveness_check: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditEvent {
  event_id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_id: string;
  details: string | null;
  timestamp: string;
}

export interface TrainingRecord {
  record_id: string;
  person_id: string;
  training_category: string;
  training_type: string;
  training_date: string;
  expiry_date: string | null;
  certificate_number: string | null;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceRecord {
  record_id: string;
  aircraft_registration: string;
  maintenance_type: string;
  description: string;
  performed_by: string;
  performed_at: string;
  next_due: string | null;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CrewMember {
  crew_id: string;
  full_name: string;
  role: string;
  base: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface DutyRecord {
  duty_id: string;
  crew_id: string;
  duty_start: string;
  duty_end: string;
  aircraft_reg: string | null;
  role: string;
  location: string | null;
  block_hours: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CrewQualification {
  qual_id: string;
  crew_id: string;
  qual_type: string;
  rating: string | null;
  issue_date: string;
  expiry_date: string;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Distribution {
  distribution_id: string;
  version_id: string;
  recipient_id: string;
  channel: string;
  status: string;
  sent_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface ROCRegister {
  roc_id: string;
  roc_number: string;
  serial_number: string | null;
  kcaa_reference: string | null;
  issue_date: string;
  expiry_date: string;
  status: string;
  categories: string | null;
  bvlos_authorized: boolean;
  night_authorized: boolean;
  max_altitude_agl: number | null;
  evlos_authorized: boolean;
  dg_category: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface QualityAudit {
  audit_id: string;
  title: string;
  audit_type: string;
  scope: string | null;
  auditor_id: string;
  auditee_id: string | null;
  planned_date: string | null;
  actual_date: string | null;
  status: string;
  findings_count: number;
  overall_result: string | null;
  report: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface AuditFinding {
  finding_id: string;
  audit_id: string;
  finding_type: string;
  description: string;
  severity: string;
  root_cause: string | null;
  evidence: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CorrectiveAction {
  car_id: string;
  finding_id: string | null;
  audit_id: string | null;
  title: string;
  description: string;
  root_cause: string | null;
  corrective_action: string | null;
  preventive_action: string | null;
  owner_id: string;
  due_date: string | null;
  status: string;
  verification: string | null;
  verified_by: string | null;
  verified_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}
export interface DGShipment {
  shipment_id: string;
  dg_class: string;
  un_number: string | null;
  proper_shipping_name: string;
  quantity: string | null;
  packaging_type: string | null;
  shipper: string | null;
  consignee: string | null;
  mission_id: string | null;
  aircraft_id: string | null;
  status: string;
  acceptance_check_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}
export interface SecurityIncident {
  incident_id: string;
  title: string;
  description: string;
  incident_type: string;
  severity: string;
  location: string | null;
  reported_by: string;
  reported_at: string;
  status: string;
  investigation_notes: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
  updated_at: string;
}
export interface OutsourcedFunction {
  function_id: string;
  provider_name: string;
  scope: string;
  contract_sla: string | null;
  applicable_requirements: string | null;
  assessment_date: string | null;
  audit_evidence: string | null;
  issues: string | null;
  actions: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface SafetyKPI {
  kpi_id: string;
  kpi_name: string;
  definition: string | null;
  target: string | null;
  period: string | null;
  current_value: string | null;
  evidence_source: string | null;
  trend: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface SecurityReview {
  review_id: string;
  meeting_date: string;
  attendees: string | null;
  minutes: string | null;
  kpi_measures: string | null;
  audit_findings: string | null;
  inspection_results: string | null;
  corrective_actions: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface DGResponsibilityMatrix {
  matrix_id: string;
  project_or_route: string;
  operation_type: string | null;
  process_stage: string;
  responsible_role: string;
  escalation_contact: string | null;
  handover_point: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface ChangeRequest {
  cr_id: string;
  document_id: string;
  version_id: string | null;
  title: string;
  description: string;
  change_type: string;
  status: string;
  requester_id: string;
  reviewer_id: string | null;
  approver_id: string | null;
  reviewed_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface ReviewComment {
  comment_id: string;
  cr_id: string;
  author_id: string;
  content: string;
  created_at: string;
}

export interface Aircraft {
  manufacturer: string | null;
  serial_number: string | null;
  roc_id: string | null;
  status: string;
  category: string | null;
  weight_class: string | null;
  max_takeoff_weight_kg: number | null;
  acquired_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}
