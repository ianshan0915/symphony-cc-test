###############################################################################
# ElastiCache Module
# - Redis 7 cluster
# - Configurable node type and count
# - Auth token from Secrets Manager, in-transit + at-rest encryption
# - Subnet group
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
# Fetch auth token from Secrets Manager
# ------------------------------------------------------------------

data "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id = var.auth_token_secret_arn
}

# ------------------------------------------------------------------
# Subnet Group
# ------------------------------------------------------------------

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project}-${var.environment}-redis-subnet"
  subnet_ids = var.data_subnet_ids

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-redis-subnet-group"
  })
}

# ------------------------------------------------------------------
# Parameter Group
# ------------------------------------------------------------------

resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.project}-${var.environment}-redis7"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-redis7-params"
  })
}

# ------------------------------------------------------------------
# Replication Group (Redis)
# ------------------------------------------------------------------

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project}-${var.environment}-redis"
  description          = "${var.project} ${var.environment} Redis cluster"

  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  port                 = var.port
  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [var.redis_security_group_id]

  # Auth & encryption
  auth_token                 = data.aws_secretsmanager_secret_version.redis_auth.secret_string
  transit_encryption_enabled = var.transit_encryption_enabled
  at_rest_encryption_enabled = var.at_rest_encryption_enabled

  # High availability
  automatic_failover_enabled = var.automatic_failover_enabled

  # Snapshots
  snapshot_retention_limit = var.snapshot_retention_limit
  snapshot_window          = var.snapshot_window
  maintenance_window       = var.maintenance_window

  # Upgrades
  auto_minor_version_upgrade = true
  apply_immediately          = false

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-redis"
  })
}
