# =============================================================================
# Egreen-Quanta Backend Production Dockerfile
# =============================================================================

FROM python:3.12-slim AS runner

# Set working directory
WORKDIR /app

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install system dependencies required for building C extensions and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code, database configurations, and migrations
COPY main.py tutor_prompt.py simulate_bell.py alembic.ini ./
COPY alembic/ ./alembic/
COPY db/ ./db/
COPY docker-entrypoint.sh ./

# Create non-privileged user and adjust permissions
RUN useradd -m -u 1000 quanta && \
    chmod +x docker-entrypoint.sh && \
    chown -R quanta:quanta /app

# Switch to non-root user
USER quanta

# Expose backend port
EXPOSE 8000

# Docker healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]
