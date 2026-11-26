#!/usr/bin/env bash
# Manage the scheduled Zoho BugTracker sync on the staging host.
#
# Default (no arguments) is --check: read-only inspection, no changes.
# --install schedules the sync every 15 minutes; the job CREATES BugTracker
# tickets for pending feedback, so run it deliberately.
set -Eeuo pipefail

CONTAINER="${DMS_BACKEND_CONTAINER:-kfl-aviation-dms-staging-backend-1}"
CRON_FILE="${DMS_BUGTRACKER_CRON_FILE:-/etc/cron.d/kfl-aviation-dms-bugtracker-sync}"
LOG_DIR="${DMS_BUGTRACKER_LOG_DIR:-/var/log/kfl-aviation-dms}"
SCHEDULE="${DMS_BUGTRACKER_SCHEDULE:-*/15 * * * *}"
MODE="${1:---check}"

if [[ "$MODE" != "--check" && "$MODE" != "--install" && "$MODE" != "--remove" ]]; then
  printf 'Usage: %s [--check|--install|--remove]\n' "$0" >&2
  exit 2
fi

if ! sudo docker inspect "$CONTAINER" >/dev/null 2>&1; then
  printf 'ERROR: backend container %s not found. Set DMS_BACKEND_CONTAINER.\n' "$CONTAINER" >&2
  exit 1
fi

printf 'Backend container: %s\n' "$CONTAINER"
sudo docker inspect --format 'state={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}} image={{.Config.Image}}' "$CONTAINER"

if sudo docker exec "$CONTAINER" test -f /app/cron_bugtracker_sync.py; then
  printf 'Sync entry point in image: present\n'
else
  printf 'ERROR: /app/cron_bugtracker_sync.py is missing from the running image.\n' >&2
  printf 'Deploy an image that includes the cron script before scheduling it.\n' >&2
  exit 1
fi

printf '\nScheduled job state:\n'
if sudo test -f "$CRON_FILE"; then
  printf '  %s: present\n' "$CRON_FILE"
  sudo awk '/cron_bugtracker_sync/ && $0 !~ /^#/ {print "  schedule: " $1, $2, $3, $4, $5; exit}' "$CRON_FILE"
else
  printf '  %s: absent (sync is NOT scheduled)\n' "$CRON_FILE"
fi

stale_entries=$(crontab -l 2>/dev/null | grep -c 'cron_bugtracker_sync\.py' || true)
printf '  current-user crontab entries referencing the sync: %s\n' "$stale_entries"
if [[ "$stale_entries" -gt 0 ]]; then
  printf '  stale entry lines (a checkout path, not the container):\n'
  crontab -l 2>/dev/null | grep 'cron_bugtracker_sync\.py' | sed 's/^/    /'
fi

cleanup_stale_crontab() {
  local backup
  backup="${HOME}/crontab.backup.$(date +%Y%m%dT%H%M%SZ)"
  crontab -l > "$backup"
  crontab -l | grep -v 'cron_bugtracker_sync\.py' | crontab -
  printf 'Removed %s stale current-user crontab entr(y/ies); backup: %s\n' "$stale_entries" "$backup"
}

printf '\nFeedback that the next sync would push to BugTracker:\n'
sudo docker exec -i "$CONTAINER" python - <<'PY'
import os
import sqlite3

# Mirrors the selection in bugtracker_sync.sync_all_pending, so the count is
# what the job would actually act on rather than a rough proxy.
SELECTION = "(bugtracker_sync_state = 'pending' OR bugtracker_id IS NULL)"

db_path = os.getenv("DMS_DB_PATH", "/app/data/dms.db")
try:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        total = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        pushed = connection.execute(
            f"SELECT COUNT(*) FROM feedback WHERE {SELECTION}"
        ).fetchone()[0]
        linked = connection.execute(
            "SELECT COUNT(*) FROM feedback WHERE bugtracker_id IS NOT NULL"
        ).fetchone()[0]
    finally:
        connection.close()
except sqlite3.Error as exc:
    print(f"  unavailable: {type(exc).__name__} (cannot read the feedback table)")
else:
    print(f"  feedback rows: {total}")
    print(f"  would be pushed to BugTracker: {pushed}")
    print(f"  already linked to a BugTracker bug: {linked}")
PY

case "$MODE" in
  --check)
    printf '\nRead-only check complete. Nothing was scheduled, executed, or changed.\n'
    ;;
  --remove)
    if sudo test -f "$CRON_FILE"; then
      sudo rm -f "$CRON_FILE"
      printf 'Removed %s. The sync is no longer scheduled.\n' "$CRON_FILE"
    else
      printf 'Nothing to remove: %s is already absent.\n' "$CRON_FILE"
    fi
    if [[ "$stale_entries" -gt 0 ]]; then
      cleanup_stale_crontab
    fi
    ;;
  --install)
    printf '\nThis will schedule a job every 15 minutes that may create real\n'
    printf 'BugTracker tickets for the pending feedback counted above.\n'
    sudo install -d -o root -g root -m 0755 "$LOG_DIR"
    tmp_file=$(mktemp)
    cat > "$tmp_file" <<EOF
# Managed by scripts/install-bugtracker-cron.sh — do not edit by hand.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
$SCHEDULE root docker exec $CONTAINER python /app/cron_bugtracker_sync.py >> $LOG_DIR/bugtracker-sync.log 2>&1
EOF
    sudo install -o root -g root -m 0644 "$tmp_file" "$CRON_FILE"
    rm -f "$tmp_file"
    printf 'Installed %s (log: %s/bugtracker-sync.log)\n' "$CRON_FILE" "$LOG_DIR"

    if [[ "$stale_entries" -gt 0 ]]; then
      cleanup_stale_crontab
    fi

    printf '\nScheduled. The first run happens within 15 minutes and is not forced here.\n'
    ;;
esac
