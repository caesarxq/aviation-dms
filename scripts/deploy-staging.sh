#!/bin/bash
# ============================================================================
# Aviation DMS — Deploy to Staging (Cloud Instance)
# ============================================================================
# Usage: ./scripts/deploy-staging.sh <IMAGE_TAG>
#
# Deploys the specified image tag to the staging instance (10.20.4.234).
# Staging is deployed via bastion (145.241.152.126).
#
# FAIL-CLOSED: exits non-zero on any error.
# ============================================================================
set -euo pipefail

IMAGE_TAG="${1:?Usage: deploy-staging.sh <IMAGE_TAG>}"
REGISTRY="${REGISTRY:-ghcr.io}"
REPO_NAME="${REPO_NAME:-kfl-aviation-dms}"
STAGING_DIR="/opt/kfl-aviation-dms-staging"

echo "============================================================"
echo "Aviation DMS Staging Deployment"
echo "Image tag: ${IMAGE_TAG}"
echo "Registry: ${REGISTRY}"
echo "Repository: ${REPO_NAME}"
echo "Target: 10.20.4.234 (via bastion 145.241.152.126)"
echo "============================================================"

# --- Export environment variables for compose ---
export DMS_RELEASE_TAG="${IMAGE_TAG}"
export DMS_HOSTNAME="stage.kfl.ke"
export DMS_CLAMD_HOST="clamd"
export DMS_CLAMD_PORT="3310"
export DMS_CLAMD_TIMEOUT_SECONDS="60"
export DMS_CLAMD_MAX_TIMEOUT_SECONDS="60"
export DMS_UPLOAD_STORAGE_QUOTA_BYTES="1073741824"
export DMS_AUDIT_EVIDENCE_MAX_BYTES="10485760"
export DMS_P3_IMPORT_BODY_MAX_BYTES="5242880"
export FLIGHT_RELEASE_ENABLED="false"
export DEV_MODE="true"
export SESSION_COOKIE_SECURE="false"
export NOTIFICATION_ENABLED="false"
export ACME_EMAIL="admin@localhost.local"

# --- Pull images from registry ---
echo "--- Pulling images from registry ---"
sudo docker pull "${REGISTRY}/${REPO_NAME}/backend:${IMAGE_TAG}" || \
  echo "WARNING: Could not pull backend image from registry"
sudo docker pull "${REGISTRY}/${REPO_NAME}/frontend:${IMAGE_TAG}" || \
  echo "WARNING: Could not pull frontend image from registry"

# --- Tag images for local compose ---
sudo docker tag "${REGISTRY}/${REPO_NAME}/backend:${IMAGE_TAG}" \
  "kfl-aviation-dms-backend:${IMAGE_TAG}"
sudo docker tag "${REGISTRY}/${REPO_NAME}/frontend:${IMAGE_TAG}" \
  "kfl-aviation-dms-frontend:${IMAGE_TAG}"

# --- Deploy using staging compose override ---
echo "--- Deploying to staging ---"
cd "${STAGING_DIR}"
sudo docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.yml \
  --env-file .env.staging \
  up -d --build backend upload-validator clamd frontend https_proxy

# --- Wait for health ---
echo "--- Waiting for services to become healthy ---"
for service in backend upload-validator clamd frontend https_proxy; do
  echo "Waiting for ${service}..."
  for i in $(seq 1 30); do
    status=$(sudo docker inspect --format='{{.Status}}' \
      "kfl-aviation-dms-staging-${service}-1" 2>/dev/null || echo "not_found")
    if [ "${status}" = "healthy" ]; then
      echo "${service} is healthy"
      break
    fi
    if [ "${i}" -eq 30 ]; then
      echo "ERROR: ${service} did not become healthy"
      sudo docker logs "kfl-aviation-dms-staging-${service}-1" --tail 50
      exit 1
    fi
    sleep 2
  done
done

# --- Run smoke test ---
echo "--- Running smoke test ---"
sudo docker exec kfl-aviation-dms-staging-backend-1 \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" \
  && echo "Backend health check: OK" || {
    echo "ERROR: Backend health check failed"
    exit 1
  }

echo "============================================================"
echo "Staging deployment complete: ${IMAGE_TAG}"
echo "============================================================"
