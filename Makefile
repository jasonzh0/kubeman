.PHONY: build bump-patch bump-minor bump-major bump clean

# Run tests
test:
	uv run pytest tests/ -v

# Build the package
build:
	uv build

# Bump patch version (0.2.2 -> 0.2.3)
bump-patch:
	@current=$$(grep -E '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	new=$$(echo $$current | awk -F. '{print $$1"."$$2"."$$3+1}'); \
	sed -i '' "s/version = \".*\"/version = \"$$new\"/" pyproject.toml; \
	sed -i '' "s/__version__ = \".*\"/__version__ = \"$$new\"/" kubeman/__init__.py; \
	echo "Bumped version from $$current to $$new"

# Bump minor version (0.2.2 -> 0.3.0)
bump-minor:
	@current=$$(grep -E '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	new=$$(echo $$current | awk -F. '{print $$1"."$$2+1".0"}'); \
	sed -i '' "s/version = \".*\"/version = \"$$new\"/" pyproject.toml; \
	sed -i '' "s/__version__ = \".*\"/__version__ = \"$$new\"/" kubeman/__init__.py; \
	echo "Bumped version from $$current to $$new"

# Bump major version (0.2.2 -> 1.0.0)
bump-major:
	@current=$$(grep -E '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	new=$$(echo $$current | awk -F. '{print $$1+1".0.0"}'); \
	sed -i '' "s/version = \".*\"/version = \"$$new\"/" pyproject.toml; \
	sed -i '' "s/__version__ = \".*\"/__version__ = \"$$new\"/" kubeman/__init__.py; \
	echo "Bumped version from $$current to $$new"

# Bump to a specific version
bump:
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make bump VERSION=x.y.z"; \
		exit 1; \
	fi; \
	sed -i '' "s/version = \".*\"/version = \"$(VERSION)\"/" pyproject.toml; \
	sed -i '' "s/__version__ = \".*\"/__version__ = \"$(VERSION)\"/" kubeman/__init__.py; \
	echo "Bumped version to $(VERSION)"

# Clean build artifacts
clean:
	rm -rf dist/ build/ *.egg-info/
