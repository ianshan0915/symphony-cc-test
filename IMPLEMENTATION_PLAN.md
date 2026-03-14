# Implementation Plan — Agentic Chat Platform

> **Linear Ticket:** [SYM-6](https://linear.app/symphony-cc/issue/SYM-6/create-implementation-plan)
> **Based On:** [PLAN.md](./PLAN.md) (SYM-5 — Architecture & Design)
> **Date:** 2026-03-14
> **Cloud:** AWS
> **CI/CD:** GitHub Actions

---

## Table of Contents

1. [Overview](#1-overview)
2. [Repository Structure](#2-repository-structure)
3. [AWS Infrastructure Architecture](#3-aws-infrastructure-architecture)
4. [Infrastructure as Code (Terraform)](#4-infrastructure-as-code-terraform)
5. [Docker & Container Strategy](#5-docker--container-strategy)
6. [CI/CD Pipeline (GitHub Actions)](#6-cicd-pipeline-github-actions)
7. [Environment Strategy](#7-environment-strategy)
8. [Secrets Management](#8-secrets-management)
9. [Database Migration Strategy](#9-database-migration-strategy)
10. [Monitoring, Logging & Alerting](#10-monitoring-logging--alerting)
11. [Security & Compliance](#11-security--compliance)
12. [Detailed Sprint Plan](#12-detailed-sprint-plan)
13. [Task Breakdown by File](#13-task-breakdown-by-file)
14. [Definition of Done](#14-definition-of-done)
15. [Rollback & Disaster Recovery](#15-rollback--disaster-recovery)
16. [Cost Estimation](#16-cost-estimation)

---

## 1. Overview

This document translates the architectural plan (PLAN.md) into a concrete, actionable implementation plan. It covers every file to create, every AWS service to provision, every CI/CD workflow to configure, and every task to complete — organized into week-by-week sprints.

### Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Cloud Provider | AWS | Mature ecosystem, broad service coverage, team familiarity |
| Container Orchestration | ECS Fargate | Serverless containers — no EC2 management overhead |
| CI/CD | GitHub Actions | Native GitHub integration, generous free tier, marketplace actions |
| IaC | Terraform | Multi-cloud capable, declarative, strong AWS provider |
| Container Registry | Amazon ECR | Native ECS integration, no cross-account image pulls |
| Database | Amazon RDS PostgreSQL | Managed, pgvector extension supported |
| Cache | Amazon ElastiCache Redis | Managed Redis, VPC-native |
| CDN / Frontend Hosting | AWS Amplify or CloudFront + S3 | SSR support via Amplify, or static export + CloudFront |
| Secrets | AWS Secrets Manager + GitHub Secrets | Runtime secrets in AWS SM, CI secrets in GitHub |
| DNS | Route 53 | Native AWS integration |
| SSL | ACM (AWS Certificate Manager) | Free managed certificates |

---

## 2. Repository Structure

```
/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                    # Lint, test, type-check on every PR
│   │   ├── deploy-staging.yml        # Deploy to staging on merge to main
│   │   ├── deploy-production.yml     # Deploy to production on release tag
│   │   ├── db-migrate.yml            # Run database migrations
│   │   └── infra-plan.yml            # Terraform plan on infra changes
│   ├── actions/
│   │   └── docker-build-push/
│   │       └── action.yml            # Reusable composite action for ECR push
│   └── CODEOWNERS
├── infrastructure/
│   ├── terraform/
│   │   ├── environments/
│   │   │   ├── staging/
│   │   │   │   ├── main.tf
│   │   │   │   ├── variables.tf
│   │   │   │   ├── outputs.tf
│   │   │   │   └── terraform.tfvars
│   │   │   └── production/
│   │   │       ├── main.tf
│   │   │       ├── variables.tf
│   │   │       ├── outputs.tf
│   │   │       └── terraform.tfvars
│   │   └── modules/
│   │       ├── networking/           # VPC, subnets, security groups
│   │       ├── ecs/                  # ECS cluster, services, task definitions
│   │       ├── rds/                  # PostgreSQL + pgvector
│   │       ├── elasticache/          # Redis cluster
│   │       ├── alb/                  # Application Load Balancer
│   │       ├── ecr/                  # Container registries
│   │       ├── secrets/              # Secrets Manager
│   │       ├── monitoring/           # CloudWatch dashboards, alarms
│   │       └── dns/                  # Route 53 + ACM
│   └── scripts/
│       ├── bootstrap.sh              # Initial AWS account setup
│       └── destroy.sh                # Teardown script
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app, CORS, lifespan
│   │   ├── config.py                 # Settings via pydantic-settings
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py               # Dependency injection
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── chat.py           # /chat/stream — SSE streaming
│   │   │       ├── threads.py        # /threads — CRUD
│   │   │       ├── assistants.py     # /assistants — agent configs
│   │   │       └── health.py         # /health — health check
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── factory.py            # create_deep_agent() wrappers
│   │   │   ├── middleware.py          # Custom middleware config
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── web_search.py
│   │   │   │   └── knowledge_base.py
│   │   │   └── prompts/
│   │   │       ├── __init__.py
│   │   │       ├── general.py
│   │   │       └── researcher.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── thread.py
│   │   │   ├── message.py
│   │   │   └── user.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── thread_service.py
│   │   │   └── agent_service.py
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── session.py            # Async SQLAlchemy session
│   │       └── migrations/           # Alembic migrations
│   │           ├── env.py
│   │           ├── alembic.ini
│   │           └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_chat.py
│   │   ├── test_threads.py
│   │   └── test_agents.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatInterface.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── ToolCallCard.tsx
│   │   ├── threads/
│   │   │   ├── ThreadList.tsx
│   │   │   └── ThreadItem.tsx
│   │   ├── sidebar/
│   │   │   ├── TasksSidebar.tsx
│   │   │   └── FilesSidebar.tsx
│   │   └── ui/
│   │       ├── Button.tsx
│   │       ├── Input.tsx
│   │       ├── ScrollArea.tsx
│   │       └── Dialog.tsx
│   ├── providers/
│   │   ├── ClientProvider.tsx
│   │   └── ChatProvider.tsx
│   ├── hooks/
│   │   ├── useAgent.ts
│   │   └── useThreads.ts
│   ├── lib/
│   │   ├── config.ts
│   │   └── utils.ts
│   ├── __tests__/
│   │   ├── ChatInterface.test.tsx
│   │   └── useAgent.test.ts
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
├── docker-compose.yml                # Local development
├── docker-compose.test.yml           # CI testing
├── Makefile                          # Common commands
└── README.md
```

---

## 3. AWS Infrastructure Architecture

```
                          ┌─────────────┐
                          │  Route 53   │
                          │  DNS Zone   │
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
                          │    ACM      │
                          │ Certificate │
                          └──────┬──────┘
                                 │
                 ┌───────────────┼───────────────┐
                 │               │               │
          ┌──────▼──────┐ ┌─────▼──────┐  ┌─────▼──────┐
          │  CloudFront │ │    ALB     │  │  AWS WAF   │
          │  (Frontend) │ │  (Backend) │  │ (Firewall) │
          └──────┬──────┘ └─────┬──────┘  └────────────┘
                 │              │
          ┌──────▼──────┐ ┌────▼──────────────────────────┐
          │  S3 Bucket  │ │         VPC (10.0.0.0/16)     │
          │  (Static /  │ │                                │
          │   Next.js)  │ │  ┌──────────────────────────┐ │
          │  or Amplify │ │  │   Public Subnets (2 AZ)  │ │
          └─────────────┘ │  │   NAT Gateway             │ │
                          │  └────────────┬─────────────┘ │
                          │               │                │
                          │  ┌────────────▼─────────────┐ │
                          │  │  Private Subnets (2 AZ)  │ │
                          │  │                           │ │
                          │  │  ┌─────────────────────┐ │ │
                          │  │  │   ECS Fargate        │ │ │
                          │  │  │   ┌───────────────┐  │ │ │
                          │  │  │   │ Backend Svc   │  │ │ │
                          │  │  │   │ (FastAPI)     │  │ │ │
                          │  │  │   │ Min: 2        │  │ │ │
                          │  │  │   │ Max: 10       │  │ │ │
                          │  │  │   └───────────────┘  │ │ │
                          │  │  │   ┌───────────────┐  │ │ │
                          │  │  │   │ Frontend Svc  │  │ │ │
                          │  │  │   │ (Next.js SSR) │  │ │ │
                          │  │  │   │ Min: 2        │  │ │ │
                          │  │  │   │ Max: 6        │  │ │ │
                          │  │  │   └───────────────┘  │ │ │
                          │  │  └─────────────────────┘ │ │
                          │  │                           │ │
                          │  │  ┌─────────────────────┐ │ │
                          │  │  │   Data Subnets      │ │ │
                          │  │  │   ┌──────────────┐  │ │ │
                          │  │  │   │ RDS Postgres │  │ │ │
                          │  │  │   │ Multi-AZ     │  │ │ │
                          │  │  │   │ + pgvector   │  │ │ │
                          │  │  │   └──────────────┘  │ │ │
                          │  │  │   ┌──────────────┐  │ │ │
                          │  │  │   │ ElastiCache  │  │ │ │
                          │  │  │   │ Redis        │  │ │ │
                          │  │  │   └──────────────┘  │ │ │
                          │  │  └─────────────────────┘ │ │
                          │  └──────────────────────────┘ │
                          └────────────────────────────────┘
```

### AWS Services Summary

| Service | Purpose | Configuration |
|---|---|---|
| **ECS Fargate** | Container orchestration | 2 services (backend, frontend), auto-scaling |
| **ECR** | Container registry | 2 repos (backend, frontend), lifecycle policies |
| **RDS PostgreSQL 16** | Primary database | db.t4g.medium, Multi-AZ, pgvector extension |
| **ElastiCache Redis 7** | Caching & queues | cache.t4g.micro, single-node (staging), cluster (prod) |
| **ALB** | Load balancing | HTTPS termination, path-based routing |
| **CloudFront** | CDN | Frontend static assets, caching |
| **S3** | Static assets / Terraform state | Versioned, encrypted |
| **Route 53** | DNS management | Hosted zone, alias records |
| **ACM** | SSL/TLS certificates | Auto-renewal, *.example.com |
| **Secrets Manager** | Runtime secrets | API keys, DB credentials |
| **CloudWatch** | Monitoring & logging | Log groups, dashboards, alarms |
| **WAF** | Web firewall | Rate limiting, IP filtering, OWASP rules |
| **VPC** | Network isolation | 2 AZs, public/private/data subnets |
| **NAT Gateway** | Outbound internet for private subnets | Single (staging), HA pair (prod) |

---

## 4. Infrastructure as Code (Terraform)

### 4.1 State Management

```hcl
# infrastructure/terraform/environments/staging/main.tf
terraform {
  required_version = ">= 1.7"

  backend "s3" {
    bucket         = "symphony-terraform-state"
    key            = "staging/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

### 4.2 Module Structure

**Networking Module** (`modules/networking/`)
```
- VPC with 10.0.0.0/16 CIDR
- 2 public subnets  (10.0.1.0/24, 10.0.2.0/24)
- 2 private subnets (10.0.10.0/24, 10.0.11.0/24)
- 2 data subnets    (10.0.20.0/24, 10.0.21.0/24)
- Internet Gateway
- NAT Gateway (1 for staging, 2 for production)
- Route tables
- Security groups:
  - alb-sg: 80, 443 from 0.0.0.0/0
  - ecs-sg: 8000, 3000 from alb-sg
  - rds-sg: 5432 from ecs-sg
  - redis-sg: 6379 from ecs-sg
```

**ECS Module** (`modules/ecs/`)
```
- ECS Cluster with Fargate capacity providers
- Backend task definition (1 vCPU, 2GB RAM)
- Frontend task definition (0.5 vCPU, 1GB RAM)
- Backend service with auto-scaling (CPU > 70%)
- Frontend service with auto-scaling (CPU > 70%)
- CloudWatch log groups
- IAM roles (task execution role, task role)
```

**RDS Module** (`modules/rds/`)
```
- PostgreSQL 16 instance (db.t4g.medium)
- pgvector extension enabled
- Multi-AZ (production only)
- Automated backups (7-day retention staging, 30-day production)
- Subnet group in data subnets
- Parameter group with pgvector
- Performance Insights enabled
```

**ElastiCache Module** (`modules/elasticache/`)
```
- Redis 7 engine
- cache.t4g.micro (staging), cache.r7g.large (production)
- Single-node (staging), 2-node cluster (production)
- Subnet group in data subnets
- Auth token via Secrets Manager
```

**ALB Module** (`modules/alb/`)
```
- Application Load Balancer in public subnets
- HTTPS listener (443) with ACM certificate
- HTTP listener (80) → redirect to HTTPS
- Target groups:
  - backend-tg: /api/* → ECS backend service
  - frontend-tg: /* → ECS frontend service
- Health checks: /health for backend, / for frontend
- Stickiness enabled for SSE streaming
- Idle timeout: 300s (for long-running SSE connections)
```

### 4.3 Terraform Variables per Environment

| Variable | Staging | Production |
|---|---|---|
| `instance_class_rds` | db.t4g.medium | db.r7g.large |
| `multi_az_rds` | false | true |
| `ecs_backend_desired` | 1 | 2 |
| `ecs_backend_max` | 2 | 10 |
| `ecs_frontend_desired` | 1 | 2 |
| `ecs_frontend_max` | 2 | 6 |
| `redis_node_type` | cache.t4g.micro | cache.r7g.large |
| `redis_num_nodes` | 1 | 2 |
| `nat_gateway_count` | 1 | 2 |
| `enable_waf` | false | true |
| `backup_retention_days` | 7 | 30 |

---

## 5. Docker & Container Strategy

### 5.1 Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies for pgvector/psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[prod]"

COPY . .

# Production stage
FROM base AS production
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Test stage
FROM base AS test
RUN pip install --no-cache-dir -e ".[dev]"
CMD ["pytest", "-v"]
```

### 5.2 Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:22-alpine AS base
WORKDIR /app

# Dependencies
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

# Builder
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Production
FROM base AS production
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

### 5.3 ECR Lifecycle Policies

- Keep last 10 tagged images per environment
- Expire untagged images after 7 days
- Tag format: `<env>-<git-sha>` (e.g., `staging-abc1234`)

---

## 6. CI/CD Pipeline (GitHub Actions)

### 6.1 Workflow Overview

```
                    ┌─────────────┐
                    │  Push / PR  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   ci.yml    │
                    │  Lint/Test  │
                    │  Type-check │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │                         │
     ┌────────▼────────┐      ┌────────▼────────┐
     │  Merge to main  │      │  Tag v*.*.*     │
     └────────┬────────┘      └────────┬────────┘
              │                         │
     ┌────────▼────────┐      ┌────────▼────────┐
     │ deploy-staging  │      │ deploy-production│
     │    .yml         │      │    .yml          │
     └────────┬────────┘      └────────┬────────┘
              │                         │
     ┌────────▼────────┐      ┌────────▼────────┐
     │  Build & Push   │      │  Build & Push   │
     │  to ECR         │      │  to ECR         │
     └────────┬────────┘      └────────┬────────┘
              │                         │
     ┌────────▼────────┐      ┌────────▼────────┐
     │  Run DB         │      │  Manual Approval│
     │  Migrations     │      │  (environment)  │
     └────────┬────────┘      └────────┬────────┘
              │                         │
     ┌────────▼────────┐      ┌────────▼────────┐
     │  Deploy ECS     │      │  Run DB         │
     │  (Staging)      │      │  Migrations     │
     └────────┬────────┘      └────────┬────────┘
              │                         │
     ┌────────▼────────┐      ┌────────▼────────┐
     │  Smoke Tests    │      │  Deploy ECS     │
     └─────────────────┘      │  (Production)   │
                               └────────┬────────┘
                                        │
                               ┌────────▼────────┐
                               │  Smoke Tests    │
                               └─────────────────┘
```

### 6.2 CI Workflow (`ci.yml`)

**Triggers:** All pull requests, pushes to `main`

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install ruff mypy
      - run: ruff check backend/
      - run: ruff format --check backend/
      - run: mypy backend/app/ --ignore-missing-imports

  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -e "backend/[dev]"
      - run: pytest backend/tests/ -v --cov=backend/app --cov-report=xml
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379
      - uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  frontend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend
      - run: npx tsc --noEmit
        working-directory: frontend

  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npm test -- --ci --coverage
        working-directory: frontend
```

### 6.3 Deploy Staging Workflow (`deploy-staging.yml`)

**Triggers:** Push to `main` (after CI passes)

```yaml
# .github/workflows/deploy-staging.yml
name: Deploy Staging

on:
  push:
    branches: [main]

permissions:
  id-token: write   # OIDC for AWS
  contents: read

env:
  AWS_REGION: us-east-1
  ECR_BACKEND_REPO: symphony/backend
  ECR_FRONTEND_REPO: symphony/frontend
  ECS_CLUSTER: symphony-staging
  ECS_BACKEND_SERVICE: backend
  ECS_FRONTEND_SERVICE: frontend

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_STAGING }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push backend image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          IMAGE_TAG: staging-${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_BACKEND_REPO:$IMAGE_TAG \
            --target production backend/
          docker push $ECR_REGISTRY/$ECR_BACKEND_REPO:$IMAGE_TAG

      - name: Build and push frontend image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          IMAGE_TAG: staging-${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_FRONTEND_REPO:$IMAGE_TAG \
            --target production frontend/
          docker push $ECR_REGISTRY/$ECR_FRONTEND_REPO:$IMAGE_TAG

      - name: Run database migrations
        env:
          DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
        run: |
          pip install -e "backend/[prod]"
          cd backend && alembic upgrade head

      - name: Deploy backend to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: backend-task-def-staging.json
          service: ${{ env.ECS_BACKEND_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true
          wait-for-minutes: 10

      - name: Deploy frontend to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: frontend-task-def-staging.json
          service: ${{ env.ECS_FRONTEND_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true
          wait-for-minutes: 10

      - name: Run smoke tests
        run: |
          curl -f https://staging-api.symphony.app/health || exit 1
          curl -f https://staging.symphony.app || exit 1
```

### 6.4 Deploy Production Workflow (`deploy-production.yml`)

**Triggers:** Git tag `v*.*.*`

```yaml
# .github/workflows/deploy-production.yml
name: Deploy Production

on:
  push:
    tags: ["v*.*.*"]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production   # Requires manual approval
    steps:
      # Same structure as staging, but:
      # - Uses production AWS role
      # - Uses production ECS cluster
      # - Uses production database URL
      # - Runs more comprehensive smoke tests
      # - Posts deployment notification to Slack
      - uses: actions/checkout@v4
      # ... (mirrors staging with production config)

      - name: Notify deployment
        uses: slackapi/slack-github-action@v2
        with:
          webhook: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {"text": "🚀 Production deployment complete: ${{ github.ref_name }}"}
```

### 6.5 Infrastructure Plan Workflow (`infra-plan.yml`)

**Triggers:** Changes to `infrastructure/` directory

```yaml
# .github/workflows/infra-plan.yml
name: Terraform Plan

on:
  pull_request:
    paths: ["infrastructure/**"]

jobs:
  plan:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [staging, production]
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - name: Terraform Init
        working-directory: infrastructure/terraform/environments/${{ matrix.environment }}
        run: terraform init
      - name: Terraform Plan
        working-directory: infrastructure/terraform/environments/${{ matrix.environment }}
        run: terraform plan -no-color
      - name: Post plan to PR
        uses: actions/github-script@v7
        with:
          script: |
            // Post terraform plan output as PR comment
```

### 6.6 Database Migration Workflow (`db-migrate.yml`)

```yaml
# .github/workflows/db-migrate.yml
name: Database Migration

on:
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, production]
      direction:
        type: choice
        options: [upgrade, downgrade]
        default: upgrade
      revision:
        description: "Target revision (default: head)"
        default: "head"

jobs:
  migrate:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e "backend/[prod]"
      - name: Run migration
        env:
          DATABASE_URL: ${{ secrets[format('{0}_DATABASE_URL', github.event.inputs.environment)] }}
        run: |
          cd backend
          alembic ${{ github.event.inputs.direction }} ${{ github.event.inputs.revision }}
```

---

## 7. Environment Strategy

| Environment | Purpose | Branch/Trigger | URL |
|---|---|---|---|
| **Local** | Development | Local machine | `localhost:3000` / `localhost:8000` |
| **CI** | Testing | PR / push | Ephemeral (GitHub Actions services) |
| **Staging** | Pre-production validation | Merge to `main` | `staging.symphony.app` |
| **Production** | Live users | Git tag `v*.*.*` | `symphony.app` |

### GitHub Environments Configuration

- **staging**: Auto-deploy, no approval required
- **production**: Requires 1 reviewer approval, 5-minute wait timer, restricted to `v*` tags

---

## 8. Secrets Management

### 8.1 GitHub Secrets (CI/CD Time)

| Secret | Environments | Description |
|---|---|---|
| `AWS_ROLE_ARN_STAGING` | staging | OIDC role ARN for staging |
| `AWS_ROLE_ARN_PRODUCTION` | production | OIDC role ARN for production |
| `STAGING_DATABASE_URL` | staging | RDS connection string (for migrations) |
| `PRODUCTION_DATABASE_URL` | production | RDS connection string (for migrations) |
| `SLACK_WEBHOOK` | production | Deployment notifications |
| `CODECOV_TOKEN` | all | Coverage upload token |

### 8.2 AWS Secrets Manager (Runtime)

| Secret Name | Contents |
|---|---|
| `symphony/<env>/database` | `{"url": "...", "username": "...", "password": "..."}` |
| `symphony/<env>/redis` | `{"url": "...", "auth_token": "..."}` |
| `symphony/<env>/anthropic` | `{"api_key": "sk-ant-..."}` |
| `symphony/<env>/langsmith` | `{"api_key": "lsv2_pt_...", "project": "..."}` |
| `symphony/<env>/app` | `{"jwt_secret": "...", "encryption_key": "..."}` |

ECS task definitions reference secrets via `valueFrom` ARN pointers — secrets are injected as environment variables at container start.

---

## 9. Database Migration Strategy

### 9.1 Alembic Setup

```
backend/
└── db/
    └── migrations/
        ├── alembic.ini        # Alembic configuration
        ├── env.py             # Async migration environment
        └── versions/
            ├── 001_initial_schema.py    # threads, messages tables
            ├── 002_add_checkpoints.py   # checkpoints table
            ├── 003_add_pgvector.py      # documents table + vector index
            └── ...
```

### 9.2 Migration Rules

1. **Forward-only in production** — Never run downgrades in prod; create a new "undo" migration instead
2. **Backward-compatible** — Each migration must be compatible with the previous application version (for zero-downtime deploys)
3. **Tested in CI** — Migrations run against a fresh PostgreSQL in CI (upgrade → seed → downgrade → upgrade cycle)
4. **Reviewed in PR** — Auto-generated migrations must be manually reviewed before merge

### 9.3 Migration Flow

```
Developer creates migration locally
  → PR opened → CI runs migration test
    → Merged to main → Staging migration runs automatically
      → Tag release → Production migration runs (after approval)
```

---

## 10. Monitoring, Logging & Alerting

### 10.1 CloudWatch Setup

**Log Groups:**
- `/ecs/symphony-<env>/backend`
- `/ecs/symphony-<env>/frontend`

**Metrics & Dashboards:**
- ECS service CPU/memory utilization
- ALB request count, latency (p50, p95, p99), error rate (4xx, 5xx)
- RDS connections, CPU, IOPS, replication lag
- ElastiCache memory usage, hit rate, evictions
- Custom metrics: streaming duration, agent execution time

### 10.2 Alarms

| Alarm | Metric | Threshold | Action |
|---|---|---|---|
| High Error Rate | ALB 5xx count | > 10 in 5 min | SNS → Slack + PagerDuty |
| High Latency | ALB p99 latency | > 5s for 5 min | SNS → Slack |
| Backend CPU | ECS CPU utilization | > 85% for 5 min | Auto-scale + Slack |
| Database Connections | RDS connections | > 80% max | SNS → Slack |
| Database CPU | RDS CPU utilization | > 80% for 10 min | SNS → Slack + PagerDuty |
| Redis Memory | ElastiCache memory | > 80% | SNS → Slack |
| Failed Deployments | ECS deployment | Failure | SNS → Slack + PagerDuty |

### 10.3 Application-Level Observability

- **LangSmith:** Agent tracing, token usage, latency, cost tracking
- **Structured Logging:** JSON logs from FastAPI with request ID correlation
- **Health Endpoints:**
  - `GET /health` — Basic liveness check
  - `GET /health/ready` — Readiness check (DB + Redis connectivity)

---

## 11. Security & Compliance

### 11.1 Network Security

- All services in **private subnets** (no public IPs on containers)
- **WAF** on ALB with managed rule groups (OWASP Top 10, rate limiting)
- **Security groups** follow least-privilege: only required ports between services
- **TLS everywhere**: ALB terminates HTTPS, internal traffic on private network

### 11.2 Application Security

- **OIDC authentication** for GitHub Actions → AWS (no long-lived access keys)
- **JWT-based auth** for API endpoints
- **CORS** restricted to known frontend origins
- **Rate limiting** via Redis (per-user, per-endpoint)
- **Input validation** via Pydantic models
- **PII filtering** middleware before sending to LLM providers

### 11.3 Data Security

- **RDS encryption at rest** (AWS KMS)
- **S3 bucket encryption** (SSE-S3)
- **Secrets rotation** via AWS Secrets Manager rotation lambdas
- **Database backups** encrypted, cross-region copy for production
- **No secrets in container images** — all injected via Secrets Manager

### 11.4 Compliance Checklist

- [ ] Enable CloudTrail for API audit logging
- [ ] Enable VPC Flow Logs
- [ ] Enable GuardDuty for threat detection
- [ ] Configure S3 bucket policies (no public access)
- [ ] Enable RDS audit logging
- [ ] Document data retention policy
- [ ] GDPR: implement user data export/deletion endpoints

---

## 12. Detailed Sprint Plan

### Sprint 0 — Foundation (Week 0, 3 days)

**Goal:** Repository setup, CI pipeline, infrastructure bootstrap

| # | Task | Files/Services | Est. | Depends On |
|---|---|---|---|---|
| 0.1 | Initialize monorepo with directory structure | All top-level dirs | 2h | — |
| 0.2 | Set up Python backend scaffolding | `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/config.py` | 3h | 0.1 |
| 0.3 | Set up Next.js frontend scaffolding | `frontend/package.json`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/tailwind.config.ts`, `frontend/tsconfig.json`, `frontend/next.config.ts` | 3h | 0.1 |
| 0.4 | Create Dockerfiles (backend + frontend) | `backend/Dockerfile`, `frontend/Dockerfile` | 2h | 0.2, 0.3 |
| 0.5 | Create docker-compose.yml for local dev | `docker-compose.yml` | 1h | 0.4 |
| 0.6 | Set up CI workflow (lint + test) | `.github/workflows/ci.yml` | 3h | 0.2, 0.3 |
| 0.7 | Set up Terraform bootstrap (S3 state bucket, DynamoDB lock, OIDC provider) | `infrastructure/scripts/bootstrap.sh`, `infrastructure/terraform/` base files | 4h | — |
| 0.8 | Create Terraform networking module | `infrastructure/terraform/modules/networking/` | 4h | 0.7 |
| 0.9 | Create Terraform ECR module | `infrastructure/terraform/modules/ecr/` | 1h | 0.7 |
| 0.10 | Create Makefile with common commands | `Makefile` | 1h | 0.5 |

**Sprint 0 Total: ~24h (3 days)**

---

### Sprint 1 — MVP Backend (Weeks 1–2)

**Goal:** Working FastAPI backend with Deep Agent and streaming

| # | Task | Files/Services | Est. | Depends On |
|---|---|---|---|---|
| 1.1 | Implement health check endpoint | `backend/app/api/routes/health.py` | 1h | 0.2 |
| 1.2 | Set up async SQLAlchemy + Alembic | `backend/app/db/session.py`, `backend/db/migrations/env.py`, `alembic.ini` | 4h | 0.2 |
| 1.3 | Create initial DB migration (threads + messages) | `backend/db/migrations/versions/001_initial_schema.py` | 3h | 1.2 |
| 1.4 | Implement thread models (SQLAlchemy + Pydantic) | `backend/app/models/thread.py`, `backend/app/models/message.py` | 3h | 1.2 |
| 1.5 | Implement thread service layer | `backend/app/services/thread_service.py` | 4h | 1.4 |
| 1.6 | Implement thread CRUD endpoints | `backend/app/api/routes/threads.py` | 4h | 1.5 |
| 1.7 | Set up Deep Agent factory | `backend/app/agents/factory.py`, `backend/app/agents/prompts/general.py` | 4h | 0.2 |
| 1.8 | Implement agent service layer | `backend/app/services/agent_service.py` | 4h | 1.7 |
| 1.9 | Implement SSE streaming chat endpoint | `backend/app/api/routes/chat.py` | 6h | 1.7, 1.8 |
| 1.10 | Implement dependency injection | `backend/app/api/deps.py` | 2h | 1.2 |
| 1.11 | Wire up FastAPI app (routers, CORS, lifespan) | `backend/app/main.py` | 2h | 1.1–1.10 |
| 1.12 | Write backend unit tests | `backend/tests/` | 6h | 1.1–1.11 |
| 1.13 | Write backend integration tests | `backend/tests/` | 4h | 1.12 |

**Sprint 1 Total: ~47h (2 weeks)**

---

### Sprint 2 — MVP Frontend (Weeks 2–3)

**Goal:** Working chat UI connected to backend

| # | Task | Files/Services | Est. | Depends On |
|---|---|---|---|---|
| 2.1 | Set up shared UI primitives (Radix) | `frontend/components/ui/Button.tsx`, `Input.tsx`, `ScrollArea.tsx`, `Dialog.tsx` | 4h | 0.3 |
| 2.2 | Implement LangGraph client provider | `frontend/providers/ClientProvider.tsx` | 2h | 0.3 |
| 2.3 | Implement useAgent hook (streaming) | `frontend/hooks/useAgent.ts` | 6h | 2.2 |
| 2.4 | Implement useThreads hook | `frontend/hooks/useThreads.ts` | 3h | 2.2 |
| 2.5 | Implement ChatInput component | `frontend/components/chat/ChatInput.tsx` | 3h | 2.1 |
| 2.6 | Implement MessageBubble component | `frontend/components/chat/MessageBubble.tsx` | 4h | 2.1 |
| 2.7 | Implement MessageList component | `frontend/components/chat/MessageList.tsx` | 3h | 2.6 |
| 2.8 | Implement ChatInterface container | `frontend/components/chat/ChatInterface.tsx` | 4h | 2.3, 2.5, 2.7 |
| 2.9 | Implement ToolCallCard component | `frontend/components/chat/ToolCallCard.tsx` | 3h | 2.1 |
| 2.10 | Implement ThreadList + ThreadItem | `frontend/components/threads/ThreadList.tsx`, `ThreadItem.tsx` | 4h | 2.4 |
| 2.11 | Implement ChatProvider (state context) | `frontend/providers/ChatProvider.tsx` | 3h | 2.3, 2.4 |
| 2.12 | Wire up main page layout | `frontend/app/page.tsx`, `frontend/app/layout.tsx`, `frontend/app/globals.css` | 3h | 2.8, 2.10, 2.11 |
| 2.13 | Set up config + utils | `frontend/lib/config.ts`, `frontend/lib/utils.ts` | 1h | 0.3 |
| 2.14 | Write frontend tests | `frontend/__tests__/` | 4h | 2.1–2.12 |
| 2.15 | End-to-end manual testing + polish | — | 4h | 2.14 |

**Sprint 2 Total: ~51h (2 weeks, overlapping with Sprint 1)**

---

### Sprint 3 — Infrastructure & Deployment (Week 3–4)

**Goal:** Staging environment running on AWS

| # | Task | Files/Services | Est. | Depends On |
|---|---|---|---|---|
| 3.1 | Create Terraform RDS module | `infrastructure/terraform/modules/rds/` | 4h | 0.7 |
| 3.2 | Create Terraform ElastiCache module | `infrastructure/terraform/modules/elasticache/` | 3h | 0.7 |
| 3.3 | Create Terraform ALB module | `infrastructure/terraform/modules/alb/` | 4h | 0.8 |
| 3.4 | Create Terraform ECS module | `infrastructure/terraform/modules/ecs/` | 6h | 0.8, 0.9 |
| 3.5 | Create Terraform secrets module | `infrastructure/terraform/modules/secrets/` | 2h | 0.7 |
| 3.6 | Create Terraform DNS module | `infrastructure/terraform/modules/dns/` | 2h | 0.7 |
| 3.7 | Create Terraform monitoring module | `infrastructure/terraform/modules/monitoring/` | 3h | 3.4 |
| 3.8 | Wire up staging environment | `infrastructure/terraform/environments/staging/` | 3h | 3.1–3.7 |
| 3.9 | Create staging deploy workflow | `.github/workflows/deploy-staging.yml` | 4h | 0.6 |
| 3.10 | Create reusable Docker build/push action | `.github/actions/docker-build-push/action.yml` | 2h | 0.9 |
| 3.11 | Create DB migration workflow | `.github/workflows/db-migrate.yml` | 2h | 1.2 |
| 3.12 | Create infra plan workflow | `.github/workflows/infra-plan.yml` | 2h | 3.8 |
| 3.13 | Apply Terraform to staging | — | 4h | 3.8 |
| 3.14 | First deployment to staging | — | 4h | 3.9, 3.13 |
| 3.15 | Verify staging end-to-end | — | 4h | 3.14 |

**Sprint 3 Total: ~49h (2 weeks)**

---

### Sprint 4 — Enhanced Features (Weeks 5–6)

**Goal:** Memory, knowledge base, observability

| # | Task | Files/Services | Est. | Depends On |
|---|---|---|---|---|
| 4.1 | Integrate LangGraph Memory Store | `backend/app/agents/factory.py`, `backend/app/agents/middleware.py` | 6h | 1.7 |
| 4.2 | Add pgvector migration + document model | `backend/db/migrations/versions/003_add_pgvector.py`, `backend/app/models/document.py` | 3h | 1.3 |
| 4.3 | Implement knowledge base search tool | `backend/app/agents/tools/knowledge_base.py` | 4h | 4.2 |
| 4.4 | Implement web search tool (Tavily) | `backend/app/agents/tools/web_search.py` | 3h | 1.7 |
| 4.5 | Implement human-in-the-loop (backend) | `backend/app/api/routes/chat.py` (interrupt/resume) | 4h | 1.9 |
| 4.6 | Implement human-in-the-loop (frontend) | `frontend/components/chat/` (approval dialog) | 4h | 2.8 |
| 4.7 | Integrate LangSmith tracing | `backend/app/agents/factory.py`, `backend/app/config.py` | 2h | 1.7 |
| 4.8 | Implement TasksSidebar | `frontend/components/sidebar/TasksSidebar.tsx` | 4h | 2.1 |
| 4.9 | Implement FilesSidebar | `frontend/components/sidebar/FilesSidebar.tsx` | 3h | 2.1 |
| 4.10 | Implement Redis rate limiting | `backend/app/api/deps.py` (rate limit middleware) | 3h | 1.10 |
| 4.11 | Add assistant config endpoints | `backend/app/api/routes/assistants.py` | 3h | 1.11 |
| 4.12 | Write tests for new features | `backend/tests/`, `frontend/__tests__/` | 6h | 4.1–4.11 |
| 4.13 | Deploy enhanced features to staging | — | 2h | 4.12 |

**Sprint 4 Total: ~47h (2 weeks)**

---

### Sprint 5 — Production Readiness (Weeks 7–8)

**Goal:** Production deployment, monitoring, security hardening

| # | Task | Files/Services | Est. | Depends On |
|---|---|---|---|---|
| 5.1 | Wire up production Terraform environment | `infrastructure/terraform/environments/production/` | 4h | 3.8 |
| 5.2 | Apply Terraform to production | — | 4h | 5.1 |
| 5.3 | Create production deploy workflow | `.github/workflows/deploy-production.yml` | 4h | 3.9 |
| 5.4 | Set up GitHub environment protection rules | — | 1h | 5.3 |
| 5.5 | Configure WAF rules | `infrastructure/terraform/modules/alb/` (WAF) | 3h | 5.1 |
| 5.6 | Set up CloudWatch dashboards | `infrastructure/terraform/modules/monitoring/` | 4h | 5.2 |
| 5.7 | Set up CloudWatch alarms + SNS | `infrastructure/terraform/modules/monitoring/` | 3h | 5.6 |
| 5.8 | Implement JWT authentication | `backend/app/api/deps.py` (auth middleware), `backend/app/models/user.py` | 6h | 1.10 |
| 5.9 | Add user model + migration | `backend/db/migrations/versions/004_add_users.py` | 2h | 5.8 |
| 5.10 | Implement structured JSON logging | `backend/app/main.py` (logging config) | 2h | 1.11 |
| 5.11 | Load testing with Locust | `backend/tests/load/locustfile.py` | 4h | 3.14 |
| 5.12 | Security audit + penetration testing | — | 4h | 5.5, 5.8 |
| 5.13 | First production deployment | — | 4h | 5.1–5.12 |
| 5.14 | Production smoke tests + validation | — | 4h | 5.13 |

**Sprint 5 Total: ~49h (2 weeks)**

---

### Sprint 6 — Scale & Specialize (Weeks 9–10)

**Goal:** Multi-agent support, advanced features, documentation

| # | Task | Files/Services | Est. | Depends On |
|---|---|---|---|---|
| 6.1 | Add researcher agent prompt + config | `backend/app/agents/prompts/researcher.py` | 3h | 1.7 |
| 6.2 | Add coding agent prompt + config | `backend/app/agents/prompts/coder.py` | 3h | 1.7 |
| 6.3 | Add writing agent prompt + config | `backend/app/agents/prompts/writer.py` | 3h | 1.7 |
| 6.4 | Implement assistant selector in frontend | `frontend/components/chat/AssistantSelector.tsx` | 3h | 4.11 |
| 6.5 | Implement sub-agent visualization | `frontend/components/chat/SubAgentProgress.tsx` | 6h | 2.9 |
| 6.6 | Migrate to StoreBackend (production) | `backend/app/agents/factory.py` | 4h | 4.1 |
| 6.7 | Set up LangSmith evaluation pipeline | `backend/evals/` | 6h | 4.7 |
| 6.8 | Implement prompt caching | `backend/app/agents/factory.py` | 3h | 1.7 |
| 6.9 | Connection pooling optimization | `backend/app/db/session.py` | 2h | 1.2 |
| 6.10 | GDPR: user data export/deletion | `backend/app/api/routes/users.py` | 4h | 5.8 |
| 6.11 | API documentation (OpenAPI + guide) | Auto-generated + `docs/` | 3h | 1.11 |
| 6.12 | Deployment guide | `docs/deployment.md` | 2h | 5.13 |
| 6.13 | Final testing + polish | — | 6h | 6.1–6.12 |

**Sprint 6 Total: ~48h (2 weeks)**

---

## 13. Task Breakdown by File

This section provides a flat list of every file to create with its purpose and sprint assignment, for tracking in Linear.

### Backend Files

| File | Purpose | Sprint |
|---|---|---|
| `backend/pyproject.toml` | Python project config, dependencies | 0 |
| `backend/Dockerfile` | Multi-stage Docker build | 0 |
| `backend/.env.example` | Environment variable template | 0 |
| `backend/app/__init__.py` | Package init | 0 |
| `backend/app/main.py` | FastAPI app entry point | 1 |
| `backend/app/config.py` | Pydantic settings | 1 |
| `backend/app/api/__init__.py` | Package init | 1 |
| `backend/app/api/deps.py` | Dependency injection (DB, auth, rate limit) | 1, 4, 5 |
| `backend/app/api/routes/__init__.py` | Package init | 1 |
| `backend/app/api/routes/health.py` | Health check endpoints | 1 |
| `backend/app/api/routes/chat.py` | SSE streaming chat endpoint | 1, 4 |
| `backend/app/api/routes/threads.py` | Thread CRUD | 1 |
| `backend/app/api/routes/assistants.py` | Assistant management | 4 |
| `backend/app/api/routes/users.py` | User management + GDPR | 5, 6 |
| `backend/app/agents/__init__.py` | Package init | 1 |
| `backend/app/agents/factory.py` | Deep Agent creation | 1, 4, 6 |
| `backend/app/agents/middleware.py` | Middleware configuration | 4 |
| `backend/app/agents/tools/__init__.py` | Package init | 1 |
| `backend/app/agents/tools/web_search.py` | Web search tool | 4 |
| `backend/app/agents/tools/knowledge_base.py` | Knowledge base search | 4 |
| `backend/app/agents/prompts/__init__.py` | Package init | 1 |
| `backend/app/agents/prompts/general.py` | General agent system prompt | 1 |
| `backend/app/agents/prompts/researcher.py` | Researcher agent prompt | 6 |
| `backend/app/agents/prompts/coder.py` | Coding agent prompt | 6 |
| `backend/app/agents/prompts/writer.py` | Writing agent prompt | 6 |
| `backend/app/models/__init__.py` | Package init | 1 |
| `backend/app/models/thread.py` | Thread SQLAlchemy + Pydantic | 1 |
| `backend/app/models/message.py` | Message SQLAlchemy + Pydantic | 1 |
| `backend/app/models/user.py` | User model | 5 |
| `backend/app/models/document.py` | Document + vector model | 4 |
| `backend/app/services/__init__.py` | Package init | 1 |
| `backend/app/services/thread_service.py` | Thread business logic | 1 |
| `backend/app/services/agent_service.py` | Agent lifecycle management | 1 |
| `backend/app/db/__init__.py` | Package init | 1 |
| `backend/app/db/session.py` | Async SQLAlchemy session | 1 |
| `backend/db/migrations/alembic.ini` | Alembic config | 1 |
| `backend/db/migrations/env.py` | Migration environment | 1 |
| `backend/db/migrations/versions/001_*.py` | Initial schema | 1 |
| `backend/db/migrations/versions/002_*.py` | Checkpoints table | 1 |
| `backend/db/migrations/versions/003_*.py` | pgvector + documents | 4 |
| `backend/db/migrations/versions/004_*.py` | Users table | 5 |
| `backend/tests/conftest.py` | Test fixtures | 1 |
| `backend/tests/test_health.py` | Health endpoint tests | 1 |
| `backend/tests/test_chat.py` | Chat endpoint tests | 1 |
| `backend/tests/test_threads.py` | Thread endpoint tests | 1 |
| `backend/tests/test_agents.py` | Agent factory tests | 1 |
| `backend/tests/load/locustfile.py` | Load testing | 5 |

### Frontend Files

| File | Purpose | Sprint |
|---|---|---|
| `frontend/package.json` | Node.js dependencies | 0 |
| `frontend/Dockerfile` | Multi-stage Docker build | 0 |
| `frontend/next.config.ts` | Next.js configuration | 0 |
| `frontend/tailwind.config.ts` | Tailwind CSS config | 0 |
| `frontend/tsconfig.json` | TypeScript config | 0 |
| `frontend/app/layout.tsx` | Root layout | 2 |
| `frontend/app/page.tsx` | Main page | 2 |
| `frontend/app/globals.css` | Global styles | 2 |
| `frontend/components/ui/Button.tsx` | Button primitive | 2 |
| `frontend/components/ui/Input.tsx` | Input primitive | 2 |
| `frontend/components/ui/ScrollArea.tsx` | Scroll area primitive | 2 |
| `frontend/components/ui/Dialog.tsx` | Dialog primitive | 2 |
| `frontend/components/chat/ChatInterface.tsx` | Main chat container | 2 |
| `frontend/components/chat/MessageList.tsx` | Message display | 2 |
| `frontend/components/chat/MessageBubble.tsx` | Single message | 2 |
| `frontend/components/chat/ChatInput.tsx` | User input | 2 |
| `frontend/components/chat/ToolCallCard.tsx` | Tool execution display | 2 |
| `frontend/components/chat/AssistantSelector.tsx` | Agent type selector | 6 |
| `frontend/components/chat/SubAgentProgress.tsx` | Sub-agent visualization | 6 |
| `frontend/components/threads/ThreadList.tsx` | Thread sidebar | 2 |
| `frontend/components/threads/ThreadItem.tsx` | Single thread entry | 2 |
| `frontend/components/sidebar/TasksSidebar.tsx` | Agent tasks display | 4 |
| `frontend/components/sidebar/FilesSidebar.tsx` | Agent files display | 4 |
| `frontend/providers/ClientProvider.tsx` | LangGraph SDK client | 2 |
| `frontend/providers/ChatProvider.tsx` | Chat state context | 2 |
| `frontend/hooks/useAgent.ts` | Agent interaction hook | 2 |
| `frontend/hooks/useThreads.ts` | Thread management hook | 2 |
| `frontend/lib/config.ts` | Configuration | 2 |
| `frontend/lib/utils.ts` | Utility functions | 2 |
| `frontend/__tests__/ChatInterface.test.tsx` | Chat UI tests | 2 |
| `frontend/__tests__/useAgent.test.ts` | Hook tests | 2 |

### Infrastructure Files

| File | Purpose | Sprint |
|---|---|---|
| `infrastructure/scripts/bootstrap.sh` | AWS account bootstrap | 0 |
| `infrastructure/scripts/destroy.sh` | Teardown script | 0 |
| `infrastructure/terraform/modules/networking/` | VPC, subnets, SGs | 0 |
| `infrastructure/terraform/modules/ecr/` | Container registries | 0 |
| `infrastructure/terraform/modules/rds/` | PostgreSQL | 3 |
| `infrastructure/terraform/modules/elasticache/` | Redis | 3 |
| `infrastructure/terraform/modules/alb/` | Load balancer + WAF | 3, 5 |
| `infrastructure/terraform/modules/ecs/` | Fargate services | 3 |
| `infrastructure/terraform/modules/secrets/` | Secrets Manager | 3 |
| `infrastructure/terraform/modules/dns/` | Route 53 + ACM | 3 |
| `infrastructure/terraform/modules/monitoring/` | CloudWatch | 3, 5 |
| `infrastructure/terraform/environments/staging/` | Staging config | 3 |
| `infrastructure/terraform/environments/production/` | Production config | 5 |

### CI/CD Files

| File | Purpose | Sprint |
|---|---|---|
| `.github/workflows/ci.yml` | Lint + test on PR | 0 |
| `.github/workflows/deploy-staging.yml` | Staging deployment | 3 |
| `.github/workflows/deploy-production.yml` | Production deployment | 5 |
| `.github/workflows/db-migrate.yml` | Database migrations | 3 |
| `.github/workflows/infra-plan.yml` | Terraform plan on PR | 3 |
| `.github/actions/docker-build-push/action.yml` | Reusable Docker action | 3 |
| `.github/CODEOWNERS` | Code ownership rules | 0 |

### Other Files

| File | Purpose | Sprint |
|---|---|---|
| `docker-compose.yml` | Local development | 0 |
| `docker-compose.test.yml` | CI testing | 0 |
| `Makefile` | Common commands | 0 |

---

## 14. Definition of Done

### Per Task
- [ ] Code written and passes linting
- [ ] Unit tests written with >80% coverage for new code
- [ ] PR reviewed and approved
- [ ] CI pipeline passes
- [ ] Deployed to staging and manually verified

### Per Sprint
- [ ] All sprint tasks completed
- [ ] Integration tests pass
- [ ] No critical bugs in staging
- [ ] Sprint retrospective documented

### Per Release
- [ ] All sprint DoDs met
- [ ] Load test results acceptable (<500ms p95 for chat streaming start)
- [ ] Security review completed
- [ ] Production deployment successful
- [ ] Smoke tests pass
- [ ] Monitoring and alerting verified

---

## 15. Rollback & Disaster Recovery

### Deployment Rollback

1. **ECS Rolling Deployment** — ECS automatically rolls back if health checks fail during deployment
2. **Manual Rollback** — Re-deploy previous task definition revision:
   ```bash
   aws ecs update-service --cluster symphony-prod \
     --service backend \
     --task-definition backend:<previous-revision>
   ```
3. **Database Rollback** — Run targeted downgrade migration via `db-migrate.yml` workflow
4. **Infrastructure Rollback** — Revert Terraform to previous commit, run `terraform apply`

### Disaster Recovery

| Scenario | RTO | RPO | Strategy |
|---|---|---|---|
| Single container failure | <1 min | 0 | ECS auto-replaces tasks |
| Single AZ failure | <5 min | 0 | Multi-AZ ECS + RDS failover |
| Region failure | <1 hour | <5 min | Cross-region RDS read replica promotion (prod) |
| Accidental data deletion | <30 min | <24h | RDS point-in-time recovery |
| Security breach | <1 hour | 0 | WAF block + rotate all secrets + redeploy |

### Backup Schedule

| Resource | Frequency | Retention | Cross-Region |
|---|---|---|---|
| RDS automated backups | Daily | 7 days (staging), 30 days (prod) | Production only |
| RDS snapshots | Weekly (manual) | 90 days | Production only |
| Terraform state (S3) | On every change | Versioned (indefinite) | No |
| ECR images | On every push | Last 10 per env | No |

---

## 16. Cost Estimation

### Monthly AWS Cost Estimate (Staging)

| Service | Configuration | Est. Monthly Cost |
|---|---|---|
| ECS Fargate (backend) | 1 task × 1 vCPU × 2GB | ~$35 |
| ECS Fargate (frontend) | 1 task × 0.5 vCPU × 1GB | ~$18 |
| RDS PostgreSQL | db.t4g.medium, single-AZ, 20GB | ~$55 |
| ElastiCache Redis | cache.t4g.micro | ~$12 |
| ALB | 1 ALB + minimal traffic | ~$22 |
| NAT Gateway | 1 gateway + data processing | ~$35 |
| ECR | ~5GB images | ~$0.50 |
| CloudWatch | Logs + metrics + dashboards | ~$10 |
| Route 53 | 1 hosted zone + queries | ~$1 |
| Secrets Manager | ~5 secrets | ~$2 |
| **Total Staging** | | **~$190/month** |

### Monthly AWS Cost Estimate (Production)

| Service | Configuration | Est. Monthly Cost |
|---|---|---|
| ECS Fargate (backend) | 2–10 tasks × 1 vCPU × 2GB | ~$70–350 |
| ECS Fargate (frontend) | 2–6 tasks × 0.5 vCPU × 1GB | ~$36–108 |
| RDS PostgreSQL | db.r7g.large, Multi-AZ, 100GB | ~$350 |
| ElastiCache Redis | cache.r7g.large, 2-node | ~$240 |
| ALB | 1 ALB + moderate traffic | ~$35 |
| CloudFront | CDN distribution | ~$10–50 |
| NAT Gateway | 2 gateways + data processing | ~$70 |
| WAF | Web ACL + managed rules | ~$25 |
| CloudWatch | Full monitoring | ~$30 |
| Route 53 | 1 hosted zone + queries | ~$2 |
| Secrets Manager | ~10 secrets | ~$4 |
| **Total Production (baseline)** | | **~$870/month** |
| **Total Production (scaled)** | | **~$1,270/month** |

### LLM API Costs (Separate)

| Provider | Model | Est. Cost/1K conversations |
|---|---|---|
| Anthropic | Claude Sonnet | ~$3–8 |
| OpenAI | GPT-4o | ~$5–15 |

> **Note:** LLM costs are highly variable based on conversation length, agent tool usage, and sub-agent spawning. LangSmith tracking is essential for cost monitoring.

---

## Timeline Summary

```
Week 0          ████ Sprint 0: Foundation (repo, CI, Terraform bootstrap)
Weeks 1-2       ████████ Sprint 1: MVP Backend (FastAPI + Deep Agents)
Weeks 2-3       ████████ Sprint 2: MVP Frontend (Next.js chat UI)
                        ↑ MVP Demo possible at end of Week 3
Weeks 3-4       ████████ Sprint 3: Infrastructure & First Deployment
Weeks 5-6       ████████ Sprint 4: Enhanced Features (memory, search, HITL)
Weeks 7-8       ████████ Sprint 5: Production Readiness
Weeks 9-10      ████████ Sprint 6: Scale & Specialize
                                  ↑ Production launch at end of Week 10
```

**Total Duration: ~10 weeks**
**Total Estimated Effort: ~315 hours**
