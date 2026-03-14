###############################################################################
# Dev Environment
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  # Uncomment after running bootstrap.sh
  # backend "s3" {
  #   bucket         = "symphony-terraform-state-ACCOUNT_ID"
  #   key            = "dev/terraform.tfstate"
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

# ------------------------------------------------------------------
# Networking
# ------------------------------------------------------------------

module "networking" {
  source = "../../modules/networking"

  project     = var.project
  environment = var.environment
  vpc_cidr    = "10.0.0.0/16"
  app_port    = 8000

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# ------------------------------------------------------------------
# ECR
# ------------------------------------------------------------------

module "ecr" {
  source = "../../modules/ecr"

  project          = var.project
  repository_names = ["backend", "frontend"]
  force_delete     = true # Allow cleanup in dev

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}
