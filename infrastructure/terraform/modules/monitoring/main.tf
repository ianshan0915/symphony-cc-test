###############################################################################
# Monitoring Module
# - CloudWatch Log Groups for ECS, RDS, Redis, ALB, and application logs
# - Dashboards and alarms to be added in Sprint 5
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

locals {
  name_prefix = "${var.project}-${var.environment}"
}

# ------------------------------------------------------------------
# CloudWatch Log Groups
# ------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "ecs_backend" {
  name              = "/ecs/${local.name_prefix}/backend"
  retention_in_days = var.retention_in_days

  tags = merge(var.tags, {
    Name    = "${local.name_prefix}-ecs-backend-logs"
    Service = "ecs"
  })
}

resource "aws_cloudwatch_log_group" "ecs_frontend" {
  name              = "/ecs/${local.name_prefix}/frontend"
  retention_in_days = var.retention_in_days

  tags = merge(var.tags, {
    Name    = "${local.name_prefix}-ecs-frontend-logs"
    Service = "ecs"
  })
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/app/${local.name_prefix}"
  retention_in_days = var.retention_in_days

  tags = merge(var.tags, {
    Name    = "${local.name_prefix}-app-logs"
    Service = "application"
  })
}

resource "aws_cloudwatch_log_group" "rds" {
  name              = "/rds/${local.name_prefix}"
  retention_in_days = var.retention_in_days

  tags = merge(var.tags, {
    Name    = "${local.name_prefix}-rds-logs"
    Service = "rds"
  })
}

resource "aws_cloudwatch_log_group" "redis" {
  name              = "/redis/${local.name_prefix}"
  retention_in_days = var.retention_in_days

  tags = merge(var.tags, {
    Name    = "${local.name_prefix}-redis-logs"
    Service = "redis"
  })
}

resource "aws_cloudwatch_log_group" "alb" {
  name              = "/alb/${local.name_prefix}"
  retention_in_days = var.retention_in_days

  tags = merge(var.tags, {
    Name    = "${local.name_prefix}-alb-logs"
    Service = "alb"
  })
}
