.PHONY: build test version bump-patch bump-minor bump-major bump clean

# Single source of truth for the version. pyproject reads it via
# [tool.hatch.version], so only this file needs to be bumped.
VERSION_FILE := kubeman/__init__.py

# Portable in-place edit (BSD/GNU sed differ on -i), so write-then-move.
define set_version
	sed 's/__version__ = ".*"/__version__ = "$(1)"/' $(VERSION_FILE) > $(VERSION_FILE).tmp \
		&& mv $(VERSION_FILE).tmp $(VERSION_FILE)
endef

# Run tests
test:
	uv run pytest

# Build the package
build:
	uv build

# Print the current version
version:
	@grep -E '^__version__' $(VERSION_FILE) | sed 's/__version__ = "\(.*\)"/\1/'

# Bump patch version (0.2.2 -> 0.2.3)
bump-patch:
	@current=$$(grep -E '^__version__' $(VERSION_FILE) | sed 's/__version__ = "\(.*\)"/\1/'); \
	new=$$(echo $$current | awk -F. '{print $$1"."$$2"."$$3+1}'); \
	$(call set_version,$$new); \
	echo "Bumped version from $$current to $$new"

# Bump minor version (0.2.2 -> 0.3.0)
bump-minor:
	@current=$$(grep -E '^__version__' $(VERSION_FILE) | sed 's/__version__ = "\(.*\)"/\1/'); \
	new=$$(echo $$current | awk -F. '{print $$1"."$$2+1".0"}'); \
	$(call set_version,$$new); \
	echo "Bumped version from $$current to $$new"

# Bump major version (0.2.2 -> 1.0.0)
bump-major:
	@current=$$(grep -E '^__version__' $(VERSION_FILE) | sed 's/__version__ = "\(.*\)"/\1/'); \
	new=$$(echo $$current | awk -F. '{print $$1+1".0.0"}'); \
	$(call set_version,$$new); \
	echo "Bumped version from $$current to $$new"

# Bump to a specific version
bump:
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make bump VERSION=x.y.z"; \
		exit 1; \
	fi; \
	$(call set_version,$(VERSION)); \
	echo "Bumped version to $(VERSION)"

# Clean build artifacts
clean:
	rm -rf dist/ build/ *.egg-info/
