#!/usr/bin/env python3
"""
Cron job for Zoho BugTracker bidirectional sync.

This script should be run periodically (e.g., every 15 minutes) via cron:
*/15 * * * * /path/to/venv/bin/python /path/to/cron_bugtracker_sync.py

It performs two sync operations:
1. sync_all_pending - syncs local feedback records that haven't been synced to BugTracker
2. sync_bugtracker_updates - pulls status updates from BugTracker and updates local records
"""

import os
import sys
import tempfile
import asyncio
import logging
from datetime import datetime

# This script sits beside the app/ package, both in the repo (backend/) and in
# the image (/app). Resolving the parent of this file's directory points at /
# inside the container, where neither code nor logs are writable.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)


def _resolve_log_dir(backend_dir: str) -> str:
    """Return a writable directory for sync logs.

    Candidates are tried in order: an explicit DMS_LOG_DIR, the source tree
    logs/ directory, a data-relative logs/ directory, an explicit fallback, and
    finally the platform temp directory. The container root filesystem is not
    writable by the backend UID, so a single fixed path would crash the job.
    """
    candidates = [
        os.getenv("DMS_LOG_DIR", ""),
        os.path.join(backend_dir, "logs"),
        os.path.join(backend_dir, "data", "logs"),
        os.getenv("DMS_LOG_FALLBACK_DIR", ""),
        tempfile.gettempdir(),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            os.makedirs(candidate, exist_ok=True)
            probe = os.path.join(candidate, ".bugtracker-sync-write-probe")
            with open(probe, "w", encoding="utf-8"):
                pass
            os.remove(probe)
        except OSError:
            continue
        return candidate
    raise RuntimeError("No writable directory available for BugTracker sync logs")


log_dir: str | None = None
log_file: str | None = None


def _configure_logging() -> str:
    """Attach file and console handlers for a real sync run.

    Deliberately called from the entry point rather than at import time so that
    importing this module (tests, probes) has no filesystem side effects.
    """
    global log_dir, log_file
    log_dir = _resolve_log_dir(BACKEND_DIR)
    log_file = os.path.join(log_dir, f"bugtracker_sync_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_dir


logger = logging.getLogger(__name__)


async def run_sync():
    """Run both sync operations and record the outcome for observability."""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Starting BugTracker sync at %s", start_time.isoformat())

    # Import after setting up path
    from app.bugtracker_sync import run_full_sync

    try:
        result = await run_full_sync()
    except Exception as exc:
        logger.exception("BugTracker sync failed: %s", exc)
        return 1

    logger.info("sync_all_pending completed: %d records synced", result["created"])
    logger.info("sync_bugtracker_updates completed: %d records updated", result["updated"])
    if result["status"] == "failed":
        logger.error("BugTracker sync status: failed (%s)", result["error"])
        return 1
    if result["status"] == "skipped":
        logger.warning("BugTracker sync skipped: %s", result["error"])
        return 0

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info("BugTracker sync completed in %.2f seconds at %s", duration, end_time.isoformat())
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    _configure_logging()
    exit_code = asyncio.run(run_sync())
    sys.exit(exit_code)