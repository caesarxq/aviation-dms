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
REPO_NAME="${REPO_NAME:-caesarxq/aviation-dms}"
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
export DMS_BACKEND_BIND_IP="10.20.4.234"
export DMS_BACKEND_HOST_PORT="8001"
export DMS_FRONTEND_BIND_IP="10.20.4.234"
export DMS_FRONTEND_HOST_PORT="8081"
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
# Compose interpolates this for the inactive local-HTTPS profile too.
export ACME_EMAIL="${ACME_EMAIL:-admin@localhost.local}"

# --- Validate the effective host bindings before pulling images ---
cd "${STAGING_DIR}"
sudo env \
  DMS_RELEASE_TAG="${DMS_RELEASE_TAG}" \
  DMS_HOSTNAME="${DMS_HOSTNAME}" \
  DMS_BACKEND_BIND_IP="${DMS_BACKEND_BIND_IP}" \
  DMS_BACKEND_HOST_PORT="${DMS_BACKEND_HOST_PORT}" \
  DMS_FRONTEND_BIND_IP="${DMS_FRONTEND_BIND_IP}" \
  DMS_FRONTEND_HOST_PORT="${DMS_FRONTEND_HOST_PORT}" \
  DMS_CLAMD_HOST="${DMS_CLAMD_HOST}" \
  DMS_CLAMD_PORT="${DMS_CLAMD_PORT}" \
  DMS_CLAMD_TIMEOUT_SECONDS="${DMS_CLAMD_TIMEOUT_SECONDS}" \
  DMS_CLAMD_MAX_TIMEOUT_SECONDS="${DMS_CLAMD_MAX_TIMEOUT_SECONDS}" \
  DMS_UPLOAD_STORAGE_QUOTA_BYTES="${DMS_UPLOAD_STORAGE_QUOTA_BYTES}" \
  DMS_AUDIT_EVIDENCE_MAX_BYTES="${DMS_AUDIT_EVIDENCE_MAX_BYTES}" \
  DMS_P3_IMPORT_BODY_MAX_BYTES="${DMS_P3_IMPORT_BODY_MAX_BYTES}" \
  FLIGHT_RELEASE_ENABLED="${FLIGHT_RELEASE_ENABLED}" \
  DEV_MODE="${DEV_MODE}" \
  SESSION_COOKIE_SECURE="${SESSION_COOKIE_SECURE}" \
  NOTIFICATION_ENABLED="${NOTIFICATION_ENABLED}" \
  ACME_EMAIL="${ACME_EMAIL}" \
  docker compose -f docker-compose.yml -f docker-compose.staging.yml \
    --env-file .env.staging config --format json |
  python3 -c 'import json, sys
config = json.load(sys.stdin)
expected = {"backend": [("10.20.4.234", "8001", 8000, "tcp")], "frontend": [("10.20.4.234", "8081", 80, "tcp")], "upload-validator": [], "clamd": []}
actual = {name: [(p.get("host_ip"), str(p.get("published")), int(p["target"]), p.get("protocol", "tcp")) for p in config["services"][name].get("ports", [])] for name in expected}
if actual != expected:
    print("ERROR: staging host port bindings do not match the private-interface allowlist")
    sys.exit(1)
backend_env = config["services"]["backend"].get("environment", {})
if str(backend_env.get("INVITE_EMAIL_ENABLED")).lower() != "false" or str(backend_env.get("NOTIFICATION_ENABLED")).lower() != "false":
    print("ERROR: staging email delivery flags must remain disabled")
    sys.exit(1)
print("Staging host port bindings and disabled email flags verified")'

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
cd "${STAGING_DIR}"
sudo env \
  DMS_RELEASE_TAG="${DMS_RELEASE_TAG}" \
  DMS_HOSTNAME="${DMS_HOSTNAME}" \
  DMS_BACKEND_BIND_IP="${DMS_BACKEND_BIND_IP}" \
  DMS_BACKEND_HOST_PORT="${DMS_BACKEND_HOST_PORT}" \
  DMS_FRONTEND_BIND_IP="${DMS_FRONTEND_BIND_IP}" \
  DMS_FRONTEND_HOST_PORT="${DMS_FRONTEND_HOST_PORT}" \
  DMS_CLAMD_HOST="${DMS_CLAMD_HOST}" \
  DMS_CLAMD_PORT="${DMS_CLAMD_PORT}" \
  DMS_CLAMD_TIMEOUT_SECONDS="${DMS_CLAMD_TIMEOUT_SECONDS}" \
  DMS_CLAMD_MAX_TIMEOUT_SECONDS="${DMS_CLAMD_MAX_TIMEOUT_SECONDS}" \
  DMS_UPLOAD_STORAGE_QUOTA_BYTES="${DMS_UPLOAD_STORAGE_QUOTA_BYTES}" \
  DMS_AUDIT_EVIDENCE_MAX_BYTES="${DMS_AUDIT_EVIDENCE_MAX_BYTES}" \
  DMS_P3_IMPORT_BODY_MAX_BYTES="${DMS_P3_IMPORT_BODY_MAX_BYTES}" \
  FLIGHT_RELEASE_ENABLED="${FLIGHT_RELEASE_ENABLED}" \
  DEV_MODE="${DEV_MODE}" \
  SESSION_COOKIE_SECURE="${SESSION_COOKIE_SECURE}" \
  NOTIFICATION_ENABLED="${NOTIFICATION_ENABLED}" \
  ACME_EMAIL="${ACME_EMAIL}" \
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
    status=$(sudo docker inspect --format='{{.State.Health.Status}}' \
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
