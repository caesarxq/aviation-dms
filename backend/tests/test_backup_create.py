"""Tests for backup_create and backup_scheduler modules.

Uses isolated temporary directories so no live data is touched.
"""

import asyncio
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.backup_create import create_backup_candidate, BackupCreateError
from app.backup_scheduler import BackupScheduler


@pytest.fixture
def temp_data_root(tmp_path):
    """Create a fake DMS data root with a database and upload storage."""
    data_root = tmp_path / "data"
    data_root.mkdir()

    # Create a minimal SQLite database
    db_path = data_root / "dms.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            role TEXT NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO users (user_id, username, role) VALUES ('u-1', 'admin', 'system_admin')"
    )
    conn.commit()
    conn.close()

    # Create upload storage roots
    for root_name in ("uploads", "kcaa-evidence", "attachments"):
        (data_root / root_name).mkdir()
        # Add a test file in each
        (data_root / root_name / "test-file.txt").write_text("test content")

    return data_root


@pytest.fixture
def temp_backup_root(tmp_path):
    """Create an isolated backup destination root."""
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    return backup_root


class TestBackupCreate:
    def test_creates_backup_candidate(self, temp_data_root, temp_backup_root):
        result = asyncio.run(
            create_backup_candidate(
                source_data_root=temp_data_root,
                dest_root=temp_backup_root,
            )
        )
        assert result["database_size_bytes"] > 0
        assert result["files_copied"] >= 1  # at least dms.db
        assert "verification" in result
        assert "manifest" in result
        # Verification runs (may not be accepted with minimal test schema)
        assert result["verification"]["read_only"] is True
        assert result["verification"]["manifest"]["present"] is True
        assert result["verification"]["manifest"]["matches"] is True

        # Candidate directory should exist
        candidate = Path(result["candidate_path"])
        assert candidate.is_dir()
        assert (candidate / "dms.db").is_file()
        assert (candidate / "backup-manifest.json").is_file()

    def test_refuses_overlapping_destination(self, temp_data_root):
        # Destination inside source root should be refused
        with pytest.raises(BackupCreateError, match="overlaps"):
            asyncio.run(
                create_backup_candidate(
                    source_data_root=temp_data_root,
                    dest_root=temp_data_root / "backups",
                )
            )

    def test_refuses_destination_equal_to_source(self, temp_data_root):
        with pytest.raises(BackupCreateError, match="overlaps"):
            asyncio.run(
                create_backup_candidate(
                    source_data_root=temp_data_root,
                    dest_root=temp_data_root,
                )
            )

    def test_refuses_unmapped_top_level_data_root(self, temp_data_root, temp_backup_root):
        (temp_data_root / "document_files").mkdir()
        (temp_data_root / "unmapped-records").mkdir()

        with pytest.raises(BackupCreateError, match="unmapped storage root"):
            asyncio.run(
                create_backup_candidate(
                    source_data_root=temp_data_root,
                    dest_root=temp_backup_root,
                )
            )

    def test_manifest_and_verification_consistency(self, temp_data_root, temp_backup_root):
        result = asyncio.run(
            create_backup_candidate(
                source_data_root=temp_data_root,
                dest_root=temp_backup_root,
            )
        )
        verification = result["verification"]
        assert verification["read_only"] is True
        # Manifest is created and matches
        manifest = verification["manifest"]
        assert manifest["present"] is True
        assert manifest["matches"] is True
        # SQLite integrity passes even with minimal schema
        assert verification["sqlite"]["database_present"] is True
        assert verification["sqlite"]["quick_check_ok"] is True
        assert verification["sqlite"]["integrity_check_ok"] is True

    def test_copies_upload_storage_roots(self, temp_data_root, temp_backup_root):
        result = asyncio.run(
            create_backup_candidate(
                source_data_root=temp_data_root,
                dest_root=temp_backup_root,
            )
        )
        paths = {f["path"] for f in result["file_inventory"]}
        assert any("uploads/test-file.txt" in p for p in paths)
        assert any("kcaa-evidence/test-file.txt" in p for p in paths)
        assert any("attachments/test-file.txt" in p for p in paths)

    def test_copies_document_files_and_extraction_storage(self, temp_data_root, temp_backup_root):
        document_root = temp_data_root / "document_files"
        extract_root = document_root / "extracts"
        extract_root.mkdir(parents=True)
        (document_root / "source.pdf").write_bytes(b"document source")
        (extract_root / "section.pdf").write_bytes(b"section extract")

        result = asyncio.run(
            create_backup_candidate(
                source_data_root=temp_data_root,
                dest_root=temp_backup_root,
            )
        )

        paths = {entry["path"] for entry in result["file_inventory"]}
        assert "document_files/source.pdf" in paths
        assert "document_files/extracts/section.pdf" in paths


class TestBackupScheduler:
    def test_scheduler_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("DMS_BACKUP_ENABLED", raising=False)
        scheduler = BackupScheduler()
        assert scheduler.enabled is False

    def test_scheduler_enabled_when_env_set(self, monkeypatch):
        monkeypatch.setenv("DMS_BACKUP_ENABLED", "true")
        monkeypatch.setenv("DMS_BACKUP_DATA_ROOT", "/tmp/fake-source")
        monkeypatch.setenv("DMS_BACKUP_DEST_ROOT", "/tmp/fake-dest")
        scheduler = BackupScheduler()
        assert scheduler.enabled is True

    def test_scheduler_refuses_without_roots(self, monkeypatch):
        monkeypatch.setenv("DMS_BACKUP_ENABLED", "true")
        monkeypatch.delenv("DMS_BACKUP_DATA_ROOT", raising=False)
        monkeypatch.delenv("DMS_BACKUP_DEST_ROOT", raising=False)
        scheduler = BackupScheduler()
        assert scheduler.source_data_root == ""
        assert scheduler.dest_root == ""

    def test_status_returns_dict(self, monkeypatch):
        monkeypatch.delenv("DMS_BACKUP_ENABLED", raising=False)
        scheduler = BackupScheduler()
        status = scheduler.status()
        assert "enabled" in status
        assert "running" in status
        assert "interval_seconds" in status
        assert status["enabled"] is False
        assert status["running"] is False
