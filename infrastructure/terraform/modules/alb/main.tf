###############################################################################
# ALB Module
# - Application Load Balancer with HTTPS listener (ACM cert)
# - HTTP → HTTPS redirect
# - Target groups: backend (/api/*), frontend (/*)
# - Health checks, SSE-friendly idle timeout (300s), stickiness
# - Optional WAF v2: OWASP managed rules, rate limiting, IP filtering
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
# Application Load Balancer
# ------------------------------------------------------------------

resource "aws_lb" "main" {
  name               = "${var.project}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.security_group_id]
  subnets            = var.public_subnet_ids
  idle_timeout       = var.idle_timeout

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-alb"
  })
}

# ------------------------------------------------------------------
# Target Groups
# ------------------------------------------------------------------

resource "aws_lb_target_group" "backend" {
  name        = "${var.project}-${var.environment}-backend-tg"
  port        = var.backend_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = var.health_check_path_backend
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    matcher             = "200"
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = var.stickiness_duration
    enabled         = true
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-backend-tg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_target_group" "frontend" {
  name        = "${var.project}-${var.environment}-frontend-tg"
  port        = var.frontend_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = var.health_check_path_frontend
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = var.stickiness_duration
    enabled         = true
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-frontend-tg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# ------------------------------------------------------------------
# HTTPS Listener (port 443) — default action: forward to frontend
# ------------------------------------------------------------------

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-https-listener"
  })
}

# ------------------------------------------------------------------
# Listener Rule — /api/* → backend target group
# ------------------------------------------------------------------

resource "aws_lb_listener_rule" "backend_api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-api-rule"
  })
}

# ------------------------------------------------------------------
# HTTP Listener (port 80) — redirect to HTTPS
# ------------------------------------------------------------------

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-http-redirect"
  })
}

# ------------------------------------------------------------------
# WAF v2 — OWASP managed rules, rate limiting, IP filtering
# ------------------------------------------------------------------

resource "aws_wafv2_ip_set" "blocklist" {
  count              = var.enable_waf && length(var.waf_ip_blocklist) > 0 ? 1 : 0
  name               = "${var.project}-${var.environment}-ip-blocklist"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"
  addresses          = var.waf_ip_blocklist

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-ip-blocklist"
  })
}

resource "aws_wafv2_web_acl" "main" {
  count       = var.enable_waf ? 1 : 0
  name        = "${var.project}-${var.environment}-waf"
  scope       = "REGIONAL"
  description = "WAF for ${var.project} ${var.environment} ALB"

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

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-waf"
  })
}

resource "aws_wafv2_web_acl_association" "main" {
  count        = var.enable_waf ? 1 : 0
  resource_arn = aws_lb.main.arn
  web_acl_arn  = aws_wafv2_web_acl.main[0].arn
}
