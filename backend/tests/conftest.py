import os
import socket
import tempfile
import threading
import time
import pytest
import asyncio
import uvicorn

# Set test DB path before importing app
TEST_DB = tempfile.mktemp(suffix=".db")
os.environ["DMS_DB_PATH"] = TEST_DB
os.environ["DEV_MODE"] = "true"
os.environ["FLIGHT_RELEASE_ENABLED"] = "true"

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Initialize test database once per session."""
    async def _init():
        await init_db()
    asyncio.run(_init())
    from app.upload_validation_service import app as validator_app

    validator_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    validator_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    validator_socket.bind(("127.0.0.1", 9100))
    validator_socket.listen(128)
    validator_socket.setblocking(False)
    validator_port = validator_socket.getsockname()[1]
    validator_server = uvicorn.Server(
        uvicorn.Config(validator_app, log_level="critical", access_log=False, lifespan="off")
    )
    validator_thread = threading.Thread(
        target=validator_server.run,
        kwargs={"sockets": [validator_socket]},
        daemon=True,
    )
    validator_thread.start()
    deadline = time.monotonic() + 5
    while not validator_server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    if not validator_server.started:
        validator_server.should_exit = True
        validator_thread.join(timeout=5)
        validator_socket.close()
        raise RuntimeError("Isolated upload-validation test service did not start")
    previous_validator_url = os.environ.get("DMS_UPLOAD_VALIDATOR_URL")
    os.environ["DMS_UPLOAD_VALIDATOR_URL"] = f"http://127.0.0.1:{validator_port}/validate"
    try:
        yield
    finally:
        validator_server.should_exit = True
        validator_thread.join(timeout=5)
        validator_socket.close()
        if previous_validator_url is None:
            os.environ.pop("DMS_UPLOAD_VALIDATOR_URL", None)
        else:
            os.environ["DMS_UPLOAD_VALIDATOR_URL"] = previous_validator_url
        try:
            os.remove(TEST_DB)
        except FileNotFoundError:
            pass


@pytest.fixture(autouse=True)
def clear_rate_limit_buckets_after_each_test():
    """Prevent the process-local API limiter leaking state across tests."""
    yield
    from app import rate_limiter

    with rate_limiter._limiter._lock:
        rate_limiter._limiter._buckets.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"X-Role": "system_admin", "X-Actor": "admin"}


@pytest.fixture
def librarian_headers():
    return {"X-Role": "librarian", "X-Actor": "u-lib"}


@pytest.fixture
def quality_headers():
    return {"X-Role": "head_quality", "X-Actor": "u-quality"}


@pytest.fixture
def safety_headers():
    return {"X-Role": "head_safety", "X-Actor": "u-safety"}


@pytest.fixture
def reporter_headers():
    return {"X-Role": "occurrence_reporter", "X-Actor": "reporter"}