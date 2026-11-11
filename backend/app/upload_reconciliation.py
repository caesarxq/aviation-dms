"""Read-only report of database file references versus persistent storage roots."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import stat
from pathlib import Path, PurePosixPath
from typing import Optional

_TABLE_SPECS = {
    "personnel_uploads": {
        "root": "uploads",
        "path_column": "file_path",
        "size_column": "file_size",
        "digest_column": "file_sha256",
    },
    "kcaa_approval_evidence": {
        "root": "kcaa_evidence",
        "path_column": "file_path",
        "name_column": "stored_filename",
        "size_column": "file_size",
        "digest_column": "file_sha256",
    },
    "audit_reports": {
        "root": "attachments",
        "path_column": "evidence_file",
        "relative_prefix": "attachments",
        "digest_column": "evidence_sha256",
    },
    "audit_report_imports": {
        "root": "attachments",
        "path_column": "evidence_file",
        "relative_prefix": "attachments",
        "digest_column": "evidence_sha256",
    },
}


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _contains_symlink(root: Path, candidate: Path) -> bool:
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _resolve_reference(root: Path, raw_value: object, relative_prefix: Optional[str]) -> Optional[Path]:
    if not isinstance(raw_value, str) or not raw_value or "\x00" in raw_value or "\\" in raw_value:
        return None
    root = Path(root)
    if root.is_symlink():
        return None
    root = root.resolve(strict=False)
    if relative_prefix:
        reference = PurePosixPath(raw_value)
        if reference.is_absolute() or len(reference.parts) != 2 or reference.parts[0] != relative_prefix:
            return None
        if reference.parts[1] in {"", ".", ".."}:
            return None
        candidate = root / reference.parts[1]
    else:
        candidate = Path(raw_value)
        if any(part in {".", ".."} for part in candidate.parts):
            return None
        if not candidate.is_absolute():
            candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root) or _contains_symlink(root, candidate):
        return None
    return resolved


def _inventory_root(root: Path) -> tuple[dict, set[Path]]:
    root = Path(root)
    result = {
        "present": False,
        "file_count": 0,
        "bytes": 0,
        "unreferenced_files": 0,
        "symlink_entries": 0,
        "scan_errors": 0,
    }
    files: set[Path] = set()
    if root.is_symlink():
        result["symlink_entries"] += 1
        return result, files
    root = root.resolve(strict=False)
    try:
        root_info = root.lstat()
    except FileNotFoundError:
        return result, files
    except OSError:
        result["scan_errors"] += 1
        return result, files
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        result["symlink_entries"] += int(stat.S_ISLNK(root_info.st_mode))
        result["scan_errors"] += int(not stat.S_ISLNK(root_info.st_mode))
        return result, files

    result["present"] = True
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        result["scan_errors"] += 1
                        continue
                    if stat.S_ISLNK(info.st_mode):
                        result["symlink_entries"] += 1
                    elif stat.S_ISDIR(info.st_mode):
                        pending.append(Path(entry.path))
                    elif stat.S_ISREG(info.st_mode):
                        file_path = Path(entry.path).resolve(strict=False)
                        files.add(file_path)
                        result["file_count"] += 1
                        result["bytes"] += info.st_size
                    else:
                        result["scan_errors"] += 1
        except OSError:
            result["scan_errors"] += 1
    return result, files


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[0]) for row in connection.execute("SELECT name FROM pragma_table_info(?)", (table,))}


def _sha256_file(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb") as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def reconcile_upload_storage(
    database: Path | str,
    uploads_root: Path | str,
    kcaa_root: Path | str,
    attachments_root: Path | str,
    verify_hashes: bool = False,
) -> dict:
    """Compare file metadata; optionally read bytes to verify stored SHA-256 values."""
    db_path = Path(database)
    try:
        info = db_path.lstat()
    except OSError as exc:
        raise ValueError("Database path must be an existing regular file") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ValueError("Database path must be a regular, non-symlink file")

    roots = {
        "uploads": Path(uploads_root),
        "kcaa_evidence": Path(kcaa_root),
        "attachments": Path(attachments_root),
    }
    root_reports: dict[str, dict] = {}
    disk_files: dict[str, set[Path]] = {}
    for name, root in roots.items():
        root_reports[name], disk_files[name] = _inventory_root(root)

    table_reports = {
        table: {
            "table_present": False,
            "records": 0,
            "missing_files": 0,
            "size_mismatches": 0,
            "unsafe_references": 0,
            "digest_column_present": False,
            "hashless_records": None,
            "hashes_checked": 0,
            "hash_mismatches": 0,
            "hash_errors": 0,
        }
        for table in _TABLE_SPECS
    }
    referenced: dict[str, set[Path]] = {name: set() for name in roots}

    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        table_names = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table, spec in _TABLE_SPECS.items():
            if table not in table_names:
                continue
            columns = _table_columns(connection, table)
            path_column = spec["path_column"]
            name_column = spec.get("name_column")
            size_column = spec.get("size_column")
            digest_column = spec.get("digest_column")
            selected = [path_column]
            if name_column and name_column in columns:
                selected.append(name_column)
            if size_column and size_column in columns:
                selected.append(size_column)
            if digest_column and digest_column in columns:
                selected.append(digest_column)
            query = "SELECT " + ", ".join(_quote_identifier(column) for column in selected)
            query += " FROM " + _quote_identifier(table)
            rows = connection.execute(query).fetchall()
            table_report = table_reports[table]
            table_report["table_present"] = True
            table_report["records"] = len(rows)
            table_report["digest_column_present"] = bool(digest_column and digest_column in columns)
            if table_report["digest_column_present"]:
                table_report["hashless_records"] = sum(not row[digest_column] for row in rows)

            root = roots[spec["root"]].resolve(strict=False)
            for row in rows:
                raw_path = row[path_column]
                if name_column and name_column in columns:
                    filename = row[name_column]
                    if not isinstance(filename, str) or Path(filename).name != filename:
                        table_report["unsafe_references"] += 1
                        continue
                    resolved = _resolve_reference(root, filename, None)
                    raw_resolved = _resolve_reference(root, raw_path, None)
                    if resolved is None or raw_resolved is None or resolved != raw_resolved:
                        table_report["unsafe_references"] += 1
                        continue
                else:
                    resolved = _resolve_reference(root, raw_path, spec.get("relative_prefix"))
                    if resolved is None:
                        table_report["unsafe_references"] += 1
                        continue

                referenced[spec["root"]].add(resolved)
                if not resolved.is_file():
                    table_report["missing_files"] += 1
                    continue
                if size_column and size_column in columns and row[size_column] is not None:
                    try:
                        if resolved.stat().st_size != int(row[size_column]):
                            table_report["size_mismatches"] += 1
                    except (OSError, TypeError, ValueError):
                        table_report["size_mismatches"] += 1
                if verify_hashes and digest_column and digest_column in columns and row[digest_column]:
                    try:
                        actual_digest = _sha256_file(resolved)
                    except OSError:
                        table_report["hash_errors"] += 1
                    else:
                        table_report["hashes_checked"] += 1
                        if not hmac.compare_digest(actual_digest, str(row[digest_column])):
                            table_report["hash_mismatches"] += 1
    finally:
        connection.close()

    for name, files in disk_files.items():
        root_reports[name]["unreferenced_files"] = len(files - referenced[name])

    return {"read_only": True, "roots": root_reports, "tables": table_reports}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="explicit SQLite database path (opened read-only)")
    parser.add_argument("--uploads-root", required=True, type=Path)
    parser.add_argument("--kcaa-root", required=True, type=Path)
    parser.add_argument("--attachments-root", required=True, type=Path)
    parser.add_argument(
        "--verify-hashes",
        action="store_true",
        help="read retained files and compare bytes with stored SHA-256 metadata",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    report = reconcile_upload_storage(
        args.db,
        args.uploads_root,
        args.kcaa_root,
        args.attachments_root,
        verify_hashes=args.verify_hashes,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
