"""P0 API routes."""
from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse, Response
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import uuid
import json
import re
import bcrypt
import hashlib
import hmac
import os
import stat
import ipaddress
import secrets
import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from collections import Counter

from .database import get_db, DB_PATH
from .audit import log_audit_event
from .rbac import has_permission, check_sod, all_role_profiles, ROLE_PERMISSIONS
from .p0_models import *
from .p0_auth import P0AuthMiddleware, SESSION_COOKIE, CSRF_COOKIE, SESSION_COOKIE_SECURE, SESSION_TTL_SECONDS, DEV_MODE, same_principal
from .upload_safety import (
    UploadMalwareDetected,
    UploadQuotaExceeded,
    UploadSafeguardConfigurationError,
    UploadScannerUnavailable,
    UploadStorageUnavailable,
    ensure_upload_capacity,
    load_upload_safety_policy,
    remove_upload_file,
    scan_upload_bytes,
    store_upload_file,
    upload_storage_lock,
    upload_request_limit,
)
from .upload_validation import UploadContentInvalid, UploadValidationUnavailable, validate_upload_content
from .backup_scheduler import BackupScheduler
from .backup_create import BackupCreateError

router = APIRouter()
TRUSTED_FRONTEND_IP = os.getenv("DMS_TRUSTED_FRONTEND_IP", "172.31.254.3")
KCAA_EVIDENCE_DIR = Path(os.getenv("KCAA_EVIDENCE_DIR", str(Path(DB_PATH).parent / "kcaa-evidence")))
MAX_KCAA_EVIDENCE_BYTES = 10 * 1024 * 1024
DMS_DOCUMENT_STORAGE_DIR = Path(os.getenv("DMS_DOCUMENT_STORAGE_DIR", str(Path(DB_PATH).parent / "document_files")))
MAX_UPLOAD_FILE_BYTES = 10 * 1024 * 1024


def _validated_kcaa_evidence_path(stored_filename: str) -> Path:
    root = KCAA_EVIDENCE_DIR.resolve()
    path = (root / stored_filename).resolve()
    if path.parent != root or path.name != stored_filename:
        raise HTTPException(status_code=400, detail="Invalid KCAA evidence storage path")
    return path


def _hash_kcaa_evidence(path: Path) -> str:
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                total += len(chunk)
                if total > MAX_KCAA_EVIDENCE_BYTES:
                    raise HTTPException(status_code=413, detail="Stored KCAA evidence exceeds the size limit")
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Stored KCAA evidence file is missing") from exc
    return digest.hexdigest()



def _actor(request: Request) -> str:
    return getattr(request.state, "actor", "")


def _role(request: Request) -> str:
    return getattr(request.state, "role", "")


def _check(request: Request, perm: str):
    if not has_permission(_role(request), perm):
        raise HTTPException(status_code=403, detail=f"Permission denied: {perm}")


def _check_document_read(request: Request):
    role = _role(request)
    if not any(has_permission(role, permission) for permission in ("document:read", "document:update", "document:propose")):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: document:read, document:update, or document:propose",
        )


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def now_iso() -> str:
    return datetime.now().isoformat()


def _auth_now() -> datetime:
    return datetime.now(timezone.utc)


def _auth_now_iso() -> str:
    return _auth_now().isoformat()


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_new_password(password: str) -> None:
    encoded = password.encode("utf-8")
    if len(password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    if len(encoded) > 72:
        raise HTTPException(status_code=400, detail="Password must not exceed 72 UTF-8 bytes")


def _safe_user(row, roles: list[str] | None = None, active_role: str | None = None) -> dict:
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": active_role or row["role"],
        "active_role": active_role or row["role"],
        "roles": roles or [],
        "department": row["department"],
    }


def _auth_profile_payload(row, roles: list[str], active_role: str, authenticated_via: str) -> dict:
    """Serialize the same complete, session-scoped profile for every auth entry point."""
    return {
        "user": _safe_user(row, roles, active_role),
        "role": active_role,
        "active_role": active_role,
        "roles": roles,
        "authenticated_via": authenticated_via,
        "permissions": sorted(ROLE_PERMISSIONS[active_role]),
        "onboarding_completed": bool(row["onboarding_completed"]),
    }


async def _create_session(db, user_id: str, active_role: str) -> tuple[str, str]:
    session_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    now = _auth_now()
    await db.execute(
        """INSERT INTO auth_sessions
           (session_id, user_id, active_role, token_hash, csrf_token_hash, created_at, expires_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id, user_id, active_role, _token_hash(token), _token_hash(csrf_token),
            now.isoformat(), (now + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat(), now.isoformat(),
        ),
    )
    return token, csrf_token


def _session_response(payload: dict, token: str, csrf_token: str) -> JSONResponse:
    response = JSONResponse(payload, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_TTL_SECONDS, httponly=True,
        secure=SESSION_COOKIE_SECURE, samesite="strict", path="/",
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token, max_age=SESSION_TTL_SECONDS, httponly=False,
        secure=SESSION_COOKIE_SECURE, samesite="strict", path="/",
    )
    return response


def _clear_session_cookies(response: JSONResponse) -> JSONResponse:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=SESSION_COOKIE_SECURE, httponly=True, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=SESSION_COOKIE_SECURE, httponly=False, samesite="strict")
    response.headers["Cache-Control"] = "no-store"
    return response


def _client_ip(request: Request) -> str:
    """Resolve the login-throttle client IP without trusting arbitrary forwarding headers."""
    peer_ip = request.client.host if request.client else "unknown"
    if peer_ip != TRUSTED_FRONTEND_IP:
        return peer_ip

    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    try:
        # Caddy overwrites XFF with one sanitized address; reject chains and malformed values.
        return str(ipaddress.ip_address(forwarded_for))
    except ValueError:
        return peer_ip


def _request_is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        import ipaddress
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _configured_bootstrap_token() -> str:
    token = os.getenv("KFL_BOOTSTRAP_TOKEN", "").strip()
    if token:
        return token
    token_file = os.getenv("KFL_BOOTSTRAP_TOKEN_FILE", "").strip()
    if not token_file:
        return ""
    try:
        return Path(token_file).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _dummy_password_hash() -> bytes:
    return bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt(rounds=12))


_DUMMY_PASSWORD_HASH = _dummy_password_hash()


@router.get("/auth/profile")
async def current_auth_profile(request: Request):
    """Return the canonical identity, assigned roles, active role, and scoped permissions."""
    actor = _actor(request)
    role = _role(request)
    roles = getattr(request.state, "roles", [])
    if not actor or role not in ROLE_PERMISSIONS or role not in roles:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT user_id, username, email, full_name, role, department, is_active, onboarding_completed "
            "FROM users WHERE user_id = ?",
            (actor,),
        )
        row = await cursor.fetchone()
        if not row or not row["is_active"]:
            raise HTTPException(status_code=401, detail="Authenticated user profile not found or disabled")
        return _auth_profile_payload(
            dict(row), roles, role, getattr(request.state, "authenticated_via", "unknown")
        )
    finally:
        await db.close()


@router.post("/auth/active-role")
async def switch_active_role(body: AuthActiveRoleRequest, request: Request):
    """Switch the current browser session to one of the user's assigned roles."""
    if getattr(request.state, "authenticated_via", "") != "session_cookie":
        raise HTTPException(status_code=401, detail="An authenticated browser session is required")
    actor = _actor(request)
    session_id = getattr(request.state, "session_id", None)
    if not isinstance(session_id, str) or not session_id:
        raise HTTPException(status_code=401, detail="An active browser session is required")
    current_role = _role(request)
    assigned_roles = getattr(request.state, "roles", [])
    if body.active_role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="Unknown role")
    if body.active_role not in assigned_roles:
        raise HTTPException(status_code=403, detail="Role is not assigned to this account")

    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            "UPDATE auth_sessions SET active_role = ? WHERE session_id = ? AND user_id = ? AND revoked_at IS NULL",
            (body.active_role, session_id, actor),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=401, detail="Session is no longer active")
        await log_audit_event(
            "auth_session", session_id, "active_role_switched", actor,
            {"from_role": current_role, "to_role": body.active_role},
            db=db,
        )
        await db.commit()
    except Exception:
        if db.in_transaction:
            await db.rollback()
        raise
    finally:
        await db.close()

    request.state.role = body.active_role
    request.state.active_role = body.active_role
    return await current_auth_profile(request)


@router.get("/auth/users")
async def list_auth_users(request: Request):
    """List canonical active accounts and their explicit assigned roles for administrators."""
    _check(request, "settings:manage")
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT user_id, username, email, full_name, role, department, is_active, password_hash
               FROM users WHERE merged_into_user_id IS NULL ORDER BY full_name, username"""
        )
        users = [dict(row) for row in await cursor.fetchall()]
        for user in users:
            cursor = await db.execute("SELECT role FROM user_roles WHERE user_id = ? ORDER BY role", (user["user_id"],))
            user["roles"] = [row["role"] for row in await cursor.fetchall()]
            user["has_password"] = bool(user["password_hash"])
            del user["password_hash"]
        return users
    finally:
        await db.close()


@router.put("/auth/users/{user_id:path}/roles")
async def update_user_roles(user_id: str, body: AuthUserRolesUpdate, request: Request):
    """Replace a canonical account's role assignments; invalidate sessions after changes."""
    _check(request, "settings:manage")
    roles = sorted(set(body.roles))
    if not roles:
        raise HTTPException(status_code=400, detail="At least one role must remain assigned")
    invalid_roles = sorted(set(roles) - set(ROLE_PERMISSIONS))
    if invalid_roles:
        raise HTTPException(status_code=400, detail=f"Unknown roles: {', '.join(invalid_roles)}")

    db = await get_db()
    actor = _actor(request)
    try:
        cursor = await db.execute(
            "SELECT canonical_user_id FROM user_id_aliases WHERE legacy_user_id = ?", (user_id,)
        )
        alias = await cursor.fetchone()
        canonical_id = alias["canonical_user_id"] if alias else user_id
        cursor = await db.execute(
            "SELECT user_id, username, email, full_name, role, department, is_active "
            "FROM users WHERE user_id = ? AND is_active = 1 AND merged_into_user_id IS NULL",
            (canonical_id,),
        )
        user_row = await cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="Active canonical user not found")
        user = dict(user_row)
        cursor = await db.execute("SELECT role FROM user_roles WHERE user_id = ? ORDER BY role", (canonical_id,))
        current_roles = {row["role"] for row in await cursor.fetchall()}
        if current_roles == set(roles):
            return {"user_id": canonical_id, "roles": roles, "active_sessions_revoked": False}

        if "system_admin" in current_roles and "system_admin" not in roles:
            cursor = await db.execute(
                """SELECT COUNT(DISTINCT u.user_id) FROM users u
                   JOIN user_roles ur ON ur.user_id = u.user_id
                   WHERE u.is_active = 1 AND u.merged_into_user_id IS NULL AND ur.role = 'system_admin'"""
            )
            if (await cursor.fetchone())[0] <= 1:
                raise HTTPException(status_code=409, detail="Cannot remove the last active system administrator")

        default_role = user["role"] if user["role"] in roles else roles[0]
        await db.execute("DELETE FROM user_roles WHERE user_id = ?", (canonical_id,))
        for role in roles:
            await db.execute("INSERT INTO user_roles (user_id, role) VALUES (?, ?)", (canonical_id, role))
        now = _auth_now_iso()
        await db.execute("UPDATE users SET role = ?, updated_at = ? WHERE user_id = ?", (default_role, now, canonical_id))
        await db.execute(
            "UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE user_id = ? AND revoked_at IS NULL",
            (now, canonical_id),
        )
        await db.commit()
    finally:
        await db.close()
    await log_audit_event(
        "user_role_assignments", canonical_id, "roles_replaced", actor,
        {"previous_roles": sorted(current_roles), "roles": roles},
    )
    return {"user_id": canonical_id, "roles": roles, "active_sessions_revoked": True}


@router.post("/auth/login")
async def auth_login(body: AuthLoginRequest, request: Request):
    """Authenticate credentials and issue a short-lived opaque HttpOnly session cookie."""
    username = body.username.strip().lower()
    password = body.password
    client_host = _client_ip(request)
    attempt_key = _token_hash(f"{username}\0{client_host}")
    now = _auth_now()
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute("SELECT * FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        attempt = await cursor.fetchone()
        if attempt:
            attempt = dict(attempt)
            locked_until = datetime.fromisoformat(attempt["locked_until"]) if attempt["locked_until"] else None
            window_start = datetime.fromisoformat(attempt["window_started_at"])
            if locked_until and locked_until > now:
                await db.rollback()
                raise HTTPException(status_code=429, detail="Login temporarily unavailable; try again later")
            if (locked_until and locked_until <= now) or now - window_start > timedelta(minutes=15):
                attempt = None

        cursor = await db.execute(
            """SELECT user_id, username, email, full_name, role, department, is_active, password_hash,
                      onboarding_completed
               FROM users WHERE lower(username) = ?""",
            (username,),
        )
        user_row = await cursor.fetchone()
        user = dict(user_row) if user_row else None
        candidate_hash = user["password_hash"].encode() if user and user.get("password_hash") else _DUMMY_PASSWORD_HASH
        try:
            password_matches = bcrypt.checkpw(password.encode("utf-8"), candidate_hash)
        except (ValueError, TypeError):
            password_matches = False
        valid = bool(user and user["is_active"] and user["password_hash"] and password_matches)
        if not valid:
            failures = (attempt["failure_count"] + 1) if attempt else 1
            window_started = attempt["window_started_at"] if attempt else now.isoformat()
            locked = (now + timedelta(minutes=15)).isoformat() if failures >= 5 else None
            await db.execute(
                """INSERT INTO auth_login_attempts (attempt_key, failure_count, window_started_at, locked_until)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(attempt_key) DO UPDATE SET failure_count = excluded.failure_count,
                     window_started_at = excluded.window_started_at, locked_until = excluded.locked_until""",
                (attempt_key, failures, window_started, locked),
            )
            await db.commit()
            raise HTTPException(status_code=401, detail="Invalid username or password")

        cursor = await db.execute("SELECT role FROM user_roles WHERE user_id = ? ORDER BY role", (user["user_id"],))
        roles = [row["role"] for row in await cursor.fetchall()]
        if not roles:
            await db.rollback()
            raise HTTPException(status_code=401, detail="Invalid username or password")
        active_role = user["role"] if user["role"] in roles else roles[0]
        await db.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        token, csrf_token = await _create_session(db, user["user_id"], active_role)
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("auth_session", user["user_id"], "login", user["user_id"], {"auth_method": "password", "active_role": active_role})
    payload = _auth_profile_payload(user, roles, active_role, "session_cookie")
    payload["message"] = "Login successful"
    return _session_response(payload, token, csrf_token)


@router.get("/auth/bootstrap-status")
async def auth_bootstrap_status(request: Request):
    """Report whether first-admin password enrollment is still available."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT password_hash, is_active FROM users WHERE user_id = 'u-admin'")
        admin = await cursor.fetchone()
        cursor = await db.execute("SELECT value FROM app_settings WHERE key = 'auth_bootstrap_completed'")
        completed = await cursor.fetchone()
        configured = bool(_configured_bootstrap_token()) or (DEV_MODE and _request_is_loopback(request))
        setup_required = bool(admin and admin["is_active"] and not admin["password_hash"] and not completed)
        return {
            "setup_required": setup_required,
            "bootstrap_configured": configured,
            "bootstrap_token_required": bool(_configured_bootstrap_token()),
        }
    finally:
        await db.close()


@router.post("/auth/bootstrap")
async def auth_bootstrap(body: AuthBootstrapRequest, request: Request):
    """Set the initial admin password once, using an operator-provided bootstrap token."""
    _validate_new_password(body.password)
    configured_token = _configured_bootstrap_token()
    local_dev_bootstrap = DEV_MODE and _request_is_loopback(request) and not configured_token
    if not local_dev_bootstrap and (not configured_token or not body.bootstrap_token or not hmac.compare_digest(body.bootstrap_token, configured_token)):
        raise HTTPException(status_code=403, detail="Invalid bootstrap authorization")

    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute("SELECT value FROM app_settings WHERE key = 'auth_bootstrap_completed'")
        if await cursor.fetchone():
            await db.rollback()
            raise HTTPException(status_code=409, detail="Initial administrator setup has already been completed")
        cursor = await db.execute(
            """SELECT user_id, username, email, full_name, role, department, is_active, password_hash,
                      onboarding_completed FROM users WHERE user_id = 'u-admin'"""
        )
        user_row = await cursor.fetchone()
        if not user_row or not user_row["is_active"] or user_row["password_hash"]:
            await db.rollback()
            raise HTTPException(status_code=409, detail="Initial administrator account is not eligible for setup")
        user = dict(user_row)
        now = _auth_now_iso()
        password_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()
        await db.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = 'u-admin'", (password_hash, now))
        await db.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES ('auth_bootstrap_completed', 'true', ?)"
            " ON CONFLICT(key) DO UPDATE SET value = 'true', updated_at = excluded.updated_at",
            (now,),
        )
        cursor = await db.execute("SELECT role FROM user_roles WHERE user_id = ? ORDER BY role", (user["user_id"],))
        roles = [row["role"] for row in await cursor.fetchall()]
        active_role = user["role"] if user["role"] in roles else "system_admin"
        token, csrf_token = await _create_session(db, user["user_id"], active_role)
        await db.commit()
        user["password_hash"] = password_hash
    finally:
        await db.close()
    await log_audit_event("auth_session", user["user_id"], "initial_admin_password_set", user["user_id"], {"active_role": active_role})
    payload = _auth_profile_payload(user, roles, active_role, "session_cookie")
    payload["message"] = "Initial administrator password set"
    return _session_response(payload, token, csrf_token)


@router.post("/auth/users/{user_id:path}/setup-token")
async def issue_password_setup_token(user_id: str, request: Request):
    _check(request, "settings:manage")
    actor = _actor(request)
    raw_token = secrets.token_urlsafe(32)
    now = _auth_now()
    expires = now + timedelta(hours=24)
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT canonical_user_id FROM user_id_aliases WHERE legacy_user_id = ?",
            (user_id,),
        )
        alias = await cursor.fetchone()
        canonical_id = alias["canonical_user_id"] if alias else user_id
        cursor = await db.execute(
            "SELECT user_id, password_hash, is_active FROM users "
            "WHERE user_id = ? AND merged_into_user_id IS NULL",
            (canonical_id,),
        )
        user = await cursor.fetchone()
        if not user or not user["is_active"]:
            raise HTTPException(status_code=404, detail="Active user not found")
        if user["password_hash"]:
            raise HTTPException(status_code=409, detail="User already has a password; use the password-change workflow")
        await db.execute(
            "UPDATE auth_setup_tokens SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
            (now.isoformat(), canonical_id),
        )
        await db.execute(
            "INSERT INTO auth_setup_tokens (setup_id, user_id, token_hash, issued_by, created_at, expires_at) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), canonical_id, _token_hash(raw_token), actor, now.isoformat(), expires.isoformat()),
        )
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("user_auth", canonical_id, "password_setup_token_issued", actor, {"expires_at": expires.isoformat()})
    return {"setup_token": raw_token, "expires_at": expires.isoformat(), "use_once": True}


@router.post("/auth/password-setup")
async def complete_password_setup(body: AuthPasswordSetupRequest, request: Request):
    _validate_new_password(body.password)
    now = _auth_now()
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        # Support both setup_token (username + token) and invite_code (token-only, username pre-filled)
        if body.invite_code:
            cursor = await db.execute(
                """SELECT t.setup_id, t.user_id, t.expires_at, t.used_at, u.password_hash, u.is_active, u.username
                   FROM auth_setup_tokens t JOIN users u ON u.user_id = t.user_id
                   WHERE t.invite_code = ? AND t.purpose = 'invite'""",
                (body.invite_code,),
            )
        else:
            username = body.username.strip().lower()
            cursor = await db.execute(
                """SELECT t.setup_id, t.user_id, t.expires_at, t.used_at, u.password_hash, u.is_active, u.username
                   FROM auth_setup_tokens t JOIN users u ON u.user_id = t.user_id
                   WHERE t.token_hash = ? AND lower(u.username) = ?""",
                (_token_hash(body.setup_token), username),
            )
        row = await cursor.fetchone()
        if not row or row["used_at"] or not row["is_active"] or row["password_hash"] or datetime.fromisoformat(row["expires_at"]) <= now:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Invalid or expired setup token")
        password_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()
        await db.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?", (password_hash, now.isoformat(), row["user_id"]))
        await db.execute("UPDATE auth_setup_tokens SET used_at = ? WHERE setup_id = ?", (now.isoformat(), row["setup_id"]))
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("user_auth", row["user_id"], "password_setup_completed", row["user_id"])
    return JSONResponse({"message": "Password set. Sign in to continue."}, headers={"Cache-Control": "no-store"})


@router.post("/auth/change-password")
async def change_password(body: AuthPasswordChangeRequest, request: Request):
    if getattr(request.state, "authenticated_via", "") != "session_cookie":
        raise HTTPException(status_code=401, detail="An authenticated browser session is required")
    _validate_new_password(body.new_password)
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT password_hash FROM users WHERE user_id = ? AND is_active = 1", (actor,))
        row = await cursor.fetchone()
        if not row or not row["password_hash"] or not bcrypt.checkpw(body.current_password.encode(), row["password_hash"].encode()):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        password_hash = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()
        now = _auth_now_iso()
        await db.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?", (password_hash, now, actor))
        await db.execute(
            "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND session_id != ? AND revoked_at IS NULL",
            (now, actor, request.state.session_id),
        )
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("auth_session", actor, "password_changed_and_sessions_revoked", actor)
    return JSONResponse({"message": "Password changed; other sessions were signed out"}, headers={"Cache-Control": "no-store"})


# --- Invite, forgot-password, reset-password ---

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

def _validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email.strip()):
        raise HTTPException(status_code=400, detail="Invalid email format")

def _generate_invite_code() -> str:
    """Generate a short, human-readable invite code like KFL-ABCD-1234."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    part1 = "".join(secrets.choice(alphabet) for _ in range(4))
    part2 = "".join(secrets.choice("0123456789") for _ in range(4))
    return f"KFL-{part1}-{part2}"


@router.post("/auth/invites", response_model=AuthInviteResponse)
async def issue_invite(body: AuthInviteRequest, request: Request):
    """Issue a one-time invite code for an account to set their password."""
    _check(request, "settings:manage")
    actor = _actor(request)
    client_host = _client_ip(request)

    # Rate limit: max 5 invite requests per actor per 15 minutes
    attempt_key = _token_hash(f"invite\0{actor}\0{client_host}")
    now = _auth_now()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        attempt = await cursor.fetchone()
        if attempt:
            attempt = dict(attempt)
            locked_until = datetime.fromisoformat(attempt["locked_until"]) if attempt["locked_until"] else None
            window_start = datetime.fromisoformat(attempt["window_started_at"])
            if locked_until and locked_until > now:
                await db.rollback()
                raise HTTPException(status_code=429, detail="Invite requests temporarily unavailable; try again later")
            if (locked_until and locked_until <= now) or now - window_start > timedelta(minutes=15):
                attempt = None
        if attempt and attempt["failure_count"] >= 5:
            locked = (now + timedelta(minutes=15)).isoformat()
            await db.execute(
                "UPDATE auth_login_attempts SET locked_until = ? WHERE attempt_key = ?",
                (locked, attempt_key),
            )
            await db.commit()
            await db.close()
            raise HTTPException(status_code=429, detail="Invite requests temporarily unavailable; try again later")

        # Validate email format if provided
        if body.email is not None:
            _validate_email(body.email)

        cursor = await db.execute("SELECT user_id, username, email, full_name, is_active FROM users WHERE lower(username) = ?", (body.username.strip().lower(),))
        user = await cursor.fetchone()
        if not user or not user["is_active"]:
            # Record failed attempt for rate limiting
            failures = (attempt["failure_count"] + 1) if attempt else 1
            window_started = attempt["window_started_at"] if attempt else now.isoformat()
            locked = (now + timedelta(minutes=15)).isoformat() if failures >= 5 else None
            await db.execute(
                """INSERT INTO auth_login_attempts (attempt_key, failure_count, window_started_at, locked_until)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(attempt_key) DO UPDATE SET failure_count = excluded.failure_count,
                   window_started_at = excluded.window_started_at, locked_until = excluded.locked_until""",
                (attempt_key, failures, window_started, locked),
            )
            await db.commit()
            await db.close()
            raise HTTPException(status_code=404, detail="Active user not found")

        # Record successful invite (reset failure count)
        await db.execute(
            """INSERT INTO auth_login_attempts (attempt_key, failure_count, window_started_at, locked_until)
               VALUES (?, 0, ?, NULL)
               ON CONFLICT(attempt_key) DO UPDATE SET failure_count = 0,
               window_started_at = excluded.window_started_at, locked_until = NULL""",
            (attempt_key, now.isoformat()),
        )

        raw_code = _generate_invite_code()
        raw_token = secrets.token_urlsafe(32)
        expires = now + timedelta(hours=24)
        try:
            # Mark any existing unused invite tokens for this user as used
            await db.execute("UPDATE auth_setup_tokens SET used_at = ? WHERE user_id = ? AND purpose = 'invite' AND used_at IS NULL", (now.isoformat(), user["user_id"]))
            await db.execute(
                """INSERT INTO auth_setup_tokens
                   (setup_id, user_id, token_hash, invite_code, purpose, issued_by, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user["user_id"], _token_hash(raw_token), raw_code, "invite", actor, now.isoformat(), expires.isoformat()),
            )
            await db.commit()
        finally:
            await db.close()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        await db.close()
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    await log_audit_event("user_auth", user["user_id"], "invite_issued", actor, {"expires_at": expires.isoformat()})
    return AuthInviteResponse(
        invite_code=raw_code,
        setup_url=f"/setup/invite/{raw_code}",
        expires_at=expires.isoformat(),
    )


@router.post("/auth/forgot-password")
async def forgot_password(body: AuthForgotPasswordRequest, request: Request):
    """Issue a reset link only when it can be delivered; keep responses non-enumerating."""
    username = body.username.strip().lower()
    client_host = _client_ip(request)
    attempt_key = _token_hash(f"forgot\\0{username}\\0{client_host}")
    now = _auth_now()
    reset_token = None
    setup_id = None
    recipient = None
    public_app_url = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    try:
        parsed_app_url = urlsplit(public_app_url)
        hostname = parsed_app_url.hostname or ""
        local_http = DEV_MODE and parsed_app_url.scheme == "http" and hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            parsed_app_url.username
            or parsed_app_url.password
            or parsed_app_url.query
            or parsed_app_url.fragment
            or not hostname
            or (parsed_app_url.scheme != "https" and not local_http)
        ):
            public_app_url = ""
    except ValueError:
        public_app_url = ""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        attempt = await cursor.fetchone()
        if attempt:
            attempt = dict(attempt)
            locked_until = datetime.fromisoformat(attempt["locked_until"]) if attempt["locked_until"] else None
            window_start = datetime.fromisoformat(attempt["window_started_at"])
            if locked_until and locked_until > now:
                await db.rollback()
                raise HTTPException(status_code=429, detail="Request temporarily unavailable; try again later")
            if (locked_until and locked_until <= now) or now - window_start > timedelta(minutes=15):
                attempt = None

        cursor = await db.execute(
            "SELECT user_id, username, email, password_hash, is_active FROM users WHERE lower(username) = ?",
            (username,),
        )
        user = await cursor.fetchone()
        failures = (attempt["failure_count"] + 1) if attempt else 1
        window_started = attempt["window_started_at"] if attempt else now.isoformat()
        locked = (now + timedelta(minutes=15)).isoformat() if failures >= 5 else None
        await db.execute(
            """INSERT INTO auth_login_attempts (attempt_key, failure_count, window_started_at, locked_until)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(attempt_key) DO UPDATE SET failure_count = excluded.failure_count,
                 window_started_at = excluded.window_started_at, locked_until = excluded.locked_until""",
            (attempt_key, failures, window_started, locked),
        )

        if user and user["is_active"] and user["password_hash"] and user["email"] and public_app_url:
            from .notifications import NOTIFICATION_ENABLED, SMTP_HOST
            if NOTIFICATION_ENABLED and SMTP_HOST:
                reset_token = secrets.token_urlsafe(32)
                setup_id = str(uuid.uuid4())
                recipient = user["email"]
                expires = now + timedelta(hours=1)
                await db.execute(
                    """INSERT INTO auth_setup_tokens
                       (setup_id, user_id, token_hash, purpose, issued_by, created_at, expires_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (setup_id, user["user_id"], _token_hash(reset_token), "reset", "system", now.isoformat(), expires.isoformat()),
                )
        await db.commit()
    finally:
        await db.close()

    if reset_token and setup_id and recipient:
        reset_url = f"{public_app_url}/reset-password/{reset_token}"
        from .notifications import send_email
        sent = await asyncio.to_thread(
            send_email,
            recipient,
            "KFL Aviation DMS password reset",
            f"Use this one-time link within one hour to reset your password:\n\n{reset_url}\n\nIf you did not request this, ignore this message.",
            "auth_password_reset",
            setup_id,
            "high",
        )
        if not sent:
            cleanup_db = await get_db()
            try:
                await cleanup_db.execute(
                    "UPDATE auth_setup_tokens SET used_at = ? WHERE setup_id = ? AND used_at IS NULL",
                    (_auth_now_iso(), setup_id),
                )
                await cleanup_db.commit()
            finally:
                await cleanup_db.close()

    return JSONResponse(
        {"message": "If an active account with a password exists, reset instructions will be sent to its registered email."},
        headers={"Cache-Control": "no-store"},
    )



@router.post("/auth/reset-password")
async def reset_password(body: AuthResetPasswordRequest, request: Request):
    """Reset password using a one-time reset token."""
    _validate_new_password(body.new_password)
    now = _auth_now()
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """SELECT t.setup_id, t.user_id, t.expires_at, t.used_at, u.password_hash, u.is_active
               FROM auth_setup_tokens t JOIN users u ON u.user_id = t.user_id
               WHERE t.token_hash = ? AND t.purpose = 'reset'""",
            (_token_hash(body.reset_token),),
        )
        row = await cursor.fetchone()
        if not row or row["used_at"] or not row["is_active"] or datetime.fromisoformat(row["expires_at"]) <= now:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        password_hash = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()
        await db.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?", (password_hash, now.isoformat(), row["user_id"]))
        await db.execute("UPDATE auth_setup_tokens SET used_at = ? WHERE setup_id = ?", (now.isoformat(), row["setup_id"]))
        # Revoke all other sessions for this user
        await db.execute("UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE user_id = ? AND revoked_at IS NULL", (now.isoformat(), row["user_id"]))
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("auth_session", row["user_id"], "password_reset_completed", row["user_id"])
    return JSONResponse({"message": "Password reset. Sign in with your new password."}, headers={"Cache-Control": "no-store"})


# --- Onboarding ---

@router.get("/auth/me/onboarding", response_model=AuthOnboardingResponse)
async def get_onboarding_status(request: Request):
    """Return the onboarding status for the authenticated user."""
    actor = _actor(request)
    roles = getattr(request.state, "roles", [])
    role = _role(request)
    if not actor or role not in ROLE_PERMISSIONS or role not in roles:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT user_id, full_name, onboarding_completed FROM users WHERE user_id = ?", (actor,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Authenticated user profile not found")
        return AuthOnboardingResponse(
            onboarding_completed=bool(row["onboarding_completed"]),
            assigned_roles=roles,
            active_role=role,
            canonical_user_id=row["user_id"],
            full_name=row["full_name"],
        )
    finally:
        await db.close()


@router.post("/auth/me/onboarding/complete")
async def complete_onboarding(request: Request):
    """Mark the authenticated user's onboarding as complete."""
    actor = _actor(request)
    roles = getattr(request.state, "roles", [])
    role = _role(request)
    if not actor or role not in ROLE_PERMISSIONS or role not in roles:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = await get_db()
    try:
        await db.execute("UPDATE users SET onboarding_completed = 1, updated_at = ? WHERE user_id = ?", (_auth_now_iso(), actor))
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("auth_session", actor, "onboarding_completed", actor)
    return JSONResponse({"message": "Onboarding complete."}, headers={"Cache-Control": "no-store"})


@router.put("/auth/me/profile")
async def update_my_profile(body: AuthProfileUpdateRequest, request: Request):
    """Update the authenticated user's own profile (email, department)."""
    actor = _actor(request)
    if not actor:
        raise HTTPException(status_code=401, detail="Authentication required")
    updates = []
    params: list = []
    if body.email is not None:
        _validate_email(body.email)
        updates.append("email = ?")
        params.append(body.email.strip())
    if body.department is not None:
        updates.append("department = ?")
        params.append(body.department.strip())
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("updated_at = ?")
    params.append(_auth_now_iso())
    params.append(actor)
    db = await get_db()
    try:
        await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params)
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("auth_session", actor, "profile_updated", actor, {"fields": updates})
    return JSONResponse({"message": "Profile updated."}, headers={"Cache-Control": "no-store"})


@router.post("/auth/logout")
async def auth_logout(request: Request):
    """Revoke the authenticated server-side session and expire both browser cookies."""
    actor = _actor(request)
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        db = await get_db()
        try:
            await db.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE session_id = ? AND revoked_at IS NULL",
                (_auth_now_iso(), session_id),
            )
            await db.commit()
        finally:
            await db.close()
        await log_audit_event("auth_session", session_id, "logout", actor)
    return _clear_session_cookies(JSONResponse({"message": "Logout successful"}))


# --- Documents ---
@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(request: Request, status: Optional[str] = None, doc_class: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check_document_read(request)
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if doc_class:
            conditions.append("doc_class = ?")
            params.append(doc_class)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM documents WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [DocumentResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def create_document(doc: DocumentCreate, request: Request):
    _check(request, "document:create")
    actor = _actor(request)
    doc_id = _gen_id("DOC")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO documents (document_id, title, doc_class, classification, status, owner_id, description, tags, created_at, updated_at, created_by, updated_by, kcaa_approval_required, review_due_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, doc.title, doc.doc_class, doc.classification, "draft", doc.owner_id, doc.description, doc.tags, now, now, actor, actor, 1 if doc.kcaa_approval_required else 0, doc.review_due_date),
        )
        await log_audit_event("document", doc_id, "created", actor, {"title": doc.title, "kcaa_required": doc.kcaa_approval_required}, db=db)
        await db.commit()
    finally:
        await db.close()
    return DocumentResponse(document_id=doc_id, title=doc.title, doc_class=doc.doc_class, classification=doc.classification, status="draft", owner_id=doc.owner_id, description=doc.description, tags=doc.tags, current_version_id=None, kcaa_approval_required=doc.kcaa_approval_required, review_due_date=doc.review_due_date, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, request: Request):
    _check_document_read(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM documents WHERE document_id = ?", (doc_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentResponse(**dict(row))
    finally:
        await db.close()


@router.patch("/documents/{doc_id}", response_model=DocumentResponse)
async def update_document(doc_id: str, update: DocumentUpdate, request: Request):
    _check(request, "document:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM documents WHERE document_id = ?", (doc_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")
        updates = []
        params = []
        for col, val in {"title": update.title, "doc_class": update.doc_class, "classification": update.classification, "description": update.description, "tags": update.tags, "owner_id": update.owner_id}.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(doc_id)
            await db.execute(f"UPDATE documents SET {', '.join(updates)} WHERE document_id = ?", params)
            await log_audit_event("document", doc_id, "updated", actor, {"fields": [col for col, val in {"title": update.title, "doc_class": update.doc_class, "classification": update.classification, "description": update.description, "tags": update.tags, "owner_id": update.owner_id}.items() if val is not None]}, db=db)
            await db.commit()
        cursor = await db.execute("SELECT * FROM documents WHERE document_id = ?", (doc_id,))
        row = await cursor.fetchone()
        return DocumentResponse(**dict(row))
    finally:
        await db.close()


# --- Versions ---
@router.get("/documents/{doc_id}/versions", response_model=List[DocumentVersionResponse])
async def list_versions(doc_id: str, request: Request, include_draft: bool = False):
    _check_document_read(request)
    if include_draft:
        _check(request, "document:update")
    db = await get_db()
    try:
        if include_draft:
            cursor = await db.execute(
                "SELECT * FROM document_versions WHERE document_id = ? ORDER BY created_at DESC",
                (doc_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM document_versions WHERE document_id = ? AND state = 'published' ORDER BY created_at DESC",
                (doc_id,),
            )
        rows = await cursor.fetchall()
        return [DocumentVersionResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/versions", response_model=DocumentVersionResponse, status_code=201)
async def create_version(ver: DocumentVersionCreate, request: Request):
    _check(request, "document:create")
    actor = _actor(request)
    ver_id = _gen_id("VER")
    now = now_iso()
    db = await get_db()
    try:
        # Check if parent document exists
        cursor = await db.execute("SELECT kcaa_approval_required FROM documents WHERE document_id = ?", (ver.document_id,))
        doc_row = await cursor.fetchone()
        if not doc_row:
            raise HTTPException(status_code=404, detail="Document not found")
        kcaa_required = doc_row["kcaa_approval_required"]
        
        await db.execute(
            "INSERT INTO document_versions (version_id, document_id, version_number, state, content, change_summary, kcaa_approved, kcaa_approved_by, kcaa_approved_at, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ver_id, ver.document_id, ver.version_number, "draft", ver.content, ver.change_summary, 0, None, None, now, now, actor, actor),
        )
        await log_audit_event("document_version", ver_id, "created", actor, {"document_id": ver.document_id, "version_number": ver.version_number}, db=db)
        await db.commit()
    finally:
        await db.close()
    return DocumentVersionResponse(version_id=ver_id, document_id=ver.document_id, version_number=ver.version_number, state="draft", content=ver.content, change_summary=ver.change_summary, approved_by=None, approved_at=None, kcaa_approved=0, kcaa_approved_by=None, kcaa_approved_at=None, published_at=None, kcaa_reference=None, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.post(
    "/versions/{version_id}/kcaa-evidence",
    status_code=201,
    dependencies=[Depends(upload_request_limit)],
)
async def upload_kcaa_approval_evidence(version_id: str, request: Request, reference: str = ""):
    """Retain a KCAA approval artifact and compute its digest server-side."""
    _check(request, "document:update")
    reference = reference.strip()
    if not reference or len(reference) > 200:
        raise HTTPException(status_code=422, detail="A KCAA approval reference of 1-200 characters is required")
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/pdf":
        raise HTTPException(status_code=415, detail="KCAA approval evidence must be a PDF")
    try:
        upload_policy = load_upload_safety_policy()
    except UploadSafeguardConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Upload safeguards are not configured") from exc
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_KCAA_EVIDENCE_BYTES:
                raise HTTPException(status_code=413, detail="KCAA evidence exceeds the 10 MiB limit")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from exc
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_KCAA_EVIDENCE_BYTES:
            raise HTTPException(status_code=413, detail="KCAA evidence exceeds the 10 MiB limit")
        content.extend(chunk)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="KCAA evidence content is not a PDF")

    actor = _actor(request)
    evidence_id = _gen_id("KCAA")
    stored_filename = f"{evidence_id}.pdf"
    root = KCAA_EVIDENCE_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = _validated_kcaa_evidence_path(stored_filename)
    file_sha256 = hashlib.sha256(content).hexdigest()
    uploaded_at = now_iso()
    committed = False
    try:
        async with upload_storage_lock():
            try:
                ensure_upload_capacity(len(content), upload_policy, extra_roots=(KCAA_EVIDENCE_DIR,))
            except UploadQuotaExceeded as exc:
                raise HTTPException(status_code=507, detail="Upload storage quota has been reached") from exc
            except UploadStorageUnavailable as exc:
                raise HTTPException(status_code=503, detail="Upload storage is unavailable") from exc
            try:
                await scan_upload_bytes(content, upload_policy)
            except UploadMalwareDetected as exc:
                raise HTTPException(status_code=422, detail="File was rejected by malware screening") from exc
            except UploadScannerUnavailable as exc:
                raise HTTPException(status_code=503, detail="Upload malware scanner is unavailable") from exc
            try:
                await validate_upload_content(content, ".pdf", MAX_KCAA_EVIDENCE_BYTES)
            except UploadContentInvalid as exc:
                raise HTTPException(status_code=415, detail="KCAA evidence is not a structurally valid PDF") from exc
            except UploadValidationUnavailable as exc:
                raise HTTPException(status_code=503, detail="Isolated PDF validation is unavailable") from exc
            try:
                path = store_upload_file(path, content)
            except UploadStorageUnavailable as exc:
                raise HTTPException(status_code=503, detail="Upload storage is unavailable") from exc

            db = await get_db()
            try:
                version = await (await db.execute(
                    "SELECT state FROM document_versions WHERE version_id = ?", (version_id,)
                )).fetchone()
                if not version:
                    raise HTTPException(status_code=404, detail="Version not found")
                if version["state"] != "approved":
                    raise HTTPException(status_code=409, detail="KCAA evidence can only be attached to an internally approved version")
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(
                    """INSERT INTO kcaa_approval_evidence
                       (evidence_id, version_id, reference, stored_filename, file_path, file_sha256,
                        file_size, uploaded_by, uploaded_at, status)
                       VALUES (?,?,?,?,?,?,?,?,?,'pending')""",
                    (evidence_id, version_id, reference, stored_filename, str(path), file_sha256, len(content), actor, uploaded_at),
                )
                await log_audit_event("kcaa_approval_evidence", evidence_id, "uploaded", actor, {
                    "version_id": version_id, "reference": reference, "file_sha256": file_sha256,
                }, db=db)
                await db.commit()
                committed = True
            except Exception:
                await db.rollback()
                raise
            finally:
                await db.close()
    except Exception as exc:
        if not committed and path.exists():
            try:
                remove_upload_file(path)
            except UploadStorageUnavailable as cleanup_exc:
                raise HTTPException(
                    status_code=503,
                    detail="Upload cleanup failed; storage reconciliation is required",
                ) from cleanup_exc
        if isinstance(exc, UploadStorageUnavailable):
            raise HTTPException(status_code=503, detail="Upload storage is unavailable") from exc
        raise
    return {
        "evidence_id": evidence_id, "version_id": version_id, "reference": reference,
        "stored_filename": stored_filename, "file_sha256": file_sha256, "file_size": len(content),
        "uploaded_by": actor, "uploaded_at": uploaded_at, "status": "pending",
    }


@router.post(
    "/versions/{version_id}/kcaa-evidence/{evidence_id}/verify",
    dependencies=[Depends(upload_request_limit)],
)
async def verify_kcaa_approval_evidence(version_id: str, evidence_id: str, request: Request):
    """Independently review retained KCAA evidence before it can satisfy publication control."""
    _check(request, "document:approve")
    actor = _actor(request)
    db = await get_db()
    try:
        evidence = await (await db.execute(
            "SELECT * FROM kcaa_approval_evidence WHERE evidence_id = ? AND version_id = ?",
            (evidence_id, version_id),
        )).fetchone()
        if not evidence:
            raise HTTPException(status_code=404, detail="KCAA evidence not found")
        if evidence["status"] != "pending":
            raise HTTPException(status_code=409, detail="KCAA evidence is not pending verification")
        if same_principal(request, evidence["uploaded_by"]):
            raise HTTPException(status_code=403, detail="The evidence uploader cannot verify the same artifact")
        path = _validated_kcaa_evidence_path(evidence["stored_filename"])
        actual_hash = _hash_kcaa_evidence(path)
        if not hmac.compare_digest(actual_hash, evidence["file_sha256"]):
            raise HTTPException(status_code=409, detail="KCAA evidence file hash no longer matches its retained record")
        verified_at = now_iso()
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            "UPDATE kcaa_approval_evidence SET status='verified', verified_by=?, verified_at=? WHERE evidence_id=? AND status='pending'",
            (actor, verified_at, evidence_id),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="KCAA evidence verification was already completed")
        await log_audit_event("kcaa_approval_evidence", evidence_id, "verified", actor, {
            "version_id": version_id, "file_sha256": actual_hash,
        }, db=db)
        await db.commit()
        return {"evidence_id": evidence_id, "version_id": version_id, "status": "verified", "verified_by": actor, "verified_at": verified_at}
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.get(
    "/versions/{version_id}/kcaa-evidence/{evidence_id}/file",
    dependencies=[Depends(upload_request_limit)],
)
async def download_kcaa_approval_evidence(version_id: str, evidence_id: str, request: Request):
    _check(request, "document:read")
    db = await get_db()
    try:
        evidence = await (await db.execute(
            "SELECT stored_filename, file_sha256, file_size FROM kcaa_approval_evidence WHERE evidence_id=? AND version_id=?",
            (evidence_id, version_id),
        )).fetchone()
        if not evidence:
            raise HTTPException(status_code=404, detail="KCAA evidence not found")
        path = _validated_kcaa_evidence_path(evidence["stored_filename"])
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise HTTPException(status_code=409, detail="KCAA evidence file is not a regular file")
                content = bytearray()
                while chunk := source.read(64 * 1024):
                    if len(content) + len(chunk) > MAX_KCAA_EVIDENCE_BYTES:
                        raise HTTPException(status_code=413, detail="Stored KCAA evidence exceeds the size limit")
                    content.extend(chunk)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail="Stored KCAA evidence file is missing") from exc
        content_hash = hashlib.sha256(content).hexdigest()
        if len(content) != evidence["file_size"] or not evidence["file_sha256"] or not hmac.compare_digest(
            content_hash, evidence["file_sha256"]
        ):
            raise HTTPException(status_code=409, detail="KCAA evidence file no longer matches its retained record")
        return Response(
            content=bytes(content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{evidence["stored_filename"]}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        await db.close()


@router.patch("/versions/{version_id}/state", response_model=DocumentVersionResponse)
async def transition_version_state(
    version_id: str,
    request: Request,
    state: Optional[str] = None,
    kcaa_reference: Optional[str] = None,
    kcaa_evidence_id: Optional[str] = None,
):
    _check(request, "document:read")
    actor = _actor(request)
    role = _role(request)
    if state not in {"draft", "in_review", "approved", "rejected", "kcaa_approved", "published"}:
        raise HTTPException(status_code=422, detail=f"Invalid version state: {state}")
    approval_reference = ""
    approval_evidence_hash = ""
    if state == "kcaa_approved" and not kcaa_evidence_id:
        raise HTTPException(status_code=422, detail="A verified KCAA evidence ID is required")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM document_versions WHERE version_id = ?", (version_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Version not found")
        row = dict(row)
        allowed_transitions = {
            "draft": {"in_review"},
            "in_review": {"approved", "rejected", "draft"},
            "approved": {"kcaa_approved", "published", "rejected"},
            "kcaa_approved": {"published", "rejected"},
            "rejected": {"draft"},
            "published": set(),
        }
        if state not in allowed_transitions.get(row["state"], set()):
            raise HTTPException(status_code=422, detail=f"Invalid version transition: {row['state']} -> {state}")
        # Permission checks based on target state
        if state in ("approved", "kcaa_approved"):
            if not has_permission(role, "document:approve"):
                raise HTTPException(status_code=403, detail="Approve permission required")
        if state == "published":
            if not has_permission(role, "document:publish"):
                raise HTTPException(status_code=403, detail="Publish permission required")
        if state in ("draft", "in_review", "rejected"):
            if not has_permission(role, "document:update"):
                raise HTTPException(status_code=403, detail="Update permission required")
        if state in ("approved", "kcaa_approved"):
            if not check_sod("version", "approve", actor, row["created_by"], getattr(request.state, "actor_aliases", None)):
                raise HTTPException(status_code=403, detail="Cannot approve own version (SoD)")
        # Check if parent document requires KCAA approval
        cursor = await db.execute("SELECT kcaa_approval_required FROM documents WHERE document_id = ?", (row["document_id"],))
        doc_row = await cursor.fetchone()
        kcaa_required = doc_row["kcaa_approval_required"] if doc_row else 0
        evidence_id_for_transition = ""
        evidence_uploader = ""
        evidence_verifier = ""
        if state == "kcaa_approved" or (state == "published" and kcaa_required):
            evidence_id_for_transition = kcaa_evidence_id if state == "kcaa_approved" else row.get("kcaa_evidence_id")
            if not evidence_id_for_transition:
                raise HTTPException(status_code=403, detail="Verified KCAA evidence is required before approval or publication")
            evidence = await (await db.execute(
                "SELECT * FROM kcaa_approval_evidence WHERE evidence_id=? AND version_id=?",
                (evidence_id_for_transition, version_id),
            )).fetchone()
            if not evidence or evidence["status"] != "verified":
                raise HTTPException(status_code=403, detail="KCAA evidence must be independently verified before approval or publication")
            evidence_uploader = evidence["uploaded_by"]
            evidence_verifier = evidence["verified_by"]
            if state == "kcaa_approved" and same_principal(request, evidence["uploaded_by"]):
                raise HTTPException(status_code=403, detail="The evidence uploader cannot grant KCAA approval for the same artifact")
            if state == "kcaa_approved" and same_principal(request, evidence["verified_by"]):
                raise HTTPException(status_code=403, detail="The evidence verifier cannot grant KCAA approval for the same artifact")
            evidence_path = _validated_kcaa_evidence_path(evidence["stored_filename"])
            actual_evidence_hash = _hash_kcaa_evidence(evidence_path)
            if not hmac.compare_digest(actual_evidence_hash, evidence["file_sha256"]):
                raise HTTPException(status_code=409, detail="KCAA evidence file hash no longer matches its verified record")
            if kcaa_reference and kcaa_reference.strip() != evidence["reference"]:
                raise HTTPException(status_code=422, detail="KCAA reference does not match the verified evidence record")
            approval_reference = evidence["reference"]
            approval_evidence_hash = actual_evidence_hash
        # KCAA gate and separation-of-duties checks for publication.
        if state == "published":
            if not check_sod("version", "publish", actor, row["created_by"], getattr(request.state, "actor_aliases", None)):
                raise HTTPException(status_code=403, detail="Cannot publish own version (SoD)")
            if kcaa_required and (
                row["kcaa_approved"] != 1
                or not row.get("kcaa_reference")
                or not row.get("kcaa_evidence_sha256")
                or not row.get("kcaa_evidence_id")
                or not row.get("kcaa_approved_by")
            ):
                raise HTTPException(status_code=403, detail="Verified KCAA approval evidence is required before publishing")
            if kcaa_required and same_principal(request, row.get("kcaa_approved_by")):
                raise HTTPException(status_code=403, detail="The KCAA approver cannot publish the same version")
            if kcaa_required and same_principal(request, evidence_uploader):
                raise HTTPException(status_code=403, detail="The KCAA evidence uploader cannot publish the same version")
            if kcaa_required and same_principal(request, evidence_verifier):
                raise HTTPException(status_code=403, detail="The KCAA evidence verifier cannot publish the same version")
        updates = ["state = ?", "updated_at = ?", "updated_by = ?"]
        params = [state, now_iso(), actor]
        if state == "approved":
            updates.append("approved_by = ?")
            params.append(actor)
            updates.append("approved_at = ?")
            params.append(now_iso())
        if state == "kcaa_approved":
            updates.extend(["kcaa_approved = 1", "kcaa_reference = ?", "kcaa_evidence_sha256 = ?", "kcaa_evidence_id = ?"])
            params.extend([approval_reference, approval_evidence_hash, evidence_id_for_transition])
            updates.append("kcaa_approved_by = ?")
            params.append(actor)
            updates.append("kcaa_approved_at = ?")
            params.append(now_iso())
        if state == "published":
            updates.append("published_at = ?")
            params.append(now_iso())
        params.append(version_id)
        await db.execute(f"UPDATE document_versions SET {', '.join(updates)} WHERE version_id = ?", params)
        if state == "published":
            now_val = now_iso()
            await db.execute(
                "UPDATE document_versions SET state = 'obsolete', updated_at = ?, updated_by = ? WHERE document_id = ? AND version_id != ? AND state = 'published'",
                (now_val, actor, row["document_id"], version_id),
            )
            await db.execute(
                "UPDATE documents SET current_version_id = ?, status = 'published', updated_at = ?, updated_by = ? WHERE document_id = ?",
                (version_id, now_val, actor, row["document_id"]),
            )
        await log_audit_event(
            "document_version",
            version_id,
            "state_changed",
            actor,
            {"from_state": row["state"], "to_state": state, "document_id": row["document_id"]},
            db=db,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM document_versions WHERE version_id = ?", (version_id,))
        row = await cursor.fetchone()
        return DocumentVersionResponse(**dict(row))
    finally:
        await db.close()


# --- Document Content ---
@router.get("/documents/{doc_id}/content", response_model=DocumentContentResponse)
async def get_document_content(doc_id: str, request: Request, include_draft: bool = False):
    """Get the effective (current published) version content of a document."""
    _check_document_read(request)
    if include_draft:
        _check(request, "document:update")
    db = await get_db()
    try:
        row = None
        if include_draft:
            cursor = await db.execute(
                "SELECT * FROM document_versions WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
                (doc_id,),
            )
            row = await cursor.fetchone()
        else:
            cursor = await db.execute(
                """SELECT v.* FROM documents d
                   JOIN document_versions v ON v.version_id = d.current_version_id
                   WHERE d.document_id = ? AND v.state = 'published'""",
                (doc_id,),
            )
            row = await cursor.fetchone()
            if not row:
                cursor = await db.execute(
                    "SELECT * FROM document_versions WHERE document_id = ? AND state = 'published' ORDER BY created_at DESC LIMIT 1",
                    (doc_id,),
                )
                row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Effective published document version not found")
        row = dict(row)
        return DocumentContentResponse(
            document_id=row["document_id"],
            version_id=row["version_id"],
            version_number=row["version_number"],
            state=row["state"],
            content=row["content"],
            change_summary=row["change_summary"],
            kcaa_approved=row["kcaa_approved"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    finally:
        await db.close()


@router.put("/documents/{doc_id}/content", response_model=DocumentContentResponse)
async def update_document_content(doc_id: str, update: DocumentContentUpdate, request: Request):
    """Update document content by creating a new draft version."""
    _check(request, "document:update")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        # Verify document exists
        cursor = await db.execute("SELECT document_id, kcaa_approval_required FROM documents WHERE document_id = ?", (doc_id,))
        doc_row = await cursor.fetchone()
        if not doc_row:
            raise HTTPException(status_code=404, detail="Document not found")
        kcaa_required = doc_row["kcaa_approval_required"]

        # Get latest version number to increment
        cursor = await db.execute(
            "SELECT version_number FROM document_versions WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
            (doc_id,),
        )
        ver_row = await cursor.fetchone()
        current_ver = ver_row["version_number"] if ver_row else "00.00.00"

        # Parse and increment patch version
        try:
            parts = current_ver.split(".")
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2]) + 1
            new_ver = f"{major:02d}.{minor:02d}.{patch:02d}"
        except Exception:
            new_ver = update.version_number or "00.01.01"

        ver_id = _gen_id("VER")

        await db.execute(
            """INSERT INTO document_versions
               (version_id, document_id, version_number, state, content, change_summary,
                kcaa_approved, kcaa_approved_by, kcaa_approved_at, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ver_id, doc_id, new_ver, "draft", update.content, update.change_summary,
                0,
                None,
                None,
                now, now, actor, actor,
            ),
        )
        await log_audit_event("document_version", ver_id, "created_from_content_update", actor, {"document_id": doc_id, "version_number": new_ver}, db=db)
        await db.commit()

        return DocumentContentResponse(
            document_id=doc_id,
            version_id=ver_id,
            version_number=new_ver,
            state="draft",
            content=update.content,
            change_summary=update.change_summary,
            kcaa_approved=0,
            created_at=now,
            updated_at=now,
        )
    finally:
        await db.close()


# --- Document file upload/download ---

DMS_DOCUMENT_STORAGE_DIR = Path(os.getenv("DMS_DOCUMENT_STORAGE_DIR", str(Path(DB_PATH).parent / "document_files")))

MAX_UPLOAD_FILE_BYTES = 10 * 1024 * 1024


@router.post("/documents/{doc_id}/file", response_model=DocumentFile)
async def upload_document_file(
    doc_id: str,
    request: Request,
    file: UploadFile = File(...),
    version_id: Optional[str] = None,
):
    """Upload a binary file (PDF, HTML, JSON) as a source document attachment."""
    _check(request, "document:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT document_id FROM documents WHERE document_id = ?", (doc_id,)
        )
        doc_row = await cursor.fetchone()
        if not doc_row:
            raise HTTPException(status_code=404, detail="Document not found")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file upload")

        file_sha256 = hashlib.sha256(content).hexdigest()
        file_size = len(content)
        uploaded_at = now_iso()
        file_id = _gen_id("DOCFILE")
        stored_filename = f"{file_id}_{file.filename}"
        root = DMS_DOCUMENT_STORAGE_DIR.resolve()
        root.mkdir(parents=True, exist_ok=True)
        file_path = root / stored_filename
        file_path_local: Path | None = file_path

        committed = False
        try:
            async with upload_storage_lock():
                try:
                    upload_policy = load_upload_safety_policy()
                    ensure_upload_capacity(file_size, upload_policy, extra_roots=(root,))
                except UploadQuotaExceeded as exc:
                    raise HTTPException(status_code=507, detail="Upload storage quota has been reached") from exc
                except UploadStorageUnavailable as exc:
                    raise HTTPException(status_code=503, detail="Upload storage is unavailable") from exc
                try:
                    await scan_upload_bytes(content, upload_policy)
                except UploadMalwareDetected as exc:
                    raise HTTPException(status_code=422, detail="File was rejected by malware screening") from exc
                except UploadScannerUnavailable as exc:
                    raise HTTPException(status_code=503, detail="Upload malware scanner is unavailable") from exc
                try:
                    await validate_upload_content(content, Path(file.filename or "").suffix or ".bin", MAX_UPLOAD_FILE_BYTES)
                except UploadContentInvalid as exc:
                    raise HTTPException(status_code=415, detail="File is not structurally valid") from exc
                except UploadValidationUnavailable as exc:
                    raise HTTPException(status_code=503, detail="Isolated file validation is unavailable") from exc
                try:
                    path = store_upload_file(file_path, content)
                except UploadStorageUnavailable as exc:
                    raise HTTPException(status_code=503, detail="Upload storage is unavailable") from exc

            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """INSERT INTO document_files
                   (file_id, document_id, version_id, stored_filename, original_filename,
                    content_type, file_path, file_sha256, file_size, uploaded_by, uploaded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    file_id, doc_id, version_id, stored_filename, file.filename or "unknown",
                    file.content_type or "application/octet-stream", str(path),
                    file_sha256, file_size, actor, uploaded_at,
                ),
            )
            await log_audit_event(
                "document", doc_id, "file_uploaded", actor,
                {"file_id": file_id, "original_filename": file.filename, "file_sha256": file_sha256, "file_size": file_size},
                db=db,
            )
            await db.commit()
            committed = True
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
    except Exception as exc:
        if not committed and file_path_local is not None and file_path_local.exists():
            try:
                remove_upload_file(file_path_local)
            except UploadStorageUnavailable:
                pass
        raise
    return DocumentFile(
        file_id=file_id,
        document_id=doc_id,
        version_id=version_id,
        stored_filename=stored_filename,
        original_filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        file_sha256=file_sha256,
        file_size=file_size,
        uploaded_by=actor,
        uploaded_at=uploaded_at,
    )


@router.get("/documents/{doc_id}/files", response_model=List[DocumentFile])
async def list_document_files(doc_id: str, request: Request):
    """List all files attached to a document."""
    _check(request, "document:read")
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM document_files WHERE document_id = ? ORDER BY uploaded_at DESC",
            (doc_id,),
        )
        rows = await cursor.fetchall()
        return [DocumentFile(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/documents/{doc_id}/file/{file_id}")
async def download_document_file(doc_id: str, file_id: str, request: Request):
    """Download a file attached to a document.

    Requires ``document:download`` permission. KCAA-approved documents
    (kcaa_approval_required=1) cannot be fully downloaded and return 403.
    All downloaded content receives an identity-bound watermark.
    """
    _check(request, "document:download")
    actor = _actor(request)
    db = await get_db()
    try:
        # Fetch file record and document classification in one query
        row = await (
            await db.execute(
                """SELECT df.stored_filename, df.original_filename, df.content_type,
                          df.file_path, df.file_sha256, df.file_size,
                          d.kcaa_approval_required, d.title, d.doc_class, d.classification
                   FROM document_files df
                   JOIN documents d ON df.document_id = d.document_id
                   WHERE df.file_id=? AND df.document_id=?""",
                (file_id, doc_id),
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document file not found")

        # Block complete download of KCAA-approved documents for all users
        if row["kcaa_approval_required"] == 1:
            await log_audit_event(
                "document", doc_id, "file_download_blocked_kcaa", actor,
                {"file_id": file_id, "original_filename": row["original_filename"],
                 "reason": "kcaa_approved_no_full_download"},
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FULL_DOWNLOAD_RESTRICTED",
                    "message": "Complete download is not permitted for this KCAA-approved document.",
                },
            )

        path = Path(row["file_path"])
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise HTTPException(status_code=409, detail="Stored file is not a regular file")
                content = bytearray()
                while chunk := source.read(64 * 1024):
                    if len(content) + len(chunk) > MAX_UPLOAD_FILE_BYTES:
                        raise HTTPException(status_code=413, detail="Stored file exceeds the size limit")
                    content.extend(chunk)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail="Stored file is missing") from exc

        content_hash = hashlib.sha256(bytes(content)).hexdigest()
        if len(content) != row["file_size"] or not hmac.compare_digest(content_hash, row["file_sha256"]):
            raise HTTPException(status_code=409, detail="Stored file no longer matches its retained record")

        # Apply identity-bound watermark before delivery
        from .watermark import apply_watermark
        user_roles = getattr(request.state, "user_roles", []) or []
        actor_roles = ",".join(sorted(user_roles)) if user_roles else "unknown"
        watermarked = apply_watermark(
            content=bytes(content),
            content_type=row["content_type"],
            user_identity=actor,
            employee_id=None,
            document_title=row["title"],
            document_revision="01.01.00",
            classification=row["classification"],
            extract_reference=None,
        )

        await log_audit_event(
            "document", doc_id, "file_downloaded", actor,
            {"file_id": file_id, "original_filename": row["original_filename"],
             "file_sha256": row["file_sha256"], "watermarked": True},
        )

        return Response(
            content=watermarked,
            media_type=row["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{row["original_filename"]}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Watermarked": "true",
            },
        )
    finally:
        await db.close()


# --- Controlled Document Security: Section Listing ---
@router.get("/documents/{doc_id}/sections", response_model=List[dict])
async def list_document_sections(doc_id: str, request: Request):
    """List the section hierarchy for a document."""
    _check(request, "document.section.view")
    db = await get_db()
    try:
        # Verify document exists
        cursor = await db.execute(
            "SELECT document_id FROM documents WHERE document_id = ?", (doc_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")

        cursor = await db.execute(
            """SELECT section_id, document_id, version_id, section_number, heading,
                      content_start_offset, content_end_offset, parent_section_id,
                      sort_order, created_at
               FROM document_sections
               WHERE document_id = ?
               ORDER BY sort_order ASC, section_number ASC""",
            (doc_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/documents/{doc_id}/sections/{section_id}", response_model=dict)
async def get_document_section(doc_id: str, section_id: str, request: Request):
    """Get section metadata for a document section."""
    _check(request, "document.section.view")
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT section_id, document_id, version_id, section_number, heading,
                      content_start_offset, content_end_offset, parent_section_id,
                      sort_order, created_at
               FROM document_sections
               WHERE section_id = ? AND document_id = ?""",
            (section_id, doc_id),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Section not found")
        return dict(row)
    finally:
        await db.close()


# --- Controlled Document Security: Section Extraction Requests ---
@router.post(
    "/documents/{doc_id}/sections/{section_id}/extract",
    response_model=SectionExtractResponse,
)
async def request_section_extraction(
    doc_id: str,
    section_id: str,
    body: SectionExtractRequest,
    request: Request,
):
    """Request extraction of a document section. Creates an approval request
    if the section is sensitive or requires approval."""
    _check(request, "document.section.extract")
    actor = _actor(request)
    db = await get_db()
    try:
        # Verify document and section exist
        cursor = await db.execute(
            "SELECT document_id FROM documents WHERE document_id = ?", (doc_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")

        cursor = await db.execute(
            """SELECT s.section_id, s.document_version_id, d.kcaa_approval_required,
                      d.classification
               FROM document_sections s
               JOIN documents d ON s.document_id = d.document_id
               WHERE s.section_id = ? AND s.document_id = ?""",
            (section_id, doc_id),
        )
        section = await cursor.fetchone()
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        # Determine if approval is required based on classification
        classification = section["classification"]
        requires_approval = classification in ("CONTROLLED", "KCAA_APPROVED")

        request_id = _gen_id("EXTRACT")
        created_at = now_iso()
        status = "pending" if requires_approval else "auto_approved"
        expires_at = None
        if requires_approval:
            from datetime import datetime, timedelta

            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()

        await db.execute(
            """INSERT INTO section_extraction_requests
               (id, document_id, document_version_id, requested_by, section_id,
                reason, status, expires_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                request_id,
                doc_id,
                section["document_version_id"],
                actor,
                section_id,
                body.reason or "Section extraction request",
                status,
                expires_at,
                created_at,
            ),
        )

        # Auto-approval: generate the extract immediately
        if not requires_approval:
            extraction_id = _gen_id("SECTRACT")
            storage_key = f"extracts/{extraction_id}.pdf"
            await db.execute(
                """INSERT INTO section_extractions
                   (id, request_id, document_version_id, section_id, generated_by,
                    storage_key, file_hash, page_count, watermark_applied, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    extraction_id,
                    request_id,
                    section["document_version_id"],
                    section_id,
                    actor,
                    storage_key,
                    "pending_hash",
                    0,
                    1,
                    created_at,
                ),
            )
            await log_audit_event(
                "document", doc_id, "section_extracted_auto", actor,
                {"request_id": request_id, "section_id": section_id,
                 "extraction_id": extraction_id},
                db=db,
            )
            await db.commit()
            return SectionExtractResponse(
                request_id=request_id,
                document_id=doc_id,
                document_version_id=section["document_version_id"],
                section_id=section_id,
                status="approved",
                approval_required=False,
                created_at=created_at,
            )

        await log_audit_event(
            "document", doc_id, "section_extraction_requested", actor,
            {"request_id": request_id, "section_id": section_id,
             "reason": body.reason},
            db=db,
        )
        await db.commit()
        return SectionExtractResponse(
            request_id=request_id,
            document_id=doc_id,
            document_version_id=section["document_version_id"],
            section_id=section_id,
            status="pending",
            approval_required=True,
            created_at=created_at,
        )
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.get("/extraction-requests", response_model=List[ExtractionRequestResponse])
async def list_extraction_requests(request: Request, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    """List the current user's section extraction requests."""
    _check(request, "document.section.extract")
    actor = _actor(request)
    db = await get_db()
    try:
        query = """SELECT id, document_id, document_version_id, requested_by, section_id,
                          reason, status, reviewed_by, review_comment, reviewed_at,
                          expires_at, created_at
                   FROM section_extraction_requests
                   WHERE requested_by = ?"""
        params = [actor]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([str(limit), str(offset)])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/extraction-requests/{request_id}", response_model=ExtractionRequestResponse)
async def get_extraction_request(request_id: str, request: Request):
    """Get the status of a section extraction request."""
    _check(request, "document.section.extract")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, document_id, document_version_id, requested_by, section_id,
                          reason, status, reviewed_by, review_comment, reviewed_at,
                          expires_at, created_at
                   FROM section_extraction_requests
                   WHERE id = ?""",
            (request_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Extraction request not found")

        # Users can only view their own requests unless they have approval rights
        if row["requested_by"] != actor and not has_permission(
            getattr(request.state, "user_role", ""), "document.extract.approve"
        ):
            raise HTTPException(status_code=403, detail="Not authorized to view this request")

        return dict(row)
    finally:
        await db.close()


@router.get("/extractions/{extraction_id}/download")
async def download_section_extraction(extraction_id: str, request: Request):
    """Download an approved section extraction. Requires document.section.extract."""
    _check(request, "document.section.extract")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT se.id, se.request_id, se.document_version_id, se.section_id,
                      se.generated_by, se.storage_key, se.file_hash, se.page_count,
                      se.watermark_applied, se.created_at,
                      d.document_id, d.title, d.classification,
                      ser.status as request_status
                   FROM section_extractions se
                   JOIN document_versions dv ON se.document_version_id = dv.version_id
                   JOIN documents d ON dv.document_id = d.document_id
                   LEFT JOIN section_extraction_requests ser ON se.request_id = ser.id
                   WHERE se.id = ?""",
            (extraction_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Extraction not found")

        # Verify request is approved if it has one
        if row["request_id"] and row["request_status"] != "approved":
            raise HTTPException(status_code=403, detail="Extraction request not approved")

        # Check user has extract permission for this document
        # (document.section.extract is already checked above)

        # Read the extracted file from storage
        storage_path = Path(row["storage_key"])
        # Try absolute path first, then relative to storage dir
        if not storage_path.is_absolute():
            storage_path = DMS_DOCUMENT_STORAGE_DIR / storage_path

        try:
            descriptor = os.open(str(storage_path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as source:
                content = bytearray()
                while chunk := source.read(64 * 1024):
                    content.extend(chunk)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail="Extraction file is missing") from exc

        # Verify integrity
        content_hash = hashlib.sha256(bytes(content)).hexdigest()
        if row["file_hash"] and content_hash != row["file_hash"]:
            raise HTTPException(status_code=409, detail="Extraction file integrity check failed")

        # Apply watermark on download
        from .watermark import apply_watermark
        watermarked = apply_watermark(
            content=bytes(content),
            content_type="application/pdf",
            user_identity=actor,
            employee_id=None,
            document_title=row["title"],
            document_revision="01.01.00",
            classification=row["classification"],
            extract_reference=extraction_id,
        )

        await log_audit_event(
            "document", row["document_id"], "section_extraction_downloaded", actor,
            {"extraction_id": extraction_id, "request_id": row["request_id"]},
        )

        return Response(
            content=watermarked,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="extract_{extraction_id}.pdf"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Watermarked": "true",
            },
        )
    finally:
        await db.close()


# --- Controlled Document Security: Extraction Approval (Admin) ---
@router.get("/admin/extraction-requests", response_model=List[ExtractionRequestResponse])
async def list_pending_extraction_approvals(request: Request):
    """List extraction requests pending approval. Requires document.extract.approve."""
    _check(request, "document.extract.approve")
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, document_id, document_version_id, requested_by, section_id,
                          reason, status, reviewed_by, review_comment, reviewed_at,
                          expires_at, created_at
                   FROM section_extraction_requests
                   WHERE status = 'pending'
                   ORDER BY created_at ASC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.post("/admin/extraction-requests/{request_id}/approve")
async def approve_extraction_request(request_id: str, request: Request):
    """Approve a section extraction request. Requires document.extract.approve."""
    _check(request, "document.extract.approve")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, document_id, document_version_id, requested_by, section_id,
                      status, expires_at
               FROM section_extraction_requests
               WHERE id = ?""",
            (request_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Extraction request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Request is not pending")
        if row["requested_by"] == actor:
            raise HTTPException(status_code=403, detail="Cannot approve your own extraction request")

        # Check expiration
        from datetime import datetime
        if row["expires_at"]:
            expires = datetime.fromisoformat(row["expires_at"])
            if datetime.utcnow() > expires:
                await db.execute(
                    "UPDATE section_extraction_requests SET status = 'expired' WHERE id = ?",
                    (request_id,),
                )
                await db.commit()
                raise HTTPException(status_code=409, detail="Request has expired")

        await db.execute(
            """UPDATE section_extraction_requests
               SET status = 'approved', reviewed_by = ?, reviewed_at = ?
               WHERE id = ?""",
            (actor, now_iso(), request_id),
        )

        await log_audit_event(
            "document", row["document_id"], "section_extraction_approved", actor,
            {"request_id": request_id, "section_id": row["section_id"]},
            db=db,
        )
        await db.commit()
        return {"status": "approved", "request_id": request_id}
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.post("/admin/extraction-requests/{request_id}/reject")
async def reject_extraction_request(request_id: str, request: Request):
    """Reject a section extraction request. Requires document.extract.approve."""
    _check(request, "document.extract.approve")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, document_id, requested_by, status
               FROM section_extraction_requests
               WHERE id = ?""",
            (request_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Extraction request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Request is not pending")
        if row["requested_by"] == actor:
            raise HTTPException(status_code=403, detail="Cannot reject your own extraction request")

        await db.execute(
            """UPDATE section_extraction_requests
               SET status = 'rejected', reviewed_by = ?, reviewed_at = ?
               WHERE id = ?""",
            (actor, now_iso(), request_id),
        )

        await log_audit_event(
            "document", row["document_id"], "section_extraction_rejected", actor,
            {"request_id": request_id},
            db=db,
        )
        await db.commit()
        return {"status": "rejected", "request_id": request_id}
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


# --- Controlled Document Security: Document Classification ---
@router.post("/admin/documents/{doc_id}/classify", response_model=DocumentClassificationResponse)
async def classify_document(doc_id: str, body: DocumentClassificationRequest, request: Request):
    """Assign a document classification (PUBLIC, TEMPLATE, CONTROLLED, KCAA_APPROVED).
    Requires document.policy.manage."""
    _check(request, "document.policy.manage")
    actor = _actor(request)
    db = await get_db()
    try:
        # Verify document exists
        cursor = await db.execute(
            "SELECT document_id FROM documents WHERE document_id = ?", (doc_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")

        # Verify classification exists
        cursor = await db.execute(
            "SELECT code, name, requires_watermark, allow_full_download, requires_approval FROM document_classifications WHERE code = ?",
            (body.classification_code,),
        )
        cls = await cursor.fetchone()
        if not cls:
            raise HTTPException(status_code=400, detail="Invalid classification code")

        # Update document classification
        await db.execute(
            "UPDATE documents SET classification = ?, updated_at = ?, updated_by = ? WHERE document_id = ?",
            (body.classification_code, now_iso(), actor, doc_id),
        )

        await log_audit_event(
            "document", doc_id, "document_classified", actor,
            {"classification_code": body.classification_code},
            db=db,
        )
        await db.commit()

        return DocumentClassificationResponse(
            document_id=doc_id,
            classification_code=cls["code"],
            name=cls["name"],
            requires_watermark=bool(cls["requires_watermark"]),
            allow_full_download=bool(cls["allow_full_download"]),
            requires_approval=bool(cls["requires_approval"]),
        )
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


# --- Controlled Document Security: Document Permissions ---
@router.get("/admin/documents/{doc_id}/permissions", response_model=List[DocumentPermissionResponse])
async def list_document_permissions(doc_id: str, request: Request):
    """List role-based permissions for a document. Requires document.policy.manage."""
    _check(request, "document.policy.manage")
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, document_id, role_id, permission_code, scope_section_id,
                      valid_from, valid_until, created_by, created_at
               FROM document_permissions
               WHERE document_id = ?
               ORDER BY created_at DESC""",
            (doc_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.put("/admin/documents/{doc_id}/permissions", response_model=List[DocumentPermissionResponse])
async def set_document_permissions(doc_id: str, grants: List[DocumentPermissionGrant], request: Request):
    """Replace role-based permissions for a document. Requires document.policy.manage."""
    _check(request, "document.policy.manage")
    actor = _actor(request)
    db = await get_db()
    try:
        # Verify document exists
        cursor = await db.execute(
            "SELECT document_id FROM documents WHERE document_id = ?", (doc_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")

        await db.execute("BEGIN IMMEDIATE")
        try:
            # Remove existing permissions
            await db.execute(
                "DELETE FROM document_permissions WHERE document_id = ?", (doc_id,)
            )

            # Insert new grants
            for grant in grants:
                permission_id = _gen_id("DOCPERM")
                created_at = now_iso()
                valid_from = grant.valid_from or created_at
                await db.execute(
                    """INSERT INTO document_permissions
                       (id, document_id, role_id, permission_code, scope_section_id,
                        valid_from, valid_until, created_by, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        permission_id, doc_id, grant.role_id, grant.permission_code,
                        grant.scope_section_id, valid_from, grant.valid_until,
                        actor, created_at,
                    ),
                )

            await log_audit_event(
                "document", doc_id, "document_permissions_updated", actor,
                {"grant_count": len(grants)},
                db=db,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        # Return the new permissions
        cursor = await db.execute(
            """SELECT id, document_id, role_id, permission_code, scope_section_id,
                      valid_from, valid_until, created_by, created_at
               FROM document_permissions
               WHERE document_id = ?
               ORDER BY created_at DESC""",
            (doc_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


# --- Change Requests ---
@router.get("/change-requests", response_model=List[ChangeRequestResponse])
async def list_change_requests(request: Request, status: Optional[str] = None, document_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "document:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if document_id:
            conditions.append("document_id = ?")
            params.append(document_id)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM change_requests WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [ChangeRequestResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/change-requests", response_model=ChangeRequestResponse, status_code=201)
async def create_change_request(cr: ChangeRequestCreate, request: Request):
    _check(request, "change_request:create")
    actor = _actor(request)
    cr_id = _gen_id("CR")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO change_requests (cr_id, document_id, version_id, title, description, change_type, status, requester_id, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (cr_id, cr.document_id, cr.version_id, cr.title, cr.description, cr.change_type, "open", actor, now, now, actor, actor),
        )
        await log_audit_event("change_request", cr_id, "created", actor, {"title": cr.title}, db=db)
        await db.commit()
    finally:
        await db.close()
    return ChangeRequestResponse(cr_id=cr_id, document_id=cr.document_id, version_id=cr.version_id, title=cr.title, description=cr.description, change_type=cr.change_type, status="open", requester_id=actor, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.patch("/change-requests/{cr_id}", response_model=ChangeRequestResponse)
async def update_change_request(cr_id: str, request: Request, status: Optional[str] = None, reviewer_id: Optional[str] = None, approver_id: Optional[str] = None):
    _check(request, "change_request:review")
    actor = _actor(request)
    role = _role(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM change_requests WHERE cr_id = ?", (cr_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Change request not found")
        row = dict(row)
        updates = []
        params = []
        if status:
            allowed_cr_transitions = {
                "open": {"submitted", "in_review", "under_review", "rejected"},
                "submitted": {"in_review", "under_review", "rejected"},
                "in_review": {"approved", "rejected"},
                "under_review": {"approved", "rejected"},
                "approved": {"implemented", "closed"},
                "rejected": {"open"},
                "implemented": {"closed"},
                "closed": set(),
            }
            if status not in allowed_cr_transitions.get(row["status"], set()):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid change-request transition: {row['status']} -> {status} (review required before approval per QMS §3.1)",
                )
            if status == "approved":
                if not has_permission(role, "change_request:approve"):
                    raise HTTPException(status_code=403, detail="Approve permission required")
                if not check_sod("change_request", "approve", actor, row["requester_id"], getattr(request.state, "actor_aliases", None)):
                    raise HTTPException(status_code=403, detail="Cannot approve own change request (SoD)")
                updates.append("approved_at = ?")
                params.append(now_iso())
                updates.append("approver_id = ?")
                params.append(actor)
            if status == "rejected":
                if not has_permission(role, "change_request:approve"):
                    raise HTTPException(status_code=403, detail="Approve permission required")
                if not check_sod("change_request", "reject", actor, row["requester_id"], getattr(request.state, "actor_aliases", None)):
                    raise HTTPException(status_code=403, detail="Cannot reject own change request (SoD)")
                updates.append("rejected_at = ?")
                params.append(now_iso())
            if status == "in_review":
                updates.append("reviewed_at = ?")
                params.append(now_iso())
                updates.append("reviewer_id = ?")
                params.append(actor)
            updates.append("status = ?")
            params.append(status)
        updates.append("updated_at = ?")
        params.append(now_iso())
        updates.append("updated_by = ?")
        params.append(actor)
        params.append(cr_id)
        await db.execute(f"UPDATE change_requests SET {', '.join(updates)} WHERE cr_id = ?", params)
        await log_audit_event(
            "change_request",
            cr_id,
            f"status_{status}" if status else "updated",
            actor,
            {"from_status": row["status"], "to_status": status} if status else {"reviewer_id": reviewer_id, "approver_id": approver_id},
            db=db,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM change_requests WHERE cr_id = ?", (cr_id,))
        updated_row = dict(await cursor.fetchone())
    finally:
        await db.close()
    return ChangeRequestResponse(**updated_row)


# --- Distributions ---
@router.get("/distributions", response_model=List[DistributionResponse])
async def list_distributions(request: Request, version_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "document:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if version_id:
            conditions.append("version_id = ?")
            params.append(version_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM distributions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [DistributionResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/distributions", response_model=DistributionResponse, status_code=201)
async def create_distribution(dist: DistributionCreate, request: Request):
    _check(request, "distribution:manage")
    actor = _actor(request)
    dist_id = _gen_id("DIST")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO distributions (distribution_id, version_id, recipient_id, channel, status, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (dist_id, dist.version_id, dist.recipient_id, dist.channel, "pending", now, now, actor, actor),
        )
        await log_audit_event("distribution", dist_id, "created", actor, {"recipient_id": dist.recipient_id, "version_id": dist.version_id}, db=db)
        await db.commit()
    finally:
        await db.close()
    return DistributionResponse(distribution_id=dist_id, version_id=dist.version_id, recipient_id=dist.recipient_id, channel=dist.channel, status="pending", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.post("/distributions/{dist_id}/acknowledge")
async def acknowledge_distribution(dist_id: str, request: Request):
    _check(request, "document:read")
    actor = _actor(request)
    role = _role(request)
    now = now_iso()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM distributions WHERE distribution_id = ?", (dist_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Distribution not found")
        dist = dict(row)
        if not same_principal(request, dist["recipient_id"]) and not has_permission(role, "distribution:manage") and role != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Only the named recipient or an authorized distribution custodian may acknowledge this distribution (QMS §3.11)",
            )
        await db.execute("UPDATE distributions SET status = 'acknowledged', acknowledged_at = ?, acknowledged_by = ?, updated_at = ?, updated_by = ? WHERE distribution_id = ?", (now, actor, now, actor, dist_id))
        await log_audit_event("distribution", dist_id, "acknowledged", actor, {"recipient_id": dist["recipient_id"]}, db=db)
        await db.commit()
    finally:
        await db.close()
    return {"status": "acknowledged"}


# --- Retention Rules ---
@router.get("/retention-rules", response_model=List[RetentionRuleResponse])
async def list_retention_rules(request: Request):
    _check(request, "document:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM retention_rules ORDER BY rule_id")
        rows = await cursor.fetchall()
        return [RetentionRuleResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# --- Legal Holds ---
@router.get("/legal-holds", response_model=List[LegalHoldResponse])
async def list_legal_holds(request: Request, status: Optional[str] = None):
    _check(request, "document:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM legal_holds WHERE status = ? ORDER BY imposed_at DESC", (status,))
        else:
            cursor = await db.execute("SELECT * FROM legal_holds ORDER BY imposed_at DESC")
        rows = await cursor.fetchall()
        return [LegalHoldResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/legal-holds", response_model=LegalHoldResponse, status_code=201)
async def create_legal_hold(hold: LegalHoldCreate, request: Request):
    _check(request, "legal_hold:manage")
    actor = _actor(request)
    hold_id = _gen_id("HOLD")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO legal_holds (hold_id, entity_type, entity_id, reason, imposed_by, imposed_at, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?, ?,?)",
            (hold_id, hold.entity_type, hold.entity_id, hold.reason, actor, now, "active", now, now),
        )
        await log_audit_event("legal_hold", hold_id, "imposed", actor, {"entity_type": hold.entity_type, "entity_id": hold.entity_id}, db=db)
        await db.commit()
    finally:
        await db.close()
    return LegalHoldResponse(hold_id=hold_id, entity_type=hold.entity_type, entity_id=hold.entity_id, reason=hold.reason, imposed_by=actor, imposed_at=now, status="active", created_at=now, updated_at=now)


@router.patch("/legal-holds/{hold_id}/release")
async def release_legal_hold(hold_id: str, request: Request):
    _check(request, "legal_hold:manage")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        cursor = await db.execute("UPDATE legal_holds SET status = 'released', released_by = ?, released_at = ?, updated_at = ? WHERE hold_id = ? AND status = 'active'", (actor, now, now, hold_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Active legal hold not found")
        await log_audit_event("legal_hold", hold_id, "released", actor, {}, db=db)
        await db.commit()
    finally:
        await db.close()
    return {"status": "released"}


# --- Compliance Obligations ---
@router.get("/compliance-obligations", response_model=List[ComplianceObligationResponse])
async def list_compliance_obligations(request: Request, status: Optional[str] = None):
    _check(request, "compliance:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM compliance_obligations WHERE status = ? ORDER BY due_date", (status,))
        else:
            cursor = await db.execute("SELECT * FROM compliance_obligations ORDER BY due_date")
        rows = await cursor.fetchall()
        return [ComplianceObligationResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# --- Regulatory References ---
@router.get("/regulatory-references", response_model=List[RegulatoryReferenceResponse])
async def list_regulatory_references(request: Request):
    _check(request, "compliance:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM regulatory_references ORDER BY ref_id")
        rows = await cursor.fetchall()
        return [RegulatoryReferenceResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# --- Audit Events ---
@router.get("/audit-events", response_model=List[AuditEventResponse])
async def list_audit_events(request: Request, entity_type: Optional[str] = None, entity_id: Optional[str] = None, limit: int = 100, offset: int = 0):
    _check(request, "audit:read")
    from .audit import query_audit_events
    events = await query_audit_events(entity_type=entity_type, entity_id=entity_id, limit=limit, offset=offset)
    return [AuditEventResponse(**e) for e in events]


# --- System administrator observability ---
@router.get("/admin/observability")
async def system_admin_observability(request: Request):
    """Return safe operational, workflow, audit, and RBAC telemetry for admins."""
    if _role(request) != "system_admin":
        raise HTTPException(status_code=403, detail="System administrator permission required")

    async def grouped_counts(db, table: str, column: str) -> dict:
        cursor = await db.execute(f"SELECT {column} AS value, COUNT(*) AS count FROM {table} GROUP BY {column} ORDER BY {column}")
        rows = await cursor.fetchall()
        return {str(row["value"]): row["count"] for row in rows}

    db = await get_db()
    try:
        integrity_cursor = await db.execute("PRAGMA integrity_check")
        integrity = await integrity_cursor.fetchone()
        table_counts = {}
        for table in ("users", "documents", "document_versions", "document_proposals", "change_requests", "audit_events", "notifications"):
            cursor = await db.execute(f"SELECT COUNT(*) AS count FROM {table}")
            table_counts[table] = (await cursor.fetchone())["count"]

        user_cursor = await db.execute(
            "SELECT user_id, username, email, full_name, role, department, is_active, merged_into_user_id, updated_at FROM users ORDER BY full_name"
        )
        users = [dict(row) for row in await user_cursor.fetchall()]
        for user in users:
            role_cursor = await db.execute("SELECT role FROM user_roles WHERE user_id = ? ORDER BY role", (user["user_id"],))
            user["roles"] = [row["role"] for row in await role_cursor.fetchall()]
        audit_cursor = await db.execute(
            "SELECT COUNT(*) AS count FROM audit_events WHERE timestamp >= datetime('now', '-24 hours')"
        )
        audit_last_24h = (await audit_cursor.fetchone())["count"]

        # Backup scheduler status
        backup_scheduler = getattr(request.app.state, "backup_scheduler", None)
        backup_status = None
        if backup_scheduler is not None:
            backup_status = backup_scheduler.status()
        else:
            backup_status = {
                "enabled": os.getenv("DMS_BACKUP_ENABLED", "false").strip().lower() == "true",
                "running": False,
                "reason": "scheduler_not_initialized",
            }

        # Scanner status: attempt a lightweight clamd connectivity probe
        scanner_status = await _probe_scanner_status()

        scheduler = getattr(request.app.state, "scheduler", None)
        scheduler_task = getattr(scheduler, "_task", None) if scheduler else None
        scheduler_running = bool(scheduler and getattr(scheduler, "_running", False) and scheduler_task and not scheduler_task.done())
        return {
            "generated_at": now_iso(),
            "health": {
                "status": "ok",
                "scheduler": "running" if scheduler_running else "not_started",
                "backup": {
                    "enabled": backup_status.get("enabled", False),
                    "running": backup_status.get("running", False),
                    "run_count": backup_status.get("run_count", 0),
                    "failure_count": backup_status.get("failure_count", 0),
                    "last_error": backup_status.get("last_error"),
                    "last_accepted": (
                        backup_status.get("last_result", {}).get("accepted")
                        if backup_status.get("last_result")
                        else None
                    ),
                },
                "scanner": scanner_status,
            },
            "database": {"status": "ok" if integrity and integrity[0] == "ok" else "degraded", "integrity": integrity[0] if integrity else "unknown"},
            "tables": table_counts,
            "users": {"total": len(users), "active": sum(1 for user in users if user["is_active"]), "inactive": sum(1 for user in users if not user["is_active"])},
            "user_profiles": users,
            "audit": {"events_last_24h": audit_last_24h, "total_events": table_counts["audit_events"]},
            "workflows": {
                "document_versions": await grouped_counts(db, "document_versions", "state"),
                "document_proposals": await grouped_counts(db, "document_proposals", "status"),
                "change_requests": await grouped_counts(db, "change_requests", "status"),
                "notifications": await grouped_counts(db, "notifications", "status"),
            },
            "role_matrix": all_role_profiles(),
        }
    finally:
        await db.close()


async def _probe_scanner_status() -> dict:
    """Lightweight clamd connectivity probe: attempt a TCP handshake.

    Returns a status dict without scanning any file. Never blocks longer than
    2 seconds so the observability endpoint stays responsive.
    """
    import socket as _socket

    try:
        policy = load_upload_safety_policy()
    except UploadSafeguardConfigurationError:
        return {"configured": False, "reachable": None, "detail": "scanner not configured"}

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(policy.clamd_host, policy.clamd_port),
            timeout=2.0,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass
        return {
            "configured": True,
            "reachable": True,
            "host": policy.clamd_host,
            "port": policy.clamd_port,
            "detail": "clamd reachable",
        }
    except asyncio.TimeoutError:
        return {
            "configured": True,
            "reachable": False,
            "host": policy.clamd_host,
            "port": policy.clamd_port,
            "detail": "clamd unreachable (timeout)",
        }
    except (OSError, ConnectionError) as exc:
        return {
            "configured": True,
            "reachable": False,
            "host": policy.clamd_host,
            "port": policy.clamd_port,
            "detail": f"clamd unreachable ({exc})",
        }


# --- Backup management (system administrator only) ---
@router.get("/backup/status")
async def backup_status(request: Request):
    """Return backup scheduler status and last run result."""
    _check(request, "backup:read")
    backup_scheduler = getattr(request.app.state, "backup_scheduler", None)
    if backup_scheduler is None:
        return {
            "enabled": os.getenv("DMS_BACKUP_ENABLED", "false").strip().lower() == "true",
            "running": False,
            "reason": "scheduler_not_initialized",
        }
    return backup_scheduler.status()


@router.get("/backup/history")
async def backup_history(request: Request, limit: int = 20):
    """Return recent backup audit events for the system administrator."""
    _check(request, "backup:read")
    from .audit import query_audit_events

    db = await get_db()
    try:
        events = await query_audit_events(
            entity_type="backup",
            entity_id="backup",
            limit=limit,
        )
        return {"events": [dict(e) for e in events]}
    finally:
        await db.close()


@router.post("/scanner/test")
async def scanner_test(request: Request):
    """Test clamd connectivity. System administrator only."""
    _check(request, "backup:read")
    return await _probe_scanner_status()


@router.post("/backup/run")
async def backup_run(request: Request):
    """Manually trigger one backup cycle. System administrator only."""
    _check(request, "backup:run")
    backup_scheduler = getattr(request.app.state, "backup_scheduler", None)
    if backup_scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="Backup scheduler is not initialized. Set DMS_BACKUP_ENABLED=true and configure DMS_BACKUP_DATA_ROOT and DMS_BACKUP_DEST_ROOT.",
        )
    try:
        result = await backup_scheduler.run_once()
        return result
    except BackupCreateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}")


# --- Evidence Pack ---
@router.post("/evidence-pack")
async def generate_evidence_pack(request: Request, entity_type: str = None, entity_id: str = None):
    _check(request, "compliance:read")
    from .audit import get_entity_audit_trail
    import hashlib, json
    events = await get_entity_audit_trail(entity_type or "document", entity_id or "")
    payload = json.dumps({"entity_type": entity_type, "entity_id": entity_id, "events": events}, sort_keys=True, default=str)
    checksum = "sha256-" + hashlib.sha256(payload.encode()).hexdigest()
    return {"entity_type": entity_type, "entity_id": entity_id, "events": events, "checksum": checksum}
