# Outputs for Aviation DMS backup/restore on OCI

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

output "backup_instance_summary" {
  value = {
    instance_id   = oci_core_instance.backup.id
    private_ip    = oci_core_instance.backup.primary_private_ip
    volume_id     = oci_core_volume.backup_staging.id
    nsg_id        = oci_core_network_security_group.backup_nsg.id
    attachment_id = oci_core_volume_attachment.backup_staging_attachment.id
  }
  description = "Summary of all backup infrastructure resources"
}
