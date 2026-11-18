import os

from app import version_info


def test_version_info_defaults_to_dev_without_environment(monkeypatch):
    monkeypatch.delenv("DMS_RELEASE_TAG", raising=False)
    monkeypatch.delenv("DMS_GIT_SHA", raising=False)
    info = version_info.get_version_info()
    assert info["name"] == "KFL Aviation DMS"
    assert info["api_version"] == "1.0.0"
    assert info["release_tag"] == "dev"
    assert info["git_sha"] is None


def test_version_info_surfaces_release_tag_and_git_sha(monkeypatch):
    monkeypatch.setenv("DMS_RELEASE_TAG", "canonical-5012309115b2a2d3b38a23e35dc6cf92a26ebcc3-20261118T200056Z")
    monkeypatch.delenv("DMS_GIT_SHA", raising=False)
    info = version_info.get_version_info()
    assert info["release_tag"] == "canonical-5012309115b2a2d3b38a23e35dc6cf92a26ebcc3-20261118T200056Z"
    assert info["git_sha"] == "5012309115b2a2d3b38a23e35dc6cf92a26ebcc3"


def test_version_info_prefers_explicit_git_sha(monkeypatch):
    monkeypatch.setenv("DMS_RELEASE_TAG", "canonical-5012309115b2a2d3b38a23e35dc6cf92a26ebcc3-20261118T200056Z")
    monkeypatch.setenv("DMS_GIT_SHA", "abc123")
    info = version_info.get_version_info()
    assert info["git_sha"] == "abc123"


def test_version_info_treats_blank_release_tag_as_dev(monkeypatch):
    monkeypatch.setenv("DMS_RELEASE_TAG", "   ")
    monkeypatch.delenv("DMS_GIT_SHA", raising=False)
    assert version_info.get_version_info()["release_tag"] == "dev"


def test_version_info_non_canonical_tag_has_no_git_sha(monkeypatch):
    monkeypatch.setenv("DMS_RELEASE_TAG", "v1.2.3")
    monkeypatch.delenv("DMS_GIT_SHA", raising=False)
    info = version_info.get_version_info()
    assert info["release_tag"] == "v1.2.3"
    assert info["git_sha"] is None
