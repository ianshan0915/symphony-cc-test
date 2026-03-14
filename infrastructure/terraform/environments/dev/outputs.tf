output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  value = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.networking.private_subnet_ids
}

output "data_subnet_ids" {
  value = module.networking.data_subnet_ids
}

output "alb_security_group_id" {
  value = module.networking.alb_security_group_id
}

output "ecs_security_group_id" {
  value = module.networking.ecs_security_group_id
}

output "rds_security_group_id" {
  value = module.networking.rds_security_group_id
}

output "redis_security_group_id" {
  value = module.networking.redis_security_group_id
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}
