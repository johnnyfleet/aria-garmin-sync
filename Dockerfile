# Base images are pinned by digest so Dependabot proposes (and CI tests) upstream rebuilds,
# including security-only rebuilds of the same tag.
FROM ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 AS uv

FROM python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv

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

# Starts as root so Unraid's Tailscale hook can install itself; aria-sync then
# drops to PUID:PGID (default 99:100, Unraid's nobody:users) before doing anything.
ENV PUID=99 PGID=100
VOLUME /data
EXPOSE 8080

# Unhealthy if no successful cycle in 3 poll intervals (default 15 min).
HEALTHCHECK --interval=5m --start-period=2m \
    CMD python -c "import os,sys,time; i=int(os.environ.get('ARIA_SYNC_POLL_INTERVAL','300')); sys.exit(time.time()-os.path.getmtime('/data/heartbeat') > 3*i)"

ENTRYPOINT ["aria-sync"]
CMD ["run"]
