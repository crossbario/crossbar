# Crossbar.io justfile
# See: https://github.com/casey/just

# -----------------------------------------------------------------------------
# -- just global configuration
# -----------------------------------------------------------------------------

set unstable := true
set positional-arguments := true

# project base directory = directory of this justfile
PROJECT_DIR := justfile_directory()

# Default recipe: show project info and list all recipes
default:
    #!/usr/bin/env bash
    set -e
    VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/.*= *"\(.*\)"/\1/')
    GIT_REV=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    echo ""
    echo "==============================================================================="
    echo "                              Crossbar.io                                      "
    echo ""
    echo "    Multi-protocol (WAMP/WebSocket, REST/HTTP, MQTT) application router       "
    echo "    for microservices and distributed applications                            "
    echo ""
    echo "   Python Package:         crossbar                                           "
    echo "   Python Package Version: ${VERSION}                                         "
    echo "   Git Version:            ${GIT_REV}                                         "
    echo "   Protocol Specification: https://wamp-proto.org/                            "
    echo "   Documentation:          https://crossbar.io/docs/                          "
    echo "   Package Releases:       https://pypi.org/project/crossbar/                 "
    echo "   Source Code:            https://github.com/crossbario/crossbar             "
    echo "   Copyright:              typedef int GmbH (Germany/EU)                      "
    echo "   License:                EUPL-1.2                                           "
    echo ""
    echo "       >>>   Created by The WAMP/Autobahn/Crossbar.io OSS Project   <<<       "
    echo "==============================================================================="
    echo ""
    just --list
    echo ""

# Tell uv to use project-local cache directory.
export UV_CACHE_DIR := './.uv-cache'

# Use this common single directory for all uv venvs.
VENV_DIR := './.venvs'

# Define a justfile-local variable for our environments.
ENVS := 'cpy314 cpy313 cpy312 cpy311 pypy311'

# -----------------------------------------------------------------------------
# -- Helper recipes
# -----------------------------------------------------------------------------

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

# Internal helper that calculates and prints the system-matching venv name.
_get-system-venv-name:
    #!/usr/bin/env bash
    set -e
    SYSTEM_VERSION=$(/usr/bin/python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    ENV_NAME="cpy$(echo ${SYSTEM_VERSION} | tr -d '.')"

    if ! echo "{{ ENVS }}" | grep -q -w "${ENV_NAME}"; then
        echo "Error: System Python (${SYSTEM_VERSION}) maps to '${ENV_NAME}', which is not a supported environment in this project." >&2
        exit 1
    fi
    # The only output of this recipe is the name itself.
    echo "${ENV_NAME}"

# Helper recipe to get the python executable path for a venv
_get-venv-python venv="":
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        VENV_NAME=$(just --quiet _get-system-venv-name)
    fi
    VENV_PATH="{{VENV_DIR}}/${VENV_NAME}"

    if [[ "$OS" == "Windows_NT" ]]; then
        echo "${VENV_PATH}/Scripts/python.exe"
    else
        echo "${VENV_PATH}/bin/python3"
    fi

# -----------------------------------------------------------------------------
# -- General/global helper recipes
# -----------------------------------------------------------------------------

# Remove ALL generated files, including venvs, caches, and build artifacts. WARNING: This is a destructive operation.
distclean:
    #!/usr/bin/env bash
    set -e

    echo "==> Performing a deep clean (distclean)..."

    # 1. Remove top-level directories known to us.
    echo "--> Removing venvs, cache, and build/dist directories..."
    rm -rf {{UV_CACHE_DIR}} {{VENV_DIR}} build/ dist/ wheelhouse/ .pytest_cache/ .ruff_cache/ .mypy_cache/
    rm -rf docs/_build/

    rm -f ./*.so
    rm -f ./.coverage.*
    rm -rf ./_trial_temp

    # 2. Use `find` to hunt down and destroy nested artifacts
    echo "--> Searching for and removing nested Python caches..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    echo "--> Searching for and removing compiled Python files..."
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true

    echo "--> Searching for and removing setuptools egg-info directories..."
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

    echo "--> Searching for and removing coverage data..."
    rm -f .coverage
    find . -type f -name ".coverage.*" -delete 2>/dev/null || true

    echo "==> Distclean complete. The project is now pristine."

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
    find . -name "*.db" -exec rm -f {} \; 2>/dev/null || true
    find . -name "*.pyc" -exec rm -f {} \; 2>/dev/null || true
    find . -name "*.log" -exec rm -f {} \; 2>/dev/null || true
    find . \( -name "*__pycache__" -type d \) -prune -exec rm -rf {} + 2>/dev/null || true
    -find . -type d -name _trial_temp -exec rm -rf {} \; 2>/dev/null || true

# -----------------------------------------------------------------------------
# -- Python virtual environments
# -----------------------------------------------------------------------------

# List all Python virtual environments
list-all:
    #!/usr/bin/env bash
    set -e
    echo
    echo "Available CPython run-times:"
    echo "============================"
    echo
    uv python list --all-platforms cpython
    echo
    echo "Available PyPy run-times:"
    echo "========================="
    echo
    uv python list --all-platforms pypy
    echo
    echo "Mapped Python run-time shortname => full version:"
    echo "================================================="
    echo
    for env in {{ENVS}}; do
        spec=$(just --quiet _get-spec "$env")
        echo "  - $env => $spec"
    done
    echo
    echo "Create a Python venv using: just create <shortname>"

# Create a single Python virtual environment (usage: `just create cpy312` or `just create`)
create venv="":
    #!/usr/bin/env bash
    set -e

    VENV_NAME="{{ venv }}"

    # This is the "default parameter" logic.
    # If VENV_NAME is empty (because `just create` was run), calculate the default.
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi

    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")

    # Only create the venv if it doesn't already exist
    if [ ! -d "${VENV_PATH}" ]; then
        # Get the Python spec just-in-time
        PYTHON_SPEC=$(just --quiet _get-spec "${VENV_NAME}")

        echo "==> Creating Python virtual environment '${VENV_NAME}' using ${PYTHON_SPEC} in ${VENV_PATH}..."
        mkdir -p "{{ VENV_DIR }}"
        uv venv --seed --python "${PYTHON_SPEC}" "${VENV_PATH}"
        echo "==> Successfully created venv '${VENV_NAME}'."
    else
        echo "==> Python virtual environment '${VENV_NAME}' already exists in ${VENV_PATH}."
    fi

    ${VENV_PYTHON} -V
    ${VENV_PYTHON} -m pip -V

    echo "==> Activate Python virtual environment with: source ${VENV_PATH}/bin/activate"

# Meta-recipe to run `create` on all environments
create-all:
    #!/usr/bin/env bash
    for venv in {{ENVS}}; do
        just create ${venv}
    done

# Get the version of a single virtual environment's Python (usage: `just version-venv cpy312`)
version-venv venv="":
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"

    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi

    if [ -d "{{ VENV_DIR }}/${VENV_NAME}" ]; then
        echo "==> Python virtual environment '${VENV_NAME}' exists:"
        "{{VENV_DIR}}/${VENV_NAME}/bin/python" -V
    else
        echo "==> Python virtual environment '${VENV_NAME}' does not exist."
    fi
    echo ""

# Get versions of all Python virtual environments
version-all:
    #!/usr/bin/env bash
    for venv in {{ENVS}}; do
        just version-venv ${venv}
    done

# -----------------------------------------------------------------------------
# -- Installation
# -----------------------------------------------------------------------------

# Install this package and its run-time dependencies in a single environment (usage: `just install cpy312` or `just install`)
install venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Installing package with package runtime dependencies in ${VENV_NAME}..."
    ${VENV_PYTHON} -m pip install .

# Install this package in development (editable) mode and its run-time dependencies in a single environment (usage: `just install-dev cpy312` or `just install-dev`)
install-dev venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Installing package - in editable mode - with package runtime dependencies in ${VENV_NAME}..."
    ${VENV_PYTHON} -m pip install -e .[dev]

# Meta-recipe to run `install` on all environments
install-all:
    #!/usr/bin/env bash
    set -e
    for venv in {{ENVS}}; do
        just install ${venv}
    done

# Meta-recipe to run `install-dev` on all environments
install-dev-all:
    #!/usr/bin/env bash
    for venv in {{ENVS}}; do
        just install-dev ${venv}
    done

# Install with latest unreleased WAMP packages from GitHub (usage: `just install-dev-latest cpy312` or `just install-dev-latest`)
install-dev-latest venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Installing package in editable mode with [dev,dev-latest] extras in ${VENV_NAME}..."
    echo "==> This will install WAMP packages from GitHub master (unreleased versions)..."
    ${VENV_PYTHON} -m pip install -e .[dev,dev-latest]

# Install with locally editable WAMP packages for cross-repo development (usage: `just install-dev-local cpy312` or `just install-dev-local`)
install-dev-local venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")

    echo "==> Installing WAMP packages in editable mode from local repos..."
    echo "==> Looking for sibling repos (../txaio, ../autobahn-python, etc.)..."

    # Install local WAMP packages in editable mode
    # txaio - no extras needed
    if [ -d "../txaio" ]; then
        echo "  ✓ Installing txaio from ../txaio"
        ${VENV_PYTHON} -m pip install -e "../txaio"
    else
        echo "  ⚠ Warning: ../txaio not found, skipping"
    fi

    # autobahn-python - install with extras needed by crossbar
    if [ -d "../autobahn-python" ]; then
        echo "  ✓ Installing autobahn-python with extras from ../autobahn-python"
        ${VENV_PYTHON} -m pip install -e "../autobahn-python[twisted,encryption,compress,serialization,scram]"
    else
        echo "  ⚠ Warning: ../autobahn-python not found, skipping"
    fi

    # zlmdb, cfxdb, wamp-xbr - no extras needed
    for pkg in zlmdb cfxdb wamp-xbr; do
        pkg_path="../${pkg}"
        if [ -d "${pkg_path}" ]; then
            echo "  ✓ Installing ${pkg} from ${pkg_path}"
            ${VENV_PYTHON} -m pip install -e "${pkg_path}"
        else
            echo "  ⚠ Warning: ${pkg_path} not found, skipping"
        fi
    done

    echo "==> Installing crossbar in editable mode with [dev] extras..."
    echo "==> Note: pip will use already-installed local WAMP packages and resolve remaining dependencies"
    # Use pip's dependency resolver - it will use the already-installed local WAMP packages
    # and install missing dependencies
    ${VENV_PYTHON} -m pip install -e .[dev] --upgrade --upgrade-strategy only-if-needed

# Install minimal build tools for building wheels (usage: `just install-build-tools cpy312`)
install-build-tools venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Installing minimal build tools in ${VENV_NAME}..."

    ${VENV_PYTHON} -V
    ${VENV_PYTHON} -m pip -V

    ${VENV_PYTHON} -m pip install build twine auditwheel

# Install the development tools for this Package in a single environment (usage: `just install-tools cpy312`)
install-tools venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Installing package development tools in ${VENV_NAME}..."

    ${VENV_PYTHON} -V
    ${VENV_PYTHON} -m pip -V

    ${VENV_PYTHON} -m pip install -e .[dev]

# Meta-recipe to run `install-tools` on all environments
install-tools-all:
    #!/usr/bin/env bash
    set -e
    for venv in {{ENVS}}; do
        just install-tools ${venv}
    done

# -----------------------------------------------------------------------------
# -- Linting, Static Typechecking
# -----------------------------------------------------------------------------

# Automatically fix all formatting and code style issues.
fix-format venv="": (install-tools venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"

    echo "==> Automatically formatting code with ${VENV_NAME}..."

    # 1. Run the FORMATTER first
    "${VENV_PATH}/bin/ruff" format crossbar

    # 2. Run the LINTER'S FIXER second
    "${VENV_PATH}/bin/ruff" check --fix crossbar
    echo "--> Formatting complete."

# Alias for fix-format (backward compatibility)
autoformat venv="": (fix-format venv)

# Lint code using Ruff in a single environment
check-format venv="": (install-tools venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    echo "==> Linting code with ${VENV_NAME}..."
    "${VENV_PATH}/bin/ruff" check crossbar

# Run static type checking with mypy
check-typing venv="": (install-tools venv) (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    echo "==> Running static type checks with ${VENV_NAME}..."
    "${VENV_PATH}/bin/mypy" \
        --exclude 'src/crossbar/worker/test/examples/' \
        --disable-error-code=import-untyped \
        --disable-error-code=import-not-found \
        --disable-error-code=attr-defined \
        src/crossbar/

# Run security checks with bandit
check-bandit venv="": (install-tools venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    echo "==> Running security checks with bandit in ${VENV_NAME}..."
    "${VENV_PATH}/bin/bandit" -r src/crossbar/ \
        --exclude src/crossbar/worker/test/examples/ \
        -ll -f txt
    echo "✓ Security checks passed (severity: MEDIUM or higher)"

# Run all checks in single environment (usage: `just check cpy312`)
check venv="": (check-format venv) (check-typing venv) (check-bandit venv)

# -----------------------------------------------------------------------------
# -- Unit tests
# -----------------------------------------------------------------------------

# Run the test suite for Twisted using trial (usage: `just test-trial cpy312`)
test-trial venv="": (install-tools venv) (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")

    echo "==> Running test suite for Twisted using trial in ${VENV_NAME}..."

    ${VENV_PYTHON} -m twisted.trial crossbar

# Run the test suite for pytest (usage: `just test-pytest cpy312`)
test-pytest venv="": (install-tools venv) (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")

    echo "==> Running test suite using pytest in ${VENV_NAME}..."

    ${VENV_PYTHON} -m pytest -sv crossbar

# Run all tests (trial + pytest + functional)
test venv="": (test-trial venv) (test-pytest venv) (test-functional venv)

# Run functional tests
test-functional venv="": (install-tools venv) (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Running functional tests with ${VENV_NAME}..."
    ${VENV_PYTHON} -m pytest -sv --no-install ./test/functests/cbtests

# Run all tests
test-all venv="": (test venv) (test-functional venv)

# Generate code coverage report (requires: `just install-dev`)
check-coverage venv="": (install-dev venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Generating coverage report with ${VENV_NAME}..."
    ${VENV_PYTHON} -m pytest --cov=src/crossbar --cov-report=html --cov-report=term src/crossbar/
    echo "--> Coverage report generated in htmlcov/"

# Alias for check-coverage (backward compatibility)
coverage venv="": (check-coverage venv)

# Upgrade dependencies in a single environment (re-installs all deps to latest)
upgrade venv="": (create venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Upgrading all dependencies in ${VENV_NAME}..."
    ${VENV_PYTHON} -m pip install --upgrade pip
    ${VENV_PYTHON} -m pip install --upgrade -e .[dev]
    echo "--> Dependencies upgraded"

# Meta-recipe to run `upgrade` on all environments
upgrade-all:
    #!/usr/bin/env bash
    set -e
    for venv in {{ENVS}}; do
        echo ""
        echo "======================================================================"
        echo "Upgrading ${venv}"
        echo "======================================================================"
        just upgrade ${venv}
    done

# -----------------------------------------------------------------------------
# -- Documentation
# -----------------------------------------------------------------------------

# Build the HTML documentation using Sphinx
docs venv="":
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    if [ ! -d "${VENV_PATH}" ]; then
        just install-tools ${VENV_NAME}
    fi
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Building documentation..."
    "${VENV_PATH}/bin/sphinx-build" -b html docs/ docs/_build/html

# Check documentation build
docs-check venv="": (install-tools venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    echo "==> Checking documentation build..."
    "${VENV_PATH}/bin/sphinx-build" -nWT -b dummy docs/ docs/_build

# Clean the generated documentation
docs-clean:
    echo "==> Cleaning documentation build artifacts..."
    rm -rf docs/_build

# -----------------------------------------------------------------------------
# -- Building and Publishing
# -----------------------------------------------------------------------------

# Build wheel only (usage: `just build cpy312`)
build venv="": (install-build-tools venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Building wheel package..."

    # Set environment variables for build
    export LMDB_FORCE_CFFI=1
    export SODIUM_INSTALL=bundled
    export PYUBJSON_NO_EXTENSION=1

    ${VENV_PYTHON} -m build --wheel
    ls -la dist/

# Build source distribution only (no wheels)
build-sourcedist venv="": (install-build-tools venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Building source distribution..."
    ${VENV_PYTHON} -m build --sdist
    ls -la dist/

# Meta-recipe to run `build` on all environments
build-all:
    #!/usr/bin/env bash
    for venv in {{ENVS}}; do
        just build ${venv}
    done
    ls -la dist/

# Verify distribution packages (wheel and source dist)
build-verifydist venv="": (install-build-tools venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")

    echo "==> Verifying built distributions with ${VENV_NAME}..."
    echo ""

    # Check if dist/ exists
    if [ ! -d "dist" ]; then
        echo "ERROR: dist/ directory not found"
        exit 1
    fi

    FAILURES=0

    # Count distributions
    WHEEL_COUNT=$(ls dist/*.whl 2>/dev/null | wc -l)
    SDIST_COUNT=$(ls dist/*.tar.gz 2>/dev/null | wc -l)

    echo "========================================================================"
    echo "Distribution Check"
    echo "========================================================================"
    echo "Wheels found: $WHEEL_COUNT"
    echo "Source dists found: $SDIST_COUNT"
    echo ""

    if [ "$WHEEL_COUNT" -eq 0 ]; then
        echo "❌ FAIL: No wheel found"
        ((++FAILURES))
    fi

    if [ "$SDIST_COUNT" -eq 0 ]; then
        echo "❌ FAIL: No source distribution found"
        ((++FAILURES))
    fi

    # Verify wheels
    if [ "$WHEEL_COUNT" -gt 0 ]; then
        for wheel in dist/*.whl; do
            WHEEL_NAME=$(basename "$wheel")
            echo "========================================================================"
            echo "Checking wheel: $WHEEL_NAME"
            echo "========================================================================"

            # Check if it's a pure Python wheel (should be!)
            if [[ "$WHEEL_NAME" == *"-py2.py3-none-any.whl" ]]; then
                echo "✓ Pure Python wheel (universal compatibility)"
            elif [[ "$WHEEL_NAME" == *"-py3-none-any.whl" ]]; then
                echo "✓ Pure Python wheel (Python 3 only)"
            else
                echo "⚠ WARNING: Not a pure Python wheel naming format"
                echo "   Expected: *-py2.py3-none-any.whl or *-py3-none-any.whl"
                ((++FAILURES))
            fi

            # Check wheel contents for license files
            echo ""
            echo "Checking for required license files:"
            if ${VENV_PYTHON} -m zipfile -l "$wheel" 2>/dev/null | grep -q "crossbar/LICENSE"; then
                echo "  ✓ Found: crossbar/LICENSE"
            else
                echo "  ❌ FAIL: crossbar/LICENSE not found in wheel"
                ((++FAILURES))
            fi

            if ${VENV_PYTHON} -m zipfile -l "$wheel" 2>/dev/null | grep -q "crossbar/LICENSES-OSS"; then
                echo "  ✓ Found: crossbar/LICENSES-OSS"
            else
                echo "  ❌ FAIL: crossbar/LICENSES-OSS not found in wheel"
                ((++FAILURES))
            fi

            echo ""
        done
    fi

    # Verify source distributions
    if [ "$SDIST_COUNT" -gt 0 ]; then
        for sdist in dist/*.tar.gz; do
            SDIST_NAME=$(basename "$sdist")
            echo "========================================================================"
            echo "Checking source dist: $SDIST_NAME"
            echo "========================================================================"

            # Check naming convention
            if [[ "$SDIST_NAME" =~ ^crossbar-[0-9]+\.[0-9]+\.[0-9]+\.tar\.gz$ ]]; then
                echo "✓ Valid source dist naming"
            else
                echo "⚠ WARNING: Unexpected naming format"
            fi

            echo ""
        done
    fi

    # Run twine check on all distributions
    echo "========================================================================"
    echo "Running twine check"
    echo "========================================================================"
    if ${VENV_PYTHON} -m twine check dist/*; then
        echo "✓ Twine check passed"
    else
        echo "❌ FAIL: Twine check failed"
        ((++FAILURES))
    fi
    echo ""

    # Summary
    echo "========================================================================"
    echo "Summary"
    echo "========================================================================"
    echo "Wheels: $WHEEL_COUNT"
    echo "Source dists: $SDIST_COUNT"
    echo "Failures: $FAILURES"
    echo ""

    if [ $FAILURES -gt 0 ]; then
        echo "❌ VERIFICATION FAILED"
        exit 1
    else
        echo "✅ ALL DISTRIBUTIONS VERIFIED SUCCESSFULLY"
    fi

# Legacy alias for build-verifydist
verify-dist venv="": (build-verifydist venv)

# Path to parent directory containing all WAMP Python repos
WAMP_REPOS_DIR := parent_directory(justfile_directory())

# List of all WAMP Python repos in dependency order
WAMP_REPOS := 'txaio autobahn-python zlmdb cfxdb wamp-xbr crossbar'

# Build all 6 WAMP Python repos (all Python versions) and collect wheels/sdists into dist-universe
build-universe:
    #!/usr/bin/env bash
    set -e

    echo "========================================================================"
    echo "Building WAMP Universe (all 6 Python repos, all Python versions)"
    echo "========================================================================"
    echo "Repos dir: {{ WAMP_REPOS_DIR }}"
    echo ""

    # Clean and create dist-universe directory
    rm -rf ./dist-universe
    mkdir -p ./dist-universe

    FAILURES=0
    BUILT_REPOS=""

    for repo in {{ WAMP_REPOS }}; do
        REPO_PATH="{{ WAMP_REPOS_DIR }}/${repo}"
        echo ""
        echo "========================================================================"
        echo "Building: ${repo}"
        echo "========================================================================"

        if [ ! -d "${REPO_PATH}" ]; then
            echo "❌ ERROR: Repository not found at ${REPO_PATH}"
            ((++FAILURES))
            continue
        fi

        if [ ! -f "${REPO_PATH}/justfile" ]; then
            echo "❌ ERROR: No justfile found in ${REPO_PATH}"
            ((++FAILURES))
            continue
        fi

        # Clean repo dist directory first
        rm -rf "${REPO_PATH}/dist"

        # Build wheels for ALL Python versions (CPython + PyPy)
        echo "--> Building wheels for all Python versions..."
        if (cd "${REPO_PATH}" && just build-all); then
            echo "✓ Wheels built"
        else
            echo "❌ FAIL: Wheel build failed"
            ((++FAILURES))
            continue
        fi

        # Build source distribution (only need one, use system Python)
        echo "--> Building source distribution..."
        if (cd "${REPO_PATH}" && just build-sourcedist); then
            echo "✓ Source distribution built"
        else
            echo "❌ FAIL: Source distribution build failed"
            ((++FAILURES))
            continue
        fi

        # Copy artifacts to dist-universe
        echo "--> Copying artifacts to dist-universe..."
        cp "${REPO_PATH}"/dist/*.whl ./dist-universe/ 2>/dev/null || true
        cp "${REPO_PATH}"/dist/*.tar.gz ./dist-universe/ 2>/dev/null || true

        BUILT_REPOS="${BUILT_REPOS} ${repo}"
        echo "✓ ${repo} complete"
    done

    echo ""
    echo "========================================================================"
    echo "Build Universe Summary"
    echo "========================================================================"
    echo "Successfully built:${BUILT_REPOS}"
    echo "Failures: ${FAILURES}"
    echo ""
    echo "Artifacts in dist-universe:"
    ls -la ./dist-universe/
    echo ""

    if [ ${FAILURES} -gt 0 ]; then
        echo "❌ BUILD UNIVERSE FAILED: ${FAILURES} repo(s) had errors"
        exit 1
    else
        WHEEL_COUNT=$(ls ./dist-universe/*.whl 2>/dev/null | wc -l)
        SDIST_COUNT=$(ls ./dist-universe/*.tar.gz 2>/dev/null | wc -l)
        echo "✅ BUILD UNIVERSE COMPLETE"
        echo "   Wheels: ${WHEEL_COUNT}"
        echo "   Source dists: ${SDIST_COUNT}"
    fi

# Verify all wheels and source dists in dist-universe (usage: `just verify-universe`)
verify-universe: (install-build-tools)
    #!/usr/bin/env bash
    set -e
    VENV_NAME=$(just --quiet _get-system-venv-name)
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")

    echo "========================================================================"
    echo "Verifying WAMP Universe (dist-universe)"
    echo "========================================================================"
    echo "Using venv: ${VENV_NAME}"
    echo ""

    # Check if dist-universe exists
    if [ ! -d "./dist-universe" ]; then
        echo "❌ ERROR: dist-universe/ directory not found"
        echo "   Run 'just build-universe' first"
        exit 1
    fi

    FAILURES=0

    # Count distributions
    WHEEL_COUNT=$(ls ./dist-universe/*.whl 2>/dev/null | wc -l)
    SDIST_COUNT=$(ls ./dist-universe/*.tar.gz 2>/dev/null | wc -l)

    echo "Found ${WHEEL_COUNT} wheel(s) and ${SDIST_COUNT} source dist(s)"
    echo ""

    if [ "${WHEEL_COUNT}" -eq 0 ] && [ "${SDIST_COUNT}" -eq 0 ]; then
        echo "❌ ERROR: No distributions found in dist-universe/"
        exit 1
    fi

    # Verify with twine check
    echo "========================================================================"
    echo "Running twine check"
    echo "========================================================================"
    if ${VENV_PYTHON} -m twine check ./dist-universe/*; then
        echo "✓ Twine check passed for all packages"
    else
        echo "❌ FAIL: Twine check failed"
        ((++FAILURES))
    fi
    echo ""

    # Check wheel types
    echo "========================================================================"
    echo "Checking wheel types"
    echo "========================================================================"
    for wheel in ./dist-universe/*.whl; do
        WHEEL_NAME=$(basename "$wheel")
        # Extract package name (everything before the version)
        PKG_NAME=$(echo "$WHEEL_NAME" | sed 's/-[0-9].*//')

        if [[ "$WHEEL_NAME" == *"-py2.py3-none-any.whl" ]] || [[ "$WHEEL_NAME" == *"-py3-none-any.whl" ]]; then
            echo "✓ ${PKG_NAME}: Pure Python wheel"
        elif [[ "$WHEEL_NAME" == *"-cp3"*"-linux"* ]] || [[ "$WHEEL_NAME" == *"-cp3"*"-manylinux"* ]]; then
            echo "✓ ${PKG_NAME}: Platform-specific wheel (CPython/CFFI)"
            # Run auditwheel on platform-specific wheels
            echo "  --> Running auditwheel show..."
            if [ -x "${VENV_PATH}/bin/auditwheel" ]; then
                "${VENV_PATH}/bin/auditwheel" show "$wheel" 2>/dev/null || echo "  ⚠ auditwheel show had warnings"
            else
                echo "  ⚠ auditwheel not available"
            fi
        elif [[ "$WHEEL_NAME" == *"-pp3"*"-linux"* ]] || [[ "$WHEEL_NAME" == *"-pp3"*"-manylinux"* ]]; then
            echo "✓ ${PKG_NAME}: Platform-specific wheel (PyPy/CFFI)"
        else
            echo "⚠ ${PKG_NAME}: Unknown wheel type: ${WHEEL_NAME}"
        fi
    done
    echo ""

    # Summary by package
    echo "========================================================================"
    echo "Package Summary"
    echo "========================================================================"
    for repo in {{ WAMP_REPOS }}; do
        # Convert repo name to package name (autobahn-python -> autobahn)
        case "${repo}" in
            autobahn-python) PKG_PATTERN="autobahn-";;
            wamp-xbr) PKG_PATTERN="xbr-";;
            *) PKG_PATTERN="${repo}-";;
        esac

        WHEEL_EXISTS=$(ls ./dist-universe/${PKG_PATTERN}*.whl 2>/dev/null | head -1)
        SDIST_EXISTS=$(ls ./dist-universe/${PKG_PATTERN}*.tar.gz 2>/dev/null | head -1)

        if [ -n "${WHEEL_EXISTS}" ] && [ -n "${SDIST_EXISTS}" ]; then
            echo "✓ ${repo}: wheel + sdist"
        elif [ -n "${WHEEL_EXISTS}" ]; then
            echo "⚠ ${repo}: wheel only (missing sdist)"
        elif [ -n "${SDIST_EXISTS}" ]; then
            echo "⚠ ${repo}: sdist only (missing wheel)"
        else
            echo "❌ ${repo}: MISSING"
            ((++FAILURES))
        fi
    done
    echo ""

    # Final summary
    echo "========================================================================"
    echo "Verification Summary"
    echo "========================================================================"
    echo "Wheels: ${WHEEL_COUNT}"
    echo "Source dists: ${SDIST_COUNT}"
    echo "Failures: ${FAILURES}"
    echo ""

    if [ ${FAILURES} -gt 0 ]; then
        echo "❌ VERIFICATION FAILED"
        exit 1
    else
        echo "✅ ALL DISTRIBUTIONS VERIFIED SUCCESSFULLY"
    fi

# Show dependency tree
deps venv="": (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")
    echo "==> Dependencies in ${VENV_NAME}:"
    ${VENV_PYTHON} -m pip list
    echo ""
    echo "To see detailed dependency tree, install 'pipdeptree' and run:"
    echo "  ${VENV_PYTHON} -m pipdeptree"

# Run a command in the venv (usage: `just run cpy312 crossbar version` or `just run cpy312 python -m pytest`)
run venv *ARGS:
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"

    # Check if venv exists
    if [ ! -d "${VENV_PATH}" ]; then
        echo "Error: venv ${VENV_NAME} does not exist. Create it with: just create ${VENV_NAME}"
        exit 1
    fi

    # Get the command - first arg becomes the executable, rest are arguments
    COMMAND_ARGS="{{ ARGS }}"
    if [ -z "${COMMAND_ARGS}" ]; then
        echo "Error: No command specified. Usage: just run <venv> <command> [args...]"
        echo "Examples:"
        echo "  just run cpy312 crossbar version"
        echo "  just run cpy312 python -m pytest"
        echo "  just run cpy312 python -c 'import crossbar; print(crossbar.__version__)'"
        exit 1
    fi

    # Try to find the command in venv/bin first, otherwise use it as-is
    FIRST_ARG=$(echo ${COMMAND_ARGS} | awk '{print $1}')
    if [ -f "${VENV_PATH}/bin/${FIRST_ARG}" ]; then
        # Command exists in venv/bin, use it
        FULL_COMMAND="${VENV_PATH}/bin/${COMMAND_ARGS}"
    elif [ "${FIRST_ARG}" = "python" ] || [ "${FIRST_ARG}" = "python3" ]; then
        # Special case for python - always use venv's python
        REST_ARGS=$(echo ${COMMAND_ARGS} | cut -d' ' -f2-)
        FULL_COMMAND="${VENV_PATH}/bin/python ${REST_ARGS}"
    else
        # Command not in venv/bin, use PATH (venv will be prepended)
        FULL_COMMAND="${COMMAND_ARGS}"
    fi

    # Activate venv and run command
    source "${VENV_PATH}/bin/activate"
    eval ${FULL_COMMAND}

# Run crossbar version command (smoke test)
test-crossbar-version venv="": (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    echo "==> Running crossbar version test with ${VENV_NAME}..."
    "${VENV_PATH}/bin/crossbar" version

# Run crossbar legal command (verify license files)
test-crossbar-legal venv="": (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    echo "==> Running crossbar legal test with ${VENV_NAME}..."
    "${VENV_PATH}/bin/crossbar" legal

# Run crossbar keys command (verify release signing keys)
test-crossbar-keys venv="": (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    echo "==> Running crossbar keys test with ${VENV_NAME}..."
    "${VENV_PATH}/bin/crossbar" keys

# Quick smoke test: test crossbar CLI commands only (no node lifecycle)
test-smoke-cli venv="": (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    CB="${VENV_PATH}/bin/crossbar"

    echo "========================================================================"
    echo "Crossbar CLI Smoke Tests"
    echo "========================================================================"
    echo "Testing with venv: ${VENV_NAME}"
    echo ""

    FAILURES=0

    # Test: crossbar version
    echo "Testing: crossbar version"
    if ${CB} version >/dev/null 2>&1; then
        echo "✓ crossbar version"
    else
        echo "❌ FAIL: crossbar version"
        ((++FAILURES))
    fi

    # Test: crossbar legal
    echo "Testing: crossbar legal"
    if ${CB} legal >/dev/null 2>&1; then
        echo "✓ crossbar legal"
    else
        echo "❌ FAIL: crossbar legal"
        ((++FAILURES))
    fi

    # Test: crossbar keys
    echo "Testing: crossbar keys"
    if ${CB} keys >/dev/null 2>&1; then
        echo "✓ crossbar keys"
    else
        echo "❌ FAIL: crossbar keys"
        ((++FAILURES))
    fi

    # Test: crossbar shell --help
    echo "Testing: crossbar shell --help"
    if ${CB} shell --help >/dev/null 2>&1; then
        echo "✓ crossbar shell --help"
    else
        echo "❌ FAIL: crossbar shell --help"
        ((++FAILURES))
    fi

    echo ""
    if [ $FAILURES -gt 0 ]; then
        echo "❌ SMOKE TEST FAILED: $FAILURES command(s) failed"
        exit 1
    else
        echo "✅ ALL CLI SMOKE TESTS PASSED"
    fi

# Quick smoke test: test node initialization and file creation
test-smoke-init venv="": (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    CB="${VENV_PATH}/bin/crossbar"
    TESTDIR="/tmp/crossbar-smoke-test-$$"

    echo "========================================================================"
    echo "Crossbar Node Initialization Smoke Test"
    echo "========================================================================"
    echo "Testing with venv: ${VENV_NAME}"
    echo "Test directory: ${TESTDIR}"
    echo ""

    FAILURES=0

    # Clean up any existing test directory
    rm -rf "${TESTDIR}"

    # Test: crossbar init
    echo "Testing: crossbar init --appdir ${TESTDIR}"
    if ${CB} init --appdir "${TESTDIR}" >/dev/null 2>&1; then
        echo "✓ crossbar init"
    else
        echo "❌ FAIL: crossbar init"
        ((++FAILURES))
    fi

    # Verify directory structure
    echo "Verifying directory structure..."
    if [ -d "${TESTDIR}/.crossbar" ]; then
        echo "✓ .crossbar/ directory created"
    else
        echo "❌ FAIL: .crossbar/ directory missing"
        ((++FAILURES))
    fi

    if [ -d "${TESTDIR}/web" ]; then
        echo "✓ web/ directory created"
    else
        echo "❌ FAIL: web/ directory missing"
        ((++FAILURES))
    fi

    # Verify required files
    echo "Verifying required files..."
    REQUIRED_FILES=(
        "${TESTDIR}/.crossbar/config.json"
        "${TESTDIR}/README.md"
        "${TESTDIR}/web/README.md"
    )

    for file in "${REQUIRED_FILES[@]}"; do
        if [ -f "$file" ]; then
            echo "✓ $(basename $file) exists"
        else
            echo "❌ FAIL: $file missing"
            ((++FAILURES))
        fi
    done

    # Test: crossbar check
    echo "Testing: crossbar check --cbdir ${TESTDIR}/.crossbar/"
    if ${CB} check --cbdir "${TESTDIR}/.crossbar/" >/dev/null 2>&1; then
        echo "✓ crossbar check"
    else
        echo "❌ FAIL: crossbar check"
        ((++FAILURES))
    fi

    # Cleanup
    echo "Cleaning up test directory..."
    rm -rf "${TESTDIR}"

    echo ""
    if [ $FAILURES -gt 0 ]; then
        echo "❌ SMOKE TEST FAILED: $FAILURES check(s) failed"
        exit 1
    else
        echo "✅ ALL INIT SMOKE TESTS PASSED"
    fi

# Quick smoke test: test node lifecycle (init, start, status, stop)
test-smoke-lifecycle venv="": (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    CB="${VENV_PATH}/bin/crossbar"
    TESTDIR="/tmp/crossbar-smoke-lifecycle-$$"
    CBDIR="${TESTDIR}/.crossbar"

    echo "========================================================================"
    echo "Crossbar Node Lifecycle Smoke Test"
    echo "========================================================================"
    echo "Testing with venv: ${VENV_NAME}"
    echo "Test directory: ${TESTDIR}"
    echo ""

    FAILURES=0

    # Cleanup function
    cleanup() {
        echo "Cleaning up..."
        ${CB} stop --cbdir "${CBDIR}" 2>/dev/null || true
        sleep 1
        rm -rf "${TESTDIR}"
    }

    # Set trap to ensure cleanup on exit
    trap cleanup EXIT

    # Clean up any existing test directory
    rm -rf "${TESTDIR}"

    # Initialize node
    echo "Initializing test node..."
    if ${CB} init --appdir "${TESTDIR}" >/dev/null 2>&1; then
        echo "✓ Node initialized"
    else
        echo "❌ FAIL: Node initialization failed"
        exit 1
    fi

    # Test: status before start (should be stopped)
    echo "Testing: crossbar status (should be stopped)"
    if ${CB} status --cbdir "${CBDIR}" --assert=stopped >/dev/null 2>&1; then
        echo "✓ Node status: stopped (before start)"
    else
        echo "❌ FAIL: Node should be stopped before start"
        ((++FAILURES))
    fi

    # Test: start node
    echo "Starting node in background..."
    ${CB} start --cbdir "${CBDIR}" >/dev/null 2>&1 &
    CB_PID=$!
    sleep 3  # Give node time to start

    # Test: status after start (should be running)
    echo "Testing: crossbar status (should be running)"
    if ${CB} status --cbdir "${CBDIR}" --assert=running >/dev/null 2>&1; then
        echo "✓ Node status: running (after start)"
    else
        echo "❌ FAIL: Node should be running after start"
        ((++FAILURES))
    fi

    # Verify PID file exists
    if [ -f "${CBDIR}/node.pid" ]; then
        echo "✓ node.pid file created"
    else
        echo "❌ FAIL: node.pid file missing"
        ((++FAILURES))
    fi

    # Check listening ports (Web on 8080, RawSocket on 8081)
    echo "Checking listening ports..."
    if ss -tln 2>/dev/null | grep -q ':8080 ' || netstat -tln 2>/dev/null | grep -q ':8080 '; then
        echo "✓ Port 8080 listening (Web transport)"
    else
        echo "⚠ WARNING: Port 8080 not detected (may be timing issue)"
    fi

    if ss -tln 2>/dev/null | grep -q ':8081 ' || netstat -tln 2>/dev/null | grep -q ':8081 '; then
        echo "✓ Port 8081 listening (RawSocket transport)"
    else
        echo "⚠ WARNING: Port 8081 not detected (may be timing issue)"
    fi

    # Test: HTTP root endpoint
    echo "Testing HTTP endpoints..."
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null | grep -q "200"; then
        echo "✓ HTTP endpoint / responding"
    else
        echo "⚠ WARNING: HTTP endpoint / not responding (may be timing issue)"
    fi

    # Test: HTTP info endpoint
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/info 2>/dev/null | grep -q "200"; then
        echo "✓ HTTP endpoint /info responding"
    else
        echo "⚠ WARNING: HTTP endpoint /info not responding (may be timing issue)"
    fi

    # Test: stop node
    echo "Stopping node..."
    if ${CB} stop --cbdir "${CBDIR}" >/dev/null 2>&1; then
        echo "✓ Node stopped successfully"
    else
        echo "❌ FAIL: Node stop failed"
        ((++FAILURES))
    fi

    sleep 1

    # Test: status after stop (should be stopped)
    echo "Testing: crossbar status (should be stopped after stop)"
    if ${CB} status --cbdir "${CBDIR}" --assert=stopped >/dev/null 2>&1; then
        echo "✓ Node status: stopped (after stop)"
    else
        echo "❌ FAIL: Node should be stopped after stop command"
        ((++FAILURES))
    fi

    echo ""
    if [ $FAILURES -gt 0 ]; then
        echo "❌ SMOKE TEST FAILED: $FAILURES check(s) failed"
        exit 1
    else
        echo "✅ ALL LIFECYCLE SMOKE TESTS PASSED"
    fi

# Run all smoke tests
test-smoke venv="": (test-smoke-cli venv) (test-smoke-init venv) (test-smoke-lifecycle venv)
    @echo ""
    @echo "========================================================================"
    @echo "✅ ALL SMOKE TESTS PASSED"
    @echo "========================================================================"

# Integration test: run autobahn-python examples against crossbar (WebSocket and RawSocket)
test-integration-ab-examples venv="" ab_python_path="":
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"

    # Get absolute paths
    WORKDIR=$(pwd)
    CB_BIN="${WORKDIR}/${VENV_PATH}/bin"
    PYTHON="${CB_BIN}/python"

    # Determine autobahn-python path
    AB_PATH="{{ ab_python_path }}"
    if [ -z "${AB_PATH}" ]; then
        # Try environment variable first
        if [ -n "${AB_PYTHON_PATH}" ]; then
            AB_PATH="${AB_PYTHON_PATH}"
        else
            # Default: sibling directory (local development)
            AB_PATH="../autobahn-python"
        fi
    fi

    # Make path absolute
    AB_PATH=$(cd "$(dirname "${AB_PATH}")" && pwd)/$(basename "${AB_PATH}")

    echo "========================================================================"
    echo "Crossbar Integration Test: Autobahn|Python Examples"
    echo "========================================================================"
    echo "Crossbar venv: ${VENV_NAME}"
    echo "Autobahn|Python path: ${AB_PATH}"
    echo ""

    FAILURES=0

    # Verify autobahn-python path exists
    if [ ! -d "${AB_PATH}" ]; then
        echo "❌ ERROR: Autobahn|Python not found at: ${AB_PATH}"
        echo ""
        echo "Please specify the path to autobahn-python:"
        echo "  1. Set environment variable: export AB_PYTHON_PATH=/path/to/autobahn-python"
        echo "  2. Pass as argument: just test-integration-ab-examples cpy311 /path/to/autobahn-python"
        echo "  3. Clone as sibling: git clone https://github.com/crossbario/autobahn-python.git ../autobahn-python"
        exit 1
    fi

    EXAMPLES_DIR="${AB_PATH}/examples"
    RUN_SCRIPT="${EXAMPLES_DIR}/run-all-examples.py"

    if [ ! -f "${RUN_SCRIPT}" ]; then
        echo "❌ ERROR: run-all-examples.py not found at: ${RUN_SCRIPT}"
        exit 1
    fi

    if [ ! -d "${EXAMPLES_DIR}/router/.crossbar" ]; then
        echo "❌ ERROR: router/.crossbar not found in examples directory"
        exit 1
    fi

    echo "✓ Found run-all-examples.py and router configuration"

    # Check if colorama is installed (required by run-all-examples.py)
    if ! ${PYTHON} -c "import colorama" 2>/dev/null; then
        echo "Installing colorama (required by run-all-examples.py)..."
        ${PYTHON} -m pip install -q colorama
    fi

    # Change to examples directory - run-all-examples.py expects to run from there
    cd "${EXAMPLES_DIR}"

    # Add crossbar to PATH so run-all-examples.py can find it
    export PATH="${CB_BIN}:${PATH}"

    # Test 1: RawSocket transport
    echo ""
    echo "========================================================================"
    echo "Test 1: RawSocket Transport (rs://127.0.0.1:8080)"
    echo "========================================================================"
    echo "Note: run-all-examples.py starts its own crossbar instance"
    echo ""
    if AUTOBAHN_DEMO_ROUTER=rs://127.0.0.1:8080 ${PYTHON} run-all-examples.py; then
        echo ""
        echo "✓ RawSocket transport tests passed"
    else
        echo ""
        echo "❌ FAIL: RawSocket transport tests failed"
        ((++FAILURES))
    fi

    # Test 2: WebSocket transport
    echo ""
    echo "========================================================================"
    echo "Test 2: WebSocket Transport (ws://127.0.0.1:8080/ws)"
    echo "========================================================================"
    echo "Note: run-all-examples.py starts its own crossbar instance"
    echo ""
    if AUTOBAHN_DEMO_ROUTER=ws://127.0.0.1:8080/ws ${PYTHON} run-all-examples.py; then
        echo ""
        echo "✓ WebSocket transport tests passed"
    else
        echo ""
        echo "❌ FAIL: WebSocket transport tests failed"
        ((++FAILURES))
    fi

    # Summary
    echo ""
    echo "========================================================================"
    echo "Summary"
    echo "========================================================================"
    if [ $FAILURES -gt 0 ]; then
        echo "❌ INTEGRATION TEST FAILED: $FAILURES transport(s) failed"
        exit 1
    else
        echo "✅ ALL INTEGRATION TESTS PASSED"
        echo "   - RawSocket transport: PASS"
        echo "   - WebSocket transport: PASS"
    fi

# Complete setup: create venv, install deps, run checks (usage: `just setup cpy312`)
setup venv: (install-dev venv) (check venv) (test venv) (test-crossbar-version venv)
    @echo "✅ Setup complete for {{venv}}"

# Quick development install (no tests, usage: `just dev cpy312`)
dev venv: (install-dev venv)
    @echo "✅ Development environment ready: {{venv}}"

# Generate OSS license metadata files
generate-license-metadata venv="":
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Using venv: ${VENV_NAME}"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    VENV_PYTHON=$(just --quiet _get-venv-python "${VENV_NAME}")

    echo "==> Generating OSS license metadata..."

    # Generate plain text license list
    ${VENV_PATH}/bin/pip-licenses -a -o name > src/crossbar/LICENSES-OSS
    echo "  ✓ Generated src/crossbar/LICENSES-OSS"

    # Generate RST formatted license table for docs
    ${VENV_PATH}/bin/pip-licenses -a -o name --format=rst > docs/oss_licenses_table.rst

    # Add header to RST file
    sed -i '1s;^;OSS Licenses\n============\n\n;' docs/oss_licenses_table.rst
    echo "  ✓ Generated docs/oss_licenses_table.rst"

    # Also generate for soss (if needed)
    ${VENV_PATH}/bin/pip-licenses -a -o name --format=rst > docs/soss_licenses_table.rst
    sed -i '1s;^;OSS Licenses\n============\n\n;' docs/soss_licenses_table.rst
    echo "  ✓ Generated docs/soss_licenses_table.rst"

    echo "==> License metadata generation complete!"

# -----------------------------------------------------------------------------
# -- Publishing
# -----------------------------------------------------------------------------

# Download GitHub release artifacts (nightly or tagged release)
download-github-release release_type="nightly":
    #!/usr/bin/env bash
    set -e
    echo "==> Downloading GitHub release artifacts ({{release_type}})..."
    rm -rf ./dist
    mkdir -p ./dist
    if [ "{{release_type}}" = "nightly" ]; then
        gh release download nightly --repo crossbario/crossbar --dir ./dist --pattern '*.whl' --pattern '*.tar.gz' || \
            echo "Note: No nightly release found or no artifacts available"
    else
        gh release download "{{release_type}}" --repo crossbario/crossbar --dir ./dist --pattern '*.whl' --pattern '*.tar.gz'
    fi
    echo ""
    echo "Downloaded artifacts:"
    ls -la ./dist/ || echo "No artifacts downloaded"

# Download release artifacts from GitHub and publish to PyPI
publish-pypi venv="" tag="": (install-build-tools venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        VENV_NAME=$(just --quiet _get-system-venv-name)
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    TAG="{{ tag }}"
    if [ -z "${TAG}" ]; then
        echo "Error: Please specify a tag to publish"
        echo "Usage: just publish-pypi cpy311 v24.1.1"
        exit 1
    fi
    echo "==> Publishing ${TAG} to PyPI..."
    echo ""
    echo "Step 1: Download release artifacts from GitHub..."
    just download-github-release "${TAG}"
    echo ""
    echo "Step 2: Verify packages with twine..."
    "${VENV_PATH}/bin/twine" check dist/*
    echo ""
    echo "Note: This is a pure Python package (py3-none-any wheel)."
    echo "      auditwheel verification is not applicable (no native extensions)."
    echo ""
    echo "Step 3: Upload to PyPI..."
    echo ""
    echo "WARNING: This will upload to PyPI!"
    echo "Press Ctrl+C to cancel, or Enter to continue..."
    read
    "${VENV_PATH}/bin/twine" upload dist/*
    echo ""
    echo "==> Successfully published ${TAG} to PyPI"

# Trigger Read the Docs build for a specific tag
publish-rtd tag="":
    #!/usr/bin/env bash
    set -e
    TAG="{{ tag }}"
    if [ -z "${TAG}" ]; then
        echo "Error: Please specify a tag to build"
        echo "Usage: just publish-rtd v24.1.1"
        exit 1
    fi
    echo "==> Triggering Read the Docs build for ${TAG}..."
    echo ""
    echo "Note: Read the Docs builds are typically triggered automatically"
    echo "      when tags are pushed to GitHub. This recipe is a placeholder"
    echo "      for manual triggering if needed."
    echo ""
    echo "To manually trigger a build:"
    echo "  1. Go to https://readthedocs.org/projects/crossbar/"
    echo "  2. Click 'Build a version'"
    echo "  3. Select the tag: ${TAG}"
    echo ""
