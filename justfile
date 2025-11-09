# Crossbar.io justfile
# See: https://github.com/casey/just

set windows-shell := ["pwsh", "-NoLogo", "-Command"]

# Default recipe (list all recipes)
_default:
    @just --list

# Internal helper to map Python version short name to full uv version spec
_get-spec short_name:
    #!/usr/bin/env bash
    set -e
    case {{short_name}} in
        cpy314)  echo "cpython-3.14";;
        cpy313)  echo "cpython-3.13";;
        cpy312)  echo "cpython-3.12";;
        cpy311)  echo "cpython-3.11";;
        cpy310)  echo "cpython-3.10";;
        pypy311) echo "pypy-3.11";;
        pypy310) echo "pypy-3.10";;
        *)       echo "Unknown environment: {{short_name}}" >&2; exit 1;;
    esac

# Internal helper to get the system's default Python venv name
_get-system-venv-name:
    #!/usr/bin/env bash
    set -e
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    major=$(echo $python_version | cut -d. -f1)
    minor=$(echo $python_version | cut -d. -f2)
    echo "cpy${major}${minor}"

# Internal helper to get the Python executable from a venv
_get-venv-python venv:
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        # Use system Python
        which python3
    else
        # Use venv Python
        if [ -f "{{venv}}/bin/python" ]; then
            echo "{{venv}}/bin/python"
        else
            echo "Error: venv {{venv}} not found or not a valid Python venv" >&2
            exit 1
        fi
    fi

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
    spec=$(just _get-spec {{venv_name}})
    echo "Creating virtual environment {{venv_name}} with Python $spec"
    uv venv --python "$spec" {{venv_name}}

# Install package and dependencies into venv
install venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    venv_to_use="{{venv}}"
    if [ -z "$venv_to_use" ]; then
        venv_to_use=$(just _get-system-venv-name)
    fi
    echo "Installing crossbar into $venv_to_use"
    uv pip install --python "$venv_to_use" -e .

# Install development dependencies into venv
install-dev venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    venv_to_use="{{venv}}"
    if [ -z "$venv_to_use" ]; then
        venv_to_use=$(just _get-system-venv-name)
    fi
    echo "Installing crossbar[dev] into $venv_to_use"
    uv pip install --python "$venv_to_use" -e ".[dev]"

# Install build tools (build, twine) into venv
install-build-tools venv="":
    #!/usr/bin/env bash
    set -e
    venv_to_use="{{venv}}"
    if [ -z "$venv_to_use" ]; then
        venv_to_use=$(just _get-system-venv-name)
    fi
    echo "Installing build tools into $venv_to_use"
    uv pip install --python "$venv_to_use" build twine

# Format code using ruff
format venv="":
    #!/usr/bin/env bash
    set -e
    python_exe=$(just _get-venv-python "{{venv}}")
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    fi
    echo "Formatting with $python_exe"
    $python_exe -m ruff format crossbar

# Lint code using ruff
lint venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    else
        python_exe="{{venv}}/bin/python"
    fi
    echo "Linting with $python_exe"
    $python_exe -m ruff check crossbar

# Auto-format code (ruff format + fix)
autoformat venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    else
        python_exe="{{venv}}/bin/python"
    fi
    echo "Auto-formatting with $python_exe"
    $python_exe -m ruff check --fix crossbar
    $python_exe -m ruff format crossbar

# Check code format (without modifying)
check-format venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    else
        python_exe="{{venv}}/bin/python"
    fi
    echo "Checking format with $python_exe"
    $python_exe -m ruff format --check crossbar

# Type check with mypy (CPython only)
check-types venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    else
        python_exe="{{venv}}/bin/python"
    fi
    echo "Type checking with $python_exe"
    $python_exe -m mypy crossbar

# Security check with bandit
check-security venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    else
        python_exe="{{venv}}/bin/python"
    fi
    echo "Security checking with $python_exe"
    $python_exe -m bandit -r crossbar

# Run all checks (format, lint, types, security)
check venv="": (check-format venv) (lint venv) (check-types venv) (check-security venv)

# Run unit tests with trial (Twisted)
test-trial venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    else
        python_exe="{{venv}}/bin/python"
    fi
    echo "Running trial tests with $python_exe"
    $python_exe -m twisted.trial crossbar

# Run unit tests with pytest
test-pytest venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    else
        python_exe="{{venv}}/bin/python"
    fi
    echo "Running pytest tests with $python_exe"
    $python_exe -m pytest -sv crossbar

# Run all unit tests (trial + pytest)
test venv="": (test-trial venv) (test-pytest venv)

# Run functional tests
test-functional venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="$venv_to_use/bin/python"
    else
        python_exe="{{venv}}/bin/python"
    fi
    echo "Running functional tests with $python_exe"
    $python_exe -m pytest -sv --no-install ./test/functests/cbtests

# Run all tests
test-all venv="": (test venv) (test-functional venv)

# Build documentation with Sphinx
docs venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="../$venv_to_use/bin/python"
    else
        python_exe="../{{venv}}/bin/python"
    fi
    echo "Building docs with $python_exe"
    cd docs && $python_exe -m sphinx -b html . _build

# Check documentation build
docs-check venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="../$venv_to_use/bin/python"
    else
        python_exe="../{{venv}}/bin/python"
    fi
    echo "Checking docs with $python_exe"
    cd docs && $python_exe -m sphinx -nWT -b dummy . _build

# Check documentation spelling
docs-spelling venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
        python_exe="../$venv_to_use/bin/python"
    else
        python_exe="../{{venv}}/bin/python"
    fi
    echo "Checking docs spelling with $python_exe"
    cd docs && $python_exe -m sphinx -nWT -b spelling -d ./_build/doctrees . ./_build/spelling

# Clean documentation build artifacts
docs-clean:
    rm -rf ./docs/_build

# Serve documentation locally
docs-serve: docs-clean
    cd docs && python -m http.server 8090 --directory _build

# Build distribution packages (wheel and sdist)
dist venv="":
    #!/usr/bin/env bash
    set -euo pipefail

    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
    else
        venv_to_use="{{venv}}"
    fi

    # Clean previous builds
    rm -rf dist build *.egg-info

    # Set environment variables for build
    export LMDB_FORCE_CFFI=1
    export SODIUM_INSTALL=bundled
    export PYUBJSON_NO_EXTENSION=1

    echo "Building distribution with $venv_to_use/bin/python"
    $venv_to_use/bin/python -m build --outdir dist

# Verify distribution packages
verify-dist venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
    else
        venv_to_use="{{venv}}"
    fi
    echo "Verifying dist with $venv_to_use/bin/python"
    $venv_to_use/bin/python -m twine check dist/*

# Upload to PyPI (requires authentication)
upload: dist
    twine upload dist/*

# Install from local wheel (useful for testing)
install-wheel venv="" wheel_path="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
    else
        venv_to_use="{{venv}}"
    fi
    echo "Installing wheel {{wheel_path}} into $venv_to_use"
    uv pip install --python "$venv_to_use" --force-reinstall {{wheel_path}}

# Show dependency tree
deps venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
    else
        venv_to_use="{{venv}}"
    fi
    echo "Dependencies in $venv_to_use:"
    $venv_to_use/bin/python -m pip list
    echo ""
    echo "To see detailed dependency tree, install 'pipdeptree' and run:"
    echo "  $venv_to_use/bin/pipdeptree"

# Run crossbar version command (smoke test)
smoke venv="":
    #!/usr/bin/env bash
    set -e
    if [ -z "{{venv}}" ]; then
        venv_to_use=$(just _get-system-venv-name)
    else
        venv_to_use="{{venv}}"
    fi
    echo "Running smoke test with $venv_to_use"
    $venv_to_use/bin/crossbar version

# Complete setup: create venv, install deps, run checks
setup venv: (create venv) (install-dev venv) (check venv) (test venv) (smoke venv)
    @echo "✓ Setup complete for {{venv}}"

# Quick development install (no tests)
dev venv: (create venv) (install-dev venv)
    @echo "✓ Development environment ready: {{venv}}"
