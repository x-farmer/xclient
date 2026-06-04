#!/usr/bin/env bash
#
# Build the x-farmer XClient OCI image. The image name is
# {registry}/{namespace}/xclient:{tag}, e.g. ghcr.io/x-farmer/xclient:<tag>.
#
# Run from the XClient project root (the directory holding this project's
# Makefile and Dockerfile). The image tag follows the project tag rule (see
# below) and is owned by the Makefile (`make print-image-tag`), matching the
# Core and Dashboard images so every x-farmer image shares the same revision
# identifier shape.
#
# Tag rule:
#   1) Clean tree + HEAD at a git tag           -> <tag>            (e.g. v1.2.3)
#   2) Clean tree, no tag at HEAD               -> <branch>-<sha7>  (e.g. dev-fd5663e)
#   3) Dirty tree (uncommitted changes)         -> <branch>-<sha7>-<timestamp>
#
# Usage:
#   skills/build-image/scripts/build-image.sh [flags]
#
# The XClient project produces a single image (xclient), so there is no target
# argument.
#
# Flags:
#   --tag <tag>          Override the resolved image tag (use the exact same tag
#                        when deploying a dirty build, whose timestamp changes).
#   --registry <reg>     Registry host in the image name (default: ghcr.io).
#   --namespace <ns>     Namespace/org in the image name (default: x-farmer).
#   --platform <list>    Build for the given platform(s) with `docker buildx`
#                        (value passed straight through, e.g.
#                        linux/amd64,linux/arm64). Without this flag a plain
#                        `docker build` for the host platform is used. A
#                        multi-platform list requires --push (buildx cannot
#                        --load a multi-arch image into the local store).
#   --print-tag          Print the resolved image tag and exit without building.
#   --push               Push the image after a successful build (for --platform
#                        builds the push happens as part of the buildx build).
#   -h, --help           Show this help.
#
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

IMAGE_NAME="xclient"
REGISTRY="ghcr.io"
NAMESPACE="x-farmer"
TAG_OVERRIDE=""
PLATFORM=""
PRINT_TAG=0
PUSH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)       TAG_OVERRIDE="${2:-}"; shift 2 ;;
    --registry)  REGISTRY="${2:-}"; shift 2 ;;
    --namespace) NAMESPACE="${2:-}"; shift 2 ;;
    --platform)  PLATFORM="${2:-}"; shift 2 ;;
    --print-tag) PRINT_TAG=1; shift ;;
    --push)      PUSH=1; shift ;;
    -h|--help)
      awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"; exit 0 ;;
    -*) die "unknown flag: $1" ;;
    *)  die "unexpected argument: $1 (this skill builds the single 'xclient' image and takes no target)" ;;
  esac
done

[[ -n "$REGISTRY" ]]  || die "--registry must not be empty"
[[ -n "$NAMESPACE" ]] || die "--namespace must not be empty"
# Image name = {registry}/{namespace}/xclient:{tag}. DOCKER_REPO is the
# {registry}/{namespace} prefix and is passed to make to override its default.
DOCKER_REPO="${REGISTRY}/${NAMESPACE}"

[[ -f Makefile && -f Dockerfile ]] || die "run from the XClient project root (Makefile and Dockerfile must be here)"

# The Makefile is the single source of truth for the tag rule; reuse it unless
# the caller pins a tag explicitly.
if [[ -n "$TAG_OVERRIDE" ]]; then
  TAG="$TAG_OVERRIDE"
else
  TAG="$(make print-image-tag 2>/dev/null || true)"
  [[ -n "$TAG" ]] || die "could not resolve image tag via 'make print-image-tag'; pass --tag"
fi

if [[ "$PRINT_TAG" == "1" ]]; then
  echo "$TAG"
  exit 0
fi

command -v docker >/dev/null 2>&1 || die "docker is required to build images"

REF="${DOCKER_REPO}/${IMAGE_NAME}:${TAG}"

# Override IMAGE_TAG so the make target tags and stamps the image with the tag
# resolved here (important for dirty builds, whose timestamp would otherwise be
# recomputed inside make, and when pinning --tag), and DOCKER_REPO so the image
# name uses the requested {registry}/{namespace} prefix.
if [[ -n "$PLATFORM" ]]; then
  # buildx path: the make target runs `docker buildx build --platform`. A
  # multi-platform manifest cannot be loaded into the local docker store, so it
  # must be pushed in the same step; fail early with a clear message instead of
  # letting buildx error out on `--load`.
  docker buildx version >/dev/null 2>&1 \
    || die "docker buildx is required for --platform builds (install the buildx plugin)"
  if [[ "$PLATFORM" == *,* && "$PUSH" != "1" ]]; then
    die "multi-platform --platform '$PLATFORM' requires --push (buildx cannot --load a multi-arch image locally)"
  fi

  # Tell the make target to push (--push) or load (--load) the buildx result.
  BUILDX_PUSH=""
  if [[ "$PUSH" == "1" ]]; then BUILDX_PUSH="1"; fi

  echo ">> Building ${REF} (buildx, platform: ${PLATFORM}$( [[ "$PUSH" == "1" ]] && echo ', push' || echo ', load' ))"
  make build-docker IMAGE_TAG="$TAG" DOCKER_REPO="$DOCKER_REPO" PLATFORM="$PLATFORM" BUILDX_PUSH="$BUILDX_PUSH"
else
  echo ">> Building ${REF}"
  make build-docker IMAGE_TAG="$TAG" DOCKER_REPO="$DOCKER_REPO"
  if [[ "$PUSH" == "1" ]]; then
    echo ">> Pushing ${REF}"
    docker push "$REF"
  fi
fi

echo ">> Done. Built image:"
echo "   ${REF}"
exit 0
