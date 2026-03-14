variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "symphony"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "retention_in_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# --- Alarms & Dashboard configuration ---

variable "enable_alarms" {
  description = "Enable CloudWatch alarms and SNS notifications"
  type        = bool
  default     = false
}

variable "enable_dashboard" {
  description = "Enable CloudWatch dashboard"
  type        = bool
  default     = false
}

variable "sns_email_endpoints" {
  description = "Email addresses for alarm notifications"
  type        = list(string)
  default     = []
}

variable "sns_slack_webhook_url" {
  description = "Slack webhook URL for alarm notifications (via Lambda or Chatbot)"
  type        = string
  default     = ""
}

# Alarm resource identifiers (passed from other modules)

variable "ecs_cluster_name" {
  description = "ECS cluster name for metric dimensions"
  type        = string
  default     = ""
}

variable "ecs_service_name" {
  description = "ECS service name for metric dimensions"
  type        = string
  default     = ""
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix for metric dimensions"
  type        = string
  default     = ""
}

variable "target_group_arn_suffix" {
  description = "Target group ARN suffix for metric dimensions"
  type        = string
  default     = ""
}

variable "rds_instance_id" {
  description = "RDS instance identifier for metric dimensions"
  type        = string
  default     = ""
}

variable "redis_cluster_id" {
  description = "ElastiCache Redis cluster ID for metric dimensions"
  type        = string
  default     = ""
}

# Alarm thresholds

variable "alarm_cpu_threshold" {
  description = "ECS CPU utilization alarm threshold (percent)"
  type        = number
  default     = 80
}

variable "alarm_memory_threshold" {
  description = "ECS memory utilization alarm threshold (percent)"
  type        = number
  default     = 80
}

variable "alarm_alb_5xx_threshold" {
  description = "ALB 5xx error count alarm threshold (per period)"
  type        = number
  default     = 50
}

variable "alarm_alb_latency_threshold" {
  description = "ALB target response time alarm threshold (seconds)"
  type        = number
  default     = 2.0
}

variable "alarm_rds_connections_threshold" {
  description = "RDS database connections alarm threshold"
  type        = number
  default     = 80
}

variable "alarm_rds_cpu_threshold" {
  description = "RDS CPU utilization alarm threshold (percent)"
  type        = number
  default     = 80
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
