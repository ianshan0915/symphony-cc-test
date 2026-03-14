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

variable "public_subnet_ids" {
  description = "IDs of the public subnets for the ALB"
  type        = list(string)
}

variable "security_group_id" {
  description = "ID of the ALB security group"
  type        = string
}

variable "certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS"
  type        = string
}

variable "backend_port" {
  description = "Port the backend containers listen on"
  type        = number
  default     = 8000
}

variable "frontend_port" {
  description = "Port the frontend containers listen on"
  type        = number
  default     = 3000
}

variable "health_check_path_backend" {
  description = "Health check path for the backend target group"
  type        = string
  default     = "/api/health"
}

variable "health_check_path_frontend" {
  description = "Health check path for the frontend target group"
  type        = string
  default     = "/"
}

variable "idle_timeout" {
  description = "Idle timeout in seconds (300s recommended for SSE)"
  type        = number
  default     = 300
}

variable "stickiness_duration" {
  description = "Duration of ALB target group stickiness in seconds"
  type        = number
  default     = 86400
}

variable "enable_waf" {
  description = "Enable WAF v2 Web ACL on the ALB"
  type        = bool
  default     = false
}

variable "waf_rate_limit" {
  description = "Maximum number of requests per 5-minute period per IP"
  type        = number
  default     = 2000
}

variable "waf_ip_blocklist" {
  description = "List of CIDR blocks to block via WAF (e.g. ['1.2.3.4/32'])"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
