from pathlib import Path
import ssl
from unittest.mock import MagicMock

import pytest

from app.notifications import _load_smtp_password


def test_smtp_secret_file_takes_precedence_over_environment_password(tmp_path):
    secret = tmp_path / "smtp-password"
    secret.write_text("mounted-secret-value\n", encoding="utf-8")

    assert _load_smtp_password(str(secret), "environment-value") == "mounted-secret-value"


def test_missing_smtp_secret_file_fails_closed_without_exposing_path(tmp_path):
    missing = tmp_path / "missing-secret"

    with pytest.raises(RuntimeError, match="SMTP password secret file cannot be read") as error:
        _load_smtp_password(str(missing), "environment-value")

    assert str(missing) not in str(error.value)


def test_empty_smtp_secret_file_fails_closed(tmp_path):
    secret = tmp_path / "empty-secret"
    secret.write_text("\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="SMTP password secret file is empty"):
        _load_smtp_password(str(secret), "environment-value")


def test_environment_password_remains_available_for_local_development():
    assert _load_smtp_password("", "development-password") == "development-password"


def test_smtp_starttls_uses_a_certificate_verifying_context(monkeypatch):
    from app import notifications

    smtp_client = MagicMock()
    smtp_client.send_message.return_value = {}
    smtp_factory = MagicMock()
    smtp_factory.return_value.__enter__.return_value = smtp_client
    monkeypatch.setattr(notifications.smtplib, "SMTP", smtp_factory)
    monkeypatch.setattr(notifications, "NOTIFICATION_ENABLED", True)
    monkeypatch.setattr(notifications, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(notifications, "SMTP_PORT", 587)
    monkeypatch.setattr(notifications, "SMTP_USER", "mailer@example.test")
    monkeypatch.setattr(notifications, "SMTP_PASS", "test-password")
    monkeypatch.setattr(notifications, "persist_notification", lambda *args, **kwargs: None)

    assert notifications.send_email("recipient@example.test", "Subject", "Body")

    tls_context = smtp_client.starttls.call_args.kwargs["context"]
    assert isinstance(tls_context, ssl.SSLContext)
    assert tls_context.verify_mode == ssl.CERT_REQUIRED
    assert tls_context.check_hostname is True


def test_invitation_email_uses_its_own_flag_and_does_not_persist_the_bearer_link(monkeypatch):
    from app import notifications

    smtp_client = MagicMock()
    smtp_client.send_message.return_value = {}
    smtp_factory = MagicMock()
    smtp_factory.return_value.__enter__.return_value = smtp_client
    monkeypatch.setattr(notifications.smtplib, "SMTP", smtp_factory)
    monkeypatch.setattr(notifications, "INVITE_EMAIL_ENABLED", True)
    monkeypatch.setattr(notifications, "NOTIFICATION_ENABLED", False)
    monkeypatch.setattr(notifications, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(notifications, "SMTP_PORT", 587)
    monkeypatch.setattr(notifications, "SMTP_USER", "mailer@example.test")
    monkeypatch.setattr(notifications, "SMTP_PASS", "test-password")
    monkeypatch.setattr(notifications, "SMTP_FROM", "no-reply@example.test")
    monkeypatch.setattr(notifications, "SMTP_FROM_CONFIGURED", True)
    monkeypatch.setattr(
        notifications,
        "persist_notification",
        lambda *args, **kwargs: pytest.fail("invite body must not be persisted in notifications"),
    )

    assert notifications.send_invitation_email(
        "recipient@example.test",
        "Invitation",
        "Plain body with one-time link",
        "<a href=\"https://dms.example.test/setup#setup_token=test-token\">Complete setup</a>",
    )

    smtp_client.starttls.assert_called_once()
    smtp_client.login.assert_called_once_with("mailer@example.test", "test-password")
    message = smtp_client.send_message.call_args.args[0]
    assert message["To"] == "recipient@example.test"
    assert message.get_content_subtype() == "alternative"
    assert len(message.get_payload()) == 2


def test_invitation_email_requires_feature_flag_and_complete_smtp_configuration(monkeypatch):
    from app import notifications

    monkeypatch.setattr(notifications, "INVITE_EMAIL_ENABLED", False)
    with pytest.raises(RuntimeError, match="Invite email is disabled"):
        notifications.send_invitation_email("recipient@example.test", "Invitation", "Text", "<p>HTML</p>")

    monkeypatch.setattr(notifications, "INVITE_EMAIL_ENABLED", True)
    monkeypatch.setattr(notifications, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(notifications, "SMTP_USER", "mailer@example.test")
    monkeypatch.setattr(notifications, "SMTP_PASS", "test-password")
    monkeypatch.setattr(notifications, "SMTP_FROM_CONFIGURED", False)
    with pytest.raises(RuntimeError, match="SMTP is not configured"):
        notifications.send_invitation_email("recipient@example.test", "Invitation", "Text", "<p>HTML</p>")


def test_invitation_email_raises_when_smtp_refuses_the_recipient(monkeypatch):
    from app import notifications

    smtp_client = MagicMock()
    smtp_client.send_message.return_value = {"recipient@example.test": (550, b"recipient refused")}
    smtp_factory = MagicMock()
    smtp_factory.return_value.__enter__.return_value = smtp_client
    monkeypatch.setattr(notifications.smtplib, "SMTP", smtp_factory)
    monkeypatch.setattr(notifications, "INVITE_EMAIL_ENABLED", True)
    monkeypatch.setattr(notifications, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(notifications, "SMTP_PORT", 587)
    monkeypatch.setattr(notifications, "SMTP_USER", "mailer@example.test")
    monkeypatch.setattr(notifications, "SMTP_PASS", "test-password")
    monkeypatch.setattr(notifications, "SMTP_FROM", "no-reply@example.test")
    monkeypatch.setattr(notifications, "SMTP_FROM_CONFIGURED", True)

    with pytest.raises(RuntimeError, match="SMTP refused one or more recipients"):
        notifications.send_invitation_email(
            "recipient@example.test",
            "Invitation",
            "Text with a setup link",
            "<p>Invitation</p>",
        )
