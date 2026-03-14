###############################################################################
# Data Module
# - RDS PostgreSQL instance
# - ElastiCache Redis cluster
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
# RDS Subnet Group
# ------------------------------------------------------------------

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet"
  subnet_ids = var.data_subnet_ids

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-db-subnet"
  })
}

# ------------------------------------------------------------------
# RDS PostgreSQL
# ------------------------------------------------------------------

resource "aws_db_instance" "main" {
  identifier = "${local.name_prefix}-postgres"

  engine               = "postgres"
  engine_version       = var.db_engine_version
  instance_class       = var.db_instance_class
  allocated_storage    = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_encrypted    = true

  db_name  = var.db_name
  username = var.db_username
  manage_master_user_password = true

  multi_az            = var.db_multi_az
  db_subnet_group_name = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_security_group_id]

  backup_retention_period = var.db_backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  deletion_protection = var.db_deletion_protection
  skip_final_snapshot = var.db_skip_final_snapshot
  final_snapshot_identifier = var.db_skip_final_snapshot ? null : "${local.name_prefix}-postgres-final"

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-postgres"
  })
}

# ------------------------------------------------------------------
# ElastiCache Subnet Group
# ------------------------------------------------------------------

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet"
  subnet_ids = var.data_subnet_ids

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-redis-subnet"
  })
}

# ------------------------------------------------------------------
# ElastiCache Parameter Group
# ------------------------------------------------------------------

resource "aws_elasticache_parameter_group" "main" {
  name   = "${local.name_prefix}-redis-params"
  family = var.redis_parameter_group_family

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-redis-params"
  })
}

# ------------------------------------------------------------------
# ElastiCache Redis
# ------------------------------------------------------------------

resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${local.name_prefix}-redis"
  engine               = "redis"
  engine_version       = var.redis_engine_version
  node_type            = var.redis_node_type
  num_cache_nodes      = var.redis_num_cache_nodes
  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [var.redis_security_group_id]

  port = 6379

  maintenance_window = "sun:05:00-sun:06:00"

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-redis"
  })
}
