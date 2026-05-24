#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"

echo "Running database migrations..."

# initial_schema uses Base.metadata.create_all() with the *current* models, so a
# fresh database already has every column/table. Later revisions are incremental
# patches for older installs. On a fresh DB, `upgrade head` fails on duplicate
# columns — bootstrap through initial_schema then stamp head.
if uv run alembic upgrade head; then
  echo "Migrations complete."
else
  echo "Standard upgrade failed — bootstrapping fresh database schema..."
  uv run alembic upgrade 8d4f50202906
  uv run alembic stamp head
  echo "Bootstrap complete (schema created, alembic stamped at head)."
fi

echo "Starting API on port ${PORT}..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
