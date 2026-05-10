#!/usr/bin/env sh
# ══════════════════════════════════════════════════════════════════
# InvoiceAI Backend — Startup Script
#
# BUG-D3: APP_PORT is the single source of truth. The port is read
# from the environment (or from .env via python-dotenv at app startup).
# Previously APP_PORT was declared in config.py but never used in the
# startup command — so changing it in .env had no effect.
#
# Usage:
#   Development (single worker, auto-reload):
#     sh start.sh
#
#   Production (4 workers, no reload):
#     ENVIRONMENT=production sh start.sh
#
#   Custom port:
#     APP_PORT=8080 sh start.sh
# ══════════════════════════════════════════════════════════════════

# Load .env if present (for local dev convenience)
if [ -f .env ]; then
  # Export only APP_PORT and WEB_CONCURRENCY from .env, ignoring secrets
  APP_PORT_FROM_ENV=$(grep -E '^APP_PORT=' .env | cut -d '=' -f2)
  if [ -n "$APP_PORT_FROM_ENV" ] && [ -z "$APP_PORT" ]; then
    APP_PORT=$APP_PORT_FROM_ENV
  fi
fi

# Defaults
APP_PORT=${APP_PORT:-8001}
WEB_CONCURRENCY=${WEB_CONCURRENCY:-1}
ENVIRONMENT=${ENVIRONMENT:-dev}

echo "[start] ENVIRONMENT=${ENVIRONMENT} PORT=${APP_PORT} WORKERS=${WEB_CONCURRENCY}"

if [ "$ENVIRONMENT" = "dev" ]; then
  # Development: single worker with hot-reload
  exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$APP_PORT" \
    --reload \
    --log-level info
else
  # Production: multiple workers, no reload
  exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$APP_PORT" \
    --workers "$WEB_CONCURRENCY" \
    --log-level info
fi
