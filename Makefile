DOCKER_REPO := ghcr.io/x-farmer

# Image / build tag rule (mirrors src/core/Makefile and src/dashboard/Makefile
# so every x-farmer image carries the same revision identifier shape):
#   1) Clean working tree AND HEAD points exactly at a git tag (annotated or
#      lightweight) -> use the tag verbatim (e.g. v1.2.3) so release builds
#      carry a stable, sortable identifier.
#   2) Clean working tree, no tag at HEAD -> <branch>-<7-char short sha>
#      (e.g. dev-fd5663e).
#   3) Dirty working tree (uncommitted changes, tracked or untracked) ->
#      <branch>-<7-char short sha>-<timestamp> (e.g. dev-fd5663e-20260603133000)
#      so every build of not-yet-committed code gets a distinct, non-clobbering
#      tag. The timestamp is recomputed on each invocation, so capture the tag
#      printed at build time and deploy it explicitly.
# Any '/' in the branch name is normalized to '-' because docker tags forbid
# slashes. The same value is baked into the image as XCLIENT_VERSION (and OCI
# labels) so logs, spans, and image tags all agree on a single revision id.
GIT_DIRTY     := $(shell test -n "$$(git status --porcelain 2>/dev/null)" && echo dirty)
GIT_TAG       := $(shell git describe --tags --exact-match HEAD 2>/dev/null)
GIT_BRANCH    := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null | tr '/' '-')
GIT_SHORT_SHA := $(shell git rev-parse --short=7 HEAD 2>/dev/null)
BUILD_STAMP   := $(shell date +%Y%m%d%H%M%S)
IMAGE_TAG     := $(if $(GIT_DIRTY),$(GIT_BRANCH)-$(GIT_SHORT_SHA)-$(BUILD_STAMP),$(if $(GIT_TAG),$(GIT_TAG),$(GIT_BRANCH)-$(GIT_SHORT_SHA)))
VERSION       := $(IMAGE_TAG)

UV ?= uv

# Optional multi-arch build controls (driven by skills/build-image). When
# PLATFORM is non-empty, build-docker switches from `docker build` to
# `docker buildx build --platform $(PLATFORM)`; the value is passed straight
# through to buildx (e.g. `linux/amd64,linux/arm64`). BUILDX_PUSH then selects
# the buildx output: a non-empty value pushes the resulting image/manifest to
# the registry (`--push`, required for multi-platform builds), while an empty
# value loads a single-platform result into the local docker image store
# (`--load`). Both default to empty, so the plain `docker build` path is
# unchanged when PLATFORM is not set.
PLATFORM   ?=
BUILDX_PUSH ?=

.PHONY: install lock sync test \
        build-docker print-image-tag clean

install:
	$(UV) sync

lock:
	$(UV) lock

sync:
	$(UV) sync --frozen

test:
	$(UV) run pytest

build-docker:
ifeq ($(strip $(PLATFORM)),)
	docker build \
	    --build-arg VERSION=$(VERSION) \
	    -t $(DOCKER_REPO)/xclient:$(IMAGE_TAG) \
	    .
else
	docker buildx build \
	    --platform $(PLATFORM) \
	    --build-arg VERSION=$(VERSION) \
	    -t $(DOCKER_REPO)/xclient:$(IMAGE_TAG) \
	    $(if $(strip $(BUILDX_PUSH)),--push,--load) \
	    .
endif

print-image-tag:
	@echo $(IMAGE_TAG)

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__
