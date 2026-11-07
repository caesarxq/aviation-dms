import os
import tempfile
import pytest
import asyncio

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
    yield
    # Cleanup
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