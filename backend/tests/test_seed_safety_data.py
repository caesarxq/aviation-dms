import asyncio

import pytest

from app import seed_safety_data


def test_seed_safety_data_refuses_non_development_mode(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "false")
    with pytest.raises(RuntimeError, match="development-only"):
        asyncio.run(seed_safety_data.seed_safety_data())


def test_seed_safety_data_has_no_embedded_shared_password():
    assert not hasattr(seed_safety_data, "TEST_PASSWORD")
    assert not hasattr(seed_safety_data, "TEST_PASSWORD_HASH")
