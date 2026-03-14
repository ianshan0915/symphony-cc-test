###############################################################################
# Production Environment
# - Production-grade sizing (Multi-AZ RDS, HA NAT, larger instances)
# - WAF protection on ALB (OWASP rules, rate limiting, IP filtering)
# - CloudWatch dashboards and alarms with SNS notifications
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  # Uncomment after running bootstrap.sh
  # backend "s3" {
  #   bucket         = "symphony-terraform-state-ACCOUNT_ID"
  #   key            = "production/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "symphony-terraform-locks"
  #   encrypt        = true
  # }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  common_tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# ------------------------------------------------------------------
# Monitoring (created first so log groups exist before compute)
# ------------------------------------------------------------------

module "monitoring" {
  source = "../../modules/monitoring"

  project           = var.project
  environment       = var.environment
  retention_in_days = var.log_retention_days

  # Enable dashboards and alarms for production
  enable_alarms    = true
  enable_dashboard = true

  sns_email_endpoints   = var.sns_email_endpoints
  sns_slack_webhook_url = var.sns_slack_webhook_url

  # Resource identifiers for metrics (populated after compute/data modules)
  ecs_cluster_name        = module.compute.ecs_cluster_name
  ecs_service_name        = module.compute.backend_service_name
  alb_arn_suffix          = module.compute.alb_arn_suffix
  target_group_arn_suffix = module.compute.backend_target_group_arn_suffix
  rds_instance_id         = module.data.rds_instance_id
  redis_cluster_id        = module.data.redis_cluster_id

  # Alarm thresholds — production-appropriate
  alarm_cpu_threshold             = 80
  alarm_memory_threshold          = 80
  alarm_alb_5xx_threshold         = 50
  alarm_alb_latency_threshold     = 2.0
  alarm_rds_connections_threshold = 80
  alarm_rds_cpu_threshold         = 80

  tags = local.common_tags
}

# ------------------------------------------------------------------
# Networking (HA NAT for production)
# ------------------------------------------------------------------

module "networking" {
  source = "../../modules/networking"

  project       = var.project
  environment   = var.environment
  vpc_cidr      = var.vpc_cidr
  app_port      = var.app_port
  enable_ha_nat = true

  tags = local.common_tags
}

# ------------------------------------------------------------------
# ECR
# ------------------------------------------------------------------

module "ecr" {
  source = "../../modules/ecr"

  project          = var.project
  repository_names = ["backend", "frontend"]
  force_delete     = false

  tags = local.common_tags
}

# ------------------------------------------------------------------
# Data (RDS Multi-AZ + Redis)
# ------------------------------------------------------------------

module "data" {
  source = "../../modules/data"

  project     = var.project
  environment = var.environment

  vpc_id             = module.networking.vpc_id
  data_subnet_ids    = module.networking.data_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids

  rds_security_group_id   = module.networking.rds_security_group_id
  redis_security_group_id = module.networking.redis_security_group_id

  # RDS — production-grade sizing
  db_instance_class          = var.db_instance_class
  db_allocated_storage       = var.db_allocated_storage
  db_max_allocated_storage   = var.db_max_allocated_storage
  db_multi_az                = true
  db_deletion_protection     = true
  db_skip_final_snapshot     = false
  db_backup_retention_period = 30

  # Redis — production-grade sizing
  redis_node_type = var.redis_node_type

  tags = local.common_tags
}

# ------------------------------------------------------------------
# Compute (ECS + ALB)
# ------------------------------------------------------------------

module "compute" {
  source = "../../modules/compute"

  project     = var.project
  environment = var.environment

  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids

  alb_security_group_id = module.networking.alb_security_group_id
  ecs_security_group_id = module.networking.ecs_security_group_id

  app_port      = var.app_port
  app_image     = var.app_image
  app_cpu       = var.app_cpu
  app_memory    = var.app_memory
  desired_count = var.desired_count

  certificate_arn = var.certificate_arn
  log_group_name  = module.monitoring.ecs_backend_log_group_name

  tags = local.common_tags
}

# ------------------------------------------------------------------
# WAF (attached to ALB via dedicated ALB module)
# Note: WAF is created as a standalone resource associated with the
# compute module's ALB since production uses the compute module.
# ------------------------------------------------------------------

resource "aws_wafv2_ip_set" "blocklist" {
  count              = length(var.waf_ip_blocklist) > 0 ? 1 : 0
  name               = "${var.project}-${var.environment}-ip-blocklist"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"
  addresses          = var.waf_ip_blocklist

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-ip-blocklist"
  })
}

resource "aws_wafv2_web_acl" "main" {
  name        = "${var.project}-${var.environment}-waf"
  scope       = "REGIONAL"
  description = "WAF for ${var.project} production ALB — OWASP rules, rate limiting, IP filtering"

  default_action {
    allow {}
  }

  # ---- OWASP Core Rule Set (CRS) ----
  rule {
    name     = "aws-managed-common-rules"
    priority = 10

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  # ---- Known Bad Inputs ----
  rule {
    name     = "aws-managed-known-bad-inputs"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # ---- SQL Injection Protection ----
  rule {
    name     = "aws-managed-sql-injection"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-sqli-rules"
      sampled_requests_enabled   = true
    }
  }

  # ---- Linux OS Protection ----
  rule {
    name     = "aws-managed-linux-rules"
    priority = 40

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesLinuxRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-linux-rules"
      sampled_requests_enabled   = true
    }
  }

  # ---- Rate Limiting ----
  rule {
    name     = "rate-limit"
    priority = 50

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-${var.environment}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  # ---- IP Blocklist ----
  dynamic "rule" {
    for_each = length(var.waf_ip_blocklist) > 0 ? [1] : []
    content {
      name     = "ip-blocklist"
      priority = 5

      action {
        block {}
      }

      statement {
        ip_set_reference_statement {
          arn = aws_wafv2_ip_set.blocklist[0].arn
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${var.project}-${var.environment}-ip-blocklist"
        sampled_requests_enabled   = true
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project}-${var.environment}-waf"
    sampled_requests_enabled   = true
  }

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-waf"
  })
}

resource "aws_wafv2_web_acl_association" "main" {
  resource_arn = module.compute.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}
