# syntax=docker/dockerfile:1

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Build the Next.js static export
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /frontend

# Install dependencies first for better layer caching. The wildcard keeps the
# COPY working whether or not a package-lock.json exists yet.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

# Build the static export (next.config: output: 'export' → produces ./out)
COPY frontend/ ./
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Python runtime (FastAPI served by uvicorn)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# uv: fast, reproducible Python dependency management from the lockfile.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/app/db/finally.db

# Install dependencies from the lockfile first (cached unless the lock changes).
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy the backend application source.
COPY backend/ ./

# Sync again to pick up the project itself (no-op for package=false projects,
# but keeps the environment consistent if that ever changes).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Copy the built frontend into the directory FastAPI serves static files from.
COPY --from=frontend-build /frontend/out ./static

# Runtime data directory (SQLite lives here, volume-mounted in production).
RUN mkdir -p /app/db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
