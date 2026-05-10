# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build deps needed by some wheels (e.g. psycopg2-binary is pre-built,
# but cryptography may need gcc on some platforms)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# BUG-D3: APP_PORT is the single source of truth for the port — must match
# APP_PORT in .env. The default of 8001 matches the config.py default.
ENV APP_PORT=8001

# Expose the port (Docker metadata only — does not publish the port).
# Overriding APP_PORT at runtime also requires changing this via --expose
# or by rebuilding the image.
EXPOSE ${APP_PORT}

# BUG-A4: Production startup — 4 workers so slow Azure AI calls don't block
# the event loop for all other requests.
#
# Override WEB_CONCURRENCY at runtime to tune for your instance size:
#   e.g.  docker run -e WEB_CONCURRENCY=8 ...
ENV WEB_CONCURRENCY=4

CMD ["sh", "-c", \
     "uvicorn app.main:app \
        --host 0.0.0.0 \
        --port ${APP_PORT} \
        --workers ${WEB_CONCURRENCY} \
        --log-level info"]
