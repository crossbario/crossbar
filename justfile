# Crossbar.io justfile
# See: https://github.com/casey/just

set windows-shell := ["pwsh", "-NoLogo", "-Command"]

# Default recipe (list all recipes)
_default:
    @just --list

# Display project version
version:
    @python -c "from crossbar._version import __version__; print(__version__)"

# Clean build artifacts and caches
clean:
    rm -rf ./build
    rm -rf ./dist
    rm -rf ./crossbar.egg-info
    rm -rf ./.crossbar
    rm -rf ./tests
    rm -rf ./.tox
    rm -rf ./vers
    rm -f .coverage.*
    rm -f .coverage
    rm -rf ./htmlcov
    rm -rf ./_trial*
    rm -rf ./pip-wheel-metadata
    rm -rf ./docs/_build
    rm -rf ./.mypy_cache
    rm -rf ./.pytest_cache
    rm -rf ./.ruff_cache
    find . -name "*.db" -exec rm -f {} \;
    find . -name "*.pyc" -exec rm -f {} \;
    find . -name "*.log" -exec rm -f {} \;
    find . \( -name "*__pycache__" -type d \) -prune -exec rm -rf {} +
    -find . -type d -name _trial_temp -exec rm -rf {} \;

# Create a new virtual environment using uv (e.g., cpy311, cpy312, pypy310)
create venv_name:
    #!/usr/bin/env bash
    set -euo pipefail

    # Parse venv name: cpy311 -> cpython 3.11, pypy310 -> pypy 3.10
    if [[ "{{venv_name}}" == cpy* ]]; then
        version="${{venv_name}:3}"
        major="${version:0:1}"
        minor="${version:1}"
        python_version="${major}.${minor}"
        echo "Creating CPython ${python_version} virtual environment: {{venv_name}}"
        uv venv --python ${python_version} {{venv_name}}
    elif [[ "{{venv_name}}" == pypy* ]]; then
        version="${{venv_name}:4}"
        major="${version:0:1}"
        minor="${version:1}"
        python_version="pypy${major}.${minor}"
        echo "Creating PyPy ${major}.${minor} virtual environment: {{venv_name}}"
        uv venv --python ${python_version} {{venv_name}}
    else
        echo "Error: venv name must start with 'cpy' or 'pypy'"
        exit 1
    fi

# Install package and dependencies into venv
install venv_name:
    uv pip install --python {{venv_name}} -e .

# Install development dependencies into venv
install-dev venv_name:
    uv pip install --python {{venv_name}} -e ".[dev]"

# Install build tools (build, twine) into venv
install-build-tools venv_name:
    uv pip install --python {{venv_name}} build twine

# Format code using ruff
format venv_name:
    {{venv_name}}/bin/python -m ruff format crossbar

# Lint code using ruff
lint venv_name:
    {{venv_name}}/bin/python -m ruff check crossbar

# Auto-format code (ruff format + fix)
autoformat venv_name:
    {{venv_name}}/bin/python -m ruff check --fix crossbar
    {{venv_name}}/bin/python -m ruff format crossbar

# Check code format (without modifying)
check-format venv_name:
    {{venv_name}}/bin/python -m ruff format --check crossbar

# Type check with mypy (CPython only)
check-types venv_name:
    {{venv_name}}/bin/python -m mypy crossbar

# Security check with bandit
check-security venv_name:
    {{venv_name}}/bin/python -m bandit -r crossbar

# Run all checks (format, lint, types, security)
check venv_name: (check-format venv_name) (lint venv_name) (check-types venv_name) (check-security venv_name)

# Run unit tests with trial (Twisted)
test-trial venv_name:
    {{venv_name}}/bin/python -m twisted.trial crossbar

# Run unit tests with pytest
test-pytest venv_name:
    {{venv_name}}/bin/python -m pytest -sv crossbar

# Run all unit tests (trial + pytest)
test venv_name: (test-trial venv_name) (test-pytest venv_name)

# Run functional tests
test-functional venv_name:
    {{venv_name}}/bin/python -m pytest -sv --no-install ./test/functests/cbtests

# Run all tests
test-all venv_name: (test venv_name) (test-functional venv_name)

# Build documentation with Sphinx
docs venv_name:
    cd docs && ../{{venv_name}}/bin/python -m sphinx -b html . _build

# Check documentation build
docs-check venv_name:
    cd docs && ../{{venv_name}}/bin/python -m sphinx -nWT -b dummy . _build

# Check documentation spelling
docs-spelling venv_name:
    cd docs && ../{{venv_name}}/bin/python -m sphinx -nWT -b spelling -d ./_build/doctrees . ./_build/spelling

# Clean documentation build artifacts
docs-clean:
    rm -rf ./docs/_build

# Serve documentation locally
docs-serve: docs-clean
    cd docs && python -m http.server 8090 --directory _build

# Build distribution packages (wheel and sdist)
dist venv_name:
    #!/usr/bin/env bash
    set -euo pipefail

    # Clean previous builds
    rm -rf dist build *.egg-info

    # Set environment variables for build
    export LMDB_FORCE_CFFI=1
    export SODIUM_INSTALL=bundled
    export PYUBJSON_NO_EXTENSION=1

    # Build with uv
    {{venv_name}}/bin/python -m build --outdir dist

# Verify distribution packages
verify-dist venv_name:
    {{venv_name}}/bin/python -m twine check dist/*

# Upload to PyPI (requires authentication)
upload: dist
    twine upload dist/*

# Install from local wheel (useful for testing)
install-wheel venv_name wheel_path:
    uv pip install --python {{venv_name}} --force-reinstall {{wheel_path}}

# Show dependency tree
deps venv_name:
    {{venv_name}}/bin/python -m pip list
    @echo ""
    @echo "To see detailed dependency tree, install 'pipdeptree' and run:"
    @echo "  {{venv_name}}/bin/pipdeptree"

# Run crossbar version command (smoke test)
smoke venv_name:
    {{venv_name}}/bin/crossbar version

# Complete setup: create venv, install deps, run checks
setup venv_name: (create venv_name) (install-dev venv_name) (check venv_name) (test venv_name) (smoke venv_name)
    @echo "✓ Setup complete for {{venv_name}}"

# Quick development install (no tests)
dev venv_name: (create venv_name) (install-dev venv_name)
    @echo "✓ Development environment ready: {{venv_name}}"
