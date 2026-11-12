FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install Ghostscript and QPDF for hybrid PDF optimization
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    qpdf \
    libqpdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and ephemeral workspace directory
RUN useradd -m -u 10001 appuser && \
    mkdir -p /tmp/optipdf_ephemeral_store && \
    chown -R appuser:appuser /tmp/optipdf_ephemeral_store

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
