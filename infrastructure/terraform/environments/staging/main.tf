###############################################################################
# Staging Environment
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  # Uncomment after running bootstrap.sh
  # backend "s3" {
  #   bucket         = "symphony-terraform-state-ACCOUNT_ID"
  #   key            = "staging/terraform.tfstate"
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

  tags = local.common_tags
}

# ------------------------------------------------------------------
# Networking
# ------------------------------------------------------------------

module "networking" {
  source = "../../modules/networking"

  project     = var.project
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
  app_port    = var.app_port

  tags = local.common_tags
}

# ------------------------------------------------------------------
# ECR (shared across environments, but referenced here for outputs)
# ------------------------------------------------------------------

module "ecr" {
  source = "../../modules/ecr"

  project          = var.project
  repository_names = ["backend", "frontend"]
  force_delete     = false # Staging should not allow accidental deletion

  tags = local.common_tags
}

# ------------------------------------------------------------------
# Data (RDS + Redis)
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

  # RDS sizing for staging
  db_instance_class        = var.db_instance_class
  db_allocated_storage     = var.db_allocated_storage
  db_max_allocated_storage = var.db_max_allocated_storage
  db_multi_az              = false
  db_deletion_protection   = false
  db_skip_final_snapshot   = false
  db_backup_retention_period = 7

  # Redis sizing for staging
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

  app_port    = var.app_port
  app_image   = var.app_image
  app_cpu     = var.app_cpu
  app_memory  = var.app_memory
  desired_count = var.desired_count

  certificate_arn = var.certificate_arn
  log_group_name  = module.monitoring.ecs_backend_log_group_name

  tags = local.common_tags
}
