Reproducible Builds with uv.lock
=================================

Crossbar.io uses `uv <https://docs.astral.sh/uv/>`_ for dependency management
and reproducible builds. The ``uv.lock`` file captures the exact versions of all
dependencies, ensuring consistent installations across different machines and over time.

Why uv.lock?
------------

As an **application** (not a library), Crossbar.io benefits from locked dependencies:

- **Reproducibility**: Every installation gets the exact same package versions
- **Security**: Known-good versions are captured and verified
- **Docker builds**: Production containers use the same dependencies tested in CI
- **Debugging**: Issues can be reproduced reliably across environments

.. note::

   The WAMP **libraries** (txaio, autobahn-python, zlmdb, cfxdb, wamp-xbr) do NOT
   commit ``uv.lock`` files. Libraries should "float" on the ecosystem to ensure
   compatibility with a wide range of downstream users.

Installation using uv sync
--------------------------

The ``uv sync`` command installs dependencies from ``uv.lock``. Different installation
modes are available depending on your needs:

Runtime Dependencies Only
~~~~~~~~~~~~~~~~~~~~~~~~~

For production use or when you just need to run Crossbar.io:

.. code-block:: bash

   uv sync

This installs only the packages required to run Crossbar.io (~160 packages).

With Development Tools
~~~~~~~~~~~~~~~~~~~~~~

For development with testing and linting tools:

.. code-block:: bash

   uv sync --extra dev

This adds pytest, ruff, bandit, and other development tools.

With Documentation Tools
~~~~~~~~~~~~~~~~~~~~~~~~

For building the documentation:

.. code-block:: bash

   uv sync --extra docs

This adds Sphinx, Furo theme, sphinx-autoapi, and other documentation tools.

All Dependencies
~~~~~~~~~~~~~~~~

To install everything (all extras):

.. code-block:: bash

   uv sync --all-extras

Understanding Markers
~~~~~~~~~~~~~~~~~~~~~

The ``uv.lock`` file uses **markers** to track which packages belong to which extras.
For example:

.. code-block:: toml

   { name = "pytest", marker = "extra == 'dev'" }
   { name = "sphinx", marker = "extra == 'docs'" }

Packages with markers are only installed when that extra is explicitly requested.
This keeps runtime installations minimal while allowing a single lock file to capture
all dependency configurations.

Frozen Installation
~~~~~~~~~~~~~~~~~~~

For maximum reproducibility (e.g., in Docker), use:

.. code-block:: bash

   uv sync --frozen

This fails if ``uv.lock`` is missing or outdated, ensuring you always install from
a known-good lock file.

Updating uv.lock with just
--------------------------

To update the lock file with the latest compatible versions:

.. code-block:: bash

   just update-uvlock

This runs ``uv lock --python 3.11`` to ensure compatibility with the lowest supported
Python version, then displays an analysis of the updated lock file.

When to Update
~~~~~~~~~~~~~~

Update ``uv.lock`` when:

- Adding or removing dependencies in ``pyproject.toml``
- Before a release to capture latest security patches
- When CI reports outdated dependencies
- After modifying version constraints

The update process:

1. Resolves all dependencies for Python 3.11+
2. Captures exact versions in ``uv.lock``
3. Displays analysis summary
4. Commit the updated ``uv.lock`` to Git

Analyzing uv.lock with just
---------------------------

To analyze the current lock file:

.. code-block:: bash

   just analyze-uvlock

Example output:

.. code-block:: text

   ===============================================================================
                            uv.lock Dependency Analysis
   ===============================================================================

   Total packages in uv.lock: 263

   Installation modes (using uv sync):
   ─────────────────────────────────────────────────────────────────────────────

     uv sync                    Runtime deps only
     uv sync --extra dev        Runtime + dev tools (pytest, ruff, etc.)
     uv sync --extra docs       Runtime + docs tools (sphinx, etc.)
     uv sync --extra dev-latest Runtime + latest from GitHub master
     uv sync --all-extras       All packages (263 total)

   Extra markers found in uv.lock:
   ─────────────────────────────────────────────────────────────────────────────

     extra == 'dev':        29 dependency entries
     extra == 'docs':       12 dependency entries
     extra == 'dev-latest': 5 dependency entries

   Note: Packages with extra markers are only installed when that extra is
         requested. The markers ensure selective installation.

   ===============================================================================

Docker Production Builds
------------------------

For production Docker images, use the frozen lock file:

.. code-block:: dockerfile

   FROM python:3.12-slim
   COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

   # Clone specific tag to get the uv.lock
   RUN git clone --branch v25.12.2 https://github.com/crossbario/crossbar /app
   WORKDIR /app

   # Install EXACTLY what was tested - frozen deps, no dev tools
   RUN uv sync --frozen --no-dev --no-editable

   ENV PATH="/app/.venv/bin:$PATH"
   ENTRYPOINT ["crossbar"]

This ensures the production container has exactly the same dependencies that were
tested in CI and verified during development.

References
----------

- `uv Documentation <https://docs.astral.sh/uv/>`_
- `uv lock command <https://docs.astral.sh/uv/reference/cli/#uv-lock>`_
- `uv sync command <https://docs.astral.sh/uv/reference/cli/#uv-sync>`_
- `PEP 751 - Lock file format <https://peps.python.org/pep-0751/>`_
