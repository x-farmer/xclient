DOCKER_REPO := ghcr.io/x-farmer

# Image / build tag rule (mirrors src/core/Makefile and src/dashboard/Makefile
# so every x-farmer image carries the same revision identifier shape):
#   1) If HEAD points exactly at a git tag (annotated or lightweight), use
#      the tag verbatim (e.g. v1.2.3) so release builds carry a stable,
#      sortable identifier.
#   2) Otherwise compose <branch>-<7-char short sha> (e.g. dev-fd5663e). Any
#      '/' in the branch name is normalized to '-' because docker tags
#      forbid slashes.
# The same value is baked into the image as XCLIENT_VERSION (and OCI labels)
# so logs, spans, and image tags all agree on a single revision identifier.
GIT_TAG       := $(shell git describe --tags --exact-match HEAD 2>/dev/null)
GIT_BRANCH    := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null | tr '/' '-')
GIT_SHORT_SHA := $(shell git rev-parse --short=7 HEAD 2>/dev/null)
IMAGE_TAG     := $(if $(GIT_TAG),$(GIT_TAG),$(GIT_BRANCH)-$(GIT_SHORT_SHA))
VERSION       := $(IMAGE_TAG)

UV ?= uv

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
	docker build \
	    --build-arg VERSION=$(VERSION) \
	    -t $(DOCKER_REPO)/xclient:$(IMAGE_TAG) \
	    .

print-image-tag:
	@echo $(IMAGE_TAG)

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__
