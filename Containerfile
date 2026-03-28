FROM docker.io/python:3.14-slim
WORKDIR /app

# Fast-CLI and Speedtest-CLI rarely get updated
COPY utils/fast-cli utils/speedtest /bin/

# Setup uv & dependencies first for caching
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml setup.cfg uv.lock /app/
RUN uv sync --locked --no-dev

# Add project files later for speedy rebuilds
COPY --parents ./medb/ ./migrations/ autoapp.py /app/

ARG MEDB_DEPLOY
ENV MEDB_DEPLOY=${MEDB_DEPLOY:-development}
CMD uv run --no-dev --frozen gunicorn -w 4 -b 0.0.0.0:4000 'autoapp:app'
# For celery: uv run --no-dev --frozen celery --app=autoapp:celery worker
