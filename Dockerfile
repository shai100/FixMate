# Image for the FixMate Celery ingestion worker (docker-compose `worker` service).
#
# The worker runs the slow ingestion pipeline (PDF extract -> chunk -> embed ->
# caption -> store) off the request path. It is the same `fixmate` package the
# host API runs, just launched as a Celery worker instead of uvicorn. Backing
# services (Postgres, Redis, MinIO, Ollama) are reached over the compose network
# via env overrides set in docker-compose.yml.
FROM python:3.12-slim

WORKDIR /app

# Install runtime deps first (cached layer), keyed only on package metadata so a
# code change doesn't force a dependency reinstall. PyMuPDF/asyncpg ship manylinux
# wheels, so no compiler toolchain is needed in the image.
COPY pyproject.toml ./
COPY fixmate ./fixmate
RUN pip install --no-cache-dir .

# Default to the Linux prefork pool (the `--pool=solo` workaround is Windows-only,
# spec/setup §9). `-l info` mirrors the documented host invocation so the logs the
# worker prints are identical whether it runs on the host or in this container.
CMD ["celery", "-A", "fixmate.ingestion.tasks", "worker", "-l", "info"]
