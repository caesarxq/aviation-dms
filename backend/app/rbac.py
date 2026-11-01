"""Role-based access control for the Aviation DMS.

The role matrix is deliberately explicit.  Every role has a documented access
level and an allow-list of permissions; unknown roles receive no permissions.
"""

ROLES = [
    "system_admin", "accountable_manager", "librarian", "head_quality", "head_safety",
    "head_security", "head_operations", "chief_pilot", "flight_ops_officer", "head_training",
    "head_maintenance", "dg_coordinator", "occurrence_reporter", "records_custodian",
    "independent_auditor", "as_contracted",
]

PERMISSIONS = [
    "document:create", "document:read", "document:update", "document:delete",
    "document:approve", "document:publish", "document:edit", "document:view",
    "document:propose", "document:annotate",
    "change_request:create", "change_request:review",
    "change_request:approve", "distribution:manage", "retention:manage", "legal_hold:manage",
    "compliance:read", "compliance:manage", "audit:read", "audit:manage",
    "safety:read", "safety:create", "safety:update", "safety:close",
    "occurrence:report", "occurrence:acknowledge", "occurrence:investigate",
    "roc:read", "roc:manage", "aircraft:read", "aircraft:manage",
    "aircraft:view", "flight:release", "security:read_sensitive", "security:manage",
    "personnel:read", "personnel:view", "personnel:manage",
    "settings:read", "settings:manage",
]

ROLE_PERMISSIONS = {
    "system_admin": set(PERMISSIONS),
    "accountable_manager": {
        "document:read", "document:approve", "document:publish", "document:propose",
        "change_request:review", "change_request:approve", "compliance:read", "compliance:manage",
        "audit:read", "safety:read", "safety:close", "roc:read", "roc:manage",
        "aircraft:read", "personnel:read", "personnel:view",
        "flight:release", "security:read_sensitive", "security:manage",
    },
    "librarian": {
        "document:create", "document:read", "document:update", "document:propose", "document:annotate",
        "change_request:create", "distribution:manage", "retention:manage", "legal_hold:manage",
        "compliance:read", "audit:read", "safety:read", "roc:read", "aircraft:read",
    },
    "head_quality": {
        "document:read", "document:approve", "document:publish", "document:propose", "document:annotate",
        "change_request:review", "change_request:approve", "compliance:read", "compliance:manage",
        "audit:read", "audit:manage", "safety:read", "safety:create", "safety:update", "safety:close",
        "roc:read", "aircraft:read", "personnel:read", "personnel:view",
    },
    "head_safety": {
        "document:read", "document:propose", "document:annotate", "safety:read", "safety:create",
        "safety:update", "safety:close", "occurrence:acknowledge", "occurrence:investigate",
        "roc:read", "aircraft:read", "audit:read", "personnel:read", "personnel:view",
        "security:read_sensitive",
    },
    "head_security": {
        "document:read", "safety:read", "safety:create", "safety:update", "audit:read", "roc:read", "aircraft:read",
        "personnel:read", "personnel:view", "security:read_sensitive", "security:manage",
    },
    "head_operations": {
        "document:read", "safety:read", "safety:create", "safety:update", "flight:release", "roc:read", "roc:manage", "aircraft:read",
        "aircraft:manage", "aircraft:view", "compliance:read", "audit:read", "personnel:read",
        "personnel:view", "personnel:manage",
    },
    "chief_pilot": {
        "document:read", "safety:read", "safety:create", "flight:release", "roc:read", "aircraft:read", "audit:read",
        "personnel:read", "personnel:view",
    },
    "flight_ops_officer": {
        "document:read", "safety:read", "safety:create", "roc:read", "aircraft:read",
        "personnel:read", "personnel:view",
    },
    "head_training": {
        "document:read", "safety:read", "safety:create", "roc:read", "aircraft:read",
        "personnel:read", "personnel:view", "personnel:manage",
    },
    "head_maintenance": {
        "document:read", "safety:read", "safety:create", "roc:read", "aircraft:read",
        "aircraft:manage", "aircraft:view", "audit:read", "personnel:read", "personnel:view",
    },
    "dg_coordinator": {
        "document:read", "safety:read", "safety:create", "roc:read", "aircraft:read",
        "personnel:read", "personnel:view",
    },
    "occurrence_reporter": {
        "document:read", "safety:read", "safety:create", "occurrence:report", "roc:read", "aircraft:read",
    },
    "records_custodian": {
        "document:read", "retention:manage", "legal_hold:manage", "compliance:read", "audit:read",
        "roc:read", "aircraft:read", "personnel:read", "personnel:view",
    },
    "independent_auditor": {
        "document:read", "audit:read", "audit:manage", "compliance:read",
        "safety:read", "roc:read", "aircraft:read", "personnel:read", "personnel:view",
    },
    "as_contracted": {"document:read", "safety:read", "roc:read", "aircraft:read"},
}

ROLE_DESCRIPTIONS = {
    "system_admin": "Platform administration, configuration, security, and unrestricted control-plane access.",
    "accountable_manager": "Executive oversight with approval authority for controlled operational and compliance workflows.",
    "librarian": "Document registration, metadata, distribution, retention, and change proposal preparation.",
    "head_quality": "Quality assurance, audit, compliance oversight, and controlled document approval/publication.",
    "head_safety": "Safety management, investigation, occurrence acknowledgement, and safety corrective action oversight.",
    "head_security": "Aviation security oversight and security-related safety records access.",
    "head_operations": "Operational control, ROC/fleet administration, and personnel operational records.",
    "chief_pilot": "Flight crew operational access and safety reporting.",
    "flight_ops_officer": "Mission and flight operations access with safety reporting.",
    "head_training": "Training program administration and personnel competency records.",
    "head_maintenance": "Maintenance and aircraft records administration.",
    "dg_coordinator": "Dangerous-goods coordination and operational safety reporting.",
    "occurrence_reporter": "Restricted occurrence and safety reporting only.",
    "records_custodian": "Records retention, legal holds, and controlled records access.",
    "independent_auditor": "Independent audit and compliance review access. Read-only on safety and operational records; no operational write authority (SMS-KFL §2.6).",
    "as_contracted": "Read-only access limited to assigned operational and safety information.",
}

ROLE_ACCESS_LEVELS = {
    "system_admin": "L4 - platform administrator",
    "accountable_manager": "L4 - accountable executive",
    "head_quality": "L3 - control owner",
    "head_safety": "L3 - control owner",
    "head_security": "L3 - control owner",
    "head_operations": "L3 - control owner",
    "head_training": "L3 - control owner",
    "head_maintenance": "L3 - control owner",
    "librarian": "L2 - records operator",
    "chief_pilot": "L2 - operational lead",
    "flight_ops_officer": "L2 - operational user",
    "dg_coordinator": "L2 - specialist user",
    "records_custodian": "L2 - records custodian",
    "independent_auditor": "L2 - independent reviewer",
    "occurrence_reporter": "L1 - reporting user",
    "as_contracted": "L1 - restricted external user",
}

SOD_RULES = {
    "change_request": {"proposer_cannot": ["approve", "reject", "publish"]},
    "version": {"proposer_cannot": ["approve", "publish"]},
}

# Separation-of-duties basis:
# - change_request: ICAO Annex 19 SMS §2.6 / KCAA SMS regulations require that the
#   person who proposes a change cannot independently approve or publish it,
#   ensuring independent review before a controlled document change takes effect.
# - version: Same principle — a document version proposer cannot approve or publish
#   their own version, preventing unilateral changes to controlled documentation.
# These rules are enforced at the application layer in p1_routes.py change request
# and document version endpoints.


def has_permission(role: str, permission: str) -> bool:
    """Return True only when the explicit role allow-list grants permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def role_profile(role: str) -> dict:
    """Return the safe, serializable profile used by admin observability."""
    permissions = sorted(ROLE_PERMISSIONS.get(role, set()))
    return {
        "role": role,
        "description": ROLE_DESCRIPTIONS.get(role, "Unknown role"),
        "access_level": ROLE_ACCESS_LEVELS.get(role, "Unclassified"),
        "permissions": permissions,
    }


def all_role_profiles() -> list[dict]:
    return [role_profile(role) for role in ROLES]


def check_sod(
    entity_type: str,
    action: str,
    actor_id: str,
    owner_id: str,
    actor_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> bool:
    """Compare canonical and retained legacy IDs for transaction-level SoD."""
    if entity_type in SOD_RULES:
        rule = SOD_RULES[entity_type]
        if action in rule.get("proposer_cannot", []):
            return owner_id not in (set(actor_ids) if actor_ids else {actor_id})
    return True
