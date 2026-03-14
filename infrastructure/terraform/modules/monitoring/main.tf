###############################################################################
# Monitoring Module
# - CloudWatch Log Groups for ECS, RDS, Redis, ALB, and application logs
# - SNS topic for alarm notifications
# - CloudWatch Dashboard: ECS, ALB, RDS, Redis key metrics
# - CloudWatch Alarms: CPU, memory, latency, errors, DB connections
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

# ------------------------------------------------------------------
# SNS Topic for Alarm Notifications
# ------------------------------------------------------------------

resource "aws_sns_topic" "alarms" {
  count = var.enable_alarms ? 1 : 0
  name  = "${local.name_prefix}-alarms"

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-alarms"
  })
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.enable_alarms ? length(var.sns_email_endpoints) : 0
  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.sns_email_endpoints[count.index]
}

resource "aws_sns_topic_subscription" "https_slack" {
  count     = var.enable_alarms && var.sns_slack_webhook_url != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "https"
  endpoint  = var.sns_slack_webhook_url
}

# ------------------------------------------------------------------
# CloudWatch Dashboard
# ------------------------------------------------------------------

resource "aws_cloudwatch_dashboard" "main" {
  count          = var.enable_dashboard ? 1 : 0
  dashboard_name = "${local.name_prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # ---- Row 1: ECS Metrics ----
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ECS CPU Utilization"
          metrics = [["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name]]
          period  = 300
          stat    = "Average"
          region  = "us-east-1"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ECS Memory Utilization"
          metrics = [["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name]]
          period  = 300
          stat    = "Average"
          region  = "us-east-1"
          view    = "timeSeries"
        }
      },
      # ---- Row 2: ALB Metrics ----
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6
        properties = {
          title   = "ALB Target Response Time"
          metrics = [["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix]]
          period  = 60
          stat    = "Average"
          region  = "us-east-1"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6
        properties = {
          title   = "ALB Request Count"
          metrics = [["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix]]
          period  = 60
          stat    = "Sum"
          region  = "us-east-1"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 6
        properties = {
          title = "ALB HTTP 5xx Errors"
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", var.alb_arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix]
          ]
          period = 60
          stat   = "Sum"
          region = "us-east-1"
          view   = "timeSeries"
        }
      },
      # ---- Row 3: RDS Metrics ----
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 8
        height = 6
        properties = {
          title   = "RDS CPU Utilization"
          metrics = [["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_instance_id]]
          period  = 300
          stat    = "Average"
          region  = "us-east-1"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 12
        width  = 8
        height = 6
        properties = {
          title   = "RDS Database Connections"
          metrics = [["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.rds_instance_id]]
          period  = 300
          stat    = "Average"
          region  = "us-east-1"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 12
        width  = 8
        height = 6
        properties = {
          title = "RDS Read/Write IOPS"
          metrics = [
            ["AWS/RDS", "ReadIOPS", "DBInstanceIdentifier", var.rds_instance_id],
            ["AWS/RDS", "WriteIOPS", "DBInstanceIdentifier", var.rds_instance_id]
          ]
          period = 300
          stat   = "Average"
          region = "us-east-1"
          view   = "timeSeries"
        }
      },
      # ---- Row 4: Redis Metrics ----
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 8
        height = 6
        properties = {
          title   = "Redis CPU Utilization"
          metrics = [["AWS/ElastiCache", "CPUUtilization", "CacheClusterId", var.redis_cluster_id]]
          period  = 300
          stat    = "Average"
          region  = "us-east-1"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 18
        width  = 8
        height = 6
        properties = {
          title = "Redis Cache Hit Rate"
          metrics = [
            ["AWS/ElastiCache", "CacheHits", "CacheClusterId", var.redis_cluster_id],
            ["AWS/ElastiCache", "CacheMisses", "CacheClusterId", var.redis_cluster_id]
          ]
          period = 300
          stat   = "Sum"
          region = "us-east-1"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 18
        width  = 8
        height = 6
        properties = {
          title   = "Redis Current Connections"
          metrics = [["AWS/ElastiCache", "CurrConnections", "CacheClusterId", var.redis_cluster_id]]
          period  = 300
          stat    = "Average"
          region  = "us-east-1"
          view    = "timeSeries"
        }
      }
    ]
  })
}

# ------------------------------------------------------------------
# CloudWatch Alarms
# ------------------------------------------------------------------

# ECS CPU Utilization
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name_prefix}-ecs-cpu-high"
  alarm_description   = "ECS CPU utilization exceeds ${var.alarm_cpu_threshold}%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = var.alarm_cpu_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  alarm_actions = [aws_sns_topic.alarms[0].arn]
  ok_actions    = [aws_sns_topic.alarms[0].arn]

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-ecs-cpu-high"
  })
}

# ECS Memory Utilization
resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name_prefix}-ecs-memory-high"
  alarm_description   = "ECS memory utilization exceeds ${var.alarm_memory_threshold}%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = var.alarm_memory_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  alarm_actions = [aws_sns_topic.alarms[0].arn]
  ok_actions    = [aws_sns_topic.alarms[0].arn]

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-ecs-memory-high"
  })
}

# ALB 5xx Errors
resource "aws_cloudwatch_metric_alarm" "alb_5xx_high" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name_prefix}-alb-5xx-high"
  alarm_description   = "ALB 5xx error count exceeds ${var.alarm_alb_5xx_threshold}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_ELB_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = var.alarm_alb_5xx_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms[0].arn]
  ok_actions    = [aws_sns_topic.alarms[0].arn]

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-alb-5xx-high"
  })
}

# ALB Target Response Time (Latency)
resource "aws_cloudwatch_metric_alarm" "alb_latency_high" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name_prefix}-alb-latency-high"
  alarm_description   = "ALB target response time exceeds ${var.alarm_alb_latency_threshold}s"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = var.alarm_alb_latency_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms[0].arn]
  ok_actions    = [aws_sns_topic.alarms[0].arn]

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-alb-latency-high"
  })
}

# RDS CPU Utilization
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name_prefix}-rds-cpu-high"
  alarm_description   = "RDS CPU utilization exceeds ${var.alarm_rds_cpu_threshold}%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = var.alarm_rds_cpu_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }

  alarm_actions = [aws_sns_topic.alarms[0].arn]
  ok_actions    = [aws_sns_topic.alarms[0].arn]

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-rds-cpu-high"
  })
}

# RDS Database Connections
resource "aws_cloudwatch_metric_alarm" "rds_connections_high" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name_prefix}-rds-connections-high"
  alarm_description   = "RDS database connections exceed ${var.alarm_rds_connections_threshold}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = var.alarm_rds_connections_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }

  alarm_actions = [aws_sns_topic.alarms[0].arn]
  ok_actions    = [aws_sns_topic.alarms[0].arn]

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-rds-connections-high"
  })
}

# RDS Free Storage Space Low
resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name_prefix}-rds-storage-low"
  alarm_description   = "RDS free storage space is below 5 GB"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120 # 5 GB in bytes
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }

  alarm_actions = [aws_sns_topic.alarms[0].arn]
  ok_actions    = [aws_sns_topic.alarms[0].arn]

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-rds-storage-low"
  })
}
