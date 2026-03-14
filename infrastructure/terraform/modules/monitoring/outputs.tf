output "ecs_backend_log_group_name" {
  description = "CloudWatch log group name for ECS backend"
  value       = aws_cloudwatch_log_group.ecs_backend.name
}

output "ecs_backend_log_group_arn" {
  description = "CloudWatch log group ARN for ECS backend"
  value       = aws_cloudwatch_log_group.ecs_backend.arn
}

output "ecs_frontend_log_group_name" {
  description = "CloudWatch log group name for ECS frontend"
  value       = aws_cloudwatch_log_group.ecs_frontend.name
}

output "ecs_frontend_log_group_arn" {
  description = "CloudWatch log group ARN for ECS frontend"
  value       = aws_cloudwatch_log_group.ecs_frontend.arn
}

output "application_log_group_name" {
  description = "CloudWatch log group name for application logs"
  value       = aws_cloudwatch_log_group.application.name
}

output "rds_log_group_name" {
  description = "CloudWatch log group name for RDS"
  value       = aws_cloudwatch_log_group.rds.name
}

output "redis_log_group_name" {
  description = "CloudWatch log group name for Redis"
  value       = aws_cloudwatch_log_group.redis.name
}

output "alb_log_group_name" {
  description = "CloudWatch log group name for ALB"
  value       = aws_cloudwatch_log_group.alb.name
}

output "sns_topic_arn" {
  description = "ARN of the alarms SNS topic (empty if alarms disabled)"
  value       = var.enable_alarms ? aws_sns_topic.alarms[0].arn : ""
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard (empty if dashboard disabled)"
  value       = var.enable_dashboard ? aws_cloudwatch_dashboard.main[0].dashboard_name : ""
}
