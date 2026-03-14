###############################################################################
# Secrets Module
# - AWS Secrets Manager resources for database, redis, anthropic, langsmith,
#   and application secrets
# - Naming convention: symphony/<env>/*
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ------------------------------------------------------------------
# Database Secret (password for RDS)
# ------------------------------------------------------------------

resource "aws_secretsmanager_secret" "database_password" {
  name                    = "${var.project}/${var.environment}/database/password"
  description             = "PostgreSQL master password for ${var.project} ${var.environment}"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, {
    Name      = "${var.project}-${var.environment}-db-password"
    Component = "database"
  })
}

resource "aws_secretsmanager_secret_version" "database_password" {
  secret_id     = aws_secretsmanager_secret.database_password.id
  secret_string = random_password.database.result
}

resource "random_password" "database" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}|:,.<>?"
}

# ------------------------------------------------------------------
# Database URL Secret (full connection string, set after RDS creation)
# ------------------------------------------------------------------

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.project}/${var.environment}/database/url"
  description             = "PostgreSQL connection URL for ${var.project} ${var.environment}"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, {
    Name      = "${var.project}-${var.environment}-db-url"
    Component = "database"
  })
}

# ------------------------------------------------------------------
# Redis Auth Token Secret
# ------------------------------------------------------------------

resource "aws_secretsmanager_secret" "redis_auth_token" {
  name                    = "${var.project}/${var.environment}/redis/auth-token"
  description             = "Redis auth token for ${var.project} ${var.environment}"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, {
    Name      = "${var.project}-${var.environment}-redis-auth"
    Component = "redis"
  })
}

resource "aws_secretsmanager_secret_version" "redis_auth_token" {
  secret_id     = aws_secretsmanager_secret.redis_auth_token.id
  secret_string = random_password.redis.result
}

resource "random_password" "redis" {
  length           = 64
  special          = true
  override_special = "!#$%&*()-_=+[]{}|:,.<>?"
}

# ------------------------------------------------------------------
# Anthropic API Key Secret
# ------------------------------------------------------------------

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name                    = "${var.project}/${var.environment}/anthropic/api-key"
  description             = "Anthropic API key for ${var.project} ${var.environment}"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, {
    Name      = "${var.project}-${var.environment}-anthropic-api-key"
    Component = "anthropic"
  })
}

# ------------------------------------------------------------------
# LangSmith API Key Secret
# ------------------------------------------------------------------

resource "aws_secretsmanager_secret" "langsmith_api_key" {
  name                    = "${var.project}/${var.environment}/langsmith/api-key"
  description             = "LangSmith API key for ${var.project} ${var.environment}"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, {
    Name      = "${var.project}-${var.environment}-langsmith-api-key"
    Component = "langsmith"
  })
}

# ------------------------------------------------------------------
# Application Secret Key
# ------------------------------------------------------------------

resource "aws_secretsmanager_secret" "app_secret_key" {
  name                    = "${var.project}/${var.environment}/app/secret-key"
  description             = "Application secret key for ${var.project} ${var.environment}"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, {
    Name      = "${var.project}-${var.environment}-app-secret-key"
    Component = "app"
  })
}

resource "aws_secretsmanager_secret_version" "app_secret_key" {
  secret_id     = aws_secretsmanager_secret.app_secret_key.id
  secret_string = random_password.app_secret.result
}

resource "random_password" "app_secret" {
  length  = 64
  special = true
}
