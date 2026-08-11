FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install system dependencies (curl for healthcheck, ffmpeg for video audio extraction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user and group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Set directory ownership to non-root user
RUN chown -R appuser:appgroup ${APP_HOME}

# Switch to non-root user
USER appuser

# Expose FastAPI application port
EXPOSE 8000

# Container Liveness Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Command to run application via Uvicorn with SIGTERM handling
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
