#!/bin/bash
# ============================================================================
# Aviation DMS — Promote Staging-Validated Image to Production
# ============================================================================
# Usage: ./scripts/promote-to-production.sh <IMAGE_TAG>
#
# Promotes a staging-validated image tag to production on the OCI instance.
# This is the production promotion step of the CI/CD pipeline.
#
# PREREQUISITES:
#   1. Image tag must be validated on staging first
#   2. Production environment protection rule must be satisfied (manual approval)
#   3. Pre-deployment backup is run automatically by deploy-prod.sh
#
# FAIL-CLOSED: exits non-zero on any error.
# ============================================================================
set -euo pipefail

IMAGE_TAG="${1:?Usage: promote-to-production.sh <IMAGE_TAG>}"
if [[ ! "${IMAGE_TAG}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
  echo "ERROR: Image tag contains unsupported characters"
  exit 1
fi
PRODUCTION_APPROVED="${PRODUCTION_APPROVED:-false}"
PROD_HOST="${PROD_HOST:-10.20.1.69}"
PROD_USER="${PROD_USER:-ubuntu}"
BASTION_HOST="${BASTION_HOST:-145.241.152.126}"
BASTION_USER="${BASTION_USER:-ubuntu}"
BASTION_KEY_FILE="${BASTION_SSH_KEY_FILE:-}"
PRODUCTION_KEY_FILE="${PRODUCTION_SSH_KEY_FILE:-}"
REGISTRY="${REGISTRY:-ghcr.io}"
REPO_NAME="${REPO_NAME:-caesarxq/aviation-dms}"

if [ "${PRODUCTION_APPROVED}" != "true" ]; then
  echo "ERROR: Set PRODUCTION_APPROVED=true only after explicit production authorization."
  exit 1
fi
if [ -z "${BASTION_KEY_FILE}" ] || [ ! -r "${BASTION_KEY_FILE}" ] || \
   [ -z "${PRODUCTION_KEY_FILE}" ] || [ ! -r "${PRODUCTION_KEY_FILE}" ]; then
  echo "ERROR: Set BASTION_SSH_KEY_FILE and PRODUCTION_SSH_KEY_FILE to readable private-key paths."
  exit 1
fi

echo "============================================================"
echo "Aviation DMS Production Promotion"
echo "Image tag: ${IMAGE_TAG}"
echo "Target: ${PROD_HOST} (via bastion ${BASTION_HOST})"
echo "============================================================"

# --- Verify image exists in registry ---
echo "--- Verifying image in registry ---"
if ! docker manifest inspect "${REGISTRY}/${REPO_NAME}/backend:${IMAGE_TAG}" >/dev/null 2>&1; then
  echo "ERROR: Image backend:${IMAGE_TAG} not found in registry"
  exit 1
fi
if ! docker manifest inspect "${REGISTRY}/${REPO_NAME}/frontend:${IMAGE_TAG}" >/dev/null 2>&1; then
  echo "ERROR: Image frontend:${IMAGE_TAG} not found in registry"
  exit 1
fi
echo "Images verified in registry"

# --- Deploy to production via SSH through bastion ---
echo "--- Deploying validated image to production ---"
ssh -i "${PRODUCTION_KEY_FILE}" -o IdentitiesOnly=yes \
    -o StrictHostKeyChecking=no \
    -o ProxyCommand="ssh -i '${BASTION_KEY_FILE}' -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -W %h:%p ${BASTION_USER}@${BASTION_HOST}" \
    "${PROD_USER}@${PROD_HOST}" \
    "sudo /opt/kfl-aviation-dms-prod/scripts/deploy-prod.sh '${IMAGE_TAG}'"

echo "============================================================"
echo "Production promotion complete: ${IMAGE_TAG}"
echo "============================================================"
