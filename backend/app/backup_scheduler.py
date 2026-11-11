"""Periodic automated backup scheduler for Aviation DMS.

Runs backup_create.create_backup_candidate on a configurable interval.
Results are recorded as audit events and notifications are sent on failure.

All configuration is fail-closed: the scheduler is disabled by default and
must be explicitly enabled via DMS_BACKUP_ENABLED=true. Source and destination
data roots must be explicitly configured; empty defaults refuse to start.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from .backup_create import create_backup_candidate, BackupCreateError
from .audit import log_audit_event
from .database import get_db


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


def _env_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default).strip())
    except (TypeError, ValueError):
        return int(default)


class BackupScheduler:
    """Background task that periodically creates backup candidates."""

    def __init__(
        self,
        interval_seconds: Optional[int] = None,
        source_data_root: Optional[str] = None,
        dest_root: Optional[str] = None,
        max_retention_count: Optional[int] = None,
        notify_on_failure: bool = True,
    ) -> None:
        self.interval_seconds = interval_seconds or _env_int(
            "DMS_BACKUP_INTERVAL_SECONDS", "86400"
        )
        self.source_data_root = source_data_root or os.getenv(
            "DMS_BACKUP_DATA_ROOT", ""
        )
        self.dest_root = dest_root or os.getenv("DMS_BACKUP_DEST_ROOT", "")
        self.max_retention_count = max_retention_count or _env_int(
            "DMS_BACKUP_MAX_RETENTION_COUNT", "5"
        )
        self.notify_on_failure = notify_on_failure or _env_bool(
            "DMS_BACKUP_NOTIFY_ON_FAILURE", "true"
        )
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._stop = asyncio.Event()
        self.last_result: Optional[dict] = None
        self.last_error: Optional[str] = None
        self.run_count = 0
        self.failure_count = 0

    @property
    def running(self) -> bool:
        return self._running

    @property
    def enabled(self) -> bool:
        return _env_bool("DMS_BACKUP_ENABLED", "false")

    async def start(self) -> None:
        """Start the periodic backup loop. No-op if disabled or already running."""
        if not self.enabled:
            return
        if self._running:
            return
        if not self.source_data_root or not self.dest_root:
            # Fail-closed: refuse to start without explicit source/destination.
            self._running = False
            return
        self._stop.clear()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the scheduler and wait for the current cycle to finish."""
        if not self._running:
            return
        self._stop.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._running = False

    async def run_once(self) -> dict:
        """Execute one backup cycle immediately and return the result."""
        if not self.source_data_root or not self.dest_root:
            raise BackupCreateError(
                "Backup source and destination roots must be configured"
            )
        from pathlib import Path

        self.run_count += 1
        try:
            result = await create_backup_candidate(
                source_data_root=Path(self.source_data_root),
                dest_root=Path(self.dest_root),
            )
            self.last_result = result
            self.last_error = None
            await self._record_audit("backup_created", result)
            if not result.get("accepted", False):
                await self._record_audit(
                    "backup_verification_failed",
                    {
                        "candidate_path": result.get("candidate_path"),
                        "blockers": result.get("blockers", []),
                    },
                )
                if self.notify_on_failure:
                    await self._send_notification(
                        "Backup verification failed",
                        f"Backup candidate at {result.get('candidate_path')} "
                        f"was created but verification failed: "
                        f"{result.get('blockers', [])}",
                        priority="high",
                    )
            return result
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self.failure_count += 1
            await self._record_audit(
                "backup_failed",
                {"error": str(exc), "source": self.source_data_root, "dest": self.dest_root},
            )
            if self.notify_on_failure:
                await self._send_notification(
                    "Backup creation failed",
                    f"Automated backup failed: {exc}",
                    priority="critical",
                )
            raise

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                # Interval elapsed; run a backup cycle.
                try:
                    await self.run_once()
                except Exception:  # noqa: BLE001
                    # Errors are logged and notified inside run_once; loop continues.
                    pass

    async def _record_audit(self, action: str, details: dict) -> None:
        import json

        db = await get_db()
        try:
            await log_audit_event(
                entity_type="backup",
                entity_id="backup",
                action=action,
                actor_id="system",
                details=details,
                db=db,
            )
            await db.commit()
        finally:
            await db.close()

    async def _send_notification(self, subject: str, body: str, priority: str = "medium") -> None:
        from .notifications import persist_notification

        persist_notification(
            recipient="system",
            subject=subject,
            body=body,
            entity_type="backup",
            entity_id=None,
            priority=priority,
            status="logged",
        )

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "source_data_root": self.source_data_root,
            "dest_root": self.dest_root,
            "max_retention_count": self.max_retention_count,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "last_result": self.last_result,
            "last_error": self.last_error,
        }
