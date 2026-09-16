FROM python:3.12-slim AS base

# Security improvement: run as non-root user
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

WORKDIR /app

# Install system dependencies in a separate layer for better caching.
# Only install what's strictly necessary (gcc for compiled Python packages).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies BEFORE copying source code.
# This layer is cached as long as requirements.txt doesn't change,
# making subsequent builds much faster.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (changes more frequently than dependencies)
COPY . .

# Switch to non-root user before running the app
RUN chown -R appuser:appgroup /app
USER appuser

# Run migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
