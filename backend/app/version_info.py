"""Runtime version/build identity for the KFL Aviation DMS.

Surfaces the release tag and originating Git SHA at runtime instead of a
hardcoded static string. The release tag is injected by the deployment
pipeline (Compose interpolation from DMS_RELEASE_TAG); the Git SHA is derived
from the ``canonical-<sha>-<timestamp>`` tag convention when present.
"""
import os
from typing import Dict, Optional

APP_NAME = "KFL Aviation DMS"
API_VERSION = "1.0.0"


def _git_sha_from_release_tag(release_tag: str) -> Optional[str]:
    """Extract the Git SHA from a canonical-<sha>-<timestamp> release tag."""
    if not release_tag.startswith("canonical-"):
        return None
    parts = release_tag.split("-", 2)
    if len(parts) >= 2 and len(parts[1]) == 40:
        return parts[1]
    return None


def get_version_info() -> Dict[str, object]:
    """Return safe, non-secret build identity for runtime surfacing."""
    release_tag = os.getenv("DMS_RELEASE_TAG", "").strip() or "dev"
    git_sha = os.getenv("DMS_GIT_SHA", "").strip() or _git_sha_from_release_tag(release_tag)
    return {
        "name": APP_NAME,
        "api_version": API_VERSION,
        "release_tag": release_tag,
        "git_sha": git_sha or None,
    }
