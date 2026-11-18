import os
import sqlite3
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlsplit

from app import notifications, p0_routes
from app.p0_routes import _token_hash


TEST_PASSWORD = "Invite-Setup-Password-2026!"


def _prepare_invitee(email: str) -> tuple[str, str | None, int, str | None]:
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        original = conn.execute(
            "SELECT username, email, is_active, password_hash FROM users WHERE user_id = 'u-quality'"
        ).fetchone()
        assert original is not None
        conn.execute(
            "UPDATE users SET email = ?, is_active = 1, password_hash = NULL WHERE user_id = 'u-quality'",
            (email,),
        )
        conn.execute("DELETE FROM auth_setup_tokens WHERE user_id = 'u-quality'")
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'auth_invite_email_outbox'"
        ).fetchone()
        if table:
            conn.execute("DELETE FROM auth_invite_email_outbox WHERE user_id = 'u-quality'")
        conn.commit()
        return original
    finally:
        conn.close()


def _restore_invitee(original: tuple[str, str | None, int, str | None]) -> None:
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute(
            "UPDATE users SET username = ?, email = ?, is_active = ?, password_hash = ? WHERE user_id = 'u-quality'",
            original,
        )
        conn.execute("DELETE FROM auth_setup_tokens WHERE user_id = 'u-quality'")
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'auth_invite_email_outbox'"
        ).fetchone()
        if table:
            conn.execute("DELETE FROM auth_invite_email_outbox WHERE user_id = 'u-quality'")
        conn.commit()
    finally:
        conn.close()


def _enable_invite_email(monkeypatch, sender):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://dms.example.test")
    monkeypatch.setattr(notifications, "INVITE_EMAIL_ENABLED", True, raising=False)
    monkeypatch.setattr(notifications, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(notifications, "SMTP_USER", "mailer@example.test")
    monkeypatch.setattr(notifications, "SMTP_PASS", "unit-test-password")
    monkeypatch.setattr(notifications, "SMTP_FROM", "no-reply@example.test")
    monkeypatch.setattr(notifications, "SMTP_FROM_CONFIGURED", True)
    monkeypatch.setattr(notifications, "send_invitation_email", sender, raising=False)


def test_invite_email_uses_registered_address_and_one_time_setup_link(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    username = original[0]
    sent = []
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: sent.append((args, kwargs)) or True)

    try:
        response = client.post(
            "/api/p0/auth/invites",
            json={"username": username},
            headers={**admin_headers, "Host": "attacker.example"},
        )

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert payload["delivery_status"] == "sent"
        assert payload["recipient_email"] == "quality-invite@example.test"
        assert payload["expires_at"]
        assert "invite_code" not in payload
        assert "setup_url" not in payload
        assert len(sent) == 1

        args, _ = sent[0]
        assert args[0] == "quality-invite@example.test"
        assert args[1] == "KFL Aviation DMS account invitation"
        text_body, html_body = args[2], args[3]
        expected_link = f"https://dms.example.test/setup?username={username}#setup_token="
        assert expected_link in text_body
        assert "Complete account setup" in html_body
        assert expected_link in html_body

        setup_url = next(line for line in text_body.splitlines() if line.startswith("https://"))
        setup_token = parse_qs(urlsplit(setup_url).fragment)["setup_token"][0]
        assert len(setup_token) == 64

        setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": username, "setup_token": setup_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert setup.status_code == 200
        repeated = client.post(
            "/api/p0/auth/password-setup",
            json={"username": username, "setup_token": setup_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert repeated.status_code == 400

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            token_row = conn.execute(
                "SELECT token_hash, invite_code FROM auth_setup_tokens WHERE user_id = 'u-quality' AND purpose = 'invite'"
            ).fetchone()
            delivery = conn.execute(
                "SELECT status, recipient_email, attempt_count FROM auth_invite_email_outbox WHERE user_id = 'u-quality'"
            ).fetchone()
        finally:
            conn.close()
        assert token_row is not None
        assert token_row[1] is None
        assert setup_token not in token_row[0]
        assert delivery == ("sent", "quality-invite@example.test", 1)
    finally:
        _restore_invitee(original)


def test_successful_invite_revokes_older_generic_setup_token(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    actor = admin_headers["X-Actor"]
    attempt_host = "invite-revoke-generic-setup-test"
    monkeypatch.setattr(p0_routes, "_client_ip", lambda request: attempt_host)
    attempt_key = _token_hash(f"invite\0{actor}\0{attempt_host}")
    sent_bodies = []
    _enable_invite_email(monkeypatch, lambda to, subject, body, html: sent_bodies.append(body) or True)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()

    try:
        generic = client.post(
            "/api/p0/auth/users/u-quality/setup-token",
            headers=admin_headers,
        )
        assert generic.status_code == 200
        generic_token = generic.json()["setup_token"]

        invite = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0]},
            headers=admin_headers,
        )
        assert invite.status_code == 200
        invite_url = next(line for line in sent_bodies[0].splitlines() if line.startswith("https://"))
        invite_token = parse_qs(urlsplit(invite_url).fragment)["setup_token"][0]

        stale_setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": original[0], "setup_token": generic_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert stale_setup.status_code == 400

        current_setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": original[0], "setup_token": invite_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert current_setup.status_code == 200
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
            conn.commit()
        finally:
            conn.close()
        _restore_invitee(original)


def test_generic_setup_reissue_marks_previous_invite_superseded(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    actor = admin_headers["X-Actor"]
    attempt_host = "generic-setup-reissue-test"
    monkeypatch.setattr(p0_routes, "_client_ip", lambda request: attempt_host)
    attempt_key = _token_hash(f"invite\0{actor}\0{attempt_host}")
    sent_bodies = []
    _enable_invite_email(monkeypatch, lambda to, subject, body, html: sent_bodies.append(body) or True)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()

    try:
        invite = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0]},
            headers=admin_headers,
        )
        assert invite.status_code == 200
        delivery_id = invite.json()["delivery_id"]
        invite_url = next(line for line in sent_bodies[0].splitlines() if line.startswith("https://"))
        invite_token = parse_qs(urlsplit(invite_url).fragment)["setup_token"][0]

        generic = client.post(
            "/api/p0/auth/users/u-quality/setup-token",
            headers=admin_headers,
        )
        assert generic.status_code == 200
        generic_token = generic.json()["setup_token"]

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            delivery_status = conn.execute(
                "SELECT status FROM auth_invite_email_outbox WHERE delivery_id = ?",
                (delivery_id,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert delivery_status == "superseded"

        stale_invite = client.post(
            "/api/p0/auth/password-setup",
            json={"username": original[0], "setup_token": invite_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert stale_invite.status_code == 400
        current_setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": original[0], "setup_token": generic_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert current_setup.status_code == 200
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
            conn.commit()
        finally:
            conn.close()
        _restore_invitee(original)


def test_invite_rate_limit_counts_successful_deliveries(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    actor = admin_headers["X-Actor"]
    attempt_host = "invite-rate-test"
    monkeypatch.setattr(p0_routes, "_client_ip", lambda request: attempt_host)
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: True)
    attempt_key = _token_hash(f"invite\0{actor}\0{attempt_host}")
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()

    try:
        responses = [
            client.post(
                "/api/p0/auth/invites",
                json={"username": original[0], "resend": index > 0},
                headers=admin_headers,
            )
            for index in range(6)
        ]
        assert [response.status_code for response in responses] == [200, 200, 200, 200, 200, 429]
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
            conn.commit()
        finally:
            conn.close()
        _restore_invitee(original)


def test_invite_email_disabled_fails_closed_without_creating_a_token(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    monkeypatch.setattr(notifications, "INVITE_EMAIL_ENABLED", False, raising=False)
    try:
        response = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0]},
            headers=admin_headers,
        )
        assert response.status_code == 503
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            tokens = conn.execute("SELECT COUNT(*) FROM auth_setup_tokens WHERE user_id = 'u-quality'").fetchone()[0]
            deliveries = conn.execute(
                "SELECT COUNT(*) FROM auth_invite_email_outbox WHERE user_id = 'u-quality'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert tokens == 0
        assert deliveries == 0
    finally:
        _restore_invitee(original)


def test_manual_invite_fallback_returns_a_link_only_when_explicitly_requested(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://dms.example.test")
    monkeypatch.setattr(notifications, "INVITE_EMAIL_ENABLED", False, raising=False)
    monkeypatch.setattr(
        notifications,
        "send_invitation_email",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("manual delivery must not send email")),
        raising=False,
    )
    try:
        response = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "delivery_method": "manual"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert payload["delivery_status"] == "manual"
        assert payload["recipient_email"] == "quality-invite@example.test"
        setup_url = payload["setup_url"]
        assert setup_url.startswith("https://dms.example.test/setup?username=")
        setup_token = parse_qs(urlsplit(setup_url).fragment)["setup_token"][0]

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            token_row = conn.execute(
                "SELECT token_hash, invite_code FROM auth_setup_tokens WHERE user_id = 'u-quality' AND purpose = 'invite'"
            ).fetchone()
            delivery = conn.execute(
                "SELECT status, attempt_count FROM auth_invite_email_outbox WHERE user_id = 'u-quality'"
            ).fetchone()
        finally:
            conn.close()
        assert token_row[1] is None
        assert setup_token not in token_row[0]
        assert delivery == ("manual", 0)

        setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": original[0], "setup_token": setup_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert setup.status_code == 200
    finally:
        _restore_invitee(original)


def test_invite_cannot_be_redirected_to_a_request_supplied_address(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    sent = []
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: sent.append(args) or True)
    try:
        response = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "email": "redirect@example.test"},
            headers=admin_headers,
        )
        assert response.status_code == 409
        assert sent == []
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            tokens = conn.execute("SELECT COUNT(*) FROM auth_setup_tokens WHERE user_id = 'u-quality'").fetchone()[0]
            deliveries = conn.execute(
                "SELECT COUNT(*) FROM auth_invite_email_outbox WHERE user_id = 'u-quality'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert tokens == 0
        assert deliveries == 0
    finally:
        _restore_invitee(original)


def test_invite_delivery_email_override_delivers_to_arbitrary_address(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    sent = []
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: sent.append(args) or True)
    try:
        response = client.post(
            "/api/p0/auth/invites",
            json={
                "username": original[0],
                "delivery_email": "alternate-delivery@example.net",
                "delivery_method": "email",
            },
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["recipient_email"] == "alternate-delivery@example.net"
        assert len(sent) == 1
        # the SMTP send goes to the override address
        assert sent[0][0] == "alternate-delivery@example.net"
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            row = conn.execute(
                "SELECT recipient_email, status FROM auth_invite_email_outbox WHERE user_id = 'u-quality' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            assert row is not None
            assert row[0] == "alternate-delivery@example.net"
            assert row[1] == "sent"
        finally:
            conn.close()
    finally:
        _restore_invitee(original)


def test_invite_delivery_email_override_requires_registered_email_without_override(client, admin_headers, monkeypatch):
    original = _prepare_invitee("")
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: True)
    try:
        # No override supplied and no registered email -> still requires a registered address.
        response = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "delivery_method": "email"},
            headers=admin_headers,
        )
        assert response.status_code == 409
    finally:
        _restore_invitee(original)


def test_invite_delivery_email_override_accepts_override_for_account_without_registered_email(client, admin_headers, monkeypatch):
    original = _prepare_invitee("")
    sent = []
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: sent.append(args) or True)
    try:
        response = client.post(
            "/api/p0/auth/invites",
            json={
                "username": original[0],
                "delivery_email": "onboard-direct@example.org",
                "delivery_method": "email",
            },
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["recipient_email"] == "onboard-direct@example.org"
        assert len(sent) == 1
        assert sent[0][0] == "onboard-direct@example.org"
    finally:
        _restore_invitee(original)


def test_invite_requires_a_registered_email_address(client, admin_headers, monkeypatch):
    original = _prepare_invitee("")
    sent = []
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: sent.append(args) or True)
    try:
        response = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0]},
            headers=admin_headers,
        )
        assert response.status_code == 409
        assert sent == []
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            tokens = conn.execute("SELECT COUNT(*) FROM auth_setup_tokens WHERE user_id = 'u-quality'").fetchone()[0]
            deliveries = conn.execute(
                "SELECT COUNT(*) FROM auth_invite_email_outbox WHERE user_id = 'u-quality'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert tokens == 0
        assert deliveries == 0
    finally:
        _restore_invitee(original)


def test_duplicate_invite_requires_explicit_reissue(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    actor = admin_headers["X-Actor"]
    attempt_host = "invite-idempotency-test"
    monkeypatch.setattr(p0_routes, "_client_ip", lambda request: attempt_host)
    sent_bodies = []
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: sent_bodies.append(args[2]) or True)
    attempt_key = _token_hash(f"invite\0{actor}\0{attempt_host}")
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()

    try:
        first = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "resend": False},
            headers=admin_headers,
        )
        duplicate = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "resend": False},
            headers=admin_headers,
        )
        assert first.status_code == 200
        assert duplicate.status_code == 409
        assert duplicate.json()["delivery_id"] == first.json()["delivery_id"]
        assert duplicate.json()["delivery_status"] == "sent"
        assert "setup_url" not in duplicate.json()
        assert len(sent_bodies) == 1

        reissued = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "resend": True},
            headers=admin_headers,
        )
        assert reissued.status_code == 200
        assert reissued.json()["delivery_id"] != first.json()["delivery_id"]
        assert len(sent_bodies) == 2
        old_link = next(line for line in sent_bodies[0].splitlines() if line.startswith("https://"))
        new_link = next(line for line in sent_bodies[1].splitlines() if line.startswith("https://"))
        assert parse_qs(urlsplit(old_link).fragment)["setup_token"] != parse_qs(urlsplit(new_link).fragment)["setup_token"]
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            statuses = conn.execute(
                "SELECT status FROM auth_invite_email_outbox WHERE user_id = 'u-quality' ORDER BY rowid"
            ).fetchall()
        finally:
            conn.close()
        assert [row[0] for row in statuses] == ["superseded", "sent"]
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
            conn.commit()
        finally:
            conn.close()
        _restore_invitee(original)


def test_failed_reissue_preserves_the_last_delivered_invitation(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    actor = admin_headers["X-Actor"]
    attempt_host = "invite-failed-reissue-test"
    monkeypatch.setattr(p0_routes, "_client_ip", lambda request: attempt_host)
    attempt_key = _token_hash(f"invite\0{actor}\0{attempt_host}")
    sent_bodies = []
    fail_send = {"value": False}

    def sender(to, subject, body, html):
        sent_bodies.append(body)
        if fail_send["value"]:
            raise OSError("simulated SMTP failure")
        return True

    _enable_invite_email(monkeypatch, sender)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()

    try:
        first = client.post("/api/p0/auth/invites", json={"username": original[0]}, headers=admin_headers)
        assert first.status_code == 200
        first_id = first.json()["delivery_id"]
        old_url = next(line for line in sent_bodies[0].splitlines() if line.startswith("https://"))
        old_token = parse_qs(urlsplit(old_url).fragment)["setup_token"][0]

        fail_send["value"] = True
        failed_reissue = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "resend": True},
            headers=admin_headers,
        )
        assert failed_reissue.status_code == 502
        second_id = failed_reissue.json()["delivery_id"]
        new_url = next(line for line in sent_bodies[1].splitlines() if line.startswith("https://"))
        new_token = parse_qs(urlsplit(new_url).fragment)["setup_token"][0]

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            old_state = conn.execute(
                """SELECT t.used_at, d.status FROM auth_setup_tokens t
                   JOIN auth_invite_email_outbox d ON d.setup_id = t.setup_id WHERE d.delivery_id = ?""",
                (first_id,),
            ).fetchone()
            new_state = conn.execute(
                """SELECT t.used_at, d.status FROM auth_setup_tokens t
                   JOIN auth_invite_email_outbox d ON d.setup_id = t.setup_id WHERE d.delivery_id = ?""",
                (second_id,),
            ).fetchone()
        finally:
            conn.close()
        assert old_state == (None, "sent")
        assert new_state[0] is not None
        assert new_state[1] == "failed"
        assert new_token != old_token

        old_setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": original[0], "setup_token": old_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert old_setup.status_code == 200
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
            conn.commit()
        finally:
            conn.close()
        _restore_invitee(original)


def test_smtp_refusal_marks_reissue_failed_and_keeps_previous_invite_usable(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    recipient = "quality-invite@example.test"
    actor = admin_headers["X-Actor"]
    attempt_host = "invite-smtp-refusal-test"
    monkeypatch.setattr(p0_routes, "_client_ip", lambda request: attempt_host)
    attempt_key = _token_hash(f"invite\0{actor}\0{attempt_host}")
    smtp_client = MagicMock()
    smtp_client.send_message.side_effect = [{}, {recipient: (550, b"recipient refused")}]
    smtp_factory = MagicMock()
    smtp_factory.return_value.__enter__.return_value = smtp_client
    monkeypatch.setattr(notifications.smtplib, "SMTP", smtp_factory)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://dms.example.test")
    monkeypatch.setattr(notifications, "INVITE_EMAIL_ENABLED", True)
    monkeypatch.setattr(notifications, "NOTIFICATION_ENABLED", False)
    monkeypatch.setattr(notifications, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(notifications, "SMTP_PORT", 587)
    monkeypatch.setattr(notifications, "SMTP_USER", "mailer@example.test")
    monkeypatch.setattr(notifications, "SMTP_PASS", "unit-test-password")
    monkeypatch.setattr(notifications, "SMTP_FROM", "no-reply@example.test")
    monkeypatch.setattr(notifications, "SMTP_FROM_CONFIGURED", True)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()

    try:
        first = client.post("/api/p0/auth/invites", json={"username": original[0]}, headers=admin_headers)
        assert first.status_code == 200
        first_id = first.json()["delivery_id"]
        first_message = smtp_client.send_message.call_args_list[0].args[0]
        text_body = first_message.get_payload(0).get_payload(decode=True).decode("utf-8")
        old_url = next(line for line in text_body.splitlines() if line.startswith("https://"))
        old_token = parse_qs(urlsplit(old_url).fragment)["setup_token"][0]

        failed_reissue = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "resend": True},
            headers=admin_headers,
        )
        assert failed_reissue.status_code == 502
        assert failed_reissue.json()["delivery_status"] == "failed"
        second_id = failed_reissue.json()["delivery_id"]

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            old_state = conn.execute(
                """SELECT t.used_at, d.status FROM auth_setup_tokens t
                   JOIN auth_invite_email_outbox d ON d.setup_id = t.setup_id WHERE d.delivery_id = ?""",
                (first_id,),
            ).fetchone()
            new_state = conn.execute(
                """SELECT t.used_at, d.status FROM auth_setup_tokens t
                   JOIN auth_invite_email_outbox d ON d.setup_id = t.setup_id WHERE d.delivery_id = ?""",
                (second_id,),
            ).fetchone()
        finally:
            conn.close()
        assert old_state == (None, "sent")
        assert new_state[0] is not None
        assert new_state[1] == "failed"

        old_setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": original[0], "setup_token": old_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert old_setup.status_code == 200
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
            conn.commit()
        finally:
            conn.close()
        _restore_invitee(original)


def test_pending_delivery_blocks_overlapping_explicit_reissue(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    actor = admin_headers["X-Actor"]
    attempt_host = "invite-pending-resend-test"
    monkeypatch.setattr(p0_routes, "_client_ip", lambda request: attempt_host)
    attempt_key = _token_hash(f"invite\0{actor}\0{attempt_host}")
    sends = []
    _enable_invite_email(monkeypatch, lambda *args, **kwargs: sends.append(args) or True)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()

    try:
        first = client.post("/api/p0/auth/invites", json={"username": original[0]}, headers=admin_headers)
        assert first.status_code == 200
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute(
                "UPDATE auth_invite_email_outbox SET status = 'pending' WHERE delivery_id = ?",
                (first.json()["delivery_id"],),
            )
            conn.commit()
        finally:
            conn.close()

        overlapping = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0], "resend": True},
            headers=admin_headers,
        )
        assert overlapping.status_code == 409
        assert overlapping.json()["delivery_status"] == "pending"
        assert len(sends) == 1
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
            conn.commit()
        finally:
            conn.close()
        _restore_invitee(original)


def test_late_smtp_completion_cannot_overwrite_a_superseded_delivery(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    sent_bodies = []

    def supersede_during_send(to, subject, body, html):
        sent_bodies.append(body)
        setup_url = next(line for line in body.splitlines() if line.startswith("https://"))
        setup_token = parse_qs(urlsplit(setup_url).fragment)["setup_token"][0]
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            setup_id = conn.execute(
                "SELECT setup_id FROM auth_setup_tokens WHERE token_hash = ?",
                (_token_hash(setup_token),),
            ).fetchone()[0]
            conn.execute("UPDATE auth_setup_tokens SET used_at = 'superseded' WHERE setup_id = ?", (setup_id,))
            conn.execute("UPDATE auth_invite_email_outbox SET status = 'superseded' WHERE setup_id = ?", (setup_id,))
            conn.commit()
        finally:
            conn.close()
        return True

    _enable_invite_email(monkeypatch, supersede_during_send)
    try:
        response = client.post(
            "/api/p0/auth/invites",
            json={"username": original[0]},
            headers=admin_headers,
        )
        assert response.status_code == 409
        assert response.json()["delivery_status"] == "superseded"
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            status = conn.execute(
                "SELECT status FROM auth_invite_email_outbox WHERE user_id = 'u-quality'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert status == "superseded"
    finally:
        _restore_invitee(original)


def test_failed_delivery_revokes_link_and_reissue_creates_a_fresh_one(client, admin_headers, monkeypatch):
    original = _prepare_invitee("quality-invite@example.test")
    actor = admin_headers["X-Actor"]
    attempt_host = "invite-retry-test"
    monkeypatch.setattr(p0_routes, "_client_ip", lambda request: attempt_host)
    attempt_key = _token_hash(f"invite\0{actor}\0{attempt_host}")
    sent_bodies = []

    def fail_delivery(to, subject, body, html):
        sent_bodies.append(body)
        raise OSError("simulated SMTP failure")

    _enable_invite_email(monkeypatch, fail_delivery)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()

    try:
        failed = client.post("/api/p0/auth/invites", json={"username": original[0]}, headers=admin_headers)
        assert failed.status_code == 502
        failed_payload = failed.json()
        assert failed_payload["delivery_status"] == "failed"
        assert failed_payload["delivery_id"]
        old_url = next(line for line in sent_bodies[0].splitlines() if line.startswith("https://"))
        old_token = parse_qs(urlsplit(old_url).fragment)["setup_token"][0]
        assert old_token not in failed.text

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            failed_token = conn.execute(
                "SELECT used_at FROM auth_setup_tokens WHERE user_id = 'u-quality' AND purpose = 'invite'"
            ).fetchone()
            failed_delivery = conn.execute(
                "SELECT status, attempt_count, failure_code FROM auth_invite_email_outbox WHERE delivery_id = ?",
                (failed_payload["delivery_id"],),
            ).fetchone()
        finally:
            conn.close()
        assert failed_token[0] is not None
        assert failed_delivery == ("failed", 1, "smtp_or_template_failure")

        sent_bodies.clear()
        _enable_invite_email(monkeypatch, lambda *args, **kwargs: sent_bodies.append(args[2]) or True)
        retried = client.post("/api/p0/auth/invites", json={"username": original[0]}, headers=admin_headers)
        assert retried.status_code == 200
        new_url = next(line for line in sent_bodies[0].splitlines() if line.startswith("https://"))
        new_token = parse_qs(urlsplit(new_url).fragment)["setup_token"][0]
        assert new_token != old_token

        old_setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": original[0], "setup_token": old_token, "password": TEST_PASSWORD},
            headers={"Origin": "http://localhost:5173"},
        )
        assert old_setup.status_code == 400
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            statuses = conn.execute(
                "SELECT status FROM auth_invite_email_outbox WHERE user_id = 'u-quality' ORDER BY rowid"
            ).fetchall()
        finally:
            conn.close()
        assert [row[0] for row in statuses] == ["failed", "sent"]
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM auth_login_attempts WHERE attempt_key = ?", (attempt_key,))
            conn.commit()
        finally:
            conn.close()
        _restore_invitee(original)
