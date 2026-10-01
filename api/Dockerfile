# API image for Cloud Run. Build from the repo root: docker build -f api/Dockerfile .
# (The repo root is the context so the image could include shared files later.)

FROM mirror.gcr.io/library/python:3.14-slim-bookworm AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install --no-cache-dir "uv==0.8.17"
WORKDIR /app
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY api/app ./app
COPY api/migrations ./migrations
COPY api/alembic.ini ./

FROM mirror.gcr.io/library/python:3.14-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH" PORT=8080 \
    ENV=prod TRUST_PROXY_HEADERS=true
# Pango and HarfBuzz for payslip PDFs (WeasyPrint); fonts ship with the app.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
USER app
EXPOSE 8080
# One process per container; Cloud Run scales instances. Concurrency is set on the service.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
