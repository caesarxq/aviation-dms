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
if [[ ! "${IMAGE_TAG}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
  echo "ERROR: Image tag contains unsupported characters"
  exit 1
fi
REGISTRY="${REGISTRY:-ghcr.io}"
REPO_NAME="${REPO_NAME:-caesarxq/aviation-dms}"
STAGING_DIR="/opt/kfl-aviation-dms-staging"

echo "============================================================"
echo "Aviation DMS Staging Deployment"
echo "Image tag: ${IMAGE_TAG}"
echo "Registry: ${REGISTRY}"
echo "Repository: ${REPO_NAME}"
echo "Target: 10.20.4.234 (via bastion 145.241.152.126)"
echo "============================================================"

# --- Validate deployment configuration before changing anything ---
cd "${STAGING_DIR}"
sudo env DMS_RELEASE_TAG="${IMAGE_TAG}" \
  DMS_HOSTNAME="stage.kfl.ke" \
  DMS_BACKEND_HOST_PORT=8001 \
  DMS_FRONTEND_HOST_PORT=8081 \
  docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.yml \
  --env-file .env.staging \
  config --quiet

# --- Pull images from registry ---
echo "--- Pulling images from registry ---"
sudo docker pull "${REGISTRY}/${REPO_NAME}/backend:${IMAGE_TAG}"
sudo docker pull "${REGISTRY}/${REPO_NAME}/frontend:${IMAGE_TAG}"

# --- Tag images for local compose ---
sudo docker tag "${REGISTRY}/${REPO_NAME}/backend:${IMAGE_TAG}" \
  "kfl-aviation-dms-backend:${IMAGE_TAG}"
sudo docker tag "${REGISTRY}/${REPO_NAME}/frontend:${IMAGE_TAG}" \
  "kfl-aviation-dms-frontend:${IMAGE_TAG}"

# --- Deploy using staging compose override ---
echo "--- Deploying to staging ---"
sudo env DMS_RELEASE_TAG="${IMAGE_TAG}" \
  DMS_HOSTNAME="stage.kfl.ke" \
  DMS_BACKEND_HOST_PORT=8001 \
  DMS_FRONTEND_HOST_PORT=8081 \
  docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.yml \
  --env-file .env.staging \
  up -d --no-build backend upload-validator clamd frontend

# --- Wait for health ---
echo "--- Waiting for services to become healthy ---"
for service in backend upload-validator clamd frontend; do
  echo "Waiting for ${service}..."
  for i in $(seq 1 30); do
    status=$(sudo docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      "kfl-aviation-dms-staging-${service}-1" 2>/dev/null || echo "not_found")
    if [ "${status}" = "healthy" ]; then
      echo "${service} is healthy"
      break
    fi
    if [ "${i}" -eq 30 ]; then
      echo "ERROR: ${service} did not become healthy (status: ${status})"
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
