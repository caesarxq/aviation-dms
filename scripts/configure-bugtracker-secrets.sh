#!/usr/bin/env bash
# Provision protected Zoho BugTracker OAuth secret files on the staging host.
# Values are prompted without echo and never written to stdout or shell history.
set -Eeuo pipefail
umask 077

SECRETS_DIR="${ZOHO_SECRETS_DIR:-/opt/kfl-aviation-dms-staging/secrets}"
ENV_FILE="${DMS_STAGING_ENV_FILE:-/opt/kfl-aviation-dms-staging/.env.staging}"
OVERWRITE=0
if [[ "${1:-}" == "--replace" ]]; then
  OVERWRITE=1
elif [[ -n "${1:-}" ]]; then
  printf 'Usage: %s [--replace]\n' "$0" >&2
  exit 2
fi

if [[ ! -r /dev/tty ]]; then
  printf 'ERROR: run this script from an interactive terminal (SSH with -t).\n' >&2
  exit 1
fi

sudo install -d -o root -g root -m 0700 "$SECRETS_DIR"

write_secret() {
  local name="$1" path="$2" value=""
  if [[ -e "$path" && "$OVERWRITE" -eq 0 ]]; then
    sudo chown 10001:10001 "$path"
    sudo chmod 0400 "$path"
    if ! sudo -u '#10001' test -r "$path"; then
      printf 'ERROR: existing secret file for %s is not readable by backend UID 10001.\n' "$name" >&2
      exit 1
    fi
    printf '%s: existing protected file preserved\n' "$name"
    return
  fi
  while [[ -z "$value" ]]; do
    read -r -s -p "Enter ${name}: " value </dev/tty
    printf '\n' >/dev/tty
    if [[ -z "$value" ]]; then
      printf 'A non-empty value is required.\n' >/dev/tty
    fi
  done
  if ! printf '%s' "$value" | sudo sh -c 'umask 077; cat > "$1" && chown 10001:10001 "$1" && chmod 0400 "$1"' sh "$path"; then
    unset value
    printf 'ERROR: could not write protected file for %s.\n' "$name" >&2
    exit 1
  fi
  unset value
  printf '%s: protected file written\n' "$name"
}

write_secret "ZOHO_CLIENT_ID" "$SECRETS_DIR/zoho_client_id"
write_secret "ZOHO_CLIENT_SECRET" "$SECRETS_DIR/zoho_client_secret"
write_secret "ZOHO_REFRESH_TOKEN" "$SECRETS_DIR/zoho_refresh_token"

sudo python3 - "$ENV_FILE" "$SECRETS_DIR" <<'PY'
import os
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
secrets_dir = Path(sys.argv[2])
values = {
    "ZOHO_BUGTRACKER_PORTAL": "kfldotke",
    "ZOHO_BUGTRACKER_PROJECT_ID": "2730932000000114802",
    "ZOHO_CLIENT_ID_SECRET_FILE": str(secrets_dir / "zoho_client_id"),
    "ZOHO_CLIENT_SECRET_SECRET_FILE": str(secrets_dir / "zoho_client_secret"),
    "ZOHO_REFRESH_TOKEN_SECRET_FILE": str(secrets_dir / "zoho_refresh_token"),
}
lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
for key, value in values.items():
    replacement = f"{key}={value}"
    matches = [i for i, line in enumerate(lines) if line.startswith(f"{key}=")]
    if matches:
        lines[matches[0]] = replacement
        for index in reversed(matches[1:]):
            del lines[index]
    else:
        lines.append(replacement)
env_path.parent.mkdir(parents=True, exist_ok=True)
env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(env_path, 0o600)
PY

printf 'Staging BugTracker secret-file paths configured in %s (path values only).\n' "$ENV_FILE"
printf 'No container was restarted and no BugTracker tickets were created.\n'
