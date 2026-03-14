output "database_password_secret_arn" {
  description = "ARN of the database password secret"
  value       = aws_secretsmanager_secret.database_password.arn
}

output "database_password_secret_name" {
  description = "Name of the database password secret"
  value       = aws_secretsmanager_secret.database_password.name
}

output "database_url_secret_arn" {
  description = "ARN of the database URL secret"
  value       = aws_secretsmanager_secret.database_url.arn
}

output "database_url_secret_name" {
  description = "Name of the database URL secret"
  value       = aws_secretsmanager_secret.database_url.name
}

output "redis_auth_token_secret_arn" {
  description = "ARN of the Redis auth token secret"
  value       = aws_secretsmanager_secret.redis_auth_token.arn
}

output "redis_auth_token_secret_name" {
  description = "Name of the Redis auth token secret"
  value       = aws_secretsmanager_secret.redis_auth_token.name
}

output "anthropic_api_key_secret_arn" {
  description = "ARN of the Anthropic API key secret"
  value       = aws_secretsmanager_secret.anthropic_api_key.arn
}

output "anthropic_api_key_secret_name" {
  description = "Name of the Anthropic API key secret"
  value       = aws_secretsmanager_secret.anthropic_api_key.name
}

output "langsmith_api_key_secret_arn" {
  description = "ARN of the LangSmith API key secret"
  value       = aws_secretsmanager_secret.langsmith_api_key.arn
}

output "langsmith_api_key_secret_name" {
  description = "Name of the LangSmith API key secret"
  value       = aws_secretsmanager_secret.langsmith_api_key.name
}

output "app_secret_key_secret_arn" {
  description = "ARN of the application secret key secret"
  value       = aws_secretsmanager_secret.app_secret_key.arn
}

output "app_secret_key_secret_name" {
  description = "Name of the application secret key secret"
  value       = aws_secretsmanager_secret.app_secret_key.name
}
