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
import asyncio
import logging
from datetime import datetime

# Add the backend directory to the path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

# Set up logging
log_dir = os.path.join(BACKEND_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"bugtracker_sync_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

from datetime import datetime


async def run_sync():
    """Run both sync operations."""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Starting BugTracker sync at %s", start_time.isoformat())
    
    # Import after setting up path
    from app.bugtracker_sync import sync_all_pending, sync_bugtracker_updates
    
    try:
        # 1. Sync pending feedback to BugTracker
        logger.info("Running sync_all_pending...")
        synced_count = await sync_all_pending()
        logger.info("sync_all_pending completed: %d records synced", synced_count)
        
        # 2. Pull status updates from BugTracker
        logger.info("Running sync_bugtracker_updates...")
        updated_count = await sync_bugtracker_updates()
        logger.info("sync_bugtracker_updates completed: %d records updated", updated_count)
        
    except Exception as exc:
        logger.exception("BugTracker sync failed: %s", exc)
        return 1
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info("BugTracker sync completed in %.2f seconds at %s", duration, end_time.isoformat())
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    from datetime import datetime
    exit_code = asyncio.run(run_sync())
    sys.exit(exit_code)