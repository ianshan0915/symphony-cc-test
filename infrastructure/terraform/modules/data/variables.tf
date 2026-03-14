variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "symphony"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "data_subnet_ids" {
  description = "IDs of the data subnets for RDS and ElastiCache"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "IDs of the private subnets (used for ElastiCache subnet group)"
  type        = list(string)
}

variable "rds_security_group_id" {
  description = "Security group ID for RDS"
  type        = string
}

variable "redis_security_group_id" {
  description = "Security group ID for Redis/ElastiCache"
  type        = string
}

# RDS variables
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB for RDS"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage in GB for RDS autoscaling"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Name of the default database"
  type        = string
  default     = "symphony"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "symphony"
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ deployment for RDS"
  type        = bool
  default     = false
}

variable "db_backup_retention_period" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7
}

variable "db_deletion_protection" {
  description = "Enable deletion protection on RDS"
  type        = bool
  default     = false
}

variable "db_skip_final_snapshot" {
  description = "Skip final snapshot when deleting RDS"
  type        = bool
  default     = true
}

# Redis variables
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "redis_parameter_group_family" {
  description = "Redis parameter group family"
  type        = string
  default     = "redis7"
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
