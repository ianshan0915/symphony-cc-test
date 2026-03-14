# Symphony

## Repository Structure

```
symphony/
├── backend/          # Backend services
├── frontend/         # Frontend application
├── infrastructure/   # IaC, Terraform, deploy configs
├── .github/          # CI/CD workflows & CODEOWNERS
├── docker-compose.yml       # Local dev services
├── docker-compose.test.yml  # CI test services
└── Makefile                 # Common developer commands
```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (with Compose v2)
- GNU Make

## Quick Start

```bash
# Start local development services (PostgreSQL + Redis)
make up

# Check service status
make ps

# Tail logs (all services, or a specific one)
make logs
make logs s=postgres

# Stop services
make down
```

## Local Services

| Service    | Image                    | Port  | Credentials              |
|------------|--------------------------|-------|--------------------------|
| PostgreSQL | `pgvector/pgvector:pg16` | 5432  | `symphony` / `symphony_local` |
| Redis      | `redis:7-alpine`         | 6379  | _(none)_                 |

## Makefile Targets

Run `make help` to see all available targets:

| Target      | Description                              |
|-------------|------------------------------------------|
| `up`        | Start local dev services                 |
| `down`      | Stop local dev services                  |
| `ps`        | Show running service status              |
| `logs`      | Tail service logs                        |
| `build`     | Build all services _(stub)_              |
| `test`      | Run all tests _(stub)_                   |
| `lint`      | Run linters _(stub)_                     |
| `test-up`   | Start CI test services (ephemeral)       |
| `test-down` | Stop CI test services                    |
| `clean`     | Remove volumes and stopped containers    |

## CI Testing

The `docker-compose.test.yml` file provides ephemeral services for CI pipelines.
Data is stored on `tmpfs` and discarded when containers stop.

```bash
make test-up    # start
# ... run tests ...
make test-down  # teardown
```
