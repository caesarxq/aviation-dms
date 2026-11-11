# Terraform: Aviation DMS Backup/Restore on OCI

Provisions a dedicated, isolated backup/restore instance on OCI for the KFL Aviation DMS.

## What this creates

| Resource | Purpose |
|----------|---------|
| `oci_core_instance` | Backup VM (2 OCPU / 4 GiB, no public IP) |
| `oci_core_volume` | Backup staging block volume (200 GiB, encrypted) |
| `oci_core_volume_attachment` | iSCSI attachment of block volume to instance |
| `oci_core_network_security_group` | Restricted network rules |

## Security properties

- **No public IP** — instance is reachable only from within the VCN
- **Security group** — inbound from backend VCN CIDR on ports 3310 (clamd) and 9100 (validator) only; outbound to HTTPS (443) for off-host storage and OCI services; DNS (UDP 53)
- **Encrypted volumes** — boot and block volumes encrypted with your KMS key
- **No SSH key** — use OCI Instance Console or bastion host for access

## Prerequisites

1. **OCI CLI configured** — `~/.oci/config` with your tenancy, user, and API key
2. **Terraform installed** — `>= 1.5.0`
3. **OCI provider** — will be auto-downloaded on `terraform init`

## Required information (get from OCI Console)

| Value | Where to find |
|-------|---------------|
| Tenancy OCID | Identity & Tenancy > Tenancy Details |
| Compartment OCID | Identity & Compartments |
| Availability Domain | Identity & Availability Domains |
| VCN OCID | Networking > Virtual Cloud Networks |
| Subnet OCID | Networking > Virtual Cloud Networks > Subnets |
| KMS Key OCID | Key Management > Keys |
| Boot Image OCID | Compute > Images (Oracle Linux 9) |

## Usage

```bash
# Copy the example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your actual OCIDs
# (never commit terraform.tfvars)

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply
terraform apply

# Destroy when no longer needed
terraform destroy
```

## Post-provisioning steps

1. **Connect to the instance** — Use OCI Instance Console or bastion host (no public SSH)
2. **Attach and mount block volume** — Run `iscsiadm` to discover and mount the block volume
3. **Configure clamd** — Copy `/clamav/clamd.conf` from this repo and start clamd
4. **Configure environment variables** — Set `DMS_CLAMD_HOST`, `DMS_CLAMD_PORT`, etc. on the backup instance
5. **Verify isolation** — Confirm the instance has no public IP and cannot reach the public internet except on port 443

## Security notes

- **Never commit `terraform.tfvars`** — it contains your tenancy OCIDs
- **Rotate KMS keys** regularly per your organization's key management policy
- **Review security group rules** before applying — the `off_host_storage_cidr` must match your actual off-host storage endpoint
- **Backup validation** — Use `backend/app/backup_validation.py` from this repo to verify restore candidates; it is read-only and does not modify data

## Cost estimate

Approximate monthly cost (OCI, us-ashburn-1):
- VM.Standard.E4.Flex (2 OCPU / 4 GiB): ~$80-120/month
- Boot volume 50 GiB: ~$2.50/month
- Block volume 200 GiB: ~$10/month
- Total: ~$95-135/month (varies by region and usage)
