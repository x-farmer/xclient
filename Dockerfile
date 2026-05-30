# syntax=docker/dockerfile:1.7
#
# x-farmer/xclient Dockerfile.
#
# Two-stage build: a CPython 3.11 toolchain stage resolves the pinned
# dependency closure from uv.lock into an installable tree, and a distroless
# Python 3.11 runtime stage ships only the interpreter, deps, and source.
#
# Base image alignment:
#   The runtime image gcr.io/distroless/python3-debian12:nonroot ships
#   CPython 3.11.2. The builder therefore uses python:3.11-slim-bookworm so
#   compiled wheels (e.g. pydantic_core's Rust extension) match the runtime
#   ABI exactly. Pure-Python and abi3 wheels work across both stages.
#
#   The project pyproject.toml declares `requires-python = ">=3.12"`, but
#   every source file parses cleanly under 3.11 and every runtime dependency
#   supports 3.11. To avoid triggering the project's `requires-python` gate
#   we install the locked dependency set without installing the project
#   itself, then drop the package source onto PYTHONPATH so the CLI is
#   reachable via `python -m xclient`.
#
# Build (preferred — uses the Makefile tag rule):
#
#   make build-docker
#
# Build (manual):
#
#   docker build \
#       --build-arg VERSION=<tag> \
#       -t ghcr.io/x-farmer/xclient:<tag> \
#       .
#
# Run:
#
#   docker run --rm ghcr.io/x-farmer/xclient:<tag> --help
#   docker run --rm -e OPENAI_API_KEY=... ghcr.io/x-farmer/xclient:<tag> \
#       chat --prompt "hello"

# ---------------------------------------------------------------------------
# build: install uv, freeze uv.lock into a requirements.txt, and materialise
# the dependency closure under /install. The xclient package itself is
# copied in afterwards so it lives next to its deps on PYTHONPATH without
# going through pip install (which would enforce requires-python>=3.12).
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS build

WORKDIR /src

# uv handles the lockfile; pip is reused for the actual install step because
# it natively understands `--target` for non-venv site-packages layouts.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir uv==0.5.5

COPY pyproject.toml uv.lock ./

# Freeze the locked dependency set into a flat requirements list. The
# --no-emit-project flag deliberately drops the xclient package itself: we
# only want its dependency closure here, not an install of the project.
#
# --no-hashes is required because uv.lock was resolved against the project's
# declared `requires-python = ">=3.12"`, so it only records hashes for cp312+
# wheels. The distroless runtime ships Python 3.11.2, so pip must be free to
# pick the cp311 wheel of every native dep (grpcio, pydantic-core, ...). The
# version pins (`==`) in the exported file still enforce the lockfile's
# resolution; only the per-file hash check is relaxed.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export \
        --frozen \
        --no-emit-project \
        --no-dev \
        --no-hashes \
        --format requirements-txt \
        -o /tmp/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
        --no-cache-dir \
        --no-compile \
        --target=/install \
        -r /tmp/requirements.txt

# Drop the package source alongside the installed deps. The distroless
# runtime sets PYTHONPATH=/app so `python -m xclient` resolves both this
# package and its dependencies from a single directory tree.
COPY src/xclient /install/xclient

# ---------------------------------------------------------------------------
# runtime: distroless Python 3.11 with the nonroot UID. The image carries
# no shell, package manager, or build tools — only the interpreter, our
# dependency closure, and the xclient package.
# ---------------------------------------------------------------------------
FROM gcr.io/distroless/python3-debian12:nonroot AS runtime

ARG VERSION=development
LABEL org.opencontainers.image.title="x-farmer xclient ${VERSION}" \
      org.opencontainers.image.description="Thin OpenAI-compatible CLI client for x-farmer API Gateway testing." \
      org.opencontainers.image.source="https://github.com/x-farmer/xclient" \
      org.opencontainers.image.vendor="x-farmer" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0"

COPY --from=build /install /app

# PYTHONPATH lets `python -m xclient` find both the package and its deps
# without a venv (venvs would carry builder-specific absolute interpreter
# paths that do not exist inside the distroless runtime).
# PYTHONDONTWRITEBYTECODE avoids polluting the read-only image with .pyc
# files on first run; PYTHONUNBUFFERED keeps logs flowing through stdio
# when the container is run non-interactively.
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XCLIENT_VERSION=${VERSION}

ENTRYPOINT ["/usr/bin/python3.11", "-m", "xclient"]
