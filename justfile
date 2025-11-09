# Crossbar.io justfile
# See: https://github.com/casey/just

# -----------------------------------------------------------------------------
# -- just global configuration
# -----------------------------------------------------------------------------

set unstable := true
set positional-arguments := true

# project base directory = directory of this justfile
PROJECT_DIR := justfile_directory()

# Default recipe: list all recipes
default:
    @echo ""
    @just --list
    @echo ""

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

    ${VENV_PYTHON} -m pip install build twine

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

    ${VENV_PYTHON} -m pip install -e .[dev,dev-latest]

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
autoformat venv="": (install-tools venv)
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
    "${VENV_PATH}/bin/mypy" crossbar/

# Run all checks in single environment (usage: `just check cpy312`)
check venv="": (check-format venv) (check-typing venv)

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

# Run all unit tests (trial + pytest)
test venv="": (test-trial venv) (test-pytest venv)

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

# Verify distribution packages
verify-dist venv="": (install-build-tools venv)
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
    echo "==> Verifying dist with ${VENV_NAME}..."
    ${VENV_PYTHON} -m twine check dist/*

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
smoke venv="": (install venv)
    #!/usr/bin/env bash
    set -e
    VENV_NAME="{{ venv }}"
    if [ -z "${VENV_NAME}" ]; then
        echo "==> No venv name specified. Auto-detecting from system Python..."
        VENV_NAME=$(just --quiet _get-system-venv-name)
        echo "==> Defaulting to venv: '${VENV_NAME}'"
    fi
    VENV_PATH="{{ VENV_DIR }}/${VENV_NAME}"
    echo "==> Running smoke test with ${VENV_NAME}..."
    "${VENV_PATH}/bin/crossbar" version

# Complete setup: create venv, install deps, run checks (usage: `just setup cpy312`)
setup venv: (install-dev venv) (check venv) (test venv) (smoke venv)
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
    ${VENV_PATH}/bin/pip-licenses --from=classifier -a -o name > LICENSES-OSS
    echo "  ✓ Generated LICENSES-OSS"

    # Generate RST formatted license table for docs
    ${VENV_PATH}/bin/pip-licenses --from=classifier -a -o name --format=rst > docs/oss_licenses_table.rst

    # Add header to RST file
    sed -i '1s;^;OSS Licenses\n============\n\n;' docs/oss_licenses_table.rst
    echo "  ✓ Generated docs/oss_licenses_table.rst"

    # Also generate for soss (if needed)
    ${VENV_PATH}/bin/pip-licenses --from=classifier -a -o name --format=rst > docs/soss_licenses_table.rst
    sed -i '1s;^;OSS Licenses\n============\n\n;' docs/soss_licenses_table.rst
    echo "  ✓ Generated docs/soss_licenses_table.rst"
    
    echo "==> License metadata generation complete!"
