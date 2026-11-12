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
if [[ ! "${IMAGE_TAG}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
  echo "ERROR: Image tag contains unsupported characters"
  exit 1
fi
REGISTRY="${REGISTRY:-ghcr.io}"
REPO_NAME="${REPO_NAME:-caesarxq/aviation-dms}"
PROD_DIR="/opt/kfl-aviation-dms-prod"
BACKUP_SCRIPT="${PROD_DIR}/scripts/full-stack-backup-prod.sh"

echo "============================================================"
echo "Aviation DMS Production Deployment"
echo "Image tag: ${IMAGE_TAG}"
echo "Registry: ${REGISTRY}"
echo "Target: Production OCI instance"
echo "============================================================"

# Validate Compose interpolation and syntax before running a backup or pulling images.
cd "${PROD_DIR}"
PREVIOUS_TAG=$(sed -n 's/^DMS_RELEASE_TAG=//p' .env.prod | head -n 1)
if [ -z "${PREVIOUS_TAG}" ]; then
  echo "ERROR: DMS_RELEASE_TAG is missing from .env.prod; cannot establish a rollback target."
  exit 1
fi
sudo env DMS_RELEASE_TAG="${IMAGE_TAG}" \
  DMS_HOSTNAME="roc.kfl.ke" \
  DMS_BACKEND_HOST_PORT=8000 \
  DMS_FRONTEND_HOST_PORT=8080 \
  docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  config --quiet

# --- Pre-deploy backup (rollback safeguard) ---
echo "--- Running pre-deployment backup ---"
if ! sudo test -x "${BACKUP_SCRIPT}"; then
  echo "ERROR: Production backup script is missing or not executable: ${BACKUP_SCRIPT}"
  echo "Deployment aborted before image pull or container changes."
  exit 1
fi
sudo "${BACKUP_SCRIPT}" || {
  echo "ERROR: Pre-deployment backup failed. Aborting deployment."
  exit 1
}
echo "Pre-deployment backup completed successfully"

# --- Pull images from registry ---
echo "--- Pulling images from registry ---"
sudo docker pull "${REGISTRY}/${REPO_NAME}/backend:${IMAGE_TAG}"
sudo docker pull "${REGISTRY}/${REPO_NAME}/frontend:${IMAGE_TAG}"

# --- Tag images for local Compose ---
sudo docker tag "${REGISTRY}/${REPO_NAME}/backend:${IMAGE_TAG}" \
  "kfl-aviation-dms-backend:${IMAGE_TAG}"
sudo docker tag "${REGISTRY}/${REPO_NAME}/frontend:${IMAGE_TAG}" \
  "kfl-aviation-dms-frontend:${IMAGE_TAG}"

# --- Deploy using production compose override ---
echo "--- Deploying to production ---"
compose_up() {
  local tag="$1"
  sudo env DMS_RELEASE_TAG="${tag}" \
    DMS_HOSTNAME="roc.kfl.ke" \
    DMS_BACKEND_HOST_PORT=8000 \
    DMS_FRONTEND_HOST_PORT=8080 \
    docker compose \
    -f docker-compose.yml \
    -f docker-compose.prod.yml \
    --env-file .env.prod \
    up -d --no-build backend upload-validator clamd frontend
}

if ! compose_up "${IMAGE_TAG}"; then
  echo "ERROR: Compose deployment command failed"
  if [ -n "${PREVIOUS_TAG}" ] && [ "${PREVIOUS_TAG}" != "${IMAGE_TAG}" ]; then
    echo "Attempting application rollback to prior tag ${PREVIOUS_TAG}"
    compose_up "${PREVIOUS_TAG}" || echo "ERROR: rollback command also failed"
  fi
  exit 1
fi

# --- Wait for health ---
echo "--- Waiting for services to become healthy ---"
for service in backend upload-validator clamd frontend; do
  echo "Waiting for ${service}..."
  healthy=false
  for i in $(seq 1 30); do
    status=$(sudo docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      "kfl-aviation-dms-prod-${service}-1" 2>/dev/null || echo "not_found")
    if [ "${status}" = "healthy" ]; then
      echo "${service} is healthy"
      healthy=true
      break
    fi
    sleep 2
  done
  if [ "${healthy}" != true ]; then
    echo "ERROR: ${service} did not become healthy (status: ${status})"
    sudo docker logs "kfl-aviation-dms-prod-${service}-1" --tail 50 || true
    if [ -n "${PREVIOUS_TAG}" ] && [ "${PREVIOUS_TAG}" != "${IMAGE_TAG}" ]; then
      echo "Attempting application rollback to prior tag ${PREVIOUS_TAG}"
      compose_up "${PREVIOUS_TAG}" || echo "ERROR: rollback command also failed"
    else
      echo "No prior DMS_RELEASE_TAG recorded; preserve current containers for manual recovery."
    fi
    exit 1
  fi
done

# --- Run smoke test ---
echo "--- Running smoke test ---"
if ! sudo docker exec kfl-aviation-dms-prod-backend-1 \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"; then
  echo "ERROR: Backend health check failed"
  if [ -n "${PREVIOUS_TAG}" ] && [ "${PREVIOUS_TAG}" != "${IMAGE_TAG}" ]; then
    echo "Attempting application rollback to prior tag ${PREVIOUS_TAG}"
    compose_up "${PREVIOUS_TAG}" || echo "ERROR: rollback command also failed"
  fi
  exit 1
fi
echo "Backend health check: OK"

# Persist the deployed tag only after all health checks pass.
sudo sed -i "s/^DMS_RELEASE_TAG=.*/DMS_RELEASE_TAG=${IMAGE_TAG}/" .env.prod

echo "============================================================"
echo "Production deployment complete: ${IMAGE_TAG}"
echo "============================================================"
