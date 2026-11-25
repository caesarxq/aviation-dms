#!/usr/bin/env bash
# Read-only staging diagnostics for Zoho BugTracker. Does not create tickets.
set -Eeuo pipefail

CONTAINER="${DMS_BACKEND_CONTAINER:-kfl-aviation-dms-staging-backend-1}"
failures=0

printf 'Backend container: %s\n' "$CONTAINER"
if ! sudo docker inspect "$CONTAINER" >/dev/null 2>&1; then
  printf 'ERROR: backend container not found. Inspect the running containers and set DMS_BACKEND_CONTAINER if its name differs.\n' >&2
  exit 1
fi

sudo docker inspect --format 'state={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}} image={{.Config.Image}}' "$CONTAINER"

if ! sudo docker exec "$CONTAINER" python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)' >/dev/null 2>&1; then
  printf 'ERROR: backend health endpoint failed inside the container.\n' >&2
  failures=$((failures + 1))
else
  printf 'Backend health endpoint: OK\n'
fi

if sudo docker exec -i "$CONTAINER" python - <<'PY'
import asyncio
from app import bugtracker_sync as sync
from app.database import get_db

required_credentials = (
    "ZOHO_CLIENT_ID",
    "ZOHO_CLIENT_SECRET",
    "ZOHO_REFRESH_TOKEN",
)
missing_credentials = []
for name in required_credentials:
    configured = bool(getattr(sync, name))
    print(f"{name}: {'set' if configured else 'missing'}")
    if not configured:
        missing_credentials.append(name)

if sync.ZOHO_ACCESS_TOKEN:
    print("ZOHO_ACCESS_TOKEN: set (optional)")
elif not missing_credentials:
    print("ZOHO_ACCESS_TOKEN: not set (refresh-token flow configured)")
else:
    print("ZOHO_ACCESS_TOKEN: not set (OAuth refresh credentials incomplete)")
print(f"ZOHO_BUGTRACKER_PORTAL: {'configured' if sync.ZOHO_BUGTRACKER_PORTAL else 'missing'}")
print(f"ZOHO_BUGTRACKER_PROJECT_ID: {'configured' if sync.ZOHO_BUGTRACKER_PROJECT_ID else 'missing'}")

async def check_schema():
    db = await get_db()
    try:
        cursor = await db.execute("PRAGMA table_info(feedback)")
        columns = {row["name"] for row in await cursor.fetchall()}
        required = {"bugtracker_id", "bugtracker_url"}
        missing = sorted(required - columns)
        if missing:
            print("BugTracker feedback schema: MISSING " + ", ".join(missing))
            return 1
        state_column = next(
            (name for name in ("bugtracker_sync_state", "zoho_form_sync_state") if name in columns),
            None,
        )
        if state_column is None:
            print("BugTracker feedback schema: MISSING sync-state column")
            return 1
        print(f"BugTracker feedback schema: OK (sync state: {state_column})")
        return 0
    finally:
        await db.close()

schema_result = asyncio.run(check_schema())
raise SystemExit(1 if missing_credentials or schema_result else 0)
PY
then
  :
else
  failures=$((failures + 1))
fi

if sudo docker exec "$CONTAINER" test -f /app/cron_bugtracker_sync.py; then
  printf 'BugTracker cron script in image: present\n'
else
  printf 'BugTracker cron script in image: MISSING\n'
  failures=$((failures + 1))
fi

if crontab -l 2>/dev/null | grep -q 'cron_bugtracker_sync\.py'; then
  printf 'Current-user crontab references BugTracker sync: yes (command suppressed)\n'
else
  printf 'Current-user crontab references BugTracker sync: no\n'
fi

if [[ "${1:-}" == "--refresh-token-check" ]]; then
  printf 'Checking Zoho OAuth refresh only; no BugTracker records will be read or changed.\n'
  if sudo docker exec -i "$CONTAINER" python - <<'PY'
import asyncio
from app import bugtracker_sync as sync

if not (sync.ZOHO_REFRESH_TOKEN and sync.ZOHO_CLIENT_ID and sync.ZOHO_CLIENT_SECRET):
    print("Zoho OAuth refresh check: SKIPPED (refresh credentials incomplete)")
    raise SystemExit(2)

async def check_refresh():
    # Force the refresh-token branch even if the container also has an access token.
    sync.ZOHO_ACCESS_TOKEN = ""
    token = await sync._get_access_token()
    if not token:
        print("Zoho OAuth refresh check: FAILED (token value withheld)")
        raise SystemExit(1)
    print("Zoho OAuth refresh check: OK (token value withheld)")

asyncio.run(check_refresh())
PY
  then
    :
  else
    failures=$((failures + 1))
  fi
fi

printf '\nNo ticket-creation or status-sync job was run. Do not invoke cron_bugtracker_sync.py as a smoke test: it may create BugTracker tickets for pending feedback.\n'
if (( failures > 0 )); then
  printf 'Verification found %s issue(s).\n' "$failures" >&2
  exit 1
fi
printf 'Verification checks passed.\n'
