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

# Embed the deploy name into the image.
# Setting a different ENV value (via build-arg) SHOULD just
# break the cache as we build it. But by experiment I've seen
# that it does not. Therefore, create a file with the contents
# of the deploy env var to forcibly break the cache and get
# a new image ID each time we change the deploy.
# https://github.com/containers/buildah/issues/5095
ARG MEDB_DEPLOY
RUN echo "${MEDB_DEPLOY:-development}" >/deploy.txt
ENV MEDB_DEPLOY=${MEDB_DEPLOY:-development}
CMD uv run --no-dev --frozen gunicorn -w 4 -b 0.0.0.0:4000 'autoapp:app'
# For celery: uv run --no-dev --frozen celery --app=autoapp:celery worker
