# Variable definitions for Aviation DMS backup/restore on OCI
#
# Copy terraform.tfvars.example to terraform.tfvals and fill in your values.
# Never commit terraform.tfvars.

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

variable "boot_image_id" {
  type        = string
  description = "Boot image OCID (Oracle Linux 9 or similar)"
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
