"""Authentication middleware for the Aviation DMS.

Browser/API requests use server-managed HTTP-only sessions with CSRF checks.
Development mode may supplement sessions with an explicit, allow-listed header
pair (X-Role / X-Actor) for local work; that path never accepts arbitrary values
and is strictly limited on loopback origins. There is no Bearer-token fallback
or privileged default identity."""

import os
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .database import get_db
from .rbac import ROLE_PERMISSIONS

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
KNOWN_ROLES = set(ROLE_PERMISSIONS)
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "28800"))
SESSION_ABSOLUTE_MAX_SECONDS = max(1, int(os.getenv("SESSION_ABSOLUTE_MAX_SECONDS", "86400")))
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", str(not DEV_MODE)).lower() == "true"
SESSION_COOKIE = "__Host-kfl_session" if SESSION_COOKIE_SECURE else "kfl_session"
CSRF_COOKIE = "__Host-kfl_csrf" if SESSION_COOKIE_SECURE else "kfl_csrf"

_raw_origins = os.getenv("AUTH_ALLOWED_ORIGINS", os.getenv("CORS_ORIGINS", "http://localhost:5173" if DEV_MODE else ""))
AUTH_ALLOWED_ORIGINS = {origin.strip().rstrip("/") for origin in _raw_origins.split(",") if origin.strip()}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return DEV_MODE
    return origin.rstrip("/") in AUTH_ALLOWED_ORIGINS


def _unauthorized(detail: str = "Authentication required") -> JSONResponse:
    response = JSONResponse(status_code=401, content={"detail": detail}, headers={"Cache-Control": "no-store"})
    response.delete_cookie(SESSION_COOKIE, path="/", secure=SESSION_COOKIE_SECURE, httponly=True, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=SESSION_COOKIE_SECURE, httponly=False, samesite="strict")
    return response


# Development identity headers are allow-listed role contexts. Account aliases
# resolve to the same canonical actor so local tests exercise production SoD identity.
DEV_IDENTITY_ROLES = {
    "admin": ("u-admin", "system_admin"),
    "u-admin": ("u-admin", "system_admin"),
    "u-maintenance": ("u-admin", "head_maintenance"),
    "u-lib": ("u-quality", "librarian"),
    "u-quality": ("u-quality", "head_quality"),
    "u-records": ("u-quality", "records_custodian"),
    "u-safety": ("u-safety/security", "head_safety"),
    "u-security": ("u-safety/security", "head_security"),
    "u-safety/security": ("u-safety/security", "head_safety"),
    "u-ops": ("u-ops", "head_operations"),
    "u-chief-pilot": ("u-ops", "chief_pilot"),
    "u-training": ("u-ops", "head_training"),
    "u-flight-ops": ("u-flight-ops", "flight_ops_officer"),
    "u-dg": ("u-flight-ops", "dg_coordinator"),
    "u-reporter": ("u-reporter", "occurrence_reporter"),
    "reporter": ("u-reporter", "occurrence_reporter"),
    "u-auditor": ("u-auditor", "independent_auditor"),
    "u-accountable": ("u-accountable", "accountable_manager"),
}

# JWT configuration
# NOTE: JWT/Bearer authentication is NOT implemented in this release.
# Production authentication is session-cookie based (HTTP-only __Host-kfl_session
# + __Host-kfl_csrf CSRF pair). These JWT settings are reserved for a future
# release and MUST NOT be used to issue or accept bearer tokens in production.
JWT_SECRET = os.getenv("JWT_SECRET", "")
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


def same_principal(request: Request, other_actor_id: str | None) -> bool:
    """Compare a stored historical actor ID to the current canonical principal."""
    return bool(other_actor_id and other_actor_id in getattr(request.state, "actor_aliases", {getattr(request.state, "actor", "")}))


class P0AuthMiddleware(BaseHTTPMiddleware):
    """Session-first auth for browser/API routes; DEV_MODE headers are an explicit local-only test path."""

    PUBLIC_PATHS = frozenset({
        "/api/p0/auth/login",
        "/api/p0/auth/bootstrap-status",
        "/api/p0/auth/bootstrap",
        "/api/p0/auth/password-setup",
        "/api/p0/auth/forgot-password",
        "/api/p0/auth/reset-password",
    })
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
    API_PREFIXES = ("/api/p0", "/api/p1", "/api/p2", "/api/p3")

    async def _load_session(self, token: str):
        db = await get_db()
        try:
            cursor = await db.execute(
                """SELECT s.session_id, s.user_id, s.active_role, s.csrf_token_hash, s.created_at, s.expires_at, s.revoked_at,
                          u.username, u.full_name, u.email, u.role AS primary_role, u.department, u.is_active
                     FROM auth_sessions s JOIN users u ON u.user_id = s.user_id
                     WHERE s.token_hash = ?""",
                (_sha256(token),),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            session = dict(row)
            expiry = datetime.fromisoformat(session["expires_at"])
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            created_at = datetime.fromisoformat(session["created_at"])
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            auth_now = datetime.now(timezone.utc)
            absolute_max = created_at + timedelta(seconds=SESSION_ABSOLUTE_MAX_SECONDS)
            if session["revoked_at"] or not session["is_active"] or expiry <= auth_now or auth_now >= absolute_max:
                await db.execute(
                    "UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE session_id = ?",
                    (auth_now.isoformat(), session["session_id"]),
                )
                await db.commit()
                return None

            # Sliding expiration can never extend a session beyond its creation-time cap.
            new_expiry = min(auth_now + timedelta(seconds=SESSION_TTL_SECONDS), absolute_max)
            await db.execute(
                "UPDATE auth_sessions SET last_seen_at = ?, expires_at = ? WHERE session_id = ?",
                (auth_now.isoformat(), new_expiry.isoformat(), session["session_id"]),
            )
            await db.commit()

            cursor = await db.execute("SELECT role FROM user_roles WHERE user_id = ? ORDER BY role", (session["user_id"],))
            roles = [role_row["role"] for role_row in await cursor.fetchall()]
            active_role = session["active_role"] or session["primary_role"]
            if active_role not in KNOWN_ROLES or active_role not in roles:
                return None
            cursor = await db.execute(
                "SELECT legacy_user_id FROM user_id_aliases WHERE canonical_user_id = ?",
                (session["user_id"],),
            )
            session["roles"] = roles
            session["role"] = active_role
            session["actor_aliases"] = {row["legacy_user_id"] for row in await cursor.fetchall()} | {session["user_id"]}
            return session
        finally:
            await db.close()

    async def _load_dev_identity(self, actor: str):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT is_active FROM users WHERE user_id = ?", (actor,))
            user = await cursor.fetchone()
            if not user or not user["is_active"]:
                return None
            cursor = await db.execute("SELECT role FROM user_roles WHERE user_id = ? ORDER BY role", (actor,))
            roles = [row["role"] for row in await cursor.fetchall()]
            cursor = await db.execute("SELECT legacy_user_id FROM user_id_aliases WHERE canonical_user_id = ?", (actor,))
            aliases = {row["legacy_user_id"] for row in await cursor.fetchall()} | {actor}
            return roles, aliases
        finally:
            await db.close()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith(self.API_PREFIXES) or request.method == "OPTIONS":
            return await call_next(request)

        if path in self.PUBLIC_PATHS:
            if request.method not in self.SAFE_METHODS and not _origin_allowed(request.headers.get("origin")):
                return JSONResponse(status_code=403, content={"detail": "Untrusted request origin"})
            request.state.actor = None
            request.state.role = None
            request.state.authenticated_via = "public"
            return await call_next(request)

        raw_token = request.cookies.get(SESSION_COOKIE)
        if raw_token:
            try:
                session = await self._load_session(raw_token)
            except Exception:
                return JSONResponse(status_code=503, content={"detail": "Authentication service unavailable"})
            if not session:
                return _unauthorized("Invalid or expired session")
            if request.method not in self.SAFE_METHODS:
                if not _origin_allowed(request.headers.get("origin")):
                    return JSONResponse(status_code=403, content={"detail": "Untrusted request origin"})
                csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
                csrf_header = request.headers.get("X-CSRF-Token", "")
                if (
                    not csrf_cookie
                    or not csrf_header
                    or not hmac.compare_digest(csrf_cookie, csrf_header)
                    or not hmac.compare_digest(_sha256(csrf_cookie), session["csrf_token_hash"])
                ):
                    return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
            request.state.actor = session["user_id"]
            request.state.role = session["role"]
            request.state.active_role = session["role"]
            request.state.roles = session["roles"]
            request.state.actor_aliases = session["actor_aliases"]
            request.state.authenticated_via = "session_cookie"
            request.state.session_id = session["session_id"]
            return await call_next(request)

        if DEV_MODE:
            raw_role = request.headers.get("X-Role")
            raw_actor = request.headers.get("X-Actor")
            if not raw_role or not raw_actor:
                return _unauthorized("Development identity headers are required")
            try:
                actor, role = validate_dev_identity(raw_actor, raw_role)
                identity = await self._load_dev_identity(actor)
            except ValueError as exc:
                return JSONResponse(status_code=401, content={"detail": str(exc)})
            except Exception:
                return JSONResponse(status_code=503, content={"detail": "Authentication service unavailable"})
            if not identity or role not in identity[0]:
                return JSONResponse(status_code=401, content={"detail": "Development role is not assigned to this account"})
            roles, actor_aliases = identity
            request.state.role = role
            request.state.active_role = role
            request.state.roles = roles
            request.state.actor_aliases = actor_aliases
            request.state.actor = actor
            request.state.authenticated_via = "development_identity"
            request.state.session_id = None
            return await call_next(request)

        return _unauthorized("Session cookie required")
