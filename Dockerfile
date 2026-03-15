FROM python:3.11-slim

# Create non-root user
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Install deps before copying code (better layer caching)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application code
COPY . /app

# Transfer ownership and drop privileges
RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s \
    CMD curl -f http://localhost:5000/health || exit 1

EXPOSE 5000

CMD ["gunicorn", "backend.app:create_app()", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-"]
