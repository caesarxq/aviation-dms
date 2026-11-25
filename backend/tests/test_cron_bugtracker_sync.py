"""Tests for the BugTracker sync cron entry point."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cron_bugtracker_sync


def test_backend_dir_is_the_directory_containing_the_script():
    """In the container the script sits beside app/ at /app, not one level below it."""
    assert os.path.dirname(os.path.abspath(cron_bugtracker_sync.__file__)) == cron_bugtracker_sync.BACKEND_DIR


def test_import_does_not_create_log_files():
    """Importing the module must stay side-effect free for tests and probes."""
    assert cron_bugtracker_sync.log_dir is None
    assert cron_bugtracker_sync.log_file is None


def test_log_dir_honours_explicit_override(monkeypatch, tmp_path):
    target = tmp_path / "bugtracker-logs"
    monkeypatch.setenv("DMS_LOG_DIR", str(target))

    assert cron_bugtracker_sync._resolve_log_dir(str(tmp_path)) == str(target)
    assert target.is_dir()


def test_log_dir_falls_back_when_default_is_not_writable(monkeypatch, tmp_path):
    """A container root filesystem is not writable by the backend UID."""
    read_only = tmp_path / "read-only"
    read_only.mkdir()
    fallback = tmp_path / "fallback-logs"
    monkeypatch.delenv("DMS_LOG_DIR", raising=False)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("DMS_LOG_FALLBACK_DIR", str(fallback))
    read_only.chmod(0o500)
    try:
        resolved = cron_bugtracker_sync._resolve_log_dir(str(read_only))
    finally:
        read_only.chmod(0o700)

    assert resolved == str(fallback)
    assert fallback.is_dir()
