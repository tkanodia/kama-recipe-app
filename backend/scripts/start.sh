#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting API on port ${PORT}..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
