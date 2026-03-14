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
