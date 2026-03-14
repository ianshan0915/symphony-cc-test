###############################################################################
# Production Environment Outputs
###############################################################################

# Networking
output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}

output "data_subnet_ids" {
  description = "Data subnet IDs"
  value       = module.networking.data_subnet_ids
}

output "nat_gateway_ips" {
  description = "NAT Gateway public IPs (HA — one per AZ)"
  value       = module.networking.nat_gateway_ips
}

# Compute
output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.compute.ecs_cluster_name
}

output "alb_dns_name" {
  description = "ALB DNS name — use for CNAME/alias to production URL"
  value       = module.compute.alb_dns_name
}

output "alb_zone_id" {
  description = "ALB zone ID for Route53 alias records"
  value       = module.compute.alb_zone_id
}

# Data
output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.data.rds_endpoint
}

output "rds_master_user_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the RDS master password"
  value       = module.data.rds_master_user_secret_arn
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = module.data.redis_endpoint
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = module.data.redis_connection_string
}

# ECR
output "ecr_repository_urls" {
  description = "ECR repository URLs"
  value       = module.ecr.repository_urls
}

# Monitoring
output "ecs_backend_log_group" {
  description = "CloudWatch log group for ECS backend"
  value       = module.monitoring.ecs_backend_log_group_name
}

output "ecs_frontend_log_group" {
  description = "CloudWatch log group for ECS frontend"
  value       = module.monitoring.ecs_frontend_log_group_name
}

output "sns_alarms_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = module.monitoring.sns_topic_arn
}

output "cloudwatch_dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = module.monitoring.dashboard_name
}

# WAF
output "waf_web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = aws_wafv2_web_acl.main.arn
}
