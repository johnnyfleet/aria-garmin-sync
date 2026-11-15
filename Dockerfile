# Base images are pinned by digest so Dependabot proposes (and CI tests) upstream rebuilds,
# including security-only rebuilds of the same tag.
FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

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

# Unhealthy if no successful cycle in 3 poll intervals (default 3 hours).
HEALTHCHECK --interval=5m --start-period=2m \
    CMD python -c "import os,sys,time; i=int(os.environ.get('ARIA_SYNC_POLL_INTERVAL','3600')); sys.exit(time.time()-os.path.getmtime('/data/heartbeat') > 3*i)"

ENTRYPOINT ["aria-sync"]
CMD ["run"]
