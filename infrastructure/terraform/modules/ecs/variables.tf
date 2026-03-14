variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "symphony"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "private_subnet_ids" {
  description = "IDs of the private subnets for ECS tasks"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "ID of the ECS security group"
  type        = string
}

# --- Backend Task ---

variable "backend_image" {
  description = "Docker image URI for the backend container"
  type        = string
}

variable "backend_port" {
  description = "Port the backend container listens on"
  type        = number
  default     = 8000
}

variable "backend_cpu" {
  description = "CPU units for the backend task (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "backend_memory" {
  description = "Memory in MiB for the backend task"
  type        = number
  default     = 2048
}

variable "backend_desired_count" {
  description = "Desired number of backend tasks"
  type        = number
  default     = 2
}

variable "backend_min_count" {
  description = "Minimum number of backend tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "backend_max_count" {
  description = "Maximum number of backend tasks for auto-scaling"
  type        = number
  default     = 4
}

variable "backend_environment" {
  description = "Environment variables for the backend container"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "backend_secrets" {
  description = "Secrets for the backend container (valueFrom ARN)"
  type = list(object({
    name      = string
    valueFrom = string
  }))
  default = []
}

# --- Frontend Task ---

variable "frontend_image" {
  description = "Docker image URI for the frontend container"
  type        = string
}

variable "frontend_port" {
  description = "Port the frontend container listens on"
  type        = number
  default     = 3000
}

variable "frontend_cpu" {
  description = "CPU units for the frontend task (512 = 0.5 vCPU)"
  type        = number
  default     = 512
}

variable "frontend_memory" {
  description = "Memory in MiB for the frontend task"
  type        = number
  default     = 1024
}

variable "frontend_desired_count" {
  description = "Desired number of frontend tasks"
  type        = number
  default     = 2
}

variable "frontend_min_count" {
  description = "Minimum number of frontend tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "frontend_max_count" {
  description = "Maximum number of frontend tasks for auto-scaling"
  type        = number
  default     = 4
}

variable "frontend_environment" {
  description = "Environment variables for the frontend container"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "frontend_secrets" {
  description = "Secrets for the frontend container (valueFrom ARN)"
  type = list(object({
    name      = string
    valueFrom = string
  }))
  default = []
}

# --- Target Groups (from ALB module) ---

variable "backend_target_group_arn" {
  description = "ARN of the backend ALB target group"
  type        = string
}

variable "frontend_target_group_arn" {
  description = "ARN of the frontend ALB target group"
  type        = string
}

# --- Auto-Scaling ---

variable "scaling_cpu_threshold" {
  description = "CPU utilization percentage to trigger scaling"
  type        = number
  default     = 70
}

# --- Logging ---

variable "log_retention_days" {
  description = "CloudWatch log group retention in days"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
