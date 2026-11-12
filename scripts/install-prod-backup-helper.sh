#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run this installer as root" >&2
  exit 1
fi

SOURCE_ROOT="${1:?Usage: install-prod-backup-helper.sh <repository-root>}"
PROD_ROOT="/opt/kfl-aviation-dms-prod"
SCRIPT_DIR="${PROD_ROOT}/scripts"
APP_DIR="${PROD_ROOT}/backup-tool/app"
SYSTEMD_DIR="/etc/systemd/system"

for required in \
  "${SOURCE_ROOT}/scripts/full-stack-backup-prod.sh" \
  "${SOURCE_ROOT}/scripts/full_stack_backup_prod.py" \
  "${SOURCE_ROOT}/backend/app/backup_create.py" \
  "${SOURCE_ROOT}/backend/app/backup_validation.py" \
  "${SOURCE_ROOT}/docs/PRODUCTION-BACKUP-IMPLEMENTATION.md" \
  "${SOURCE_ROOT}/deploy/systemd/kfl-aviation-dms-backup.service" \
  "${SOURCE_ROOT}/deploy/systemd/kfl-aviation-dms-backup.timer"; do
  if [[ ! -f "${required}" ]]; then
    echo "ERROR: required helper file is missing" >&2
    exit 1
  fi
done

install -d -o root -g root -m 0755 "${SCRIPT_DIR}" "${APP_DIR}"
install -d -o root -g root -m 0700 /etc/kfl-aviation-dms-prod/backup-secrets
install -d -o root -g root -m 0700 /var/lib/kfl-aviation-dms-prod-backups/staging
install -m 0750 "${SOURCE_ROOT}/scripts/full-stack-backup-prod.sh" "${SCRIPT_DIR}/full-stack-backup-prod.sh"
install -m 0644 "${SOURCE_ROOT}/scripts/full_stack_backup_prod.py" "${SCRIPT_DIR}/full_stack_backup_prod.py"
install -m 0644 "${SOURCE_ROOT}/deploy/systemd/backup.env.example" "${PROD_ROOT}/backup-tool/backup.env.example"
install -m 0644 "${SOURCE_ROOT}/docs/PRODUCTION-BACKUP-IMPLEMENTATION.md" "${PROD_ROOT}/backup-tool/README.md"
cp -a "${SOURCE_ROOT}/backend/app/." "${APP_DIR}/"
chown -R root:root "${APP_DIR}"
find "${APP_DIR}" -type d -exec chmod 0755 {} +
find "${APP_DIR}" -type f -exec chmod 0644 {} +
install -m 0644 "${SOURCE_ROOT}/deploy/systemd/kfl-aviation-dms-backup.service" "${SYSTEMD_DIR}/kfl-aviation-dms-backup.service"
install -m 0644 "${SOURCE_ROOT}/deploy/systemd/kfl-aviation-dms-backup.timer" "${SYSTEMD_DIR}/kfl-aviation-dms-backup.timer"
systemctl daemon-reload

printf '%s\n' \
  "Production backup helper and systemd units installed." \
  "The timer remains disabled; no backup was run and production services were not restarted." \
  "Configure the non-secret backup.env and protected Restic/SSH files, verify the off-host key and retention policy, then run a manual backup/restore before enabling it."
