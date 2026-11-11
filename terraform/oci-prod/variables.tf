# Variable definitions for Aviation DMS production app instance on OCI
#
# Copy terraform.tfvars.example to terraform.tfvars and fill in your values.
# Never commit terraform.tfvars.

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
