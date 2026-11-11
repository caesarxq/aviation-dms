# Terraform configuration for Aviation DMS backup/restore instance on OCI
#
# Provision:
#   - Compute instance (private, no public IP)
#   - Encrypted boot volume (50 GiB)
#   - Encrypted block volume for backup staging
#   - Network Security Group with restricted inbound/outbound rules
#
# All values that identify your tenancy, compartment, VCN, or subnet are
# variables. Fill in terraform.tfvars (do not commit secrets).

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "hashicorp/oci"
      version = "~> 5.0"
    }
  }
}

provider "oci" {
  # Authentication is handled by OCI CLI config file (~/.oci/config) or
  # environment variables (TF_VAR_tenancy_ocid, etc.). Do not hardcode
  # credentials here.
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "tenancy_ocid" {
  type        = string
  description = "OCI Tenancy OCID"
}

variable "compartment_ocid" {
  type        = string
  description = "Compartment OCID for backup instance resources"
}

variable "availability_domain" {
  type        = string
  description = "Availability Domain for the backup instance"
}

variable "subnet_id" {
  type        = string
  description = "Private subnet OCID (no public IP assignment)"
}

variable "vcn_id" {
  type        = string
  description = "VCN OCID for network security group"
}

variable "kms_key_id" {
  type        = string
  description = "KMS Master Encryption Key OCID for volume encryption"
}

variable "instance_shape" {
  type        = string
  default     = "VM.Standard.E4.Flex"
  description = "Compute shape (general purpose)"
}

variable "ocpus" {
  type        = number
  default     = 2
  description = "OCPU count for the backup instance"
}

variable "memory_in_gbs" {
  type        = number
  default     = 4
  description = "Memory in GBs for the backup instance"
}

variable "boot_volume_size_in_gbs" {
  type        = number
  default     = 50
  description = "Boot volume size in GBs"
}

variable "block_volume_size_in_gbs" {
  type        = number
  default     = 200
  description = "Backup staging block volume size in GBs"
}

variable "display_name" {
  type        = string
  default     = "aviation-dms-backup"
  description = "Display name for the compute instance"
}

variable "backend_vcn_cidr" {
  type        = string
  default     = "172.31.254.0/24"
  description = "Backend VCN CIDR for inbound scanner/validator access"
}

variable "off_host_storage_cidr" {
  type        = string
  description = "Approved off-host storage endpoint CIDR (outbound)"
}

# ---------------------------------------------------------------------------
# Network Security Group
# ---------------------------------------------------------------------------

resource "oci_core_network_security_group" "backup_nsg" {
  compartment_id = var.compartment_ocid
  display_name   = "nsg-aviation-dms-backup"
  vcn_id         = var.vcn_id

  # Inbound: backend subnet to clamd (3310) and validator (9100)
  security_rule {
    direction          = "INGRESS"
    protocol           = "6"
    source             = var.backend_vcn_cidr
    source_type        = "CIDR"
    stateless          = false
    description        = "Backend to ClamAV INSTREAM"
    destination_port_range {
      min = 3310
      max = 3310
    }
  }

  security_rule {
    direction          = "INGRESS"
    protocol           = "6"
    source             = var.backend_vcn_cidr
    source_type        = "CIDR"
    stateless          = false
    description        = "Backend to upload validator"
    destination_port_range {
      min = 9100
      max = 9100
    }
  }

  # Outbound: to approved off-host storage endpoint (HTTPS)
  security_rule {
    direction          = "EGRESS"
    protocol           = "6"
    destination        = var.off_host_storage_cidr
    destination_type   = "CIDR"
    stateless          = false
    description        = "Outbound to off-host storage (HTTPS)"
    destination_port_range {
      min = 443
      max = 443
    }
  }

  # Outbound: OCI services (Object Storage, KMS) over HTTPS
  security_rule {
    direction          = "EGRESS"
    protocol           = "6"
    destination        = "0.0.0.0/0"
    destination_type   = "CIDR"
    stateless          = false
    description        = "Outbound to OCI services (HTTPS)"
    destination_port_range {
      min = 443
      max = 443
    }
  }

  # Outbound: DNS
  security_rule {
    direction          = "EGRESS"
    protocol           = "17"
    destination        = "0.0.0.0/0"
    destination_type   = "CIDR"
    stateless          = true
    description        = "Outbound DNS (UDP 53)"
    destination_port_range {
      min = 53
      max = 53
    }
  }

  tags = {
    "CreatedBy" = "terraform"
    "Purpose"   = "aviation-dms-backup"
  }
}

# ---------------------------------------------------------------------------
# Compute Instance
# ---------------------------------------------------------------------------

resource "oci_core_instance" "backup" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = var.display_name
  shape               = var.instance_shape

  metadata = {
    "ssh_authorized_keys" = ""
  }

  shape_config {
    ocpus        = var.ocpus
    memory_in_gbs = var.memory_in_gbs
    networking_bandwidth_in_gbps = 1.0  # baseline; adjust as needed
  }

  source_details {
    source_type  = "image"
    source_id    = var.boot_image_id
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
    kms_key_id   = var.kms_key_id
  }

  # Primary VNIC: private only, no public IP
  create_vnic_details {
    subnet_id         = var.subnet_id
    assign_public_ip  = false
    skip_source_dest_check = false
    display_name      = "${var.display_name}-vnic"
    nsg_ids           = [oci_core_network_security_group.backup_nsg.id]
    hostname_label    = "aviation-dms-backup"
  }

  tags = {
    "CreatedBy" = "terraform"
    "Purpose"   = "aviation-dms-backup"
  }
}

# ---------------------------------------------------------------------------
# Block Volume (backup staging)
# ---------------------------------------------------------------------------

resource "oci_core_volume" "backup_staging" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "${var.display_name}-block-volume"
  size_in_gbs         = var.block_volume_size_in_gbs
  kms_key_id          = var.kms_key_id
  vpus_per_gb         = 10  # balanced performance; adjust for restore throughput

  tags = {
    "CreatedBy" = "terraform"
    "Purpose"   = "aviation-dms-backup-storage"
  }
}

# ---------------------------------------------------------------------------
# Volume Attachment
# ---------------------------------------------------------------------------

resource "oci_core_volume_attachment" "backup_staging_attachment" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  instance_id         = oci_core_instance.backup.id
  volume_id           = oci_core_volume.backup_staging.id
  type                = "iscsi"

  # The instance must run the iscsiadm service to mount this volume
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "instance_id" {
  value       = oci_core_instance.backup.id
  description = "OCID of the backup compute instance"
}

output "instance_private_ip" {
  value       = oci_core_instance.backup.primary_private_ip
  description = "Private IP of the backup instance"
}

output "volume_id" {
  value       = oci_core_volume.backup_staging.id
  description = "OCID of the backup staging block volume"
}

output "nsg_id" {
  value       = oci_core_network_security_group.backup_nsg.id
  description = "OCID of the network security group"
}

output "backup_volume_attachment_id" {
  value       = oci_core_volume_attachment.backup_staging_attachment.id
  description = "OCID of the block volume attachment"
}
