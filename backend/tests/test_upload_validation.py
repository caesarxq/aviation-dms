import asyncio
import importlib
import importlib.util
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter


def _validation_module():
    if importlib.util.find_spec("app.upload_validation") is None:
        pytest.fail("isolated upload-content validation is not implemented")
    return importlib.import_module("app.upload_validation")


def _valid_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_validation_accepts_valid_pdf_and_rejects_malformed_signature_match():
    validation = _validation_module()

    asyncio.run(validation.validate_upload_content_local(_valid_pdf(), ".pdf", 1024 * 1024))
    with pytest.raises(validation.UploadContentInvalid):
        asyncio.run(
            validation.validate_upload_content_local(
                b"%PDF-1.7 but not a valid PDF", ".pdf", 1024 * 1024
            )
        )


def test_pdf_validation_fails_closed_on_parser_timeout(tmp_path, monkeypatch):
    validation = _validation_module()
    slow_worker = tmp_path / "slow_worker.py"
    slow_worker.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
    monkeypatch.setattr(validation, "WORKER_PATH", slow_worker)
    monkeypatch.setattr(validation, "PARSER_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(validation.UploadValidationUnavailable):
        asyncio.run(validation.validate_upload_content_local(_valid_pdf(), ".pdf", 1024 * 1024))


def test_upload_validation_fails_closed_without_isolated_validator(monkeypatch):
    validation = _validation_module()
    monkeypatch.delenv("DMS_UPLOAD_VALIDATOR_URL", raising=False)
    monkeypatch.setenv("DEV_MODE", "false")

    with pytest.raises(validation.UploadValidationUnavailable):
        asyncio.run(validation.validate_upload_content(_valid_pdf(), ".pdf", 1024 * 1024))


def test_upload_validation_rejects_untrusted_service_url_in_production(monkeypatch):
    validation = _validation_module()
    monkeypatch.setenv("DMS_UPLOAD_VALIDATOR_URL", "http://example.invalid/validate")
    monkeypatch.setenv("DEV_MODE", "false")

    with pytest.raises(validation.UploadValidationUnavailable):
        asyncio.run(validation.validate_upload_content(_valid_pdf(), ".pdf", 1024 * 1024))


def test_upload_validation_rejects_non_9100_port_in_production(monkeypatch):
    """Production endpoint must require port 9100; any other port is rejected."""
    validation = _validation_module()
    monkeypatch.setenv("DMS_UPLOAD_VALIDATOR_URL", "http://upload-validator:9999/validate")
    monkeypatch.setenv("DEV_MODE", "false")

    with pytest.raises(validation.UploadValidationUnavailable):
        asyncio.run(validation.validate_upload_content(_valid_pdf(), ".pdf", 1024 * 1024))


def test_upload_validation_rejects_non_9100_port_in_dev_mode(monkeypatch):
    """Local test endpoint must also require port 9100; any other port is rejected."""
    validation = _validation_module()
    monkeypatch.setenv("DMS_UPLOAD_VALIDATOR_URL", "http://127.0.0.1:9999/validate")
    monkeypatch.setenv("DEV_MODE", "true")

    with pytest.raises(validation.UploadValidationUnavailable):
        asyncio.run(validation.validate_upload_content(_valid_pdf(), ".pdf", 1024 * 1024))


def test_upload_validation_uses_isolated_validator_service():
    validation = _validation_module()

    asyncio.run(validation.validate_upload_content(_valid_pdf(), ".pdf", 1024 * 1024))


def test_cancelled_validator_request_closes_connection(monkeypatch):
    import socket as _socket
    # Check if port 9100 is available; conftest fixture may already hold it
    test_socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    test_socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    try:
        test_socket.bind(("127.0.0.1", 9100))
    except OSError:
        test_socket.close()
        pytest.skip("port 9100 already in use by session-scoped validator fixture")
    test_socket.close()

    validation = _validation_module()
    monkeypatch.setenv("DEV_MODE", "true")
    request_received = asyncio.Event()
    client_disconnected = asyncio.Event()

    async def handler(reader, writer):
        request_line = await reader.readline()
        assert request_line.startswith(b"POST /validate?")
        content_length = 0
        while line := await reader.readline():
            if line in (b"\r\n", b"\n"):
                break
            if line.lower().startswith(b"content-length:"):
                content_length = int(line.split(b":", 1)[1].strip())
        await reader.readexactly(content_length)
        request_received.set()
        await reader.read()
        client_disconnected.set()
        writer.close()
        await writer.wait_closed()

    async def exercise_cancellation():
        server = await asyncio.start_server(handler, "127.0.0.1", 9100)
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setenv("DMS_UPLOAD_VALIDATOR_URL", f"http://127.0.0.1:{port}/validate")
        monkeypatch.setattr(validation, "VALIDATOR_HTTP_TIMEOUT_SECONDS", 2, raising=False)
        task = asyncio.create_task(validation.validate_upload_content(b"pdf", ".pdf", 10))
        try:
            await asyncio.wait_for(request_received.wait(), timeout=1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=1)
            await asyncio.wait_for(client_disconnected.wait(), timeout=1)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            server.close()
            await server.wait_closed()

    asyncio.run(exercise_cancellation())


def test_validator_response_has_total_deadline_not_only_socket_idle_timeout(monkeypatch):
    validation = _validation_module()
    monkeypatch.setenv("DEV_MODE", "true")

    async def handler(reader, writer):
        request_line = await reader.readline()
        assert request_line.startswith(b"POST /validate?")
        content_length = 0
        while line := await reader.readline():
            if line in (b"\r\n", b"\n"):
                break
            if line.lower().startswith(b"content-length:"):
                content_length = int(line.split(b":", 1)[1].strip())
        await reader.readexactly(content_length)
        writer.write(b"HTTP/1.1 204 No Content\r\n")
        await writer.drain()
        await asyncio.sleep(0.25)
        try:
            writer.write(b"Content-Length: 0\r\nConnection: close\r\n\r\n")
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        writer.close()
        await writer.wait_closed()

    async def exercise_deadline():
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setenv("DMS_UPLOAD_VALIDATOR_URL", f"http://127.0.0.1:{port}/validate")
        monkeypatch.setattr(validation, "VALIDATOR_HTTP_TIMEOUT_SECONDS", 0.1, raising=False)
        try:
            with pytest.raises(validation.UploadValidationUnavailable):
                await validation.validate_upload_content(b"pdf", ".pdf", 10)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(exercise_deadline())


def test_parser_worker_applies_os_resource_limits(monkeypatch):
    import os
    import resource
    import sys

    worker = importlib.import_module("app.upload_validation_worker")
    monkeypatch.setattr(worker, "os", os, raising=False)
    monkeypatch.setattr(worker, "resource", resource, raising=False)
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    limits = {}
    monkeypatch.setattr(resource, "setrlimit", lambda name, value: limits.__setitem__(name, value))
    monkeypatch.setattr(os, "umask", lambda value: 0)

    worker._apply_worker_restrictions()

    assert limits[resource.RLIMIT_CPU] == (5, 6)
    assert limits[resource.RLIMIT_FSIZE] == (0, 0)
    assert limits[resource.RLIMIT_NOFILE] == (16, 16)
    assert limits[resource.RLIMIT_CORE] == (0, 0)
    if sys.platform.startswith("linux"):
        assert limits[resource.RLIMIT_AS] == (512 * 1024 * 1024, 512 * 1024 * 1024)


def test_parser_worker_drops_root_privileges(monkeypatch):
    import os
    import pwd
    import resource

    worker = importlib.import_module("app.upload_validation_worker")
    monkeypatch.setattr(worker, "os", os, raising=False)
    monkeypatch.setattr(worker, "pwd", pwd, raising=False)
    monkeypatch.setattr(worker, "resource", resource, raising=False)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=65534, pw_gid=65534))
    groups = []
    gids = []
    uids = []
    monkeypatch.setattr(os, "setgroups", lambda value: groups.append(value))
    monkeypatch.setattr(os, "setgid", lambda value: gids.append(value))
    monkeypatch.setattr(os, "setuid", lambda value: uids.append(value))
    monkeypatch.setattr(resource, "setrlimit", lambda name, value: None)
    monkeypatch.setattr(os, "umask", lambda value: 0)

    worker._apply_worker_restrictions()

    assert groups == [[]]
    assert gids == [65534]
    assert uids == [65534]
