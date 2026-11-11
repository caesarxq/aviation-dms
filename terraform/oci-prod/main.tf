# ============================================================================
# Terraform configuration for Aviation DMS Production App Instance on OCI
# ============================================================================
# Provisions:
#   - Compute instance (private, no public IP) for backend/frontend/validator/clamd
#   - Encrypted boot volume (100 GiB)
#   - Network Security Group with restricted inbound/outbound rules
#   - Outputs for bastion Caddy configuration
#
# The instance is reached via bastion (145.241.152.126) which proxies
# HTTPS traffic from roc.kfl.ke to the production backend.
# ============================================================================

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
  description = "Compartment OCID for production app instance resources"
}

variable "availability_domain" {
  type        = string
  description = "Availability Domain for the production app instance"
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

variable "boot_image_id" {
  type        = string
  description = "Boot image OCID (Oracle Linux 9 or similar)"
}

variable "instance_shape" {
  type        = string
  default     = "VM.Standard.E4.Flex"
  description = "Compute shape for production app instance"
}

variable "ocpus" {
  type        = number
  default     = 4
  description = "OCPU count for the production app instance"
}

variable "memory_in_gbs" {
  type        = number
  default     = 8
  description = "Memory in GBs for the production app instance"
}

variable "boot_volume_size_in_gbs" {
  type        = number
  default     = 100
  description = "Boot volume size in GBs"
}

variable "display_name" {
  type        = string
  default     = "aviation-dms-prod"
  description = "Display name for the production compute instance"
}

variable "bastion_ip" {
  type        = string
  description = "Bastion public IP (for SSH access and Caddy proxy source)"
}

variable "backend_vcn_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "Production VCN CIDR"
}

# ---------------------------------------------------------------------------
# Network Security Group
# ---------------------------------------------------------------------------

resource "oci_core_network_security_group" "prod_nsg" {
  compartment_id = var.compartment_ocid
  display_name   = "nsg-aviation-dms-prod"
  vcn_id         = var.vcn_id

  # Inbound: bastion to backend (8000) and frontend (8080)
  security_rule {
    direction          = "INGRESS"
    protocol           = "6"
    source             = var.bastion_ip
    source_type        = "CIDR"
    stateless          = false
    description        = "Bastion to backend API (8000)"
    destination_port_range {
      min = 8000
      max = 8000
    }
  }

  security_rule {
    direction          = "INGRESS"
    protocol           = "6"
    source             = var.bastion_ip
    source_type        = "CIDR"
    stateless          = false
    description        = "Bastion to frontend (8080)"
    destination_port_range {
      min = 8080
      max = 8080
    }
  }

  # Inbound: bastion SSH (22)
  security_rule {
    direction          = "INGRESS"
    protocol           = "6"
    source             = var.bastion_ip
    source_type        = "CIDR"
    stateless          = false
    description        = "Bastion SSH (22)"
    destination_port_range {
      min = 22
      max = 22
    }
  }

  # Inbound: clamd (3310) from backend only (same instance, loopback)
  security_rule {
    direction          = "INGRESS"
    protocol           = "6"
    source             = var.backend_vcn_cidr
    source_type        = "CIDR"
    stateless          = false
    description        = "Internal clamd access (3310)"
    destination_port_range {
      min = 3310
      max = 3310
    }
  }

  # Inbound: upload-validator (9100) from backend only
  security_rule {
    direction          = "INGRESS"
    protocol           = "6"
    source             = var.backend_vcn_cidr
    source_type        = "CIDR"
    stateless          = false
    description        = "Internal upload-validator access (9100)"
    destination_port_range {
      min = 9100
      max = 9100
    }
  }

  # Outbound: HTTPS to OCI services and external
  security_rule {
    direction          = "EGRESS"
    protocol           = "6"
    destination        = "0.0.0.0/0"
    destination_type   = "CIDR"
    stateless          = false
    description        = "Outbound HTTPS (443)"
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
    "Purpose"   = "aviation-dms-production"
  }
}

# ---------------------------------------------------------------------------
# Compute Instance
# ---------------------------------------------------------------------------

resource "oci_core_instance" "prod_app" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = var.display_name
  shape               = var.instance_shape

  metadata = {
    "ssh_authorized_keys" = ""
  }

  shape_config {
    ocpus                 = var.ocpus
    memory_in_gbs         = var.memory_in_gbs
    networking_bandwidth_in_gbps = 1.0
  }

  source_details {
    source_type  = "image"
    source_id    = var.boot_image_id
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
    kms_key_id   = var.kms_key_id
  }

  # Primary VNIC: private only, no public IP
  create_vnic_details {
    subnet_id                 = var.subnet_id
    assign_public_ip          = false
    skip_source_dest_check    = false
    display_name              = "${var.display_name}-vnic"
    nsg_ids                   = [oci_core_network_security_group.prod_nsg.id]
    hostname_label            = "aviation-dms-prod"
  }

  tags = {
    "CreatedBy" = "terraform"
    "Purpose"   = "aviation-dms-production"
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "instance_id" {
  value       = oci_core_instance.prod_app.id
  description = "OCID of the production app compute instance"
}

output "instance_private_ip" {
  value       = oci_core_instance.prod_app.primary_private_ip
  description = "Private IP of the production app instance"
}

output "nsg_id" {
  value       = oci_core_network_security_group.prod_nsg.id
  description = "OCID of the production network security group"
}

output "bastion_ip" {
  value       = var.bastion_ip
  description = "Bastion public IP for Caddy proxy configuration"
}
