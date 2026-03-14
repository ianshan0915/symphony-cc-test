# ── Base stage ────────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app/ ./app/

# ── Production stage ─────────────────────────────────────────
FROM base AS production

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Test stage ───────────────────────────────────────────────
FROM base AS test

RUN pip install --no-cache-dir '.[dev]'
COPY tests/ ./tests/

CMD ["pytest"]
