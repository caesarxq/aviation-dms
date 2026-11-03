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
