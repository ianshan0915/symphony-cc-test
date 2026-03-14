###############################################################################
# RDS Module
# - PostgreSQL 16 with pgvector extension
# - Multi-AZ option, automated backups, Performance Insights
# - DB subnet group, custom parameter group
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
# Fetch password from Secrets Manager
# ------------------------------------------------------------------

data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = var.db_password_secret_arn
}

# ------------------------------------------------------------------
# DB Subnet Group
# ------------------------------------------------------------------

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-${var.environment}-db-subnet"
  subnet_ids = var.data_subnet_ids

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-db-subnet-group"
  })
}

# ------------------------------------------------------------------
# Parameter Group — enables pgvector and tunes PostgreSQL 16
# ------------------------------------------------------------------

resource "aws_db_parameter_group" "main" {
  name_prefix = "${var.project}-${var.environment}-pg16-"
  family      = "postgres16"
  description = "Custom parameter group for PostgreSQL 16 with pgvector"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-pg16-params"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# ------------------------------------------------------------------
# RDS Instance
# ------------------------------------------------------------------

resource "aws_db_instance" "main" {
  identifier = "${var.project}-${var.environment}-postgres"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = var.master_username
  password = data.aws_secretsmanager_secret_version.db_password.secret_string

  multi_az            = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_security_group_id]
  parameter_group_name   = aws_db_parameter_group.main.name
  publicly_accessible    = false

  # Backups
  backup_retention_period = var.backup_retention_period
  backup_window           = var.backup_window
  maintenance_window      = var.maintenance_window

  # Performance Insights
  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_retention_period = var.performance_insights_retention_period

  # Snapshots & protection
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.project}-${var.environment}-postgres-final"
  copy_tags_to_snapshot     = true

  # Logging
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-postgres"
  })
}
