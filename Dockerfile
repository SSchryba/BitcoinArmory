FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
    python-dotenv==1.0.0 \
    requests==2.31.0 \
    redis==5.0.1 \
    web3==6.15.1 \
    docker==7.0.0 \
    psutil==5.9.8

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 monitor \
    && chown -R monitor:monitor /app
USER monitor

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:6379/ping')" || exit 1

# Run the monitor
CMD ["python", "TransactionMonitor.py"] 