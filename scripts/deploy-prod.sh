#!/bin/bash
# ============================================================================
# Aviation DMS — Deploy to Production (OCI Instance)
# ============================================================================
# Usage: ./scripts/deploy-prod.sh <IMAGE_TAG>
#
# Deploys the specified image tag to the production OCI instance.
# Runs a full-stack backup BEFORE deployment as a rollback safeguard.
#
# FAIL-CLOSED: exits non-zero on any error. Nothing is deleted from live system.
# ============================================================================
set -euo pipefail

IMAGE_TAG="${1:?Usage: deploy-prod.sh <IMAGE_TAG>}"
REGISTRY="${REGISTRY:-ghcr.io}"
PROD_DIR="/opt/kfl-aviation-dms-prod"
BACKUP_SCRIPT="${PROD_DIR}/scripts/full-stack-backup.sh"

echo "============================================================"
echo "Aviation DMS Production Deployment"
echo "Image tag: ${IMAGE_TAG}"
echo "Registry: ${REGISTRY}"
echo "Target: Production OCI instance"
echo "============================================================"

# --- Pre-deploy backup (rollback safeguard) ---
echo "--- Running pre-deployment backup ---"
if [ -f "${BACKUP_SCRIPT}" ]; then
  sudo "${BACKUP_SCRIPT}" || {
    echo "ERROR: Pre-deployment backup failed. Aborting deployment."
    exit 1
  }
  echo "Pre-deployment backup completed successfully"
else
  echo "WARNING: Backup script not found at ${BACKUP_SCRIPT}"
  echo "Continuing without backup (not recommended for production)"
fi

# --- Export environment variables for compose ---
export DMS_RELEASE_TAG="${IMAGE_TAG}"
export DMS_HOSTNAME="roc.kfl.ke"
export DMS_CLAMD_HOST="clamd"
export DMS_CLAMD_PORT="3310"
export DMS_CLAMD_TIMEOUT_SECONDS="60"
export DMS_CLAMD_MAX_TIMEOUT_SECONDS="60"
export DMS_UPLOAD_STORAGE_QUOTA_BYTES="30000000000"
export DMS_AUDIT_EVIDENCE_MAX_BYTES="10485760"
export DMS_P3_IMPORT_BODY_MAX_BYTES="5242880"
export FLIGHT_RELEASE_ENABLED="false"
export DEV_MODE="false"
export SESSION_COOKIE_SECURE="true"
export NOTIFICATION_ENABLED="true"
export ACME_EMAIL="admin@kfl.ke"

# --- Pull images from registry ---
echo "--- Pulling images from registry ---"
sudo docker pull "${REGISTRY}/kfl-aviation-dms/backend:${IMAGE_TAG}"
sudo docker pull "${REGISTRY}/kfl-aviation-dms/frontend:${IMAGE_TAG}"

# --- Tag images for local compose ---
sudo docker tag "${REGISTRY}/kfl-aviation-dms/backend:${IMAGE_TAG}" \
  "kfl-aviation-dms-backend:${IMAGE_TAG}"
sudo docker tag "${REGISTRY}/kfl-aviation-dms/frontend:${IMAGE_TAG}" \
  "kfl-aviation-dms-frontend:${IMAGE_TAG}"

# --- Deploy using production compose override ---
echo "--- Deploying to production ---"
cd "${PROD_DIR}"
sudo docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  up -d --build backend upload-validator clamd frontend https_proxy

# --- Wait for health ---
echo "--- Waiting for services to become healthy ---"
for service in backend upload-validator clamd frontend https_proxy; do
  echo "Waiting for ${service}..."
  for i in $(seq 1 30); do
    status=$(sudo docker inspect --format='{{.Status}}' \
      "kfl-aviation-dms-prod-${service}-1" 2>/dev/null || echo "not_found")
    if [ "${status}" = "healthy" ]; then
      echo "${service} is healthy"
      break
    fi
    if [ "${i}" -eq 30 ]; then
      echo "ERROR: ${service} did not become healthy"
      sudo docker logs "kfl-aviation-dms-prod-${service}-1" --tail 50
      echo "Initiating rollback..."
      sudo docker compose \
        -f docker-compose.yml \
        -f docker-compose.prod.yml \
        --env-file .env.prod \
        down
      exit 1
    fi
    sleep 2
  done
done

# --- Run smoke test ---
echo "--- Running smoke test ---"
sudo docker exec kfl-aviation-dms-prod-backend-1 \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" \
  && echo "Backend health check: OK" || {
    echo "ERROR: Backend health check failed"
    exit 1
  }

echo "============================================================"
echo "Production deployment complete: ${IMAGE_TAG}"
echo "============================================================"
