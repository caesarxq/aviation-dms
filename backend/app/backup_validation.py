"""Validate an isolated, explicit DMS data-volume restore candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
from pathlib import Path, PurePosixPath
from typing import Optional

from .database import SCHEMA
from .upload_reconciliation import reconcile_upload_storage

MANIFEST_NAME = "backup-manifest.json"
_FORMAT_VERSION = 1
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ACTIVE_DEVELOPMENT_DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
_REQUIRED_SCHEMA_TABLES = frozenset(
    re.findall(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)", SCHEMA, re.IGNORECASE)
)
_REQUIRED_SCHEMA_COLUMNS = {
    "users": {"user_id", "username", "email", "role", "is_active"},
    "user_roles": {"user_id", "role"},
    "user_id_aliases": {"legacy_user_id", "canonical_user_id"},
    "documents": {"document_id", "title", "status", "owner_id"},
    "document_versions": {"version_id", "document_id", "version_number", "state"},
    "audit_events": {"event_id", "entity_type", "entity_id", "action", "actor_id", "timestamp"},
    "audit_reports": {"audit_id", "audit_number", "audit_date", "auditor_id", "auditee_id", "status", "evidence_file", "evidence_sha256"},
    "audit_findings": {"finding_id", "audit_id", "finding_number", "title", "description", "status"},
    "audit_report_imports": {"import_id", "audit_number", "source_auditor_id", "evidence_file", "evidence_sha256", "payload_json", "payload_sha256", "imported_by", "status"},
    "personnel_uploads": {"upload_id", "person_id", "file_path", "file_size", "file_sha256"},
    "kcaa_approval_evidence": {"evidence_id", "version_id", "file_path", "file_sha256", "file_size"},
}


def _candidate_root(data_root: Path | str) -> Path:
    root = Path(data_root)
    try:
        info = root.lstat()
    except OSError as exc:
        raise ValueError("Restore candidate must be an existing directory") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ValueError("Restore candidate must be a regular directory, not a symlink")
    resolved = root.resolve()
    active_data = ACTIVE_DEVELOPMENT_DATA_ROOT.resolve(strict=False)
    if resolved == active_data or resolved.is_relative_to(active_data) or active_data.is_relative_to(resolved):
        raise ValueError("Refusing a restore candidate that overlaps active development data")
    return resolved


def _file_entries(root: Path) -> list[dict]:
    entries: list[dict] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as children:
                for child in children:
                    item_path = Path(child.path)
                    info = child.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        raise ValueError("Restore candidate contains a symbolic link")
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(item_path)
                        continue
                    if not stat.S_ISREG(info.st_mode):
                        raise ValueError("Restore candidate contains a non-regular file")
                    relative = item_path.relative_to(root).as_posix()
                    if relative == MANIFEST_NAME:
                        continue
                    relative_path = PurePosixPath(relative)
                    if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
                        raise ValueError("Restore candidate contains an unsafe relative path")
                    descriptor = os.open(item_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                    digest = hashlib.sha256()
                    total = 0
                    with os.fdopen(descriptor, "rb") as source:
                        opened = os.fstat(source.fileno())
                        if not stat.S_ISREG(opened.st_mode):
                            raise ValueError("Restore candidate contains a non-regular file")
                        while chunk := source.read(1024 * 1024):
                            total += len(chunk)
                            digest.update(chunk)
                        if total != opened.st_size:
                            raise ValueError("Restore candidate changed during inventory")
                    entries.append({"path": relative, "size": total, "sha256": digest.hexdigest()})
        except OSError as exc:
            raise ValueError("Restore candidate could not be inventoried safely") from exc
    return sorted(entries, key=lambda entry: entry["path"])


def write_backup_manifest(data_root: Path | str) -> dict:
    """Create a new manifest beside an isolated backup; never overwrite one."""
    root = _candidate_root(data_root)
    manifest_path = root / MANIFEST_NAME
    if manifest_path.exists() or manifest_path.is_symlink():
        raise ValueError("Backup manifest already exists; refusing to overwrite it")
    manifest = {"format_version": _FORMAT_VERSION, "files": _file_entries(root)}
    payload = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        directory_fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            manifest_path.unlink()
        except OSError:
            pass
        raise
    return {"manifest_created": True, "file_count": len(manifest["files"])}


def _verify_manifest(root: Path) -> dict:
    path = root / MANIFEST_NAME
    if path.is_symlink() or not path.is_file():
        return {"present": False, "matches": False, "listed_files": 0, "mismatch_count": 0}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"present": True, "matches": False, "listed_files": 0, "mismatch_count": 1}
    if not isinstance(manifest, dict) or manifest.get("format_version") != _FORMAT_VERSION:
        return {"present": True, "matches": False, "listed_files": 0, "mismatch_count": 1}
    listed = manifest.get("files")
    if not isinstance(listed, list):
        return {"present": True, "matches": False, "listed_files": 0, "mismatch_count": 1}

    expected = {}
    for entry in listed:
        if not isinstance(entry, dict):
            return {"present": True, "matches": False, "listed_files": len(listed), "mismatch_count": 1}
        relative = entry.get("path")
        size = entry.get("size")
        digest = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or not _HASH_RE.fullmatch(digest)
        ):
            return {"present": True, "matches": False, "listed_files": len(listed), "mismatch_count": 1}
        relative_path = PurePosixPath(relative)
        if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
            return {"present": True, "matches": False, "listed_files": len(listed), "mismatch_count": 1}
        if relative == MANIFEST_NAME or relative in expected:
            return {"present": True, "matches": False, "listed_files": len(listed), "mismatch_count": 1}
        expected[relative] = (size, digest)

    try:
        actual = {
            entry["path"]: (entry["size"], entry["sha256"])
            for entry in _file_entries(root)
        }
    except ValueError:
        return {"present": True, "matches": False, "listed_files": len(expected), "mismatch_count": 1}
    mismatch_count = sum(expected.get(name) != value for name, value in actual.items())
    mismatch_count += sum(name not in actual for name in expected)
    return {
        "present": True,
        "matches": mismatch_count == 0,
        "listed_files": len(expected),
        "mismatch_count": mismatch_count,
    }


def _sqlite_checks(database: Path) -> dict:
    if database.is_symlink() or not database.is_file():
        return {
            "database_present": False,
            "quick_check_ok": False,
            "integrity_check_ok": False,
            "foreign_key_violation_count": None,
        }
    try:
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            quick = [row[0] for row in connection.execute("PRAGMA quick_check")]
            integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
            foreign_keys = list(connection.execute("PRAGMA foreign_key_check"))
        finally:
            connection.close()
    except sqlite3.DatabaseError:
        return {
            "database_present": True,
            "quick_check_ok": False,
            "integrity_check_ok": False,
            "foreign_key_violation_count": None,
        }
    return {
        "database_present": True,
        "quick_check_ok": quick == ["ok"],
        "integrity_check_ok": integrity == ["ok"],
        "foreign_key_violation_count": len(foreign_keys),
    }


def _core_schema_check(database: Path) -> dict:
    try:
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            present = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            missing_columns = []
            for table, required_columns in _REQUIRED_SCHEMA_COLUMNS.items():
                if table not in present:
                    continue
                actual_columns = {
                    str(row[0])
                    for row in connection.execute("SELECT name FROM pragma_table_info(?)", (table,))
                }
                missing_columns.extend(
                    f"{table}.{column}" for column in sorted(required_columns - actual_columns)
                )
        finally:
            connection.close()
    except sqlite3.DatabaseError:
        present = set()
        missing_columns = []
    missing_tables = sorted(_REQUIRED_SCHEMA_TABLES - present)
    return {
        "present": bool(_REQUIRED_SCHEMA_TABLES) and not missing_tables and not missing_columns,
        "required_table_count": len(_REQUIRED_SCHEMA_TABLES),
        "missing_table_count": len(missing_tables),
        "missing_tables": missing_tables,
        "missing_column_count": len(missing_columns),
        "missing_columns": sorted(missing_columns),
    }


def verify_backup_candidate(data_root: Path | str) -> dict:
    """Read-only verification; does not migrate, repair, restore, or delete."""
    root = _candidate_root(data_root)
    manifest = _verify_manifest(root)
    sqlite_report = _sqlite_checks(root / "dms.db")
    core_schema = _core_schema_check(root / "dms.db") if sqlite_report["database_present"] else {
        "present": False,
        "required_table_count": len(_REQUIRED_SCHEMA_TABLES),
        "missing_table_count": len(_REQUIRED_SCHEMA_TABLES),
        "missing_tables": sorted(_REQUIRED_SCHEMA_TABLES),
        "missing_column_count": 0,
        "missing_columns": [],
    }
    storage = None
    if sqlite_report["database_present"] and sqlite_report["quick_check_ok"] and sqlite_report["integrity_check_ok"]:
        try:
            storage = reconcile_upload_storage(
                root / "dms.db",
                root / "uploads",
                root / "kcaa-evidence",
                root / "attachments",
                verify_hashes=True,
            )
        except (sqlite3.DatabaseError, ValueError):
            storage = None

    blockers = []
    if not manifest["matches"]:
        blockers.append("backup_manifest_missing_or_mismatch")
    if not sqlite_report["quick_check_ok"] or not sqlite_report["integrity_check_ok"]:
        blockers.append("sqlite_integrity_check_failed")
    if not core_schema["present"]:
        blockers.append("required_dms_schema_missing")
    if sqlite_report["foreign_key_violation_count"] not in (0, None):
        blockers.append("sqlite_foreign_key_violations")
    if sqlite_report["foreign_key_violation_count"] is None:
        blockers.append("sqlite_foreign_key_check_unavailable")
    if not sqlite_report["database_present"]:
        blockers.append("sqlite_database_missing")
    elif storage is None:
        blockers.append("storage_reconciliation_unavailable")
    else:
        for root_report in storage["roots"].values():
            if root_report["unreferenced_files"] or root_report["symlink_entries"] or root_report["scan_errors"]:
                blockers.append("storage_inventory_requires_review")
                break
        for table_report in storage["tables"].values():
            if (
                table_report["missing_files"]
                or table_report["size_mismatches"]
                or table_report["unsafe_references"]
                or table_report["hash_mismatches"]
                or table_report["hash_errors"]
            ):
                blockers.append("storage_references_require_review")
                break
            if table_report["records"] and (
                not table_report["digest_column_present"] or table_report["hashless_records"]
            ):
                blockers.append("hashless_evidence_requires_revalidation")
                break
    return {
        "read_only": True,
        "accepted": not blockers,
        "blockers": sorted(set(blockers)),
        "manifest": manifest,
        "sqlite": sqlite_report,
        "core_schema": core_schema,
        "storage": storage,
        "scope_note": "Data-integrity checks only; this does not establish off-host custody, RPO/RTO, restore service objectives, or operational/regulatory readiness.",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("create-manifest", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--data-root", required=True, type=Path)
        subparser.add_argument(
            "--confirm-isolated-candidate",
            required=True,
            action="store_true",
            help="confirm this path is a stopped, isolated candidate, never a live DMS volume",
        )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "create-manifest":
        report = write_backup_manifest(args.data_root)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    report = verify_backup_candidate(args.data_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
