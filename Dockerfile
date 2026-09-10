# =========================
# Production Dockerfile
# =========================
FROM python:3.12-slim

# Metadata
LABEL maintainer="thuleseeker"
LABEL description="Homepage API - FastAPI-based customizable homepage with cards"

ARG APP_VERSION=1.2.1

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_VERSION=${APP_VERSION} \
    PYTHONPATH=/app/backend \
    UPLOADS_DIR=/app/data/uploads \
    DATABASE_PATH=/app/data/homepage.db

# Working directory
WORKDIR /app

# Install dependencies first (better Docker layer caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy frontend code
COPY frontend/ ./frontend/

# Create the unprivileged runtime user and the persistent data directory
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data/uploads \
    && chown -R app:app /app/data

USER app

# Expose port
EXPOSE 8000

# Run the application (PORT is honoured, see README)
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
