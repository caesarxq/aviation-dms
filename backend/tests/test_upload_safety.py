import asyncio
import stat
import struct

import pytest

from app import upload_safety


def _policy(monkeypatch, *, scope="system", quota="1024", host="127.0.0.1", port="3310"):
    monkeypatch.setenv("DMS_UPLOAD_QUOTA_SCOPE", scope)
    monkeypatch.setenv("DMS_UPLOAD_STORAGE_QUOTA_BYTES", quota)
    monkeypatch.setenv("DMS_CLAMD_HOST", host)
    monkeypatch.setenv("DMS_CLAMD_PORT", port)
    monkeypatch.setenv("DMS_CLAMD_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DMS_CLAMD_MAX_TIMEOUT_SECONDS", "30")
    return upload_safety.load_upload_safety_policy()


def test_policy_fails_closed_when_required_values_are_missing(monkeypatch):
    for name in (
        "DMS_UPLOAD_QUOTA_SCOPE",
        "DMS_UPLOAD_STORAGE_QUOTA_BYTES",
        "DMS_CLAMD_HOST",
        "DMS_CLAMD_PORT",
        "DMS_CLAMD_TIMEOUT_SECONDS",
        "DMS_CLAMD_MAX_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(upload_safety.UploadSafeguardConfigurationError):
        upload_safety.load_upload_safety_policy()


def test_policy_requires_explicit_quota_scope(monkeypatch):
    _policy(monkeypatch)
    monkeypatch.delenv("DMS_UPLOAD_QUOTA_SCOPE", raising=False)

    with pytest.raises(upload_safety.UploadSafeguardConfigurationError):
        upload_safety.load_upload_safety_policy()


def test_policy_rejects_invalid_quota_and_scanner_port(monkeypatch):
    with pytest.raises(upload_safety.UploadSafeguardConfigurationError):
        _policy(monkeypatch, quota="0")

    with pytest.raises(upload_safety.UploadSafeguardConfigurationError):
        _policy(monkeypatch, port="65536")

    with pytest.raises(upload_safety.UploadSafeguardConfigurationError):
        _policy(monkeypatch, scope="per_person")


def test_policy_rejects_nonfinite_and_overmaximum_scanner_timeouts(monkeypatch):
    _policy(monkeypatch)
    for timeout in ("inf", "-inf", "nan"):
        monkeypatch.setenv("DMS_CLAMD_TIMEOUT_SECONDS", timeout)
        with pytest.raises(upload_safety.UploadSafeguardConfigurationError):
            upload_safety.load_upload_safety_policy()

    monkeypatch.setenv("DMS_CLAMD_TIMEOUT_SECONDS", "31")
    monkeypatch.setenv("DMS_CLAMD_MAX_TIMEOUT_SECONDS", "30")
    with pytest.raises(upload_safety.UploadSafeguardConfigurationError):
        upload_safety.load_upload_safety_policy()


def test_quota_counts_existing_files_and_rejects_excess(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir()
    (root / "existing.bin").write_bytes(b"1234567")
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    policy = _policy(monkeypatch, quota="10")

    assert upload_safety.ensure_upload_capacity(3, policy) == 7
    with pytest.raises(upload_safety.UploadQuotaExceeded):
        upload_safety.ensure_upload_capacity(4, policy)


def test_quota_fails_closed_on_symlink_inside_storage(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"private")
    (root / "linked.bin").symlink_to(outside)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    policy = _policy(monkeypatch)

    with pytest.raises(upload_safety.UploadStorageUnavailable):
        upload_safety.ensure_upload_capacity(0, policy)


def test_store_upload_file_uses_private_modes_and_exclusive_creation(tmp_path):
    path = tmp_path / "private" / "credential.pdf"

    stored = upload_safety.store_upload_file(path, b"verified-content")

    assert stored.read_bytes() == b"verified-content"
    assert stat.S_IMODE(stored.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(stored.stat().st_mode) == 0o600
    with pytest.raises(upload_safety.UploadStorageUnavailable):
        upload_safety.store_upload_file(path, b"must-not-overwrite")


async def _clamd_response(response: bytes, expected_payload: bytes) -> None:
    async def handler(reader, writer):
        command = await reader.readexactly(len(b"zINSTREAM\x00"))
        assert command == b"zINSTREAM\x00"
        received = bytearray()
        while True:
            size = struct.unpack("!I", await reader.readexactly(4))[0]
            if size == 0:
                break
            received.extend(await reader.readexactly(size))
        assert bytes(received) == expected_payload
        writer.write(response + b"\x00")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    policy = upload_safety.UploadSafetyPolicy(
        quota_scope="system",
        storage_quota_bytes=1024,
        clamd_host="127.0.0.1",
        clamd_port=port,
        scanner_timeout_seconds=2,
    )
    try:
        await upload_safety.scan_upload_bytes(expected_payload, policy)
    finally:
        server.close()
        await server.wait_closed()


def test_clamd_instream_accepts_clean_and_rejects_infected_or_error():
    async def run():
        await _clamd_response(b"stream: OK", b"sample bytes")
        with pytest.raises(upload_safety.UploadMalwareDetected):
            await _clamd_response(b"stream: Eicar-Test-Signature FOUND", b"sample bytes")
        with pytest.raises(upload_safety.UploadScannerUnavailable):
            await _clamd_response(b"stream: daemon error ERROR", b"sample bytes")

    asyncio.run(run())


def test_scanner_cancellation_closes_clamd_connection():
    async def scenario():
        request_received = asyncio.Event()
        client_disconnected = asyncio.Event()

        async def handler(reader, writer):
            await reader.readexactly(len(b"zINSTREAM\x00"))
            while True:
                size = struct.unpack("!I", await reader.readexactly(4))[0]
                if size == 0:
                    break
                await reader.readexactly(size)
            request_received.set()
            await reader.read()
            client_disconnected.set()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        policy = upload_safety.UploadSafetyPolicy(
            quota_scope="system",
            storage_quota_bytes=1024,
            clamd_host="127.0.0.1",
            clamd_port=port,
            scanner_timeout_seconds=2,
        )
        task = asyncio.create_task(upload_safety.scan_upload_bytes(b"sample bytes", policy))
        try:
            await asyncio.wait_for(request_received.wait(), timeout=1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(client_disconnected.wait(), timeout=1)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_upload_request_limit_bounds_concurrent_in_memory_buffers():
    async def scenario():
        active = 0
        maximum_active = 0
        two_slots_filled = asyncio.Event()
        release = asyncio.Event()

        async def request():
            nonlocal active, maximum_active
            async for _ in upload_safety.upload_request_limit():
                active += 1
                maximum_active = max(maximum_active, active)
                if active == 2:
                    two_slots_filled.set()
                await release.wait()
                active -= 1

        tasks = [asyncio.create_task(request()) for _ in range(3)]
        await asyncio.wait_for(two_slots_filled.wait(), timeout=1)
        await asyncio.sleep(0)
        assert active == 2
        assert not tasks[2].done()
        release.set()
        await asyncio.gather(*tasks)
        assert maximum_active == 2

    asyncio.run(scenario())


def test_file_upload_routes_and_p3_body_guard_register_memory_bounds():
    from app import p0_routes, p2_routes, p3_routes
    from app.main import app

    route_paths = (
        (p0_routes.router, "/versions/{version_id}/kcaa-evidence", "POST"),
        (p0_routes.router, "/versions/{version_id}/kcaa-evidence/{evidence_id}/verify", "POST"),
        (p0_routes.router, "/versions/{version_id}/kcaa-evidence/{evidence_id}/file", "GET"),
        (p2_routes.router, "/personnel/uploads/file", "POST"),
        (p2_routes.router, "/personnel/uploads/{upload_id}/file", "GET"),
        (p2_routes.router, "/personnel/uploads/{upload_id}/verify", "PATCH"),
        (p3_routes.router, "/audit-reports/{audit_id}/evidence", "GET"),
        (p3_routes.router, "/audit-report-imports/{import_id}/evidence", "GET"),
    )
    for router, path, method in route_paths:
        route = next(
            route for route in router.routes
            if getattr(route, "path", None) == path and method in getattr(route, "methods", set())
        )
        assert any(
            dependency.call is upload_safety.upload_request_limit
            for dependency in getattr(route, "dependant").dependencies
        )
    assert any(
        middleware.cls is upload_safety.P3RequestBodyLimitMiddleware
        for middleware in app.user_middleware
    )


def test_p3_body_guard_limits_chunked_requests_without_content_length():
    async def exercise():
        messages = [
            {"type": "http.request", "body": b"a" * 100_000, "more_body": True},
            {"type": "http.request", "body": b"b" * 40_000, "more_body": False},
        ]
        responses = []

        async def receive():
            return messages.pop(0)

        async def send(message):
            responses.append(message)

        async def consume_body(scope, next_receive, next_send):
            while True:
                message = await next_receive()
                if not message.get("more_body"):
                    break

        middleware = upload_safety.P3RequestBodyLimitMiddleware(consume_body)
        await middleware(
            {
                "type": "http",
                "path": "/api/p3/audit-reports",
                "method": "POST",
                "headers": [],
            },
            receive,
            send,
        )

        assert responses[0]["status"] == 413

    asyncio.run(exercise())
