"""P0 Pydantic models."""
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime


class DocClass(str, Enum):
    operations_manual = "operations_manual"
    safety_manual = "safety_manual"
    maintenance_manual = "maintenance_manual"
    training_manual = "training_manual"
    emergency_plan = "emergency_plan"
    sop = "sop"
    checklist = "checklist"
    form = "form"
    policy = "policy"
    procedure = "procedure"


class ApprovalState(str, Enum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    kcaa_pending = "kcaa_pending"
    kcaa_approved = "kcaa_approved"
    published = "published"
    obsolete = "obsolete"


class ChangeStatus(str, Enum):
    open = "open"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    implemented = "implemented"
    closed = "closed"


class Classification(str, Enum):
    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"


class DocumentCreate(BaseModel):
    title: str
    doc_class: str
    classification: str = "S2"
    description: Optional[str] = None
    tags: Optional[str] = None
    owner_id: str
    kcaa_approval_required: bool = False
    review_due_date: Optional[str] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    doc_class: Optional[str] = None
    classification: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    owner_id: Optional[str] = None
    kcaa_approval_required: Optional[bool] = None
    review_due_date: Optional[str] = None


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    doc_class: str
    classification: str
    status: str
    owner_id: str
    description: Optional[str] = None
    tags: Optional[str] = None
    current_version_id: Optional[str] = None
    kcaa_approval_required: bool = False
    review_due_date: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class DocumentVersionCreate(BaseModel):
    document_id: str
    version_number: str
    content: Optional[str] = None
    change_summary: Optional[str] = None


class DocumentVersionResponse(BaseModel):
    version_id: str
    document_id: str
    version_number: str
    state: str
    content: Optional[str] = None
    change_summary: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    kcaa_approved: int = 0
    kcaa_approved_by: Optional[str] = None
    kcaa_approved_at: Optional[str] = None
    published_at: Optional[str] = None
    kcaa_reference: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class ChangeRequestCreate(BaseModel):
    document_id: str
    version_id: Optional[str] = None
    title: str
    description: str
    change_type: str = "minor"


class ChangeRequestResponse(BaseModel):
    cr_id: str
    document_id: str
    version_id: Optional[str] = None
    title: str
    description: str
    change_type: str
    status: str
    requester_id: str
    reviewer_id: Optional[str] = None
    approver_id: Optional[str] = None
    reviewed_at: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class DistributionCreate(BaseModel):
    version_id: str
    recipient_id: str
    channel: str = "email"


class DistributionResponse(BaseModel):
    distribution_id: str
    version_id: str
    recipient_id: str
    channel: str
    status: str
    sent_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class RetentionRuleResponse(BaseModel):
    rule_id: str
    record_class: str
    description: Optional[str] = None
    statutory_years: Optional[int] = None
    kfl_policy_years: Optional[int] = None
    trigger_event: Optional[str] = None
    disposal_method: Optional[str] = None
    classification: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class LegalHoldCreate(BaseModel):
    entity_type: str
    entity_id: str
    reason: str


class LegalHoldResponse(BaseModel):
    hold_id: str
    entity_type: str
    entity_id: str
    reason: str
    imposed_by: str
    imposed_at: str
    released_by: Optional[str] = None
    released_at: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


class ComplianceObligationResponse(BaseModel):
    obligation_id: str
    reference: str
    title: str
    description: Optional[str] = None
    source: Optional[str] = None
    due_date: Optional[str] = None
    status: str
    owner_id: Optional[str] = None
    evidence: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str


class RegulatoryReferenceResponse(BaseModel):
    ref_id: str
    source: str
    title: str
    section: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    created_at: str
    updated_at: str


class AuditEventResponse(BaseModel):
    event_id: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: str
    details: Optional[str] = None
    timestamp: str


# --- Document Content ---
class DocumentContentUpdate(BaseModel):
    content: str
    change_summary: Optional[str] = None
    version_number: Optional[str] = None


class DocumentContentResponse(BaseModel):
    document_id: str
    version_id: str
    version_number: str
    state: str
    content: Optional[str] = None
    change_summary: Optional[str] = None
    kcaa_approved: int = 0
    created_at: str
    updated_at: str
