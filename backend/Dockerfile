# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# CPU wheels keep CUDA libraries out of the portable default image.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip pip install -e ".[web,analytics]"

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browsers \
    HF_HOME=/app/.cache/huggingface \
    EMBEDDING_DEVICE=cpu
COPY --from=builder /opt/venv /opt/venv
# Crawling requires both the browser executable and its shared libraries.
RUN python -m playwright install --with-deps chromium \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 qubettera \
    && useradd --uid 10001 --gid qubettera --create-home qubettera \
    && mkdir -p /app/data /app/outputs /app/.cache/huggingface \
    && chown -R qubettera:qubettera /app /home/qubettera
COPY --chown=qubettera:qubettera pyproject.toml README.md ./
COPY --chown=qubettera:qubettera src ./src
COPY --chown=qubettera:qubettera resources ./resources
COPY --chown=qubettera:qubettera backend ./backend
USER qubettera
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
