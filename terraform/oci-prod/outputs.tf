# Outputs for production app instance

output "instance_id" {
  value       = oci_core_instance.prod_app.id
  description = "OCID of the production app compute instance"
}

output "instance_private_ip" {
  value       = oci_core_instance.prod_app.primary_private_ip
  description = "Private IP of the production app instance — configure bastion Caddy to proxy to this IP:8000/:8080"
}

output "nsg_id" {
  value       = oci_core_network_security_group.prod_nsg.id
  description = "OCID of the production network security group"
}

output "bastion_ip" {
  value       = var.bastion_ip
  description = "Bastion public IP for Caddy proxy configuration"
}
