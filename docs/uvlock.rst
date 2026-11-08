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

Dependency Policy
-----------------

This section is the authoritative description of how Crossbar.io handles its
dependencies (`#2388 <https://github.com/crossbario/crossbar/issues/2388>`_).

**Crossbar.io follows the latest stable releases of its dependencies.** As the
application at the top of the WAMP stack, it is tested and shipped against the
newest releases, not against old ones.

Two tiers:

- ``pyproject.toml`` declares, for each direct dependency, a **lower bound**
  (``>=``) and, only where really needed, an **upper bound** (``<``):

  - A lower bound is the oldest version Crossbar.io works with, raised to the
    **first release with the fix** where an older version has a known security
    advisory (a *security floor*; the reason is noted next to the requirement).
    The published wheel installs without the lock, so these floors keep
    ``pip install crossbar`` off vulnerable versions too.
  - An upper bound (*cap*) is set only for a known incompatibility, and every
    cap carries a comment with the reason and the condition for removing it.

- ``uv.lock`` pins the **latest releases allowed by those bounds**, for every
  direct and transitive dependency, including the ``dev`` and ``docs`` extras.

Upgrading the lock is one command, ``just update-uvlock`` (``uv lock --upgrade``,
see below). Run it at least before every release, and whenever a dependency
publishes a security fix.

Current caps:

.. list-table::
   :header-rows: 1

   * - Requirement
     - Reason
     - Remove when
   * - ``pytest<9.2`` (``dev``)
     - pytest-tap 3.5 makes pytest 9.2.0 abort at startup (`#2383 <https://github.com/crossbario/crossbar/issues/2383>`_)
     - a pytest-tap release with python-tap/pytest-tap#139 is out
   * - ``eth-abi<5.2.0``, ``parsimonious<0.11.0``
     - eth-abi 6 is untested with the XBR code (``crossbar/__init__.py`` patches ``eth_abi``)
     - the XBR code is checked against eth-abi 6

Tests in ``crossbar.test.test_dependencies`` check the security floors: declared
in the package metadata, pinned in ``uv.lock``, and installed in the test
environment.

CI tests both tiers:

- the **Unit Tests** jobs install with ``just install-dev`` (``pip install -e .[dev]``),
  which resolves fresh from ``pyproject.toml``: the newest releases within the
  bounds, as a ``pip install crossbar`` user gets them;
- the **Unit Tests from uv.lock** jobs install with ``just install-dev-locked``
  (``uv sync --frozen --extra dev``), which installs exactly what ``uv.lock``
  pins, as a ``uv sync --frozen`` deployment gets it, and check with
  ``just check-locked`` before and after the tests that nothing moved.

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

To upgrade the lock file to the latest releases allowed by ``pyproject.toml``:

.. code-block:: bash

   just update-uvlock

This runs ``uv lock --upgrade --python 3.11``: every package is re-resolved to its
newest release within the lower and upper bounds declared in ``pyproject.toml``,
for the lowest supported Python version. Then it displays an analysis of the
updated lock file.

.. note::

   ``--upgrade`` matters: plain ``uv lock`` keeps every existing pin that still
   fits ``pyproject.toml`` and only resolves what changed, so the lock goes stale
   (before #2388 it had fallen months behind, with known advisories open).
   To bump a single package without touching the rest, use
   ``uv lock --upgrade-package <name>`` instead.

When to Update
~~~~~~~~~~~~~~

Update ``uv.lock`` when:

- Before every release, to capture the latest releases and security patches
- When a dependency publishes a security fix
- Adding or removing dependencies in ``pyproject.toml``
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

     uv sync                      Runtime deps only (153 packages)
     uv sync --extra dev          Runtime + dev tools (247 packages)
     uv sync --extra docs         Runtime + docs tools (186 packages)
     uv sync --all-extras         All packages (257 packages)

   Extra markers in uv.lock (dependency graph entries):
   ─────────────────────────────────────────────────────────────────────────────

     extra == 'dev':        29 entries
     extra == 'docs':       12 entries

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

The **Unit Tests from uv.lock** CI jobs test exactly these versions, so the
production container gets the same dependencies that were tested in CI.

Dependabot and Automated Updates
--------------------------------

Crossbar.io uses `Dependabot <https://docs.github.com/en/code-security/dependabot>`_
to track upstream dependency releases. The configuration is version-controlled in
``.github/dependabot.yml`` (not just GitHub UI settings), so the bot's behavior is
explicit, reviewable, and reproducible.

Because we maintain a two-tier dependency model — abstract ``>=`` floors (with
deliberate caps) in ``pyproject.toml``, and exact pins in ``uv.lock`` — Dependabot
PRs are reviewed using a simple rule based on **which files the PR touches**.

The two-lane review policy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Fast lane — PR touches** ``uv.lock`` **only:**

The new version fits *within* our existing ``pyproject.toml`` constraints. This is
almost always a transitive dependency, or a direct one with headroom under its cap.
Our declared compatibility contract is unchanged.

- **Action:** merge once CI is green.

**Manual lane — PR touches** ``pyproject.toml`` **as well:**

Dependabot had to **rewrite a declared constraint** to let the new version in —
usually to cross an upper cap we set on purpose. This is a change to our
compatibility contract, not just a re-pin.

- **Action:** review before merging. Read the upstream changelog/migration guide,
  check *how* the constraint was rewritten (did it keep a sane cap?), and apply
  extra scrutiny to major-version bumps of TLS/crypto-adjacent dependencies
  (e.g. ``urllib3``, ``pyopenssl``, ``cryptography``) — green CI is necessary but
  not sufficient for those, since CI may not exercise every TLS, proxy, or retry
  code path.

.. note::

   Patch and minor bumps are **grouped** into a single PR to reduce noise. If a
   grouped PR happens to touch ``pyproject.toml``, the whole PR is treated as the
   manual lane.

Ignored and capped dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``.github/dependabot.yml`` **ignores** the versions excluded by a cap in
``pyproject.toml`` where a bump is known to break (currently ``pytest>=9.2``, see
the caps table above). Remove the ignore entry together with the cap.

``eth-abi`` and ``parsimonious`` are capped at the **minor** level. They are not
ignored, but any bump rewrites their ``pyproject.toml`` cap and therefore lands in
the manual review lane anyway.

The XBR / Ethereum stack (``eth-*``, ``hexbytes``, ``web3``) is kept out of the
grouped minor/patch PR, because it moves in lockstep across major versions
(eth-account 0.14 needs hexbytes 2); these bumps come as their own PRs.

.. note::

   These ignore rules only suppress *routine version updates*. Dependabot
   **security advisories** still raise PRs for vulnerable versions regardless of
   the caps above — security fixes are never silently held back.

Relationship to ``just update-uvlock``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dependabot is the **notifier and CI gate**, not the source of truth for how the
lockfile is resolved. The canonical way we refresh ``uv.lock`` remains:

.. code-block:: bash

   just update-uvlock

which upgrades every package to its latest allowed release, resolved for the lowest
supported Python (3.11) for widest compatibility. When in doubt (for example, to
reconcile several Dependabot PRs at once) re-run ``just update-uvlock`` locally,
run the tests, and commit the result.

References
----------

- `uv Documentation <https://docs.astral.sh/uv/>`_
- `uv lock command <https://docs.astral.sh/uv/reference/cli/#uv-lock>`_
- `uv sync command <https://docs.astral.sh/uv/reference/cli/#uv-sync>`_
- `PEP 751 - Lock file format <https://peps.python.org/pep-0751/>`_
