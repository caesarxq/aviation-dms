"""RBAC engine for Aviation DMS."""
ROLES = [
    "system_admin", "librarian", "head_quality", "head_safety", "head_security",
    "head_operations", "chief_pilot", "flight_ops_officer", "head_training",
    "head_maintenance", "dg_coordinator", "occurrence_reporter", "records_custodian",
    "independent_auditor", "as_contracted",
]

PERMISSIONS = [
    "document:create", "document:read", "document:update", "document:delete",
    "document:approve", "document:publish", "change_request:create", "change_request:review",
    "change_request:approve", "distribution:manage", "retention:manage", "legal_hold:manage",
    "compliance:read", "compliance:manage", "audit:read", "audit:manage",
    "safety:read", "safety:create", "safety:update", "safety:close",
    "occurrence:report", "occurrence:acknowledge", "occurrence:investigate",
    "roc:read", "roc:manage", "aircraft:read", "aircraft:manage",
]

ROLE_PERMISSIONS = {
    "system_admin": set(PERMISSIONS),
    "librarian": {"document:create", "document:read", "document:update", "change_request:create", "distribution:manage", "retention:manage", "legal_hold:manage", "compliance:read", "audit:read", "safety:read", "roc:read", "aircraft:read"},
    "head_quality": {"document:read", "document:approve", "document:publish", "change_request:review", "change_request:approve", "compliance:read", "compliance:manage", "audit:read", "safety:read", "safety:close", "roc:read", "aircraft:read"},
    "head_safety": {"document:read", "safety:read", "safety:create", "safety:update", "safety:close", "occurrence:acknowledge", "occurrence:investigate", "roc:read", "aircraft:read", "audit:read"},
    "head_security": {"document:read", "safety:read", "safety:create", "audit:read", "roc:read", "aircraft:read"},
    "head_operations": {"document:read", "safety:read", "safety:create", "roc:read", "roc:manage", "aircraft:read", "aircraft:manage", "compliance:read", "audit:read"},
    "chief_pilot": {"document:read", "safety:read", "safety:create", "roc:read", "aircraft:read", "audit:read"},
    "flight_ops_officer": {"document:read", "safety:read", "safety:create", "roc:read", "aircraft:read"},
    "head_training": {"document:read", "safety:read", "safety:create", "roc:read", "aircraft:read"},
    "head_maintenance": {"document:read", "safety:read", "safety:create", "roc:read", "aircraft:read", "aircraft:manage", "audit:read"},
    "dg_coordinator": {"document:read", "safety:read", "safety:create", "roc:read", "aircraft:read"},
    "occurrence_reporter": {"safety:read", "safety:create", "occurrence:report", "roc:read", "aircraft:read"},
    "records_custodian": {"document:read", "retention:manage", "legal_hold:manage", "compliance:read", "audit:read", "roc:read", "aircraft:read"},
    "independent_auditor": {"document:read", "audit:read", "audit:manage", "compliance:read", "safety:read", "roc:read", "aircraft:read"},
    "as_contracted": {"document:read", "safety:read", "roc:read", "aircraft:read"},
}

SOD_RULES = {
    "change_request": {"proposer_cannot": ["approve", "reject", "publish"]},
    "version": {"proposer_cannot": ["approve", "publish"]},
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def check_sod(entity_type: str, action: str, actor_id: str, owner_id: str) -> bool:
    if entity_type in SOD_RULES:
        rule = SOD_RULES[entity_type]
        if action in rule.get("proposer_cannot", []):
            return actor_id != owner_id
    return True
