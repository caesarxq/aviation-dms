#!/usr/bin/env bash
# Exercise the BugTracker CREATE path with a single disposable feedback row.
#
# BugTracker reads are verified; this proves a local feedback row becomes a real
# BugTracker ticket. It is deliberately two-step and marked:
#   --check    (default) read-only: show the current state and what would happen
#   --create   insert one clearly-labelled test row and run the sync once
#   --cleanup  delete the BugTracker test bug AND the local test row
#
# --create and --cleanup change live systems; run them deliberately.
set -Eeuo pipefail

CONTAINER="${DMS_BACKEND_CONTAINER:-kfl-aviation-dms-staging-backend-1}"
MODE="${1:---check}"

if [[ "$MODE" != "--check" && "$MODE" != "--create" && "$MODE" != "--cleanup" ]]; then
  printf 'Usage: %s [--check|--create|--cleanup]\n' "$0" >&2
  exit 2
fi

if ! sudo docker inspect "$CONTAINER" >/dev/null 2>&1; then
  printf 'ERROR: backend container %s not found. Set DMS_BACKEND_CONTAINER.\n' "$CONTAINER" >&2
  exit 1
fi

printf 'Backend container: %s\n' "$CONTAINER"

run_in_container() {
  sudo docker exec -i \
    -e DMS_BACKEND_CONTAINER="$CONTAINER" \
    "$CONTAINER" python -
}

case "$MODE" in
  --check)
    run_in_container <<'PY'
import asyncio
import os
from app.database import get_db

MARKER = "BTRACKER-SMOKE-TEST"

async def main():
    db = await get_db()
    try:
        rows = await (await db.execute(
            "SELECT feedback_id, ticket_number, bugtracker_id, status, bugtracker_sync_state "
            "FROM feedback WHERE goal LIKE ?", (f"%{MARKER}%",)
        )).fetchall()
        total = (await (await db.execute("SELECT COUNT(*) FROM feedback")).fetchone())[0]
        pending = (await (await db.execute(
            "SELECT COUNT(*) FROM feedback WHERE (bugtracker_sync_state = 'pending' OR bugtracker_id IS NULL)"
        )).fetchone())[0]
    finally:
        await db.close()

    print(f"  feedback rows: {total}")
    print(f"  would be pushed by a sync: {pending}")
    print(f"  leftover smoke-test rows: {len(rows)}")
    for row in rows:
        state = "linked" if row["bugtracker_id"] else "not linked"
        print(f"    {row['ticket_number']} ({state})")

asyncio.run(main())
PY
    printf '\nRead-only check complete. --create would add ONE row and run the sync once.\n'
    ;;

  --create)
    run_in_container <<'PY'
import asyncio
import uuid
from datetime import datetime, timezone

from app import bugtracker_sync
from app.database import get_db

MARKER = "BTRACKER-SMOKE-TEST"

if not bugtracker_sync._is_configured():
    print("ERROR: BugTracker is not configured; aborting before writing anything.")
    raise SystemExit(1)

feedback_id = f"SMOKE-{uuid.uuid4().hex[:8].upper()}"
ticket_number = f"SMOKE-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
now = datetime.now(timezone.utc).isoformat()

async def insert():
    db = await get_db()
    try:
        existing = await (await db.execute(
            "SELECT COUNT(*) FROM feedback WHERE goal LIKE ?", (f"%{MARKER}%",)
        )).fetchone()
        if existing[0]:
            print("ERROR: a smoke-test row already exists; run --cleanup first.")
            raise SystemExit(1)
        await db.execute(
            """INSERT INTO feedback
               (feedback_id, ticket_number, actor_user_id, actor_role, source_route,
                issue_type, app_area, goal, reproduction_steps, expected_result, actual_result,
                impact, observation_time, screenshot_info, contact, status, priority,
                owner_id, bugtracker_id, bugtracker_url, bugtracker_sync_state,
                next_update_at, resolved_at, closed_at, resolution, resolution_note,
                verification, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (feedback_id, ticket_number, "smoke-test", "system_admin", "script",
             "bug", "BugTracker integration", f"{MARKER}: verify create path", "", "", "",
             "suggestion", now, None, "staging@kfl.ke", "new", "P4",
             None, None, None, "pending",
             None, None, None, None, None, None,
             now, now, "smoke-test", "smoke-test"),
        )
        await db.commit()
    finally:
        await db.close()
    print(f"Inserted {ticket_number} (pending, no BugTracker id).")

async def main():
    await insert()
    synced = await bugtracker_sync.sync_all_pending()
    print(f"sync_all_pending created: {synced}")

    db = await get_db()
    try:
        row = await (await db.execute(
            "SELECT bugtracker_id, bugtracker_url, bugtracker_sync_state "
            "FROM feedback WHERE feedback_id = ?", (feedback_id,)
        )).fetchone()
    finally:
        await db.close()

    if row and row["bugtracker_id"]:
        print("CREATE PATH OK")
        print(f"  bugtracker_id: {row['bugtracker_id']}")
        print(f"  url: {row['bugtracker_url']}")
        print(f"  state: {row['bugtracker_sync_state']}")
        print("Next: run --cleanup to remove the test bug and the local row.")
    else:
        print("CREATE PATH FAILED (no BugTracker id was stored).")
        print("Check the log above for the POST status code and Zoho's message.")
        print("Next: run --cleanup to remove the local test row.")
        raise SystemExit(1)

asyncio.run(main())
PY
    ;;

  --cleanup)
    run_in_container <<'PY'
import asyncio

import httpx

from app import bugtracker_sync as sync
from app.database import get_db

MARKER = "BTRACKER-SMOKE-TEST"

async def main():
    db = await get_db()
    try:
        rows = await (await db.execute(
            "SELECT feedback_id, ticket_number, bugtracker_id FROM feedback WHERE goal LIKE ?",
            (f"%{MARKER}%",),
        )).fetchall()
    finally:
        await db.close()

    if not rows:
        print("No smoke-test rows found; nothing to clean up.")
        return

    token = await sync._get_access_token()
    for row in rows:
        bug_id = row["bugtracker_id"]
        if bug_id and token:
            url = sync._bug_item_url(bug_id)
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.delete(
                        url, headers={"Authorization": f"Zoho-oauthtoken {token}"}, timeout=30
                    )
                print(f"  DELETE bug {bug_id}: HTTP {resp.status_code}")
            except Exception as exc:
                print(f"  DELETE bug {bug_id} failed: {type(exc).__name__}")
                print(f"  Delete it manually: {sync.ZOHO_BUGTRACKER_PORTAL} -> {bug_id}")
        elif bug_id:
            print(f"  No token available; delete bug {bug_id} manually in BugTracker.")

        db = await get_db()
        try:
            await db.execute("DELETE FROM feedback WHERE feedback_id = ?", (row["feedback_id"],))
            await db.commit()
        finally:
            await db.close()
        print(f"  Removed local row {row['ticket_number']}")

asyncio.run(main())
PY
    printf '\nCleanup complete. Re-run --check to confirm zero leftover rows.\n'
    ;;
esac
