FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)" || exit 1

# Use the venv built at image-build time directly (avoids re-syncing on every start)
CMD [".venv/bin/uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
