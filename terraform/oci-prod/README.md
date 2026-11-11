# Aviation DMS Production OCI Terraform

Provisions the production app instance on OCI. This is separate from the backup instance (`terraform/oci-backup/`).

## Architecture

```
DNS: roc.kfl.ke → bastion 145.241.152.126 → production app instance (private IP)
                                             ├── backend:8000
                                             ├── frontend:8080
                                             ├── upload-validator:9100 (internal)
                                             └── clamd:3310 (internal)
```

## Prerequisites

- OCI CLI configured (`~/.oci/config`) or environment variables set
- Terraform >= 1.5.0
- Existing VCN, subnet, and KMS key in your OCI tenancy
- Bastion host at `145.241.152.126` already running

## Usage

```bash
cd terraform/oci-prod

# Copy example vars and fill in your values
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your OCIDs

# Initialize
terraform init

# Review plan
terraform plan

# Apply
terraform apply

# Get the production instance private IP
terraform output instance_private_ip
```

## Outputs

| Output | Description |
|--------|-------------|
| `instance_id` | OCID of the production compute instance |
| `instance_private_ip` | Private IP — configure bastion Caddy to proxy `roc.kfl.ke` to this IP:8000/:8080 |
| `nsg_id` | OCID of the network security group |
| `bastion_ip` | Bastion public IP |

## Post-Deployment Steps

1. **SSH to the production instance** via bastion:
   ```bash
   ssh -i <key> -o ProxyCommand="ssh -i <key> -W %h:%p ubuntu@145.241.152.126" ubuntu@<PRIVATE_IP>
   ```

2. **Clone the repository** and deploy:
   ```bash
   git clone <repo-url>
   cd aviation-dms
   cp .env.prod.example .env.prod
   # Edit .env.prod with production values
   ./scripts/deploy-prod.sh <IMAGE_TAG>
   ```

3. **Update bastion Caddy** to proxy `roc.kfl.ke` to the production instance IP:
   ```caddy
   roc.kfl.ke {
       reverse_proxy /api/* <PROD_PRIVATE_IP>:8000
       reverse_proxy <PROD_PRIVATE_IP>:8080
   }
   ```

## Security

- Instance has no public IP (private only)
- All access via bastion SSH proxy
- NSG restricts inbound to bastion IP only (ports 22, 8000, 8080)
- Clamd (3310) and validator (9100) are internal-only
- Boot volume encrypted with KMS key
- `no-new-privileges`, capability dropping, read-only FS on containers

## Separation from Backup Instance

This production app instance is separate from `terraform/oci-backup/`:
- Backup instance (`10.20.173.120`): clamd + backup storage only
- Production app instance: backend, frontend, validator, clamd for production traffic
- Production backups are pushed TO the backup instance
