import asyncio
import sqlite3

from app import database


def test_v2_migration_from_completed_v1_preserves_status_hashes_and_relations(tmp_path, monkeypatch):
    migration_db = tmp_path / "canonical-identity-v1.sqlite3"
    canonical_migration = database.migrate_canonical_account_ids_v2

    async def skip_v2_for_legacy_fixture():
        return None

    monkeypatch.setattr(database, "DB_PATH", str(migration_db))
    monkeypatch.setattr(database, "migrate_canonical_account_ids_v2", skip_v2_for_legacy_fixture)
    asyncio.run(database.init_db())

    conn = sqlite3.connect(migration_db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "UPDATE users SET is_active = 0, onboarding_completed = 1, password_hash = 'dummy-quality-hash' WHERE user_id = 'u-lib'"
    )
    conn.execute("UPDATE users SET password_hash = 'dummy-quality-hash' WHERE user_id = 'u-quality'")
    conn.execute(
        "UPDATE users SET is_active = 0, onboarding_completed = 1, password_hash = 'dummy-safety-hash' WHERE user_id = 'u-safety'"
    )
    conn.execute("UPDATE users SET password_hash = 'dummy-safety-hash' WHERE user_id = 'u-security'")
    conn.execute(
        """INSERT INTO auth_sessions
           (session_id, user_id, token_hash, csrf_token_hash, created_at, expires_at, last_seen_at)
           VALUES ('session-quality-v1', 'u-lib', 'dummy-token-hash-quality', 'dummy-csrf-hash-quality',
                   '2026-01-01', '2027-01-01', '2026-01-01')"""
    )
    conn.execute(
        """INSERT INTO auth_sessions
           (session_id, user_id, token_hash, csrf_token_hash, created_at, expires_at, last_seen_at)
           VALUES ('session-safety-v1', 'u-safety', 'dummy-token-hash-safety', 'dummy-csrf-hash-safety',
                   '2026-01-01', '2027-01-01', '2026-01-01')"""
    )
    conn.execute(
        """INSERT INTO auth_setup_tokens
           (setup_id, user_id, token_hash, issued_by, created_at, expires_at)
           VALUES ('setup-quality-v1', 'u-lib', 'dummy-setup-hash-quality', 'u-admin', '2026-01-01', '2027-01-01')"""
    )
    conn.execute(
        """INSERT INTO auth_setup_tokens
           (setup_id, user_id, token_hash, issued_by, created_at, expires_at)
           VALUES ('setup-safety-v1', 'u-safety', 'dummy-setup-hash-safety', 'u-admin', '2026-01-01', '2027-01-01')"""
    )
    conn.execute(
        """INSERT INTO audit_reports
           (audit_id, audit_number, audit_date, auditor_id, auditee_id, created_at, updated_at)
           VALUES ('AUD-ID-MIGRATION', 'AUD-ID-MIGRATION', '2026-01-01', 'u-safety', 'u-lib', '2026-01-01', '2026-01-01')"""
    )
    conn.execute(
        """INSERT INTO personnel_licenses
           (license_id, person_id, license_type, expiry_date, created_at, updated_at, created_by, updated_by)
           VALUES ('LIC-ID-MIGRATION', 'u-safety', 'pilot_license', '2027-01-01', '2026-01-01', '2026-01-01', 'u-safety', 'u-safety')"""
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, "migrate_canonical_account_ids_v2", canonical_migration)
    asyncio.run(canonical_migration())
    asyncio.run(canonical_migration())

    conn = sqlite3.connect(migration_db)
    try:
        quality = conn.execute(
            "SELECT username, role, is_active, onboarding_completed, password_hash, merged_into_user_id "
            "FROM users WHERE user_id = 'u-quality'"
        ).fetchone()
        assert quality == ("librarian", "head_quality", 0, 1, "dummy-quality-hash", None)
        assert conn.execute(
            "SELECT is_active, merged_into_user_id, password_hash FROM users WHERE user_id = 'u-lib'"
        ).fetchone() == (0, "u-quality", None)

        safety = conn.execute(
            "SELECT username, role, is_active, onboarding_completed, password_hash, merged_into_user_id "
            "FROM users WHERE user_id = 'u-safety/security'"
        ).fetchone()
        assert safety == ("safety", "head_safety", 0, 1, "dummy-safety-hash", None)
        assert conn.execute(
            "SELECT is_active, merged_into_user_id FROM users WHERE user_id = 'u-security'"
        ).fetchone() == (0, "u-safety/security")

        assert conn.execute(
            "SELECT auditor_id, auditee_id FROM audit_reports WHERE audit_id = 'AUD-ID-MIGRATION'"
        ).fetchone() == ("u-safety/security", "u-quality")
        assert conn.execute(
            "SELECT person_id FROM personnel_licenses WHERE license_id = 'LIC-ID-MIGRATION'"
        ).fetchone() == ("u-safety/security",)
        assert conn.execute(
            "SELECT user_id, revoked_at IS NOT NULL FROM auth_sessions WHERE session_id = 'session-quality-v1'"
        ).fetchone() == ("u-lib", 1)
        assert conn.execute(
            "SELECT user_id, revoked_at IS NOT NULL FROM auth_sessions WHERE session_id = 'session-safety-v1'"
        ).fetchone() == ("u-safety/security", 1)
        assert conn.execute(
            "SELECT user_id, used_at IS NOT NULL FROM auth_setup_tokens WHERE setup_id = 'setup-safety-v1'"
        ).fetchone() == ("u-safety/security", 1)
        aliases = set(conn.execute("SELECT legacy_user_id, canonical_user_id FROM user_id_aliases"))
        assert ("u-lib", "u-quality") in aliases
        assert ("u-safety", "u-safety/security") in aliases
        assert ("u-safety/security", "u-safety/security") in aliases
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()
