.PHONY: all push clean release

# Variables that can be overridden from command line
PLATFORMS ?= linux/amd64,linux/arm64,linux/arm/v7,linux/arm/v6,linux/arm/v5,linux/ppc64le,linux/s390x
TAG ?= nightly
IMAGE_NAME ?= clustermeerkat/wg-obf-easy
MULTIARCH_IMAGE := $(IMAGE_NAME):$(TAG)

# Parse version from backend/version.py
VERSION := $(shell grep -E "^VERSION\s*=\s*" backend/version.py | sed -E "s/^VERSION\s*=\s*['\"](.*)['\"].*/\1/")

# Default target
all: build

# Build multi-arch image without push
build:
	rm -rf static
	cd frontend && npm install
	cd frontend && npm run build
	docker buildx build --platform $(PLATFORMS) -t $(MULTIARCH_IMAGE) .

# Build and push multi-arch image
push:
	rm -rf static
	cd frontend && npm install
	cd frontend && npm run build
	docker buildx build --platform $(PLATFORMS) -t $(MULTIARCH_IMAGE) --push .

# Clean build artifacts
clean:
	rm -rf static
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true

# Build and push with version from backend/version.py
release:
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: Could not parse VERSION from backend/version.py"; \
		exit 1; \
	fi
	rm -rf static
	cd frontend && npm install
	cd frontend && npm run build
	docker buildx build --platform $(PLATFORMS) -t $(IMAGE_NAME):$(VERSION) --push .
