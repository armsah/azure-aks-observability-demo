variable "location" {
  type        = string
  description = "Azure region."
  default     = "westeurope"
}

variable "project_name" {
  type        = string
  description = "Short project name."
  default     = "azmon-demo"
}

variable "kubernetes_version" {
  type        = string
  description = "Optional AKS Kubernetes version. Leave null for the default supported version."
  default     = null
}
