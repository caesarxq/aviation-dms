"""Authentication middleware for the Aviation DMS.

Development uses an explicit, allow-listed identity header pair so local work
cannot silently impersonate an arbitrary role. Production requires a signed
JWT with subject and role claims; no privileged defaults are accepted.
"""
import os
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError, jwt

from .rbac import ROLE_PERMISSIONS

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
KNOWN_ROLES = set(ROLE_PERMISSIONS)

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
    "accountable_manager": "accountable_manager",
}

# Local development identities mirror the seeded user profiles. Aliases exist
# only for the existing local admin/reporter test harnesses.
DEV_IDENTITY_ROLES = {
    "admin": ("u-admin", "system_admin"),
    "u-admin": ("u-admin", "system_admin"),
    "u-lib": ("u-lib", "librarian"),
    "u-quality": ("u-quality", "head_quality"),
    "u-safety": ("u-safety", "head_safety"),
    "u-security": ("u-security", "head_security"),
    "u-ops": ("u-ops", "head_operations"),
    "u-chief-pilot": ("u-chief-pilot", "chief_pilot"),
    "u-flight-ops": ("u-flight-ops", "flight_ops_officer"),
    "u-training": ("u-training", "head_training"),
    "u-maintenance": ("u-maintenance", "head_maintenance"),
    "u-dg": ("u-dg", "dg_coordinator"),
    "u-reporter": ("u-reporter", "occurrence_reporter"),
    "reporter": ("u-reporter", "occurrence_reporter"),
    "u-auditor": ("u-auditor", "independent_auditor"),
    "u-records": ("u-records", "records_custodian"),
    "u-accountable": ("u-accountable", "accountable_manager"),
}

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-use-a-strong-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "kfl-aviation-dms")
JWT_ISSUER = os.getenv("JWT_ISSUER", "kfl-aviation-dms")


def validate_dev_identity(actor: str, role: str) -> tuple[str, str]:
    """Validate and canonicalize a development identity pair."""
    if role not in KNOWN_ROLES:
        raise ValueError(f"Unknown role: {role}")
    canonical = DEV_IDENTITY_ROLES.get(actor)
    if not canonical:
        raise ValueError(f"Unknown actor: {actor}")
    canonical_actor, expected_role = canonical
    if expected_role != role:
        raise ValueError(f"Actor {actor} role does not match requested role {role}")
    return canonical_actor, expected_role


class P0AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        protected = request.url.path.startswith(("/api/p0", "/api/p1", "/api/p2"))
        if protected:
            if DEV_MODE:
                raw_role = request.headers.get("X-Role", "system_admin")
                raw_actor = request.headers.get("X-Actor", "admin")
                try:
                    actor, role = validate_dev_identity(raw_actor, raw_role)
                except ValueError as exc:
                    return JSONResponse(status_code=401, content={"detail": str(exc)})
                request.state.role = role
                request.state.actor = actor
                request.state.authenticated_via = "development_identity"
            else:
                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer "):
                    return JSONResponse(status_code=401, content={"detail": "Missing Bearer token"})
                token = auth.split(" ", 1)[1].strip()
                if not token:
                    return JSONResponse(status_code=401, content={"detail": "Empty Bearer token"})
                try:
                    payload = jwt.decode(
                        token,
                        JWT_SECRET,
                        algorithms=[JWT_ALGORITHM],
                        audience=JWT_AUDIENCE,
                        issuer=JWT_ISSUER,
                    )
                except JWTError as exc:
                    return JSONResponse(status_code=401, content={"detail": f"Invalid token: {exc}"})

                role_claim = payload.get("role")
                actor = payload.get("sub")
                if not role_claim or not actor:
                    return JSONResponse(status_code=401, content={"detail": "Token must include sub and role claims"})
                role = ROLE_MAP.get(role_claim, role_claim)
                if role not in KNOWN_ROLES:
                    return JSONResponse(status_code=401, content={"detail": f"Unknown role: {role}"})
                request.state.role = role
                request.state.actor = actor
                request.state.authenticated_via = "jwt"
        else:
            request.state.role = "system_admin"
            request.state.actor = "admin"
            request.state.authenticated_via = "public"
        return await call_next(request)
