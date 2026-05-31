FROM python:3.11-slim

WORKDIR /app

# Build tools for native wheels (e.g. hnswlib pulled in by graphrag-sdk) +
# Node.js for npx-launched MCP connector servers (optional; only used if
# CONNECTORS_ENABLED=true). Node install is cheap and keeps connectors self-contained.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)" || exit 1

# Use the venv built at image-build time directly (avoids re-syncing on every start)
CMD [".venv/bin/uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
