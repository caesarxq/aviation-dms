"""P0 Auth middleware - JWT validation and role mapping."""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import os

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

KNOWN_ROLES = {
    "system_admin", "librarian", "head_quality", "head_safety", "head_security",
    "head_operations", "chief_pilot", "flight_ops_officer", "head_training",
    "head_maintenance", "dg_coordinator", "occurrence_reporter", "records_custodian",
    "independent_auditor", "as_contracted",
}

ROLE_MAP = {
    "qms_head": "head_quality",
    "sms_head": "head_safety",
    "security_head": "head_security",
    "ops_head": "head_operations",
    "chief_pilot": "chief_pilot",
    "flight_ops": "flight_ops_officer",
    "training_head": "head_training",
    "maintenance_head": "head_maintenance",
    "dg_coordinator": "dg_coordinator",
    "occurrence_reporter": "occurrence_reporter",
    "records_custodian": "records_custodian",
    "auditor": "independent_auditor",
    "librarian": "librarian",
    "admin": "system_admin",
}


class P0AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/p0") or request.url.path.startswith("/api/p1"):
            if DEV_MODE:
                # Development-only convenience: header-based identity.
                # Not safe for production. Requires explicit DEV_MODE=true.
                role = request.headers.get("X-Role", "system_admin")
                actor = request.headers.get("X-Actor", "admin")
                if role not in KNOWN_ROLES:
                    raise HTTPException(status_code=401, detail=f"Unknown role: {role}")
                request.state.role = role
                request.state.actor = actor
            else:
                # Production: validate JWT.
                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer "):
                    raise HTTPException(status_code=401, detail="Missing token")
                token = auth.split(" ", 1)[1]
                # Fail-closed: no JWT validation infrastructure is wired yet,
                # so every bearer token is rejected until implementation.
                raise HTTPException(status_code=401, detail="JWT validation not implemented")
        else:
            request.state.role = "system_admin"
            request.state.actor = "admin"
        return await call_next(request)
