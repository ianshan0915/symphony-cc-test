###############################################################################
# ALB Module
# - Application Load Balancer with HTTPS listener (ACM cert)
# - HTTP → HTTPS redirect
# - Target groups: backend (/api/*), frontend (/*)
# - Health checks, SSE-friendly idle timeout (300s), stickiness
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
