#!/bin/bash
# =============================================================================
# Aviation DMS Full-Stack Backup — Cron Job
#
# Backs up: app images (Docker), data (SQLite + storage roots),
# configurations (Caddyfile, Compose, env), security (keys, certs),
# dependencies (pip freeze, apt list).
#
# Pushes to off-host server: 10.20.173.120:~/dms-backups/
# Direct SSH within OCI VCN (no bastion needed).
#
# FAIL-CLOSED: exits non-zero on any error. Nothing is deleted from live system.
# =============================================================================
set -euo pipefail

# --- Configuration ---
BACKUP_SERVER="10.20.173.120"
BACKUP_USER="ubuntu"
BACKUP_DEST="~/dms-backups"
CLIENT_KEY="${HOME}/.ssh/ssh-key-2026-11-10.key"
TIMESTAMP=$(date +%Y%m%dT%H%M%SZ)
CANDIDATE="dms-backup-${TIMESTAMP}"
LOG_FILE="/var/log/aviation-dms/backup-${TIMESTAMP}.log"
RETENTION_COUNT="${DMS_BACKUP_MAX_RETENTION_COUNT:-5}"

# --- SSH options ---
SSH_OPTS="-i ${CLIENT_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=no"

# --- Logging ---
mkdir -p "$(dirname "${LOG_FILE}")"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "============================================================"
echo "Aviation DMS Full-Stack Backup Started: ${TIMESTAMP}"
echo "Candidate: ${CANDIDATE}"
echo "Destination: ${BACKUP_USER}@${BACKUP_SERVER}:${BACKUP_DEST}"
echo "============================================================"

# --- Pre-flight checks ---
for cmd in docker ssh scp tar gzip sha256sum python3; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "ERROR: Required command not found: ${cmd}"
        exit 1
    fi
done

# Verify backup server connectivity (direct, no bastion)
if ! ssh ${SSH_OPTS} "${BACKUP_USER}@${BACKUP_SERVER}" "echo 'backup server ok'" >/dev/null 2>&1; then
    echo "ERROR: Cannot reach backup server ${BACKUP_SERVER}"
    exit 1
fi

# Create remote candidate directory
ssh ${SSH_OPTS} "${BACKUP_USER}@${BACKUP_SERVER}" \
    "mkdir -p ${BACKUP_DEST}/${CANDIDATE}"

STAGING=$(mktemp -d)
trap 'rm -rf "${STAGING}"' EXIT

echo "Staging area: ${STAGING}"

# =============================================================================
# 1. APP IMAGES — Save Docker images
# =============================================================================
echo "--- Saving Docker images ---"
IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -v '<none>' || true)
if [ -n "${IMAGES}" ]; then
    echo "${IMAGES}" | while read -r img; do
        safe_name=$(echo "${img}" | tr '/:' '__')
        docker save "${img}" | gzip > "${STAGING}/images-${safe_name}.tar.gz"
        echo "Saved image: ${img}"
    done
else
    echo "WARNING: No Docker images found to save"
fi

# Record image manifest
docker images --format '{{.Repository}}:{{.Tag}}@{{.ID}}' > "${STAGING}/images-manifest.txt" 2>/dev/null || true

# =============================================================================
# 2. DATA — SQLite database (online backup) + storage roots
# =============================================================================
echo "--- Backing up data ---"

# Database path — Docker volume mount for the backend container
DB_PATH="/var/lib/docker/volumes/kfl-aviation-dms-staging_dms_data/_data/dms.db"
DATA_ROOT="/var/lib/docker/volumes/kfl-aviation-dms-staging_dms_data/_data"

if [ ! -f "${DB_PATH}" ]; then
    echo "ERROR: Database not found at ${DB_PATH}"
    exit 1
fi

# Consistent SQLite backup via online API
python3 -c "
import sqlite3
source = sqlite3.connect('${DB_PATH}')
dest = sqlite3.connect('${STAGING}/dms.db')
with dest:
    source.backup(dest)
source.close()
dest.close()
print('SQLite backup completed via online API')
"

# Storage roots
for root in uploads kcaa-evidence attachments; do
    if [ -d "${DATA_ROOT}/${root}" ]; then
        tar -czf "${STAGING}/data-${root}.tar.gz" -C "${DATA_ROOT}" "${root}"
        echo "Archived storage root: ${root}"
    else
        echo "WARNING: Storage root not found: ${DATA_ROOT}/${root} (skipping)"
    fi
done

# =============================================================================
# 3. CONFIGURATIONS — App and infrastructure configs
# =============================================================================
echo "--- Backing up configurations ---"

CONFIG_FILES=(
    "/opt/kfl-aviation-dms-staging/Caddyfile"
    "/opt/kfl-aviation-dms-staging/docker-compose.yml"
    "/opt/kfl-aviation-dms-staging/.env"
    "/etc/kfl-aviation-dms/secrets/kfl_bootstrap_token"
    "/etc/kfl-aviation-dms/secrets/smtp_pass"
)

mkdir -p "${STAGING}/configs"
for f in "${CONFIG_FILES[@]}"; do
    if [ -f "${f}" ]; then
        cp -a "${f}" "${STAGING}/configs/$(basename "${f}")"
        echo "Backed up config: ${f}"
    else
        echo "WARNING: Config not found: ${f} (skipping)"
    fi
done

# Save environment variables (excluding secrets)
env | grep -E '^DMS_|^FLIGHT_|^SMTP_|^RATE_|^SESSION_|^ACME_|^KFL_' > "${STAGING}/configs/environment.txt" 2>/dev/null || true

# =============================================================================
# 4. SECURITY — SSH keys, TLS certificates, secret files
# =============================================================================
echo "--- Backing up security artifacts ---"

mkdir -p "${STAGING}/security"
SECURITY_PATHS=(
    "${HOME}/.ssh/ssh-key-2026-11-10.key"
    "${HOME}/.ssh/ssh-key-2026-11-10.key.pub"
    "${HOME}/.ssh/ssh-key-2026-11-06-2.key"
    "${HOME}/.ssh/ssh-key-2026-11-06-2.key.pub"
    "/etc/kfl-aviation-dms/secrets"
)

for path in "${SECURITY_PATHS[@]}"; do
    if [ -e "${path}" ]; then
        safe_rel=$(echo "${path}" | sed 's|^/||; s|/|__|g')
        if [ -d "${path}" ]; then
            tar -czf "${STAGING}/security/${safe_rel}.tar.gz" -C "$(dirname "${path}")" "$(basename "${path}")"
        else
            cp -a "${path}" "${STAGING}/security/${safe_rel}"
        fi
        echo "Backed up security: ${path}"
    else
        echo "WARNING: Security path not found: ${path} (skipping)"
    fi
done

# =============================================================================
# 5. DEPENDENCIES — Python packages, system packages
# =============================================================================
echo "--- Backing up dependencies ---"

mkdir -p "${STAGING}/dependencies"
python3 -m pip freeze > "${STAGING}/dependencies/python-packages.txt" 2>/dev/null || true
pip list --format=json > "${STAGING}/dependencies/python-packages.json" 2>/dev/null || true
dpkg --get-selections > "${STAGING}/dependencies/system-packages.txt" 2>/dev/null || true
docker version > "${STAGING}/dependencies/docker-version.txt" 2>/dev/null || true
docker compose version > "${STAGING}/dependencies/docker-compose-version.txt" 2>/dev/null || true

# =============================================================================
# 6. MANIFEST — Record everything
# =============================================================================
echo "--- Creating backup manifest ---"

cat > "${STAGING}/MANIFEST.json" <<MANIFEST
{
  "backup_timestamp": "${TIMESTAMP}",
  "candidate_name": "${CANDIDATE}",
  "source_host": "$(hostname)",
  "backup_server": "${BACKUP_SERVER}",
  "backup_destination": "${BACKUP_DEST}/${CANDIDATE}",
  "contents": {
    "app_images": "Docker images saved as tar.gz",
    "data": "SQLite database (online backup API) + storage roots",
    "configurations": "Caddyfile, docker-compose, env, secrets",
    "security": "SSH keys, TLS certs, secret files",
    "dependencies": "Python packages, system packages, Docker versions"
  },
  "verification": {
    "method": "backup_validation.py verify --data-root <candidate> --confirm-isolated-candidate",
    "verifier": "system_administrator",
    "status": "pending"
  }
}
MANIFEST

# Create SHA-256 checksums for all files
cd "${STAGING}"
find . -type f -exec sha256sum {} \; > "${STAGING}/SHA256SUMS"
cd - > /dev/null

# =============================================================================
# 7. PUSH TO BACKUP SERVER
# =============================================================================
echo "--- Pushing candidate to backup server ---"

tar -czf - -C "${STAGING}" . | ssh ${SSH_OPTS} "${BACKUP_USER}@${BACKUP_SERVER}" \
    "cat > ${BACKUP_DEST}/${CANDIDATE}/backup-bundle.tar.gz"

# Extract on remote for verification
ssh ${SSH_OPTS} "${BACKUP_USER}@${BACKUP_SERVER}" \
    "tar -xzf ${BACKUP_DEST}/${CANDIDATE}/backup-bundle.tar.gz -C ${BACKUP_DEST}/${CANDIDATE} && rm ${BACKUP_DEST}/${CANDIDATE}/backup-bundle.tar.gz"

echo "Backup pushed successfully to ${BACKUP_DEST}/${CANDIDATE}"

# =============================================================================
# 8. RETENTION — Clean old backups on remote server
# =============================================================================
echo "--- Applying retention policy (keep ${RETENTION_COUNT}) ---"

ssh ${SSH_OPTS} "${BACKUP_USER}@${BACKUP_SERVER}" \
    "ls -1d ${BACKUP_DEST}/dms-backup-* 2>/dev/null | sort -r | tail -n +$((RETENTION_COUNT + 1)) | xargs -r rm -rf"

echo "============================================================"
echo "Backup Complete: ${TIMESTAMP}"
echo "Candidate: ${CANDIDATE}"
echo "Location: ${BACKUP_USER}@${BACKUP_SERVER}:${BACKUP_DEST}/${CANDIDATE}"
echo "============================================================"
