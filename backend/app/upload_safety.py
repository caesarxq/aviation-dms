"""Fail-closed upload policy, malware scanning, quota and private storage helpers."""
from __future__ import annotations

import asyncio
import fcntl
import math
import os
import stat
import struct
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .database import DB_PATH

SCAN_CHUNK_BYTES = 64 * 1024
MAX_CONCURRENT_UPLOAD_REQUESTS = 2
_UPLOAD_REQUEST_SLOTS = asyncio.Semaphore(MAX_CONCURRENT_UPLOAD_REQUESTS)


class UploadSafeguardConfigurationError(RuntimeError):
    """Required upload security configuration is missing or invalid."""


class UploadScannerUnavailable(RuntimeError):
    """The malware scanner is unavailable or returned an invalid response."""


class UploadMalwareDetected(RuntimeError):
    """The configured malware scanner rejected the submitted file."""


class UploadQuotaExceeded(RuntimeError):
    """The upload would exceed the configured total storage quota."""


class UploadStorageUnavailable(RuntimeError):
    """Storage could not be safely inventoried or written."""


async def upload_request_limit():
    """Bound per-process in-memory upload buffers before reading request bodies."""
    async with _UPLOAD_REQUEST_SLOTS:
        yield


class _RequestBodyLimitExceeded(Exception):
    pass


class P3RequestBodyLimitMiddleware:
    """Admit P3 JSON mutations before parsing and cap their bodies at ASGI ingress."""

    SMALL_MUTATION_BODY_LIMIT_BYTES = 128 * 1024

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or not scope.get("path", "").startswith("/api/p3/")
            or scope.get("method") not in {"POST", "PUT", "PATCH"}
        ):
            await self.app(scope, receive, send)
            return

        if scope["path"] == "/api/p3/audit-report-imports" and scope["method"] == "POST":
            raw_limit = os.getenv("DMS_P3_IMPORT_BODY_MAX_BYTES", "").strip()
            try:
                body_limit = int(raw_limit)
            except ValueError:
                await self._send_error(send, 503, "P3 import body limit is not configured")
                return
            if body_limit <= 0:
                await self._send_error(send, 503, "P3 import body limit is not configured")
                return
        else:
            body_limit = self.SMALL_MUTATION_BODY_LIMIT_BYTES

        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        raw_content_length = headers.get(b"content-length")
        if raw_content_length is not None:
            try:
                content_length = int(raw_content_length)
            except ValueError:
                await self._send_error(send, 400, "Invalid Content-Length")
                return
            if content_length < 0:
                await self._send_error(send, 400, "Invalid Content-Length")
                return
            if content_length > body_limit:
                await self._send_error(send, 413, "Request body exceeds the configured limit")
                return

        await _UPLOAD_REQUEST_SLOTS.acquire()
        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > body_limit:
                    raise _RequestBodyLimitExceeded
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyLimitExceeded:
            await self._send_error(send, 413, "Request body exceeds the configured limit")
        finally:
            _UPLOAD_REQUEST_SLOTS.release()

    @staticmethod
    async def _send_error(send, status: int, detail: str):
        body = ('{"detail":"' + detail + '"}').encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


@dataclass(frozen=True)
class UploadSafetyPolicy:
    quota_scope: str
    storage_quota_bytes: int
    clamd_host: str
    clamd_port: int
    scanner_timeout_seconds: float


def load_upload_safety_policy() -> UploadSafetyPolicy:
    quota_scope = os.getenv("DMS_UPLOAD_QUOTA_SCOPE", "").strip().lower()
    quota_raw = os.getenv("DMS_UPLOAD_STORAGE_QUOTA_BYTES", "").strip()
    host = os.getenv("DMS_CLAMD_HOST", "").strip()
    port_raw = os.getenv("DMS_CLAMD_PORT", "").strip()
    timeout_raw = os.getenv("DMS_CLAMD_TIMEOUT_SECONDS", "").strip()
    timeout_max_raw = os.getenv("DMS_CLAMD_MAX_TIMEOUT_SECONDS", "").strip()

    try:
        quota = int(quota_raw)
        port = int(port_raw)
        timeout = float(timeout_raw)
        timeout_max = float(timeout_max_raw)
    except ValueError as exc:
        raise UploadSafeguardConfigurationError(
            "Upload quota and scanner settings must be configured with valid values"
        ) from exc

    if (
        quota_scope != "system"
        or quota <= 0
        or not host
        or "\x00" in host
        or not 1 <= port <= 65535
        or not math.isfinite(timeout)
        or not math.isfinite(timeout_max)
        or timeout <= 0
        or timeout_max <= 0
        or timeout > timeout_max
    ):
        raise UploadSafeguardConfigurationError(
            "A supported upload quota scope, quota, and finite scanner timeout within its approved maximum are required"
        )

    return UploadSafetyPolicy(
        quota_scope=quota_scope,
        storage_quota_bytes=quota,
        clamd_host=host,
        clamd_port=port,
        scanner_timeout_seconds=timeout,
    )


async def scan_upload_bytes(payload: bytes | bytearray | memoryview, policy: UploadSafetyPolicy) -> None:
    """Stream bytes to clamd asynchronously so cancellation closes the socket."""
    writer = None
    try:
        async with asyncio.timeout(policy.scanner_timeout_seconds):
            reader, writer = await asyncio.open_connection(policy.clamd_host, policy.clamd_port)
            writer.write(b"zINSTREAM\x00")
            await writer.drain()
            view = memoryview(payload)
            for offset in range(0, len(view), SCAN_CHUNK_BYTES):
                chunk = view[offset : offset + SCAN_CHUNK_BYTES]
                writer.write(struct.pack("!I", len(chunk)))
                writer.write(chunk)
                await writer.drain()
            writer.write(struct.pack("!I", 0))
            await writer.drain()
            response = bytearray()
            while not response.endswith(b"\x00"):
                chunk = await reader.read(1024)
                if not chunk or len(response) + len(chunk) > 4096:
                    raise OSError("scanner closed without a bounded response")
                response.extend(chunk)
            message = bytes(response[:-1]).decode("utf-8", errors="replace").strip()
            if message.endswith(": OK"):
                return
            if message.endswith(" FOUND"):
                raise UploadMalwareDetected("The uploaded file was rejected by malware scanning")
            raise UploadScannerUnavailable("The malware scanner did not return a clean result")
    except (UploadMalwareDetected, UploadScannerUnavailable, asyncio.CancelledError):
        raise
    except Exception as exc:
        raise UploadScannerUnavailable("The malware scanner is unavailable") from exc
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass


def _configured_roots(extra_roots: Iterable[Path] = ()) -> list[Path]:
    data_root = Path(DB_PATH).parent
    candidates = [
        Path(os.getenv("UPLOAD_DIR") or data_root / "uploads"),
        Path(os.getenv("KCAA_EVIDENCE_DIR") or data_root / "kcaa-evidence"),
        Path(os.getenv("AUDIT_REPORT_EVIDENCE_DIR") or data_root / "attachments"),
        *(Path(root) for root in extra_roots),
    ]
    resolved: list[Path] = []
    for candidate in candidates:
        if candidate.is_symlink():
            raise UploadStorageUnavailable("Upload storage contains a symbolic-link root")
        root = candidate.resolve(strict=False)
        if any(root == existing or root.is_relative_to(existing) for existing in resolved):
            continue
        resolved = [existing for existing in resolved if not existing.is_relative_to(root)]
        resolved.append(root)
    return resolved


def _directory_bytes(root: Path) -> int:
    try:
        try:
            root_info = root.lstat()
        except FileNotFoundError:
            return 0
        if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
            raise UploadStorageUnavailable("Upload storage root is not a regular directory")
        total = 0
        pending = [root]
        while pending:
            current = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        raise UploadStorageUnavailable("Upload storage contains a symbolic link")
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(Path(entry.path))
                    elif stat.S_ISREG(info.st_mode):
                        total += info.st_size
                    else:
                        raise UploadStorageUnavailable("Upload storage contains a non-regular file")
        return total
    except UploadStorageUnavailable:
        raise
    except OSError as exc:
        raise UploadStorageUnavailable("Upload storage could not be inventoried safely") from exc


def ensure_upload_capacity(
    additional_bytes: int,
    policy: UploadSafetyPolicy,
    extra_roots: Iterable[Path] = (),
) -> int:
    if additional_bytes < 0:
        raise ValueError("additional_bytes must be non-negative")
    used_bytes = sum(_directory_bytes(root) for root in _configured_roots(extra_roots))
    if used_bytes + additional_bytes > policy.storage_quota_bytes:
        raise UploadQuotaExceeded("The configured upload storage quota would be exceeded")
    return used_bytes


@asynccontextmanager
async def upload_storage_lock():
    """Serialize quota checks and file/metadata commits across local workers."""
    lock_path = Path(DB_PATH).parent / ".dms-upload-storage.lock"
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.fchmod(descriptor, 0o600)
    except OSError as exc:
        raise UploadStorageUnavailable("Upload storage lock is unavailable") from exc

    acquired = False
    try:
        while not acquired:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                await asyncio.sleep(0.05)
        yield
    except OSError as exc:
        raise UploadStorageUnavailable("Upload storage lock failed") from exc
    finally:
        if acquired:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        else:
            os.close(descriptor)


def store_upload_file(path: Path, payload: bytes | bytearray | memoryview) -> Path:
    """Create a private, exclusive file and fsync it and its directory."""
    try:
        if path.parent.is_symlink():
            raise UploadStorageUnavailable("Upload storage root is unsafe")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
        root = path.parent.resolve()
        if path.name in {"", ".", ".."}:
            raise UploadStorageUnavailable("Upload filename is invalid")
        safe_path = root / path.name
        if safe_path.parent != root:
            raise UploadStorageUnavailable("Upload path escaped its storage root")
        descriptor = os.open(safe_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        directory_fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return safe_path
    except UploadStorageUnavailable:
        raise
    except OSError as exc:
        raise UploadStorageUnavailable("Upload file could not be stored safely") from exc


def remove_upload_file(path: Path) -> None:
    """Remove a failed upload and fsync the containing directory."""
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise UploadStorageUnavailable("Failed upload could not be removed") from exc
    try:
        directory_fd = os.open(path.parent.resolve(), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise UploadStorageUnavailable("Upload cleanup could not be persisted") from exc
