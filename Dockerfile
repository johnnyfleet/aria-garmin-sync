FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ARIA_SYNC_DATA_DIR=/data \
    HOME=/tmp \
    TZ=Pacific/Auckland

# Unraid's nobody:users, so files in appdata keep sensible ownership.
USER 99:100
VOLUME /data

# Unhealthy if no successful cycle in 3 poll intervals (default 15 min).
HEALTHCHECK --interval=5m --start-period=2m \
    CMD python -c "import os,sys,time; i=int(os.environ.get('ARIA_SYNC_POLL_INTERVAL','300')); sys.exit(time.time()-os.path.getmtime('/data/heartbeat') > 3*i)"

ENTRYPOINT ["aria-sync"]
CMD ["run"]
