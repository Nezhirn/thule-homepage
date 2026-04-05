# =========================
# Production Dockerfile
# =========================
FROM python:3.14-slim AS production

# Metadata
LABEL maintainer="thuleseeker"
LABEL description="Homepage API - FastAPI-based customizable homepage with cards"
LABEL version="1.0.1"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
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

# Create necessary directories for persistent data
RUN mkdir -p /app/data/uploads

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
