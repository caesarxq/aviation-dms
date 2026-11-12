#!/bin/bash
# ============================================================================
# Find Ubuntu 24.04 LTS Boot Image OCID in OCI me-riyadh-1 region
# ============================================================================
# Run this in OCI Cloud Shell after configuring OCI CLI
# ============================================================================

set -euo pipefail

# --- Configuration ---
REGION="me-riyadh-1"
COMPARTMENT_ID="${1:-}"  # Optional: pass compartment OCID as argument

echo "============================================================"
echo "Searching for Ubuntu 24.04 LTS boot image in $REGION"
echo "============================================================"

# --- Set region ---
oci mb region list 2>/dev/null | grep -q "$REGION" || \
  oci setup config --region "$REGION" --force 2>/dev/null || true

# --- Get compartment OCID if not provided ---
if [ -z "$COMPARTMENT_ID" ]; then
    echo "No compartment OCID provided. Finding root compartment..."
    TENANCY_ID=$(oci iam tenancy get | jq -r '.data.id')
    COMPARTMENT_ID="$TENANCY_ID"
    echo "Using tenancy as compartment: $COMPARTMENT_ID"
fi

echo "Compartment: $COMPARTMENT_ID"
echo "Region: $REGION"
echo ""

# --- Search for Ubuntu 24.04 images ---
echo "--- Searching for Ubuntu 24.04 images ---"

# Method 1: Search by display name containing "Ubuntu" and "24.04"
IMAGE_OCID=$(oci compute image list \
    --compartment-id "$COMPARTMENT_ID" \
    --region "$REGION" \
    --display-name "Ubuntu" \
    --query "data[?contains('\"'+display_name+'\"', 'Ubuntu') && contains('\"'+display_name+'\"', '24.04')].{id:id, display_name:display_name, operating_system:operating_system, version:version}" \
    --raw-output 2>/dev/null || true)

if [ -z "$IMAGE_OCID" ] || [ "$IMAGE_OCID" = "[]" ]; then
    echo "No exact match found. Trying broader search..."

    # Method 2: List all images and filter for Ubuntu 24
    IMAGE_OCID=$(oci compute image list \
        --compartment-id "$COMPARTMENT_ID" \
        --region "$REGION" \
        --query "data[?contains(lower(display_name), 'ubuntu') && contains(lower(display_name), '24')].{id:id, display_name:display_name, operating_system:operating_system, version:version}" \
        --raw-output 2>/dev/null || true)
fi

# --- Display results ---
if [ -z "$IMAGE_OCID" ] || [ "$IMAGE_OCID" = "[]" ]; then
    echo ""
    echo "ERROR: No Ubuntu 24.04 image found in compartment $COMPARTMENT_ID in region $REGION"
    echo ""
    echo "Possible reasons:"
    echo "  1. The image is not available in this compartment"
    echo "  2. The image is in a different compartment (try listing all compartments)"
    echo "  3. The image name doesn't contain 'Ubuntu 24.04'"
    echo ""
    echo "To list all available images:"
    echo "  oci compute image list --compartment-id $COMPARTMENT_ID --region $REGION --query 'data[].{id:id, display_name:display_name}'"
    exit 1
fi

echo ""
echo "============================================================"
echo "FOUND UBUNTU 24.04 IMAGE(S)"
echo "============================================================"
echo "$IMAGE_OCID" | jq '.'

echo ""
echo "============================================================"
echo "USE THIS OCID IN terraform.tfvars:"
echo "============================================================"
PRIMARY_OCID=$(echo "$IMAGE_OCID" | jq -r '.[0].id // empty')
if [ -n "$PRIMARY_OCID" ] && [ "$PRIMARY_OCID" != "null" ]; then
    echo "boot_image_id = \"$PRIMARY_OCID\""
    echo ""
    echo "To update terraform.tfvars automatically:"
    echo "  sed -i 's|boot_image_id = .*|boot_image_id = \"$PRIMARY_OCID\"|' terraform/oci-prod/terraform.tfvars"
else
    echo "Could not extract primary OCID. Please copy manually from the output above."
fi
echo "============================================================"
