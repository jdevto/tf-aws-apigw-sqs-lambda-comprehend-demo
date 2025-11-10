locals {
  common_tags = {
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Environment = var.environment
  }

  # Naming conventions
  name_prefix = "${var.project_name}-${var.environment}"
}
