# Multi-stage build for efficient image
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Ensure scripts are in PATH
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app:$PYTHONPATH

# Switch to non-root user
USER appuser

# Pre-build the index during image build (optional - comment out if you want to build at runtime)
# This requires the httpx repo to be present during build
RUN if [ -d "./httpx" ]; then \
        python app.py index || echo "Index pre-build failed, will build at runtime"; \
    fi

# Default command - show help
CMD ["python", "app.py", "--help"]
