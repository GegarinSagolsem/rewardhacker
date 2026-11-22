# RewardHacker images (one Dockerfile, two targets):
#   api    (default) Cloud Run: FastAPI + the built dashboard on one origin.
#   worker           Cloud Build step: `rh worker --once`, drives the build machine's Docker
#                    daemon through its socket (Cloud Run has no Docker daemon).

# --- dashboard ---------------------------------------------------------------------------
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- shared Python runtime ---------------------------------------------------------------
FROM python:3.12-slim AS py
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv PYTHONUNBUFFERED=1
WORKDIR /app
# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project --extra api --extra llm --extra gcs
COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --extra api --extra llm --extra gcs
ENV PATH=/app/.venv/bin:$PATH

# --- worker ------------------------------------------------------------------------------
FROM py AS worker
COPY --from=docker:29-cli /usr/local/bin/docker /usr/local/bin/docker
# Root is needed for the Docker socket; the machine is a throwaway Cloud Build VM.
ENV RH_STORAGE_DIR=/tmp/rh/tasks
ENTRYPOINT ["rh"]
CMD ["worker", "--once", "--idle-exit", "45"]

# --- api (default target) ----------------------------------------------------------------
FROM py AS api
COPY --from=web /web/dist /app/web
RUN useradd --uid 10001 --no-create-home app && mkdir -p /tmp/rh && chown app /tmp/rh
USER app
# Cloud Run's filesystem is in-memory: keep the task-extraction cache small and in /tmp.
ENV RH_WEB_DIR=/app/web RH_STORAGE_DIR=/tmp/rh/tasks RH_EXPORTS_DIR=/tmp/rh/exports PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn rewardhacker.api.app:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
