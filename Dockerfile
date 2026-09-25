# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app

# Install deps first for layer caching
COPY pyproject.toml uv.lock ./
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then uv sync --frozen; else uv sync --frozen --no-dev; fi

# Separate interpreter for the grading sandbox, pinned to the Pyodide package versions so
# a snippet behaves the same in the browser and on the server (see harness/requirements.txt).
COPY harness/requirements.txt /tmp/harness-requirements.txt
RUN uv venv /opt/harness-venv && \
    VIRTUAL_ENV=/opt/harness-venv uv pip install --no-cache -r /tmp/harness-requirements.txt
ENV SANDBOX_PYTHON=/opt/harness-venv/bin/python

COPY . .

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000
# Render injects $PORT; default 8000 locally
CMD ["sh", "-c", "alembic upgrade head && python -m app.games.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
