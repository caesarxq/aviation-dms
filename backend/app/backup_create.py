"""Create isolated backup candidates from live DMS data.

This module copies the live SQLite database (using the online backup API for
consistency) and all configured upload storage roots into a timestamped
candidate directory, then creates a manifest and verifies integrity.

All operations are copy-only: nothing is deleted, moved, or modified on the
live system. The candidate directory must never overlap with the active data
root -- that condition is refused with an error.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import sqlite3
import stat
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Optional

from .backup_validation import (
    MANIFEST_NAME,
    _candidate_root,
    _file_entries,
    write_backup_manifest,
    verify_backup_candidate,
)
from .database import DB_PATH

# Upload storage roots that must be included in every backup candidate.
# These paths mirror the defaults used by upload_reconciliation.py.
DEFAULT_STORAGE_ROOTS = (
    "uploads",
    "kcaa-evidence",
    "attachments",
    "document_files",
)


class BackupCreateError(RuntimeError):
    """Raised when backup candidate creation cannot proceed safely."""


def _data_root() -> Path:
    """Return the resolved active DMS data root (parent of DB_PATH)."""
    return Path(DB_PATH).resolve().parent


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _copy_sqlite_database(source_db: Path, dest_db: Path) -> int:
    """Copy a SQLite database using the online backup API for a consistent snapshot.

    Returns the number of pages copied.
    """
    source = sqlite3.connect(str(source_db.resolve()))
    dest = sqlite3.connect(str(dest_db.resolve()))
    try:
        with dest:
            source.backup(dest)
    finally:
        source.close()
        dest.close()
    return dest_db.stat().st_size if dest_db.is_file() else 0


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        with os.fdopen(descriptor, "rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
    finally:
        pass  # fdopen takes ownership of the descriptor
    return digest.hexdigest()


def _copy_file_tree(source_root: Path, dest_root: Path) -> dict[str, dict]:
    """Copy a directory tree of regular files only. Symlinks are refused.

    Returns a mapping of relative path -> {size, sha256}.
    """
    entries: dict[str, dict] = {}
    pending = [source_root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as children:
                for child in children:
                    child_path = Path(child.path)
                    info = child.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        raise BackupCreateError(
                            f"Refusing to copy symlink: {child_path}"
                        )
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(child_path)
                        continue
                    if not stat.S_ISREG(info.st_mode):
                        raise BackupCreateError(
                            f"Refusing to copy non-regular file: {child_path}"
                        )
                    relative = child_path.relative_to(source_root).as_posix()
                    relative_path = PurePosixPath(relative)
                    if (
                        relative_path.is_absolute()
                        or any(part in {"", ".", ".."} for part in relative_path.parts)
                    ):
                        raise BackupCreateError(
                            f"Unsafe relative path in storage: {relative}"
                        )
                    dest_file = dest_root / relative
                    dest_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    shutil.copy2(child_path, dest_file)
                    os.chmod(dest_file, 0o600)
                    entries[relative] = {
                        "size": info.st_size,
                        "sha256": _hash_file(child_path),
                    }
        except OSError as exc:
            raise BackupCreateError(
                f"Could not inventory storage root {source_root}: {exc}"
            ) from exc
    return entries


def _validate_source_data_root(source_root: Path, storage_roots: tuple[str, ...]) -> None:
    """Refuse unknown or unsafe top-level entries instead of silently omitting data."""
    allowed_files = {
        "dms.db",
        "dms.db-wal",
        "dms.db-shm",
        "dms.db-journal",
        ".dms-upload-storage.lock",
    }
    allowed = allowed_files | set(storage_roots)
    try:
        entries = list(os.scandir(source_root))
    except OSError as exc:
        raise BackupCreateError("Could not inventory the active DMS data root") from exc
    for entry in entries:
        if entry.name not in allowed:
            raise BackupCreateError(f"Refusing unmapped storage root: {entry.name}")
        info = entry.stat(follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            raise BackupCreateError(f"Refusing symlink in active DMS data root: {entry.name}")
        if entry.name in storage_roots and not stat.S_ISDIR(info.st_mode):
            raise BackupCreateError(f"Storage root is not a regular directory: {entry.name}")
        if entry.name in allowed_files and not stat.S_ISREG(info.st_mode):
            raise BackupCreateError(f"Database or lock entry is not a regular file: {entry.name}")


async def create_backup_candidate(
    source_data_root: Optional[Path | str] = None,
    dest_root: Optional[Path | str] = None,
    include_storage_roots: tuple[str, ...] = DEFAULT_STORAGE_ROOTS,
) -> dict:
    """Create an isolated backup candidate from live DMS data.

    Steps:
      1. Validate source and destination do not overlap.
      2. Copy the SQLite database using the online backup API.
      3. Copy each configured upload storage root.
      4. Create a backup-manifest.json beside the candidate.
      5. Run read-only verification on the candidate.

    Returns the verification report dict.
    """
    source_input = Path(source_data_root) if source_data_root else Path(DB_PATH).parent
    if source_input.is_symlink():
        raise BackupCreateError("Active DMS data root must not be a symlink")
    source_root = source_input.resolve()
    dest = (
        Path(dest_root).resolve() if dest_root else _data_root().parent / "backups"
    )

    if not source_root.is_dir():
        raise BackupCreateError("Active DMS data root must be a regular directory")
    if any(not name or Path(name).name != name or name in {".", ".."} for name in include_storage_roots):
        raise BackupCreateError("Backup storage-root names must be safe top-level directories")
    _validate_source_data_root(source_root, include_storage_roots)

    # Refuse if destination overlaps with source.
    if dest == source_root or dest.is_relative_to(source_root) or source_root.is_relative_to(dest):
        raise BackupCreateError(
            "Backup destination overlaps the active DMS data root; refusing to proceed"
        )

    # Destination must be a regular directory (or creatable as one).
    if dest.exists():
        info = dest.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise BackupCreateError(
                f"Backup destination exists but is not a regular directory: {dest}"
            )
    else:
        dest.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Candidate directory name with timestamp.
    candidate = dest / f"dms-backup-{_iso_now()}"
    candidate.mkdir(parents=True, exist_ok=True, mode=0o700)

    created_at = datetime.now(tz=timezone.utc).isoformat()
    files_copied: list[dict] = []

    try:
        # --- 1. Copy SQLite database (consistent online backup) ---
        source_db = source_root / "dms.db"
        if not source_db.is_file():
            raise BackupCreateError(f"Live database not found: {source_db}")
        dest_db = candidate / "dms.db"
        db_size = _copy_sqlite_database(source_db, dest_db)
        files_copied.append(
            {
                "path": "dms.db",
                "size": db_size,
                "sha256": _hash_file(dest_db),
                "copied_from": str(source_db),
            }
        )

        # --- 2. Copy each configured upload storage root ---
        for root_name in include_storage_roots:
            source_storage = source_root / root_name
            if not source_storage.exists():
                # Keep the expected root present in the restored candidate.
                (candidate / root_name).mkdir(parents=True, exist_ok=True, mode=0o700)
                continue
            dest_storage = candidate / root_name
            entries = _copy_file_tree(source_storage, dest_storage)
            for relative, info in entries.items():
                files_copied.append(
                    {
                        "path": f"{root_name}/{relative}",
                        "size": info["size"],
                        "sha256": info["sha256"],
                        "copied_from": str(source_storage / relative),
                    }
                )

        # Fail if a new top-level store appeared while the candidate was being copied.
        _validate_source_data_root(source_root, include_storage_roots)

        # --- 3. Create manifest beside the candidate ---
        manifest_report = write_backup_manifest(candidate)

        # --- 4. Verify the candidate (read-only) ---
        verification = verify_backup_candidate(candidate)

        return {
            "created_at": created_at,
            "candidate_path": str(candidate),
            "source_data_root": str(source_root),
            "backup_destination_root": str(dest),
            "database_size_bytes": db_size,
            "files_copied": len(files_copied),
            "file_inventory": files_copied,
            "manifest": manifest_report,
            "verification": verification,
            "accepted": verification.get("accepted", False),
            "blockers": verification.get("blockers", []),
        }
    except Exception:
        # Clean up the partially-created candidate on failure.
        import shutil as _shutil

        try:
            _shutil.rmtree(candidate)
        except OSError:
            pass
        raise
