output "zone_id" {
  description = "ID of the Route 53 hosted zone"
  value       = aws_route53_zone.main.zone_id
}

output "zone_name_servers" {
  description = "Name servers for the hosted zone"
  value       = aws_route53_zone.main.name_servers
}

output "certificate_arn" {
  description = "ARN of the validated ACM certificate"
  value       = aws_acm_certificate.main.arn
}

output "certificate_validation_id" {
  description = "ID of the ACM certificate validation"
  value       = aws_acm_certificate_validation.main.id
}

output "domain_name" {
  description = "The root domain name"
  value       = var.domain_name
}

output "api_fqdn" {
  description = "Fully qualified domain name for the API"
  value       = aws_route53_record.api.fqdn
}
