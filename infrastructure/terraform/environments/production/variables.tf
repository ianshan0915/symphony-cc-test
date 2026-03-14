variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name"
  type        = string
  default     = "symphony"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

# Networking
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.2.0.0/16"
}

variable "app_port" {
  description = "Application port for ECS tasks"
  type        = number
  default     = 8000
}

# Compute
variable "app_image" {
  description = "Docker image URI for the backend application"
  type        = string
}

variable "app_cpu" {
  description = "CPU units for the ECS task (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "app_memory" {
  description = "Memory in MiB for the ECS task"
  type        = number
  default     = 2048
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 3
}

variable "certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS"
  type        = string
  default     = ""
}

# Data — RDS
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.large"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB for RDS"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage in GB for RDS autoscaling"
  type        = number
  default     = 500
}

# Data — Redis
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.r6g.large"
}

# Monitoring
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 90
}

variable "sns_email_endpoints" {
  description = "Email addresses for alarm notifications"
  type        = list(string)
  default     = []
}

variable "sns_slack_webhook_url" {
  description = "Slack webhook URL for alarm notifications"
  type        = string
  default     = ""
}

# WAF
variable "waf_rate_limit" {
  description = "Maximum requests per 5-minute period per IP before WAF blocks"
  type        = number
  default     = 2000
}

variable "waf_ip_blocklist" {
  description = "CIDR blocks to block via WAF"
  type        = list(string)
  default     = []
}
