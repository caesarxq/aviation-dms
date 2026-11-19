"""Killable, bounded worker for validating untrusted uploaded files."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit

PARSER_TIMEOUT_SECONDS = 5.0
VALIDATOR_HTTP_TIMEOUT_SECONDS = PARSER_TIMEOUT_SECONDS + 2
MAX_CONCURRENT_PARSERS = 2
VALIDATOR_REQUEST_CHUNK_BYTES = 64 * 1024
WORKER_PATH = Path(__file__).with_name("upload_validation_worker.py")
_VALIDATION_SLOTS = asyncio.Semaphore(MAX_CONCURRENT_PARSERS)


class UploadContentInvalid(ValueError):
    """The uploaded bytes do not form an allowed, structurally valid file."""


class UploadValidationUnavailable(RuntimeError):
    """The isolated parser could not complete within its resource limits."""


async def validate_upload_content_local(
    payload: bytes | bytearray | memoryview,
    extension: str,
    max_bytes: int,
    max_image_pixels: int = 40_000_000,
) -> None:
    if len(payload) > max_bytes:
        raise UploadContentInvalid("Upload exceeds the configured per-file maximum")
    if extension not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise UploadContentInvalid("Unsupported upload extension")

    command = [
        sys.executable,
        "-I",
        os.fspath(WORKER_PATH),
        extension,
        str(max_bytes),
        str(max_image_pixels),
    ]
    async with _VALIDATION_SLOTS:
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env={"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
            )
            await asyncio.wait_for(
                process.communicate(bytes(payload)), timeout=PARSER_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            raise UploadValidationUnavailable("Isolated file validation timed out") from exc
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            raise
        except (OSError, ValueError) as exc:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            raise UploadValidationUnavailable("Isolated file validation could not start") from exc

        if process.returncode == 0:
            return
        if process.returncode == 1:
            raise UploadContentInvalid("The file is not structurally valid for its declared format")
        raise UploadValidationUnavailable("Isolated file validation failed")


def _configured_validator_url() -> str:
    url = os.getenv("DMS_UPLOAD_VALIDATOR_URL", "").strip()
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise UploadValidationUnavailable("Isolated validation service is not configured") from exc
    production_endpoint = (
        parsed.scheme == "http"
        and parsed.hostname == "upload-validator"
        and port == 9100
        and parsed.path == "/validate"
        and not parsed.query
        and not parsed.username
        and not parsed.password
    )
    local_test_endpoint = (
        os.getenv("DEV_MODE", "false").lower() == "true"
        and parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and port == 9100
        and parsed.path == "/validate"
        and not parsed.query
        and not parsed.username
        and not parsed.password
    )
    if not (production_endpoint or local_test_endpoint):
        raise UploadValidationUnavailable("Isolated validation service is not configured")
    return url


async def _validate_via_isolated_service(
    url: str,
    payload: bytes,
    extension: str,
    max_bytes: int,
    max_image_pixels: int,
) -> None:
    parsed = urlsplit(url)
    host = parsed.hostname
    port = parsed.port or 80
    query = urlencode(
        {"extension": extension, "max_bytes": max_bytes, "max_image_pixels": max_image_pixels}
    )
    target = f"{parsed.path}?{query}"
    writer = None
    try:
        async with asyncio.timeout(VALIDATOR_HTTP_TIMEOUT_SECONDS):
            reader, writer = await asyncio.open_connection(host, port)
            headers = (
                f"POST {target} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                "Content-Type: application/octet-stream\r\n"
                f"Content-Length: {len(payload)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            writer.write(headers)
            await writer.drain()
            for offset in range(0, len(payload), VALIDATOR_REQUEST_CHUNK_BYTES):
                writer.write(payload[offset : offset + VALIDATOR_REQUEST_CHUNK_BYTES])
                await writer.drain()

            status_line = await reader.readline()
            if not status_line or len(status_line) > 8192:
                raise UploadValidationUnavailable("Isolated validation service returned an invalid response")
            parts = status_line.decode("ascii").strip().split(" ", 2)
            if len(parts) < 2 or not parts[0].startswith("HTTP/1.") or not parts[1].isdigit():
                raise UploadValidationUnavailable("Isolated validation service returned an invalid response")
            status = int(parts[1])
            response_header_bytes = len(status_line)
            while True:
                line = await reader.readline()
                response_header_bytes += len(line)
                if not line or response_header_bytes > 16 * 1024:
                    raise UploadValidationUnavailable("Isolated validation service returned invalid headers")
                if line in (b"\r\n", b"\n"):
                    break
                if b":" not in line:
                    raise UploadValidationUnavailable("Isolated validation service returned invalid headers")
            if status == 204:
                return
            if status in {400, 413, 415, 422}:
                raise UploadContentInvalid("The file is not structurally valid for its declared format")
            raise UploadValidationUnavailable("Isolated validation service failed")
    except (UploadContentInvalid, UploadValidationUnavailable, asyncio.CancelledError):
        raise
    except TimeoutError as exc:
        raise UploadValidationUnavailable("Isolated validation service exceeded its deadline") from exc
    except (OSError, ValueError, UnicodeError) as exc:
        raise UploadValidationUnavailable("Isolated validation service is unavailable") from exc
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass


async def validate_upload_content(
    payload: bytes | bytearray | memoryview,
    extension: str,
    max_bytes: int,
    max_image_pixels: int = 40_000_000,
) -> None:
    """Validate through the isolated validator container; never parse in the API process."""
    if len(payload) > max_bytes:
        raise UploadContentInvalid("Upload exceeds the configured per-file maximum")
    if extension not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise UploadContentInvalid("Unsupported upload extension")
    url = _configured_validator_url()
    async with _VALIDATION_SLOTS:
        await _validate_via_isolated_service(
            url,
            bytes(payload),
            extension,
            max_bytes,
            max_image_pixels,
        )
