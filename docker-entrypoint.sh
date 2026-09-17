#!/usr/bin/env bash
set -e

echo "=== [Egreen-Quanta Backend Entrypoint] Starting ==="

# Function to wait for PostgreSQL
wait_for_postgres() {
    echo "Waiting for PostgreSQL database to be reachable..."
    python - <<'EOF'
import os
import sys
import time
import urllib.parse
import socket

db_url = os.getenv("DATABASE_URL", "")
if not db_url:
    print("DATABASE_URL is not set; skipping database connectivity check.")
    sys.exit(0)

# Clean up asyncpg prefix for urllib parse if present
clean_url = db_url.replace("postgresql+asyncpg://", "http://").replace("postgresql://", "http://")
parsed = urllib.parse.urlparse(clean_url)
host = parsed.hostname or "localhost"
port = parsed.port or 5432

max_retries = 30
for attempt in range(1, max_retries + 1):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"Connected successfully to PostgreSQL at {host}:{port}")
            sys.exit(0)
    except (socket.error, OSError) as e:
        print(f"[{attempt}/{max_retries}] PostgreSQL not ready yet ({e}); retrying in 1s...")
        time.sleep(1)

print(f"ERROR: Could not connect to PostgreSQL at {host}:{port} after {max_retries} attempts.")
sys.exit(1)
EOF
}

# Wait for DB if DATABASE_URL is configured
wait_for_postgres

# Apply database migrations
echo "Applying database migrations (alembic upgrade head)..."
alembic upgrade head
echo "Database migrations applied successfully."

# Start uvicorn server
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"

echo "Starting Uvicorn production server on ${HOST}:${PORT} with ${WORKERS} workers..."
exec uvicorn main:app --host "${HOST}" --port "${PORT}" --workers "${WORKERS}"
