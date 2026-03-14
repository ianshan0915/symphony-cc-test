variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "symphony"
}

variable "repository_names" {
  description = "List of ECR repository names to create"
  type        = list(string)
  default     = ["backend", "frontend"]
}

variable "force_delete" {
  description = "Allow force deletion of repositories (useful for dev/test)"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
