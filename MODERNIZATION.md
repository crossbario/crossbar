# WAMP Python Stack Modernization

This document tracks the modernization effort across all WAMP Python packages and infrastructure repositories, working from the foundation up through the stack to Crossbar.io.

## Objective

Modernize the entire WAMP Python ecosystem to achieve:
- **Professional packaging and distribution** (RHEL9 native packages, PyPI wheels)
- **Modern build tooling** (pyproject.toml, ruff, uv, just, pytest, mypy)
- **Comprehensive CI/CD** (GitHub Actions with reusable workflows)
- **High-quality documentation** (Sphinx + Furo theme + RTD)
- **Enterprise-grade stability and maintainability**
- **Consistent infrastructure** (centralized git hooks, CI/CD actions via submodules)

## The Group of Projects and WAMP

This project is member of a _group of projects_ all related to
[WAMP](https://wamp-proto.org/), and it is _crucial_ to understand the
interrelation and dependencies between the projects in the group.

This is because those projects "all fit together" not by accident, but because
they were _designed_ for this from the very beginning. That's the whole reason
they exist. WAMP.

It all starts from:

- [WAMP](https://github.com/wamp-proto/wamp-proto/): The Web Application
  Messaging Protocol (the protocol specification and website)

The WAMP protocol is the umbrella project, and compliance to its specification
is a _top-priority_ for the _WAMP Client Library implementation projects_ in
the _group of projects_:

- [Autobahn|Python](https://github.com/crossbario/autobahn-python/): WebSocket
  & WAMP for Python on Twisted and asyncio.
- [Autobahn|JS](https://github.com/crossbario/autobahn-js): WAMP for Browsers
  and NodeJS.
- [Autobahn|Java](https://github.com/crossbario/autobahn-java): WebSocket &
  WAMP in Java for Android and Java 8
- [Autobahn|C++](https://github.com/crossbario/autobahn-cpp): WAMP for C++ in
  Boost/Asio

The only _WAMP Router implementation project_ (currently) in the _group of
projects_ is:

- [Crossbar.io](https://github.com/crossbario/crossbar): Crossbar.io is an open
  source networking platform for distributed and microservice applications. It
  implements the open Web Application Messaging Protocol (WAMP)

Again, compliance to the WAMP protocol implementation is a _top-priority_ for
Crossbar.io, as is compatibility with all _WAMP Client Library implementation
projects_ in the _group of projects_.

Further, it is crucial to understand that **Crossbar.io** is a Python project
which builds on **Autobahn|Python**, and more so, it builds on
[Twisted](https://twisted.org/).

While **Crossbar.io** only runs on **Twisted**, **Autobahn|Python** itself
crucially supports _both_ **Twisted** _and_ **asyncio** (in the Python standard
library) - by design.

This flexibility to allow users of **Autobahn|Python** to switch the underlying
networking framework between **Twisted** and **asyncio** seamlessly, and with
almost zero code changes on the user side, is also crucial, and this capability
is provided by:

- [txaio](https://github.com/crossbario/txaio/): txaio is a helper library for
  writing code that runs **unmodified** on **both** Twisted and asyncio /
  Trollius.

**Autobahn|Python** further provides both
[WebSocket](https://www.rfc-editor.org/rfc/rfc6455.html) _Client_ and _Server_
implementations, another crucial capability used in Crossbar.io, the group's
_WAMP Router implementation project_, and in Autobahn|Python, the group's _WAMP
Client Library implementation project_ for Python application code.

Stemming from the participation of the original developer (Tobias Oberstein) of
the _group of projects_ in the IETF HyBi working group during the RFC6455
specification, **Autobahn|Python** is also the basis for:

- [Autobahn|Testsuite](https://github.com/crossbario/autobahn-testsuite): The
  Autobahn|Testsuite provides a fully automated test suite to verify client and
  server implementations of The WebSocket Protocol (and WAMP) for specification
  conformance and implementation robustness.

**Autobahn|Python** fully conforms to RFC6455 and passes all of the hundreds of
WebSocket implementation tests in **Autobahn|Testsuite**.

Finally, **Crossbar.io** has a number of advanced features requiring
**persistence**, for example _WAMP Event History_ (see _WAMP Advanced Profile_)
and others, and these capabilities build on:

- [zLMDB](https://github.com/crossbario/zlmdb): Object-relational transactional
  in-memory database layer based on LMDB

which in turn is then used for the **Crossbar.io** specific embedded database
features:

- [cfxdb](https://github.com/crossbario/cfxdb): cfxdb is a Crossbar.io Python
  support package with core database access classes written in native Python.

### Python Runtime Requirements

All Python projects within the _group of projects_, that is:

- Autobahn|Python
- Crossbar.io
- txaio
- zLMDB
- cfxdb

must aim to:

- Maintain compatibility across Python versions
- Ensure consistent behavior between Twisted and asyncio backends (when applicable)

Further, all Python projects must support both:

- [CPython](https://www.python.org/), and
- [PyPy](https://pypy.org/)

as the Python (the language itself) run-time environment (the language
implementation).

This support is a MUST and a top-priority. Compatibility with other Python
run-time environments is currently not a priority.

Running on PyPy allows "almost C-like" performance, since PyPy is a _tracing
JIT compiler_ for Python with a _generational garbage collector_. Both of these
features are crucial for high-performance, throughput/bandwidth and consistent
low-latency in networking or WAMP in particular.

For reasons too long to lay out here, it is of the essence to only depend on
Python-level dependencies in all of the Python projects within the _group of
projects_ which:

- **DO** use [CFFI](https://cffi.readthedocs.io/en/latest/) to link native code
- **NOT** use CPyExt, the historically grown CPython extension API that is
  implementation defined only

This is a deep rabbit hole, but here is [one
link](https://pypy.org/posts/2018/09/inside-cpyext-why-emulating-cpython-c-8083064623681286567.html)
to dig into for some background.

## Repository Overview

### Infrastructure Repositories

```
0. wamp-proto         ← WAMP protocol specification + message test vectors
0. wamp-ai            ← Centralized AI policy, guidelines, git hooks
0. wamp-cicd          ← Centralized GitHub Actions, scripts, templates
```

### Application Repositories (Dependency Chain)

```
1. txaio              ← Foundation (Twisted/asyncio abstraction)
2. autobahn-python    ← WAMP client library
3. zlmdb              ← Database layer (LMDB + CFFI)
4. cfxdb              ← Crossbar DB access
5. wamp-xbr           ← XBR/Blockchain extensions
6. crossbar           ← WAMP Router (>160 transitive deps)
```

## Git Submodules Strategy

Every application repository should have the following submodules:

| Repository | Own Submodules | Vendored Submodules | Dependencies |
|------------|----------------|---------------------|--------------|
| wamp-proto | wamp-ai, wamp-cicd | - | - |
| txaio | wamp-ai, wamp-cicd | - | - |
| autobahn-python | wamp-ai, wamp-cicd, wamp-proto | flatbuffers | txaio |
| zlmdb | wamp-ai, wamp-cicd | flatbuffers, lmdb | txaio |
| cfxdb | wamp-ai, wamp-cicd, wamp-proto | - | autobahn-python, zlmdb |
| wamp-xbr | wamp-ai, wamp-cicd | - | autobahn-python |
| crossbar | wamp-ai, wamp-cicd, wamp-proto | - | autobahn-python, cfxdb, wamp-xbr |

**Key Points**:
- **wamp-ai**: Provides AI_GUIDELINES.md, AI_POLICY.md, git hooks (commit-msg, pre-push)
- **wamp-cicd**: Provides reusable GitHub Actions, scripts, templates
- **wamp-proto**: Provides WAMP message test vectors for serialization testing
- Submodules should always point to latest versions (bump during modernization)
- No edits to submodules in consuming repos (only version bumps)
- Setup via `just setup-repo` from `.ai/` directory (creates symlinks, configures git hooks)

## Modernization Matrix

| Modernization Task | wamp-proto | txaio | autobahn-python | zlmdb | cfxdb | wamp-xbr | crossbar |
|-------------------|------------|-------|-----------------|-------|-------|----------|----------|
| **Git Infrastructure** | | | | | | | |
| .ai submodule | ❓ | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| .cicd submodule | ❓ | ❓ | ✅ | ❓ | ❓ | ❓ | ❓ |
| wamp-proto submodule | N/A | N/A | ✅ | N/A | ❓ | N/A | ❓ |
| Git hooks configured | ❓ | ❓ | ✅ | ❓ | ❓ | ❓ | ❓ |
| **Build System** | | | | | | | |
| pyproject.toml (PEP 621) | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Remove setup.py | N/A | ⚠️ | ⚠️ | ⚠️ | ✅ | ⚠️ | ⚠️ |
| Remove setup.cfg | N/A | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ |
| Remove requirements.txt | N/A | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ |
| **Task Runner** | | | | | | | |
| justfile | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Remove Makefile | ❓ | ❓ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Remove tox.ini | N/A | ⚠️ | ❓ | ❓ | ❓ | ❓ | ❓ |
| **Code Quality** | | | | | | | |
| ruff (lint + format) | ❓ | ⚠️ | ❓ | ❓ | ❓ | ❓ | ✅ |
| ruff config in pyproject | ❓ | ❌ | ❓ | ❓ | ❓ | ❓ | ✅ |
| mypy (type checking) | N/A | ✅ | ❓ | ❓ | ❓ | ❓ | ✅ |
| mypy config in pyproject | N/A | ✅ | ❓ | ❓ | ❓ | ❓ | ✅ |
| **Testing** | | | | | | | |
| pytest | ❓ | ✅ | ✅ | ❓ | ❓ | ❓ | ✅ |
| pytest coverage | ❓ | ✅ | ✅ | ❓ | ❓ | ❓ | ✅ |
| **Dependencies** | | | | | | | |
| uv support | ✅ | ✅ | ✅ | ❓ | ❓ | ❓ | ✅ |
| Dep version audit | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **CI/CD** | | | | | | | |
| GitHub Actions | ✅ | ✅ | ✅ | ❓ | ❓ | ❓ | ✅ |
| Matrix testing | ❓ | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Wheel building | N/A | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| PyPI publishing | N/A | ❓ | ✅ | ❓ | ❓ | ❓ | ❓ |
| **Documentation** | | | | | | | |
| Modern Sphinx | ✅ | ✅ | ✅ | ❓ | ❓ | ❓ | ✅ |
| Furo theme | ❓ | ❌ | ❓ | ❓ | ❓ | ❓ | ❌ |
| RTD integration | ✅ | ✅ | ✅ | ❓ | ❓ | ❓ | ✅ |
| API docs | ✅ | ✅ | ✅ | ❓ | ❓ | ❓ | ⚠️ |
| **Packaging** | | | | | | | |
| Native wheels | N/A | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| CFFI (not CPyExt) | N/A | N/A | ✅ | ✅ | N/A | N/A | ✅ |
| RHEL9 RPM | N/A | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Code Cleanup** | | | | | | | |
| TODO/FIXME audit | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ |
| Type hints | ✅ | ⚠️ | ⚠️ | ❓ | ❓ | ❓ | ⚠️ |
| Docstrings | ✅ | ⚠️ | ⚠️ | ❓ | ❓ | ❓ | ⚠️ |

**Legend**:
- ✅ Complete
- ⚠️ Partially done / needs work
- ❌ Not started
- ❓ Status unknown / needs audit
- N/A Not applicable

## Phase 0: Infrastructure Setup

**Objective**: Fix foundation repositories (wamp-ai, wamp-cicd) before building on them.

**Philosophy**: Bottom-up approach - ensure infrastructure is solid before modernizing application repos.

### Phase 0.1: wamp-ai

**Status**: 3 open issues (all blockers)

**Tasks**:
1. [ ] Fix #1: Print note to disable pre-push hook for human tagging
   - Location: `.ai/.githooks/pre-push`
   - Issue: https://github.com/wamp-proto/wamp-ai/issues/1
2. [ ] Fix #2: Prevent AI commits to master/main branch
   - Location: `.ai/.githooks/commit-msg` or new hook
   - Issue: https://github.com/wamp-proto/wamp-ai/issues/2
3. [ ] Fix #4: Add audit file template
   - Location: `.ai/templates/AUDIT.md`
   - Issue: https://github.com/wamp-proto/wamp-ai/issues/4

**Deliverables**:
- Updated git hooks with human-friendly messages
- Audit file template for use in all repos
- Documentation updates in wamp-ai README.md

### Phase 0.2: wamp-cicd

**Status**: 2 open issues (all blockers)

**Tasks**:
1. [ ] Fix #1: Add reusable GitHub Issue and PR templates
   - Location: `.cicd/templates/`
   - Issue: https://github.com/wamp-proto/wamp-cicd/issues/1
2. [ ] Fix #2: Add validate-audit-file reusable action
   - Location: `.cicd/actions/validate-audit-file/`
   - Issue: https://github.com/wamp-proto/wamp-cicd/issues/2

**Deliverables**:
- Reusable Issue/PR templates (to be copied into repos)
- GitHub Action for validating audit files
- Documentation for using reusable actions

**Phase 0 Blockers**: None

#### Phase 0 Completion Summary

**Status**: ✅ **COMPLETE** (2025-11-25)

Infrastructure repositories successfully updated with all Phase 0 improvements:

| Repository | Commit | Issues Completed | Description |
|------------|--------|------------------|-------------|
| wamp-ai | [ef27ea8](https://github.com/wamp-proto/wamp-ai/commit/ef27ea8) | [#1](https://github.com/wamp-proto/wamp-ai/issues/1), [#2](https://github.com/wamp-proto/wamp-ai/issues/2), [#4](https://github.com/wamp-proto/wamp-ai/issues/4) | Git hooks, audit templates, AI policy |
| wamp-cicd | [e3d9e93](https://github.com/wamp-proto/wamp-cicd/commit/e3d9e93) | [#1](https://github.com/wamp-proto/wamp-cicd/issues/1), [#2](https://github.com/wamp-proto/wamp-cicd/issues/2) | GitHub templates, CI/CD actions |

**Completed Work**:

**wamp-ai (ef27ea8)**:
- Added human-friendly message to `.githooks/pre-push` for tag management (#1)
- Implemented branch protection in `.githooks/commit-msg` to prevent AI commits to master/main (#2)
- Created audit file template at `templates/AUDIT.md` with just recipe `generate-audit-file` (#4)
- Updated documentation in README.md

**wamp-cicd (e3d9e93)**:
- Added GitHub Issue templates (bug_report.md, feature_request.md, config.yml) (#1)
- Added GitHub PR template (pull_request_template.md) (#1)
- Created `just deploy-github-templates` recipe for easy template deployment (#1)
- Added validate-audit-file reusable GitHub Action (#2)
- Updated documentation in README.md

**Infrastructure Foundation**:
- ✅ Centralized AI policy and git hooks (wamp-ai)
- ✅ Consistent Issue/PR templates ready for deployment (wamp-cicd)
- ✅ Audit file generation and validation system
- ✅ Reusable CI/CD infrastructure (GitHub Actions)
- ✅ All Phase 1 work built on this solid foundation

## Phase 1: Per-Repo Modernization

**Objective**: Modernize all 7 application repositories in dependency order with consistent tooling.

**Execution Strategy**: Complete each sub-phase across all repos before moving to the next sub-phase.

**Repository Order** (dependencies):
1. wamp-proto (no Python deps)
2. txaio (no deps)
3. autobahn-python (deps: txaio)
4. zlmdb (deps: txaio)
5. cfxdb (deps: autobahn-python, zlmdb)
6. wamp-xbr (deps: autobahn-python)
7. crossbar (deps: autobahn-python, cfxdb, wamp-xbr)

### Phase 1.1: Git Submodules Setup

**Objective**: Ensure all repos have proper git infrastructure (submodules, hooks, symlinks).

**Tasks per repository**:
1. [ ] Add/update `.ai` submodule to latest wamp-ai
2. [ ] Add/update `.cicd` submodule to latest wamp-cicd
3. [ ] Add `wamp-proto` submodule if applicable (autobahn-python, cfxdb, crossbar)
4. [ ] Run `just setup-repo` from `.ai/` directory
5. [ ] Verify git hooks are active: `git config core.hooksPath`
6. [ ] Commit symlinks (CLAUDE.md, AI_POLICY.md, .gemini/GEMINI.md)
7. [ ] Commit git config changes
8. [ ] Test git hooks work (try committing with "Co-Authored-By: AI")
9. [ ] Push to bare repo

**Deliverables per repository**:
- `.ai/` submodule at latest version
- `.cicd/` submodule at latest version
- `wamp-proto` submodule at latest version (if applicable)
- Git hooks configured and tested
- All symlinks committed

**Blockers**: Requires Phase 0 complete

#### Phase 1.1 Completion Summary

**Status**: ✅ **COMPLETE** (2025-11-25)

All repositories successfully updated with Phase 1.1 infrastructure:

| Repository | Branch | Issue | PR | Status |
|------------|--------|-------|----|----|
| wamp-proto | fix_556 | [#556](https://github.com/wamp-proto/wamp-proto/issues/556) | [#557](https://github.com/wamp-proto/wamp-proto/pull/557) | ⏸️ Pending review |
| txaio | modernization-phase-1.1 | [#200](https://github.com/crossbario/txaio/issues/200) | [#201](https://github.com/crossbario/txaio/pull/201) | ✅ Merged |
| autobahn-python | modernization-phase-1.1 | [#1784](https://github.com/crossbario/autobahn-python/issues/1784) | [#1785](https://github.com/crossbario/autobahn-python/pull/1785) | ✅ Merged |
| zlmdb | modernization-phase-1.1 | [#77](https://github.com/crossbario/zlmdb/issues/77) | [#78](https://github.com/crossbario/zlmdb/pull/78) | ✅ Merged |
| cfxdb | modernization-phase-1.1 | [#97](https://github.com/crossbario/cfxdb/issues/97) | [#98](https://github.com/crossbario/cfxdb/pull/98) | ✅ Merged |
| wamp-xbr | modernization-phase-1.1 | [#153](https://github.com/wamp-proto/wamp-xbr/issues/153) | [#152](https://github.com/wamp-proto/wamp-xbr/pull/152) | ✅ Merged |
| crossbar | modernization-take1 | [#2138](https://github.com/crossbario/crossbar/issues/2138) | [#2139](https://github.com/crossbario/crossbar/pull/2139) | ⏳ In progress |

**Completed Work**:
- Updated `.ai` submodule to `ef27ea8` (audit file generation, simplified AI_POLICY.md reference)
- Updated `.cicd` submodule to `e3d9e93` (GitHub templates, deploy recipe)
- Deployed GitHub Issue/PR templates to all repos (`.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE/`)
- Created audit files documenting AI-assisted work (`.audit/oberstet_modernization-phase-11.md`)
- Configured git hooks via `.ai/.githooks` (commit-msg, pre-push)
- All changes verified and synced across asgard1 ↔ bare repos ↔ dev PC ↔ GitHub

**Infrastructure Foundation Established**:
- ✅ Centralized AI policy enforcement via git hooks
- ✅ Consistent Issue/PR templates across ecosystem
- ✅ Audit trail for AI-assisted work
- ✅ Reusable CI/CD infrastructure ready for Phase 1.2+

### Phase 1.2: Per-Repo Infrastructure

**Objective**: Complete per-repository infrastructure modernization including build tooling, wheel building, documentation, and test coverage.

**Branch**: `modernization-phase-1.2` (all sub-phases on same branch)

**Repository Order** (dependencies):
1. wamp-proto (no Python deps) - uses branch `fix_556`
2. txaio (no deps)
3. autobahn-python (deps: txaio)
4. zlmdb (deps: txaio)
5. cfxdb (deps: autobahn-python, zlmdb)
6. wamp-xbr (deps: autobahn-python)
7. crossbar (deps: autobahn-python, cfxdb, wamp-xbr)

#### Common Justfile Recipes Specification

All repositories MUST implement the following common justfile recipes with consistent behavior.
Repository-specific recipes may be added as needed, but the common set ensures uniform developer experience.

**Environment Management:**
| Recipe | Parameters | Description |
|--------|------------|-------------|
| `create` | `venv=""` | Create a single Python virtual environment |
| `create-all` | - | Meta-recipe to run `create` on all environments |
| `list-all` | - | List all Python virtual environments |
| `version` | `venv=""` | Get the version of a single environment's Python |
| `version-all` | - | Get versions of all Python virtual environments |

**Installation:**
| Recipe | Parameters | Description |
|--------|------------|-------------|
| `install` | `venv=""` | Install this package and its run-time dependencies |
| `install-all` | - | Meta-recipe to run `install` on all environments |
| `install-dev` | `venv=""` | Install this package in development (editable) mode |
| `install-dev-all` | - | Meta-recipe to run `install-dev` on all environments |
| `install-tools` | `venv=""` | Install development tools (ruff, mypy, pytest, etc.) |
| `install-tools-all` | - | Meta-recipe to run `install-tools` on all environments |
| `upgrade` | `venv=""` | Upgrade dependencies in a single environment |
| `upgrade-all` | - | Meta-recipe to run `upgrade` on all environments |

**Quality Checks:**
| Recipe | Parameters | Description |
|--------|------------|-------------|
| `check` | `venv=""` | Run all checks (format, typing, security) in single environment |
| `check-format` | `venv=""` | Lint code using Ruff |
| `check-typing` | `venv=""` | Run static type checking with mypy |
| `check-coverage` | `venv=""` | Combined coverage report from tests |
| `fix-format` | `venv=""` | Automatically fix all formatting and code style issues |

**Build/Package:**
| Recipe | Parameters | Description |
|--------|------------|-------------|
| `build` | `venv=""` | Build wheel only |
| `build-all` | - | Meta-recipe to run `build` on all environments |
| `build-sourcedist` | `venv=""` | Build source distribution only (no wheels) |
| `verify-wheels` | `venv=""` | Verify wheels using twine check and auditwheel |
| `clean-build` | - | Clean build artifacts |

**Testing:**
| Recipe | Parameters | Description |
|--------|------------|-------------|
| `test` | `venv=""` | Run unit tests |
| `test-all` | - | Meta-recipe to run `test` on all environments |

**Documentation:**
| Recipe | Parameters | Description |
|--------|------------|-------------|
| `docs` | `venv=""` | Build the HTML documentation using Sphinx |
| `docs-clean` | - | Clean the generated documentation |
| `docs-view` | `venv=""` | Build documentation and open in system viewer |

**Publishing:**
| Recipe | Parameters | Description |
|--------|------------|-------------|
| `publish` | `venv="" tag=""` | Publish to both PyPI and Read the Docs (meta-recipe) |
| `publish-pypi` | `venv="" tag=""` | Download release artifacts from GitHub and publish to PyPI |
| `publish-rtd` | `tag=""` | Trigger Read the Docs build for a specific tag |
| `download-github-release` | `release_type="nightly"` | Download GitHub release artifacts |

**Cleanup/Utility:**
| Recipe | Parameters | Description |
|--------|------------|-------------|
| `default` | - | Default recipe: show project header and list all recipes |
| `distclean` | - | Remove ALL generated files (venvs, caches, build artifacts) |
| `setup-completion` | - | Setup bash tab completion for the current user |

**Notes:**
- `venv=""` parameter accepts values like `cpy311`, `cpy314`, `pypy311`, or empty for default
- `verify-wheels` should print "skipped because not binary" for pure Python packages
- Repository-specific recipes (e.g., autobahn's NVX flags, wamp-xbr's Solidity builds) are allowed in addition to common set

---

#### Phase 1.2.1: Build Tooling

**Objective**: Modernize build systems to use pyproject.toml, ruff, uv, just, pytest, mypy.

**Tasks per repository**:
1. [x] Audit current build system status
2. [x] Add/update ruff configuration in pyproject.toml
3. [x] Remove flake8 configuration (replaced by ruff)
4. [x] Add/update mypy configuration in pyproject.toml
5. [x] Remove tox configuration (replaced by justfile) - renamed to .orig
6. [x] Add/update pytest configuration in pyproject.toml
7. [x] Add/update coverage configuration in pyproject.toml
8. [x] Verify justfile has all necessary recipes (test, check-format, check-typing, build, etc.)
9. [x] Remove/minimize setup.py (keep minimal shim if needed for editable installs)
10. [x] Remove setup.cfg if exists - renamed to .orig
11. [x] Remove requirements.txt (move to pyproject.toml) - N/A for most repos
12. [x] Run `just check` to verify ruff/bandit pass (mypy has known type issues)
13. [x] Commit changes and push to bare repo

**Deliverables per repository**:
- pyproject.toml with complete modern configuration
- No legacy build files (setup.py minimized, setup.cfg/requirements.txt removed)
- ruff, mypy, pytest configured
- justfile with comprehensive recipes
- All checks passing

**Blockers**: Requires Phase 1.1 complete

##### Phase 1.2.1 Completion Summary

**Status**: ✅ **COMPLETE** (2025-11-26)

All repositories have completed Phase 1.2.1 build tooling modernization:

| Repository | Branch | Issue | PR | Status |
|------------|--------|-------|----|----|
| txaio | modernization-phase-1.2 | [#202](https://github.com/crossbario/txaio/issues/202) | [#203](https://github.com/crossbario/txaio/pull/203) | ✅ Complete |
| autobahn-python | modernization-phase-1.2 | [#1787](https://github.com/crossbario/autobahn-python/issues/1787) | [#1788](https://github.com/crossbario/autobahn-python/pull/1788) | ✅ Complete |
| zlmdb | modernization-phase-1.2 | [#79](https://github.com/crossbario/zlmdb/issues/79) | [#80](https://github.com/crossbario/zlmdb/pull/80) | ✅ Complete |
| cfxdb | modernization-phase-1.2 | [#102](https://github.com/crossbario/cfxdb/issues/102) | [#103](https://github.com/crossbario/cfxdb/pull/103) | ✅ Complete |
| wamp-xbr | modernization-phase-1.2 | [#154](https://github.com/wamp-proto/wamp-xbr/issues/154) | [#155](https://github.com/wamp-proto/wamp-xbr/pull/155) | ✅ Complete |
| crossbar | modernization-phase-1.2 | [#2140](https://github.com/crossbario/crossbar/issues/2140) | [#2141](https://github.com/crossbario/crossbar/pull/2141) | ✅ Complete |

**Completed Work**:

All repositories now have:
- ✅ pyproject.toml with PEP 621 metadata, ruff, mypy, pytest, coverage configs
- ✅ Comprehensive justfile with standardized recipes
- ✅ Legacy files renamed to .orig (setup.cfg, tox.ini)
- ✅ setup.py minimized to shim with env vars (LMDB_FORCE_CFFI, etc.)
- ✅ PEP 639 compliant license expressions
- ✅ Verified builds passing (twine check, wheel builds)

**Verification Results**:
- ruff format/lint: PASSED (all repos)
- bandit security: PASSED (no medium/high severity)
- twine check: PASSED (all wheels valid)
- mypy: Known type issues exist (disallow_untyped_defs=false) - not blocking

**Notes**:
- wamp-xbr has dual build system (Python + Solidity/Truffle) - justfile wraps Makefile targets
- crossbar's `install-dev-local` recipe enables cross-repo development with editable installs

#### Phase 1.2.2: Wheel Building

**Objective**: Ensure native wheels for all platforms (x86-64, ARM64) and Python implementations (CPython, PyPy).

**Tasks per repository**:
1. [x] Audit current wheel building status
2. [x] Verify CFFI usage (not CPyExt) for native extensions
3. [x] Add/update GitHub Actions for wheel building
4. [x] Test wheel building locally: `just build cpy311`
5. [x] Test wheel building for PyPy: `just build pypy311`
6. [x] Configure ARM64 wheel building (GitHub Actions or cross-compile)
7. [x] Verify wheels are manylinux compatible (auditwheel check)
8. [x] Test wheels on different platforms
9. [x] Configure PyPI publishing workflow (release.yml with trusted publishing)
10. [x] Commit changes and push to bare repo

**Deliverables per repository**:
- Native wheels for x86-64 (CPython 3.11-3.14, PyPy 3.11)
- Native wheels for ARM64 (CPython 3.11-3.14, PyPy 3.11)
- GitHub Actions for automated wheel building
- PyPI publishing workflow ready

**Blockers**: Requires Phase 1.2.1 complete

##### Phase 1.2.2 Completion Summary

**Status**: ✅ **COMPLETE** (2025-11-27)

All repositories have completed Phase 1.2.2 wheel building modernization:

| Repository | Wheel Type | release.yml | PyPI Trusted | Status |
|------------|------------|-------------|--------------|--------|
| txaio | `py3-none-any` | ✅ | ✅ | ✅ Complete |
| autobahn-python | `cp3xx-*` (CFFI) | ✅ | ✅ | ✅ Complete |
| zlmdb | `cp3xx-*` (CFFI) | ✅ | ✅ | ✅ Complete |
| cfxdb | `py3-none-any` | ✅ | ✅ | ✅ Complete |
| wamp-xbr | `py2.py3-none-any` | ✅ | ✅ | ✅ Complete |
| crossbar | `py3-none-any` | ✅ | ✅ | ✅ Complete |

**Completed Work**:

1. **Wheel Building Verified**:
   - All repos: `just build cpy311` works correctly
   - Pure Python packages: `py3-none-any` wheels (txaio, cfxdb, wamp-xbr, crossbar)
   - CFFI packages: Platform-specific wheels with auditwheel verification (autobahn-python, zlmdb)

2. **GitHub Actions Standardization**:
   - All repos now use single `release.yml` for releases
   - Legacy workflows retired (deploy.yml, deploy-wheels.yml → .orig)
   - PyPI trusted publishing (OIDC) configured
   - GitHub Releases created automatically

3. **Multi-Platform Support** (autobahn-python, zlmdb):
   - Linux x86_64: manylinux compatible
   - macOS ARM64: Native wheels
   - Windows x86_64: Native wheels
   - PyPy 3.11: Supported

4. **Wheel Verification**:
   - twine check: All wheels pass
   - auditwheel: manylinux_2_5/2_34 compatible (CFFI packages)
   - Pure Python: "skipped - no native extensions" (correct)

**Notes**:
- Pure Python packages don't need manylinux/auditwheel (no native extensions)
- CFFI packages use vendored bindings (zlmdb vendors lmdb)
- All packages use PyPI trusted publishing (no password secrets needed)

#### Standardized Project Directory Structure

**Objective**: Adopt modern Python project structure (2025 best practices) across all 6 repos.

All WAMP Python projects follow the **src layout** as recommended by:
- [Python Packaging User Guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [uv project structure](https://docs.astral.sh/uv/concepts/projects/layout/)
- [pyOpenSci Python Package Guide](https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html)

##### Why src Layout?

1. **Test isolation**: Tests run against the installed package, not source directory
2. **Import safety**: Package must be installed to be imported (catches packaging issues early)
3. **Smaller wheels**: Tests excluded from distribution automatically
4. **Modern tooling**: Default for `uv init --lib`, Hatch, PDM, and other modern tools
5. **Clear separation**: Source, tests, and docs are clearly separated

##### Standard Directory Structure (All 6 Repos)

```
package-name/
├── .ai/                      # Git submodule: wamp-ai (AI policy, git hooks)
├── .cicd/                    # Git submodule: wamp-cicd (GitHub Actions, templates)
├── .github/                  # GitHub-specific (Issues, PR templates, workflows)
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE/
│   └── workflows/
│       ├── main.yml          # CI: lint, test, coverage
│       └── release.yml       # CD: build wheels, publish PyPI
├── .venvs/                   # Local virtual environments (gitignored)
├── docs/                     # Sphinx documentation
│   ├── _static/              # Static assets (CSS, images, SVGs)
│   ├── _templates/           # Custom Sphinx templates
│   ├── conf.py               # Sphinx configuration
│   ├── index.md              # Documentation entry point (MyST)
│   └── spelling_wordlist.txt # Project-specific spelling dictionary
├── examples/                 # Example code and usage demos
│   ├── README.md             # Examples overview
│   └── ...                   # Example scripts/projects
├── src/                      # Source code root (PEP 517 src layout)
│   └── package_name/         # Actual package (importable name)
│       ├── __init__.py
│       ├── _version.py       # Version (single source of truth)
│       ├── py.typed          # PEP 561 type marker (libraries only)
│       └── ...               # Package modules
├── tests/                    # Test suite (AT PROJECT ROOT, not in src/)
│   ├── __init__.py
│   ├── conftest.py           # pytest fixtures
│   └── test_*.py             # Test modules
├── .gitignore
├── .readthedocs.yaml         # RTD build configuration
├── AI_POLICY.md -> .ai/AI_POLICY.md
├── CHANGELOG.md              # Release history
├── CLAUDE.md -> .ai/AI_GUIDELINES.md
├── LICENSE
├── README.md                 # GitHub landing page
├── justfile                  # Task runner
├── pyproject.toml            # Package metadata and tool configuration (SINGLE SOURCE)
└── uv.lock                   # Locked dependencies (committed to VCS)
```

**Key directory placement rules:**

| Directory | Location | Rationale |
|-----------|----------|-----------|
| `src/` | Project root | Contains only importable package code |
| `tests/` | Project root | **NOT inside src/** - excluded from wheel automatically |
| `examples/` | Project root | Example code for users, excluded from wheel |
| `docs/` | Project root | Sphinx documentation, excluded from wheel |

##### Application vs Library: The Only Difference

Crossbar uses the **same src layout** as the 5 libraries. The only structural difference
is the `[project.scripts]` section in pyproject.toml, which creates an executable CLI:

```toml
# Libraries: no scripts section (or optional CLI tools)
# Application (crossbar): CLI entry point
[project.scripts]
crossbar = "crossbar:run"
```

This tells Python to create an executable binary named `crossbar` when installed, which
invokes the `run()` function from the `crossbar` package.

**Note**: Applications don't need `py.typed` since they're not imported by other packages.

##### Key PEP Compliance

| PEP | Description | Implementation |
|-----|-------------|----------------|
| [PEP 517](https://peps.python.org/pep-0517/) | Build system interface | `[build-system]` in pyproject.toml |
| [PEP 518](https://peps.python.org/pep-0518/) | Build requirements | `requires` in `[build-system]` |
| [PEP 621](https://peps.python.org/pep-0621/) | Project metadata | `[project]` in pyproject.toml |
| [PEP 660](https://peps.python.org/pep-0660/) | Editable installs | `pip install -e .` with modern backends |
| [PEP 561](https://peps.python.org/pep-0561/) | Type information | `py.typed` marker + type hints |
| [PEP 639](https://peps.python.org/pep-0639/) | License expression | `license = "MIT"` (SPDX identifier) |

##### pyproject.toml Structure

```toml
[build-system]
requires = ["setuptools>=70.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "package-name"
version = "25.11.1"
description = "Package description"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    {name = "typedef int GmbH", email = "contact@typedefint.eu"}
]
keywords = ["wamp", "websocket", "rpc", "pubsub"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: Implementation :: CPython",
    "Programming Language :: Python :: Implementation :: PyPy",
]

dependencies = [
    # Runtime dependencies
]

[project.optional-dependencies]
docs = [
    # Documentation tools (see Phase 1.2.3)
]
dev = [
    # Developer tools (lint, test, build)
]

[project.urls]
Homepage = "https://github.com/crossbario/package-name"
Documentation = "https://package-name.readthedocs.io"
Repository = "https://github.com/crossbario/package-name"
Issues = "https://github.com/crossbario/package-name/issues"

# CLI entry points (crossbar only)
[project.scripts]
crossbar = "crossbar:run"

[tool.setuptools.packages.find]
where = ["src"]
include = ["package_name*"]

[tool.setuptools.package-data]
package_name = ["py.typed"]

# Tool configurations (ruff, mypy, pytest, coverage)
# See Phase 1.2.1 for details
```

##### Migration from Flat Layout to src Layout

For each repo, the migration involves:

1. **Create src directory**: `mkdir -p src`
2. **Move package**: `git mv package_name src/package_name`
3. **Move tests out** (if inside package): `git mv src/package_name/tests tests`
4. **Add py.typed**: `touch src/package_name/py.typed`
5. **Update pyproject.toml**: Change `[tool.setuptools.packages.find]` to use `where = ["src"]`
6. **Update imports in tests**: Change from `from package_name` to same (no change needed, installed package)
7. **Update docs/conf.py**: Adjust `sys.path` if needed for autoapi
8. **Verify build**: `just build && just test`

##### Files to Remove (Legacy - No Exceptions)

For 2025, all legacy build/config files are **deleted** (not renamed, not kept as shims):

| File | Action | Reason |
|------|--------|--------|
| `setup.py` | **DELETE** | Replaced by pyproject.toml - no shim needed with modern pip/uv |
| `setup.cfg` | **DELETE** | Replaced by pyproject.toml |
| `tox.ini` | **DELETE** | Replaced by justfile |
| `Makefile` | **DELETE** | Replaced by justfile |
| `requirements.txt` | **DELETE** | Replaced by pyproject.toml + uv.lock |
| `requirements-dev.txt` | **DELETE** | Replaced by `[project.optional-dependencies]` |
| `MANIFEST.in` | **DELETE** | setuptools auto-discovers with pyproject.toml |
| `.flake8` | **DELETE** | Replaced by ruff in pyproject.toml |
| `mypy.ini` | **DELETE** | Replaced by `[tool.mypy]` in pyproject.toml |
| `pytest.ini` | **DELETE** | Replaced by `[tool.pytest.ini_options]` in pyproject.toml |
| `.pylintrc` | **DELETE** | Replaced by ruff |
| `yapf.ini` / `.style.yapf` | **DELETE** | Replaced by ruff formatter |

**Note**: Modern pip (23.1+) and uv fully support PEP 517/518/621. No `setup.py` shim is needed.

##### Dependency Specification Policy

Different strategies for libraries vs applications:

###### Libraries (txaio, autobahn-python, zlmdb, cfxdb, wamp-xbr)

**Strategy**: Maximize Compatibility ("floats on top of the latest ecosystem", "can be installed alongside other packages in one venv")

| Aspect | Policy |
|--------|--------|
| `pyproject.toml` | Define direct dependencies with lower bounds (`>=`), upper bounds only if absolutely required (`<`) |
| `uv.lock` | **DO NOT include** - would unnecessarily constrain downstream users |
| CI/CD | Uses open-ended (`>=`) deps - simulates exactly what end-users experience with `pip install` |

**Rationale**: If a dependency releases a breaking change, CI fails immediately, alerting us to fix our code or cap the version (e.g., `<3.0`). This catches compatibility issues before users do.

###### Application (crossbar)

**Strategy**: Maximize Reproducibility ("recommended to install in a dedicated venv")

| Aspect | Policy |
|--------|--------|
| `pyproject.toml` | Define direct dependencies with sensible guards (`>=`), upper bounds only if required |
| `uv.lock` | **MUST be committed to Git** - ensures exact reproducibility |
| CI/CD | Uses `uv sync --frozen` to install exact pinned deps (direct + transitive) |

**Release workflow**:
1. Before release: `uv sync --upgrade` to update all deps to latest stable
2. Run full test suite (unit, functional, integration)
3. Commit updated `uv.lock` with the release
4. Tag release in Git
5. Publish to PyPI (convenience channel)
6. Build Docker images from Git tag (production channel)

**Distribution channels**:

| Channel | Strictness | Use Case |
|---------|------------|----------|
| PyPI (`pip install crossbar`) | Medium | Convenience, development |
| Git + Docker + uv (`uv sync --frozen`) | **Maximum** | Production, security-critical |

**Production Dockerfile example**:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Clone the specific tag to get the uv.lock
RUN git clone --branch v2025.1.0 https://github.com/crossbario/crossbar /app
WORKDIR /app

# Install EXACTLY what was tested - frozen deps, hash verification, no editable installs
RUN uv sync --frozen --no-dev --no-editable --require-hashes

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["crossbar"]
```

This guarantees customers running Docker get the **exact bytes** tested in CI/CD and verified in integration testing.

**uv flags explained**:
- `--frozen`: Use exact versions from `uv.lock`, fail if lock file is missing or outdated
- `--no-dev`: Exclude development dependencies
- `--no-editable`: Install as regular packages, not editable (more robust)
- `--require-hashes`: Verify package integrity via cryptographic hashes in `uv.lock`

**References**:
- [PEP 621](https://peps.python.org/pep-0621/) - Project metadata in pyproject.toml
- [PEP 751](https://peps.python.org/pep-0751/) - Lock file format (standard `pylock.toml`)
- [uv lock documentation](https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile)

**Note on lock file formats**: We standardize on `uv.lock` (uv-native format) for all tooling.
PEP 751 defines a standard `pylock.toml` format - export via `uv export -o pylock.toml` if needed
for interoperability with other tools.

##### Standard .gitignore

```gitignore
# Build artifacts
build/
dist/
*.egg-info/
*.egg
*.whl

# Virtual environments
.venv/
.venvs/
venv/

# Cache
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Documentation build
docs/_build/
docs/_autosummary/
docs/autoapi/

# OS
.DS_Store
Thumbs.db

# uv
.uv-cache/
# NOTE: uv.lock is committed for crossbar (application), NOT committed for libraries

# Project-specific
dist-universe/
```

---

#### Phase 1.2.3: Documentation

**Objective**: Modernize documentation with Sphinx + Furo theme + RTD integration across all 6 Python repos.

##### Goals

1. **Sphinx with Furo Theme**: All repos use modern Furo theme (not sphinx_rtd_theme)
2. **sphinx-autoapi**: Use sphinx-autoapi for API docs (NOT autodoc)
3. **Noto Fonts**: Configure Furo with Google Noto font family for consistency
4. **Standardized Justfile Recipes**:
   - `docs`: Build HTML documentation
   - `docs-check`: Run Sphinx spelling checker against `docs/spelling_wordlist.txt`
   - `docs-clean`: Clean generated documentation
   - `publish-rtd`: Trigger RTD build for tag/release
5. **RTD Configuration**: Each repo has `.readthedocs.yaml` (ubuntu-24.04, Python 3.11)
6. **Consistent pyproject.toml**: Documentation deps in `[docs]` extra, dev tools in `[dev]` extra

##### Standard .readthedocs.yaml Template

```yaml
version: 2

build:
  os: ubuntu-24.04
  tools:
    python: "3.11"

python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs

sphinx:
  configuration: docs/conf.py
```

##### Standard Documentation Dependencies (pyproject.toml)

Documentation tools are in a separate `[docs]` extra (used by RTD), while `[dev]` contains
developer tools. Developers install with `pip install -e ".[dev,docs]"`.

```toml
[project.optional-dependencies]
# Documentation tools (used by RTD via .readthedocs.yaml)
docs = [
    # --- Core Sphinx + MyST ---
    "sphinx>=7.2",
    "myst-parser>=2.0",

    # --- Theme ---
    "furo>=2024.7.0",

    # --- API docs (modern, fast, no-import parsing) ---
    "sphinx-autoapi>=2.1.0",

    # --- UX Enhancements ---
    "sphinx-copybutton>=0.5",
    "sphinx-design>=0.5",

    # --- Images (optional but useful; works with Sphinx 7) ---
    "sphinxcontrib-images>=0.9",

    # --- Spell checking ---
    "sphinxcontrib-spelling>=8.0",
    "pyenchant>=3.2",

    # --- Static asset optimization ---
    "scour>=0.38",

    # --- Social previews ---
    "sphinxext-opengraph>=0.9",

    # --- Optional (improves auto-linking in MyST) ---
    "linkify-it-py>=2.0.0",
]

# Developer tools (linting, testing, building)
dev = [
    # Build tools
    "build>=1.0.0",
    "wheel>=0.42.0",
    "twine>=5.0.0",

    # Testing
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "coverage>=7.0.0",

    # Code quality
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

**Installation patterns:**
- **RTD builds**: `.readthedocs.yaml` uses `extra_requirements: [docs]`
- **Developers**: `pip install -e ".[dev,docs]"` or `just install-dev` (which installs both)
- **CI/CD**: Install `[dev]` for testing, `[docs]` for doc builds

**Notes on key dependencies:**
- **sphinx-autoapi**: Uses static analysis (no imports) - crucial for txaio/autobahn where importing both Twisted and asyncio modules simultaneously would fail
- **myst-parser**: Allows writing docs in Markdown alongside RST - gradual migration possible
- **sphinx-design**: Provides Bootstrap-like components (cards, tabs, grids, badges)
- **sphinxext-opengraph**: Generates `<meta>` tags for better link previews on social media/Slack/Discord
- **scour**: SVG optimization tool (preferred format for diagrams) - cleans/optimizes SVG files at build time

##### MyST Markdown vs reStructuredText Strategy

**MyST Markdown is the preferred format for modern Python documentation in 2025.**

MyST (Markedly Structured Text) provides full Sphinx functionality with Markdown syntax:
- Cross-referencing functions, classes, methods
- Type linking
- API auto-generation (via AutoAPI)
- Sphinx domains (Python, JavaScript, etc.)
- Math, admonitions, TOCs
- Multi-page structuring
- Full RTD compatibility

MyST is now recommended by Sphinx core for narrative documentation, and is used by
FastAPI, Pydantic, NumPy (migrating), Jupyter ecosystem, Furo, and Scientific Python projects.

**Recommended Format by Documentation Type:**

| Documentation Type | Format | Rationale |
|--------------------|--------|-----------|
| API Reference | AutoAPI (auto-generated) | Zero maintenance, parsed from source |
| Tutorials / How-tos | MyST Markdown | Clean, readable, easy to write |
| Explanations / Concepts | MyST Markdown | Best readability for narrative |
| Changelogs | Markdown | Conventional format |
| README | Markdown | GitHub-friendly rendering |
| Legacy RST docs | Keep RST (migrate gradually) | No forced migration |

**Migration Strategy for Existing Repos:**

1. **Enable MyST alongside RST** - Both formats work in same docs/ directory
2. **Write new docs in MyST** - All new tutorials, guides in `.md` files
3. **Gradual RST migration** - Convert RST files to MyST as they are updated
4. **Keep API docs auto-generated** - AutoAPI handles this automatically

**MyST Configuration (docs/conf.py):**

```python
extensions = [
    "myst_parser",
    # ... other extensions
]

# MyST configuration
myst_enable_extensions = [
    "colon_fence",      # ::: directive syntax
    "deflist",          # Definition lists
    "fieldlist",        # Field lists
    "html_admonition",  # HTML admonitions
    "html_image",       # HTML images
    "linkify",          # Auto-link URLs (requires linkify-it-py)
    "replacements",     # Text replacements
    "smartquotes",      # Smart quotes
    "strikethrough",    # ~~strikethrough~~
    "substitution",     # Substitutions
    "tasklist",         # Task lists (- [ ] item)
]

# Allow both .rst and .md source files
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
```

##### Standard docs/conf.py (Complete Template)

This is the complete, standardized Sphinx configuration for all 6 WAMP Python repos:

```python
# docs/conf.py
import os
import sys
from datetime import datetime

# -- Path setup --------------------------------------------------------------
# Ensures AutoAPI can import your project (src layout)
sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------
project = "package_name"  # Change per repo
author = "Crossbar.io Project"
copyright = f"{datetime.now():%Y}, {author}"

# Dynamically get version from the package
try:
    from package_name import __version__ as release
except Exception:
    release = "dev"

version = release

# -- General configuration ---------------------------------------------------
extensions = [
    # MyST Markdown support
    "myst_parser",

    # Core Sphinx extensions
    "sphinx.ext.autodoc",            # Required by AutoAPI internally
    "sphinx.ext.napoleon",           # Google/NumPy style docstrings
    "sphinx.ext.intersphinx",        # Cross-link other projects
    "sphinx.ext.autosectionlabel",   # {ref} headings automatically
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",           # Link to highlighted source

    # Modern UX extensions
    "sphinx_design",                 # Cards, tabs, grids
    "sphinx_copybutton",             # Copy button for code blocks
    "sphinxext.opengraph",           # Social media meta tags
    "sphinxcontrib.images",          # Enhanced image handling
    "sphinxcontrib.spelling",        # Spell checking

    # API documentation (no-import, static analysis)
    "autoapi.extension",
]

# Source file suffixes (both RST and MyST Markdown)
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- MyST Configuration ------------------------------------------------------
myst_enable_extensions = [
    "colon_fence",        # ::: directive blocks
    "deflist",            # Definition lists
    "tasklist",           # Task lists (- [ ] item)
    "attrs_block",        # Block attributes
    "attrs_inline",       # Inline attributes
    "smartquotes",        # Smart quote substitution
    "linkify",            # Auto-link URLs (requires linkify-it-py)
]
myst_heading_anchors = 3  # Generate anchors for h1-h3

# -- AutoAPI Configuration ---------------------------------------------------
autoapi_type = "python"
autoapi_dirs = ["../src/package_name"]  # Change per repo
autoapi_add_toctree_entry = True
autoapi_keep_files = False              # Cleaner RTD builds
autoapi_generate_api_docs = True
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]
autoapi_ignore = [
    "*/_version.py",
    "*/test_*.py",
    "*/*_test.py",
    "*/conftest.py",
]
autoapi_python_use_implicit_namespaces = True
autoapi_member_order = "alphabetical"   # Predictable ordering

# -- Intersphinx Configuration -----------------------------------------------
# Cross-reference documentation across WAMP ecosystem and dependencies
intersphinx_mapping = {
    # Python Standard Library
    "python": ("https://docs.python.org/3", None),

    # Critical 3rd Party Libraries
    "twisted": ("https://docs.twisted.org/en/stable/", None),
    "cryptography": ("https://cryptography.io/en/latest/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),

    # Ethereum/Web3 (for wamp-xbr, cfxdb)
    "web3": ("https://web3py.readthedocs.io/en/stable/", None),

    # WAMP Ecosystem (the "mesh" - add as needed per repo)
    "txaio": ("https://txaio.readthedocs.io/en/latest/", None),
    "autobahn": ("https://autobahn.readthedocs.io/en/latest/", None),
    "zlmdb": ("https://zlmdb.readthedocs.io/en/latest/", None),
    "cfxdb": ("https://cfxdb.readthedocs.io/en/latest/", None),
    "crossbar": ("https://crossbar.readthedocs.io/en/latest/", None),
}
intersphinx_cache_limit = 5  # Cache remote inventories for 5 days

# -- HTML Output (Furo Theme) ------------------------------------------------
html_theme = "furo"
html_title = f"{project} {release}"

# Furo theme options with Noto fonts
html_theme_options = {
    # Source repository links
    "source_repository": "https://github.com/crossbario/package_name/",
    "source_branch": "master",
    "source_directory": "docs/",

    # Noto fonts from Google Fonts
    "light_css_variables": {
        "font-stack": "'Noto Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font-stack--monospace": "'Noto Sans Mono', SFMono-Regular, Menlo, Consolas, monospace",
    },
    "dark_css_variables": {
        "font-stack": "'Noto Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font-stack--monospace": "'Noto Sans Mono', SFMono-Regular, Menlo, Consolas, monospace",
    },
}

# Static files
html_static_path = ["_static"]
html_css_files = [
    # Load Noto fonts from Google Fonts
    "https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700&family=Noto+Sans+Mono:wght@400;500&display=swap",
    "custom.css",  # Project-specific overrides
]

# Logo and favicon (if available)
# html_logo = "_static/logo.png"
# html_favicon = "_static/favicon.ico"

# -- sphinxcontrib-images Configuration --------------------------------------
images_config = {
    "override_image_directive": True,
    "default_image_width": "80%",
}

# -- Spelling Configuration --------------------------------------------------
spelling_lang = "en_US"
spelling_word_list_filename = "spelling_wordlist.txt"
spelling_show_suggestions = True

# -- OpenGraph (Social Media Meta Tags) -------------------------------------
ogp_site_url = "https://package_name.readthedocs.io/en/latest/"
ogp_image = "_static/social-card.png"  # If available

# -- Miscellaneous -----------------------------------------------------------
todo_include_todos = True               # Show TODO items in docs
add_module_names = False                # Cleaner module paths in API docs
autosectionlabel_prefix_document = True # Avoid section label collisions
pygments_style = "sphinx"               # Code highlighting style
```

##### Per-Repo Intersphinx Customization

Each repo should include only relevant intersphinx mappings:

| Repository | Include in intersphinx_mapping |
|------------|-------------------------------|
| txaio | python, twisted |
| autobahn-python | python, twisted, txaio, cryptography |
| zlmdb | python, txaio, numpy |
| cfxdb | python, autobahn, zlmdb, web3 |
| wamp-xbr | python, autobahn, web3 |
| crossbar | python, twisted, autobahn, txaio, zlmdb, cfxdb, cryptography |

##### Standard Justfile Documentation Recipes

```just
# Build documentation
docs venv="":
    #!/usr/bin/env bash
    VENV_NAME="${venv:-cpy311}"
    VENV_PATH="${VENVS_DIR}/${VENV_NAME}"
    source "${VENV_PATH}/bin/activate"
    cd docs && sphinx-build -b html . _build/html

# Check documentation spelling
docs-check venv="":
    #!/usr/bin/env bash
    VENV_NAME="${venv:-cpy311}"
    VENV_PATH="${VENVS_DIR}/${VENV_NAME}"
    source "${VENV_PATH}/bin/activate"
    cd docs && sphinx-build -b spelling . _build/spelling

# Clean generated documentation
docs-clean:
    rm -rf docs/_build docs/_autosummary

# Trigger RTD build (for human use only - requires RTD API token)
publish-rtd tag="":
    #!/usr/bin/env bash
    if [ -z "{{tag}}" ]; then
        echo "Usage: just publish-rtd <tag>"
        echo "Example: just publish-rtd v25.11.1"
        exit 1
    fi
    echo "Triggering RTD build for tag: {{tag}}"
    echo "Note: This requires RTD webhook or API token configuration"
```

##### Tasks per repository

1. [ ] Audit current documentation status (docs/conf.py, theme, extensions)
2. [ ] Update pyproject.toml with documentation dependencies (furo, sphinx-autoapi, etc.)
3. [ ] Migrate docs/conf.py to Furo theme with Noto fonts
4. [ ] Replace autodoc with sphinx-autoapi configuration
5. [ ] Add/update docs/spelling_wordlist.txt with project-specific terms
6. [ ] Add .readthedocs.yaml if missing
7. [ ] Add justfile recipes: docs, docs-check, docs-clean, publish-rtd
8. [ ] Verify documentation builds: `just docs cpy311`
9. [ ] Verify spelling check: `just docs-check cpy311`
10. [ ] Commit changes and push to bare repo

##### Deliverables per repository

- docs/conf.py: Furo theme + sphinx-autoapi + Noto fonts
- .readthedocs.yaml: RTD build configuration
- docs/spelling_wordlist.txt: Project-specific spelling dictionary
- justfile: docs, docs-check, docs-clean, publish-rtd recipes
- pyproject.toml: Updated dev dependencies

**Blockers**: Requires Phase 1.2.2 complete

#### Phase 1.2.4: Unit Test Coverage

**Objective**: Ensure test infrastructure exists and provides foundation for comprehensive testing.

**Note**: This phase focuses on infrastructure and baseline coverage, not 100% coverage (that's future work).

**Tasks per repository**:
1. [ ] Audit current test coverage
2. [ ] Verify pytest is properly configured
3. [ ] Run tests: `just test cpy314`
4. [ ] Run coverage report: `just check-coverage cpy314`
5. [ ] Identify critical untested code paths
6. [ ] Add baseline tests for critical paths
7. [ ] Verify tests pass on all Python versions (cpy311-314, pypy311)
8. [ ] Verify tests work with both Twisted and asyncio (if applicable)
9. [ ] Commit changes and push to bare repo

**Deliverables per repository**:
- Test infrastructure verified and working
- Baseline test coverage for critical code paths
- Tests passing on all supported Python versions
- Tests work with both Twisted and asyncio (txaio, autobahn-python)

**Blockers**: Requires Phase 1.2.3 complete

### Phase 1.3: CI/CD

**Objective**: Comprehensive GitHub Actions workflows for automated testing, building, publishing.

**Branch**: `modernization-phase-1.3` (new branch after Phase 1.2 merge)

**Tasks per repository**:
1. [ ] Audit current GitHub Actions workflows
2. [ ] Add/update main.yml (quality checks, tests, coverage)
3. [ ] Add/update release.yml (wheel building, PyPI publishing)
4. [ ] Add/update wheels.yml (multi-platform wheel building)
5. [ ] Integrate reusable actions from .cicd submodule
6. [ ] Enable matrix testing (CPython 3.11-3.14, PyPy 3.11)
7. [ ] Enable multi-OS testing (ubuntu, macos, windows)
8. [ ] Enable mypy type checking in CI
9. [ ] Enable pytest coverage in CI
10. [ ] Verify all workflows pass on GitHub
11. [ ] Commit changes and push to bare repo

**Deliverables per repository**:
- Comprehensive GitHub Actions workflows
- Matrix testing (Python versions, OS)
- Automated wheel building and publishing
- All CI checks passing

**Blockers**: Requires Phase 1.2 complete (all sub-phases merged)

## Phase 2: Integration Test Coverage

**Objective**: End-to-end integration testing across the entire WAMP stack.

**Status**: Future work (after Phase 1 complete)

**Scope**:
- Cross-language testing (AutobahnJS ↔ Crossbar ↔ AutobahnPython)
- Cross-component testing (Client ↔ Router ↔ Client)
- Cross-node testing (Router ↔ Router)
- Cross-operator testing (XBR with multiple router operators)
- Performance testing (throughput, latency)
- Stress testing (connection storms, message floods)

**Philosophy**: Only start after solid foundation is in place (Phase 1 complete). Integration testing reveals issues best addressed with stable, well-tested lower-level components.

**Deliverables**:
- Integration test suite (pytest-based)
- Performance benchmarks
- Automated integration testing in CI/CD
- Documentation for running integration tests

**Blockers**: Requires Phase 1 complete for all repos

## Success Criteria

### Technical
- [ ] All repos have .ai and .cicd submodules at latest versions
- [ ] Git hooks configured and working uniformly
- [ ] All packages use modern pyproject.toml (PEP 621)
- [ ] Consistent tooling across stack (ruff, mypy, just, pytest)
- [ ] Native wheels for x86-64 + ARM64, CPython + PyPy
- [ ] RHEL9 RPM packages available
- [ ] Comprehensive CI/CD via GitHub Actions
- [ ] Modern documentation (Sphinx + Furo + RTD)
- [ ] Zero legacy build files (setup.py minimized, tox.ini/Makefile removed)
- [ ] Baseline test coverage for all repos
- [ ] Integration test suite operational

### Business
- [ ] Customer "peace of mind" - professional, stable foundation
- [ ] Easy deployment on RHEL9
- [ ] Clear upgrade path
- [ ] Professional documentation
- [ ] Enterprise-grade quality

## Timeline

**Phase 0** (Infrastructure):
- wamp-ai fixes: 0.5-1 day
- wamp-cicd fixes: 0.5-1 day
- **Subtotal**: 1-2 days

**Phase 1** (Per-Repo Modernization):
- Phase 1.1 (Git submodules): 0.5 day per repo × 7 = 3.5 days
- Phase 1.2: Per-Repo Infrastructure (single branch):
  - Phase 1.2.1 (Build tooling): 0.5-1 day per repo × 7 = 3.5-7 days
  - Phase 1.2.2 (Wheels): 0.5-1 day per repo × 7 = 3.5-7 days
  - Phase 1.2.3 (Documentation): 0.5 day per repo × 7 = 3.5 days
  - Phase 1.2.4 (Test coverage): 0.5-1 day per repo × 7 = 3.5-7 days
- Phase 1.3 (CI/CD): 0.5-1 day per repo × 7 = 3.5-7 days
- **Subtotal**: 18-35 days

**Phase 2** (Integration Testing):
- Integration test infrastructure: 2-3 days
- Test implementation: 3-5 days
- **Subtotal**: 5-8 days

**Total Estimated**: 24-45 days (5-9 weeks)

**Note**: Estimates assume sequential execution. Some parallelization possible (e.g., different repos in same sub-phase). Phases 1.2.1-1.2.4 are on the same branch to reduce merge/review overhead.

## Notes

- This work is being done with AI assistance (Claude Code)
- All changes follow the multi-stage git workflow (asgard1 → bare repo → dev PC → GitHub)
- Each package will be updated incrementally with proper testing
- Backward compatibility maintained where possible
- Customer (US defense contractor) focus: robustness, professionalization, RHEL9 support
- Bottom-up execution: fix foundation first, then build on solid base
- Test early, test often: verify each layer before proceeding to next

---

## Appendix: Crossbar.io - WAMP Ecosystem Integration Hub

This appendix provides a deep analysis of how Crossbar.io serves as the integration
point for all WAMP ecosystem packages, and documents the critical `install-dev-local`
recipe that enables cross-repository development.

### WAMP Ecosystem Dependency Architecture

Crossbar integrates all core WAMP ecosystem packages with extensive usage:

| Package | Import Count | Purpose |
|---------|-------------|---------|
| autobahn-python | 394+ | WAMP protocol implementation, WebSocket client/server |
| txaio | 157+ | Twisted/asyncio abstraction layer |
| cfxdb | 55 | Database schema for management realms (LMDB-based) |
| wamp-xbr | 30 | XBR blockchain/marketplace features |
| zlmdb | 13 | Object-relational database layer on LMDB |

The dependency chain is strictly ordered:

```
txaio (foundation)
    ↓
autobahn-python (protocol layer)
    ↓
┌───┴───┐
│       │
zlmdb   wamp-xbr
│
cfxdb
    ↓
crossbar (application layer - integrates all)
```

### The `install-dev-local` Recipe

The justfile's `install-dev-local` recipe is the **linchpin** enabling cross-repository
development across the entire WAMP ecosystem:

```bash
just install-dev-local cpy311
```

**What it does:**

1. **Auto-detects sibling repositories** (`../txaio`, `../autobahn-python`, etc.)
2. **Installs them in dependency order** in editable mode (`pip install -e`)
3. **Gracefully degrades** to PyPI versions if repos are missing
4. **Respects the dependency chain** while allowing local development

**Implementation highlights:**

```bash
# Install local WAMP packages in editable mode
if [ -d "../txaio" ]; then
    echo "  ✓ Installing txaio from ../txaio"
    ${VENV_PYTHON} -m pip install -e "../txaio"
fi

if [ -d "../autobahn-python" ]; then
    echo "  ✓ Installing autobahn-python with extras from ../autobahn-python"
    ${VENV_PYTHON} -m pip install -e "../autobahn-python[twisted,encryption,compress,serialization,scram]"
fi

for pkg in zlmdb cfxdb wamp-xbr; do
    pkg_path="../${pkg}"
    if [ -d "${pkg_path}" ]; then
        echo "  ✓ Installing ${pkg} from ${pkg_path}"
        ${VENV_PYTHON} -m pip install -e "${pkg_path}"
    fi
done
```

**Why this matters:**

- Enables **simultaneous development** across multiple repos
- Changes in txaio/autobahn immediately visible in crossbar
- No need for manual pip commands or version juggling
- Pip's resolver uses already-installed local packages for remaining deps
- Critical for debugging cross-package issues

### asgard1 Infrastructure Design

The development server (asgard1) layout is specifically designed to support this workflow:

```
/home/oberstet/work/wamp/
├── txaio/              # Foundation package
├── autobahn-python/    # Protocol layer
├── zlmdb/              # Database layer
├── cfxdb/              # Crossbar DB access
├── wamp-xbr/           # Blockchain extensions
└── crossbar/           # Integration hub
```

This layout ensures:
- All repos are sibling directories (required by `install-dev-local`)
- AI agents can work across repos
- Changes can be tested end-to-end before push

### pyproject.toml Dependency Configuration

Crossbar's `pyproject.toml` demonstrates sophisticated dependency management:

```toml
dependencies = [
    # WAMP packages with explicit extras
    "autobahn[twisted,encryption,compress,serialization,scram]>=25.10.2",
    "txaio>=25.11.1",
    "zlmdb>=25.11.1",
    "cfxdb>=25.11.1",
    "xbr>=25.11.1",
    # ... 160+ total transitive dependencies
]

[project.optional-dependencies]
dev = [
    # Standard development tools
    "pytest>=7.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    # ...
]

dev-latest = [
    # Install from GitHub master for testing
    "autobahn @ git+https://github.com/crossbario/autobahn-python.git",
    "txaio @ git+https://github.com/crossbario/txaio.git",
    # ...
]
```

Three installation modes are supported:
1. **Standard**: `just install` - Uses PyPI versions
2. **Latest**: `just install-dev-latest` - Uses GitHub master branches
3. **Local**: `just install-dev-local` - Uses local editable repos (for development)

### Build Environment Configuration

Crossbar sets critical environment variables for PyPy compatibility:

```python
os.environ['LMDB_FORCE_CFFI'] = '1'       # CFFI bindings (not CPyExt)
os.environ['SODIUM_INSTALL'] = 'bundled'  # Self-contained libsodium
os.environ['PYUBJSON_NO_EXTENSION'] = '1' # Pure Python UBJSON
```

These ensure:
- Pure Python/CFFI dependencies only
- No CPython extension API usage
- Full PyPy compatibility
- Consistent behavior across implementations

### Cross-Repo Development Workflow Example

**Scenario:** Fix a bug in autobahn that affects crossbar

```bash
# 1. Set up crossbar with local packages
cd /home/oberstet/work/wamp/crossbar
just install-dev-local cpy311

# 2. Make changes in autobahn
cd ../autobahn-python
# ... edit code ...

# 3. Test immediately in crossbar (no reinstall needed!)
cd ../crossbar
just test cpy311

# 4. If tests pass, commit both repos
cd ../autobahn-python
git add . && git commit -m "fix: ..."

cd ../crossbar
# crossbar tests still use the local autobahn
```

This workflow is only possible because:
- Repos are in sibling directories
- Editable installs point to actual source
- No version conflicts (pip uses local packages)

### Key Design Patterns

1. **Dependency Ordering**: Always install foundation → protocol → infrastructure → application

2. **Optional Features via Extras**: Autobahn installed with 5 extras for crossbar:
   - `twisted` - Twisted networking framework
   - `encryption` - End-to-end encryption
   - `compress` - Message compression
   - `serialization` - Multiple serializers (JSON, CBOR, MsgPack, FlatBuffers)
   - `scram` - SCRAM authentication

3. **Graceful Degradation**: Missing local repos fall back to PyPI versions

4. **Version Constraints**:
   - Strict for WAMP packages (protocol compliance)
   - Conservative for Twisted (stability)
   - Restrictive for Ethereum stack (API volatility)

### Remaining Modernization Opportunities

- [ ] Increase type hints coverage (currently `disallow_untyped_defs = false`)
- [ ] Create DEPENDENCIES.md documenting ~160+ transitive dependencies
- [ ] Automated dependency security scanning
- [ ] RHEL9 native RPM packaging

---

## Appendix: wamp-xbr - Dual Build System Analysis

This appendix documents the unique characteristics of the wamp-xbr repository,
which has a dual build system for both Python and Solidity/Ethereum smart contracts.

### Repository Overview

wamp-xbr contains:
- **Python package** (`xbr/`): XBR smart contracts ABIs and Python bindings
- **Solidity contracts** (`contracts/`): Ethereum smart contracts source
- **Truffle migrations** (`migrations/`): Deployment scripts for Ethereum

### Directory Structure

```
wamp-xbr/
├── xbr/                    # Python package
│   ├── __init__.py
│   ├── _version.py
│   ├── _abi.py            # Loads compiled contract ABIs
│   ├── abi -> ../build/contracts  # Symlink to compiled ABIs
│   ├── contract -> ../contracts   # Symlink to Solidity source
│   ├── templates/         # Jinja2 templates for code generation
│   └── test/              # Python tests
├── contracts/              # Solidity smart contracts
│   ├── XBRToken.sol
│   ├── XBRNetwork.sol
│   ├── XBRMarket.sol
│   └── ...
├── migrations/             # Truffle deployment scripts
├── build/contracts/        # Compiled ABIs (generated by Truffle)
├── Makefile               # Solidity/Truffle build targets
├── justfile               # Python build recipes + Makefile wrappers
├── pyproject.toml         # Python package metadata
└── truffle-config.js      # Truffle configuration
```

### Key Observations

1. **Symlinks Bundle Artifacts**: The Python package includes symlinks that bundle
   compiled Solidity ABIs into the wheel:
   - `xbr/abi` → `../build/contracts` (compiled JSON ABIs)
   - `xbr/contract` → `../contracts` (Solidity source for reference)

2. **Dual Build Pipeline**:
   - **Solidity**: `make compile` → Truffle compiles `.sol` to JSON ABIs
   - **Python**: `just build` → setuptools packages Python + bundled ABIs

3. **Build Order Dependency**: Python package requires compiled ABIs to function:
   ```bash
   make compile      # First: compile Solidity → build/contracts/*.json
   just build cpy311 # Second: build Python wheel with bundled ABIs
   ```

4. **Pure Python Package**: Despite the native contract compilation step,
   the Python wheel itself is `py2.py3-none-any` (pure Python, no native code).

### Phase 1.2 Approach

For Phase 1.2, we:
- Created justfile with Python recipes + Makefile wrappers
- Kept Makefile as-is (complex Solidity tooling)
- Updated pyproject.toml with dev deps and tool configs
- Renamed setup.py to setup.py.orig

### Justfile Makefile Wrappers

The justfile wraps Makefile targets for seamless developer experience:

```just
# Run a Makefile target (for Solidity/Truffle targets)
make target:
    #!/usr/bin/env bash
    echo "==> Running Makefile target: {{target}}"
    make {{target}}

# Compile Solidity smart contracts
truffle-compile:
    just make compile

# Run Solidity tests
truffle-test:
    just make test

# Start local Ganache blockchain
ganache-run:
    just make ganache_run
```

### Dependencies

The xbr package has significant Ethereum ecosystem dependencies:
- `web3>=6.0.0` - Ethereum client library
- `eth-abi>=4.0.0` - ABI encoding/decoding
- `eth-account` - Account management
- `py-eth-sig-utils` - EIP-712 typed data signing
- `py-ecc` - Elliptic curve cryptography

These enable:
- Smart contract interaction
- Transaction signing
- EIP-712 signature generation
- Cryptographic operations for XBR marketplace

### Future Work

- [ ] Consider npm/truffle modernization (parallel to Python)
- [ ] Add Hardhat support as Truffle alternative
- [ ] Automated ABI bundling in CI/CD
- [ ] Pre-built wheels with ABIs for PyPI releases

---

## Appendix: Crossbar.io Dependencies Analysis

This appendix provides a comprehensive analysis of all transitive dependencies for
Crossbar.io, including classification by type, native extension status, CFFI vs CPyExt
usage, and PyPy compatibility.

### Overview Statistics

- **Total packages (runtime)**: ~160 transitive dependencies
- **Direct dependencies**: ~45 packages
- **WAMP ecosystem (own)**: 5 packages (2 with native CFFI extensions)
- **Packages with native extensions**: ~25 packages
- **CFFI-based (PyPy compatible)**: ~7 packages (incl. autobahn, zlmdb)
- **CPyExt-based (limited PyPy)**: ~18 packages

### Critical: Vendored Dependencies Architecture

A key architectural decision in the WAMP ecosystem is **vendoring** of certain
dependencies to ensure consistent behavior, CFFI-only bindings, and PyPy compatibility.

#### Vendored Packages

| Vendored Package | Vendored Into | Location | Notes |
|------------------|---------------|----------|-------|
| **LMDB** | zlmdb | `zlmdb/lmdb/` | CFFI bindings (`_lmdb_cffi.so`), NOT py-lmdb |
| **FlatBuffers** | autobahn | `flatbuffers/` (top-level) | Bundled as separate package in wheel |
| **FlatBuffers** | zlmdb | `zlmdb/flatbuffers/` | Reflection schemas |

#### Why Vendoring Matters

1. **LMDB in zlmdb**: zlmdb vendors its own CFFI-based LMDB bindings instead of
   depending on `py-lmdb` from PyPI. This ensures:
   - CFFI bindings (not CPyExt) for PyPy compatibility
   - Consistent API across all platforms
   - No dependency on external py-lmdb package

2. **FlatBuffers in autobahn**: autobahn vendors the Google FlatBuffers Python
   library as a top-level `flatbuffers` package in its wheel:
   ```toml
   # autobahn's pyproject.toml
   [tool.setuptools.packages.find]
   include = ["autobahn*", "twisted.plugins", "flatbuffers*"]
   ```

3. **Crossbar's Dependencies**: Crossbar should **NOT** have direct dependencies on:
   - `lmdb` or `py-lmdb` - uses zlmdb's vendored LMDB
   - `flatbuffers` - uses autobahn's vendored FlatBuffers

#### ✅ Resolved: Redundant lmdb Dependency (Removed)

**Issue**: crossbar's `pyproject.toml` previously included `"lmdb>=1.4.0"` as a
direct dependency, which was **incorrect/redundant**.

**Why it was wrong**:
- Crossbar imports `zlmdb`, never `lmdb` directly
- zlmdb vendors its own CFFI LMDB bindings (`zlmdb/lmdb/_lmdb_cffi.so`)
- Having `lmdb>=1.4.0` could install py-lmdb (CPyExt) which conflicts with the design

**Resolution**: Removed `"lmdb>=1.4.0"` from crossbar's pyproject.toml dependencies.
Added comment to prevent future re-introduction:
```toml
# NOTE: LMDB access is through zlmdb which vendors its own CFFI bindings
# Do NOT add "lmdb" or "py-lmdb" here - crossbar imports zlmdb, never lmdb directly
```

### Dependency Tree - WAMP Ecosystem Core

```
crossbar==25.11.1
├── [OWN] autobahn[twisted,encryption,compress,serialization,scram]==25.11.1  [NATIVE:CFFI] ✅ PyPy
│   │   ├── nvx: _utf8validator, _xormasker (WebSocket accelerators)
│   │   └── [VENDORED] flatbuffers (top-level package in wheel)
│   ├── [OWN] txaio>=25.9.2
│   ├── cryptography>=3.4.6  [NATIVE:CFFI] ✅ PyPy
│   │   └── cffi>=2.0.0
│   ├── hyperlink>=21.0.0
│   ├── msgpack>=1.0.2  [NATIVE:CPyExt] ⚠️
│   ├── ujson>=4.0.2  [NATIVE:CPyExt] ⚠️
│   ├── cbor2>=5.2.0  [NATIVE:CPyExt] ⚠️ (has pure Python fallback)
│   └── py-ubjson>=0.16.1  [NATIVE:CPyExt] ⚠️
│
├── [OWN] txaio>=25.9.2  (pure Python)
│
├── [OWN] zlmdb>=25.10.2  [NATIVE:CFFI] ✅ PyPy
│   │   ├── [VENDORED] lmdb: _lmdb_cffi (CFFI bindings, NOT py-lmdb!)
│   │   └── [VENDORED] flatbuffers (reflection schemas)
│   ├── cffi>=1.15.1  [NATIVE:CFFI] ✅ PyPy
│   ├── cbor2>=5.4.6
│   ├── PyNaCl>=1.5.0  [NATIVE:CFFI] ✅ PyPy
│   │   └── cffi>=2.0.0
│   ├── numpy>=1.24.1  [NATIVE:CPyExt] ⚠️
│   └── [OWN] txaio>=23.1.1
│
│   ⚠️ NOTE: crossbar should NOT depend on lmdb or flatbuffers directly!
│
├── [OWN] cfxdb>=25.11.1
│   ├── [OWN] autobahn>=25.10.2
│   ├── [OWN] zlmdb>=25.10.2
│   ├── eth_abi>=5.1.0
│   ├── eth-account>=0.13.0
│   └── web3>=7.6.0  (many nested deps)
│
├── [OWN] xbr>=25.11.1 (wamp-xbr)
│   ├── web3[ipfs]>=6.0.0
│   ├── eth-abi>=4.0.0
│   └── py-eth-sig-utils>=0.4.0
│
├── Twisted[tls,conch,http2]>=22.10.0  [NATIVE:CPyExt] ⚠️
│   ├── attrs>=22.2.0
│   ├── Automat>=24.8.0
│   ├── constantly>=15.1
│   ├── hyperlink>=17.1.1
│   ├── incremental>=24.7.0
│   └── zope.interface>=5  [NATIVE:CPyExt] ⚠️
│
├── treq>=22.2.0
└── txtorcon>=22.0.0
```

### Package Classification

#### Group 1: WAMP Ecosystem (Own Packages)

| Package | Version | Type | PyPI Wheels | PyPy |
|---------|---------|------|-------------|------|
| txaio | 25.9.2 | Pure Python | ✅ py3-none-any | ✅ |
| autobahn | 25.11.1 | **Native (CFFI)** | ✅ cp311-manylinux, etc. | ✅ |
| zlmdb | 25.10.2 | **Native (CFFI)** | ✅ cp311-manylinux, etc. | ✅ |
| cfxdb | 25.11.1 | Pure Python | ✅ py3-none-any | ✅ |
| xbr (wamp-xbr) | 25.11.1 | Pure Python | ✅ py3-none-any | ✅ |

**Note**: autobahn and zlmdb include CFFI-based native extensions for performance:
- **autobahn**: `_nvx_utf8validator`, `_nvx_xormasker` (WebSocket frame masking/validation accelerators)
- **zlmdb**: `_lmdb_cffi` (CFFI bindings to LMDB database)

These use CFFI (not CPyExt), ensuring full PyPy compatibility with near-native performance.

#### Group 2: Cryptography & Security (CFFI-based, PyPy Compatible)

| Package | Version | PyPI Wheels | Notes |
|---------|---------|-------------|-------|
| cryptography | 46.0.3 | ✅ x86_64, ARM64 | Uses CFFI, rust-based backend |
| PyNaCl | 1.6.1 | ✅ x86_64, ARM64 | CFFI bindings to libsodium |
| bcrypt | 5.0.0 | ✅ x86_64, ARM64 | CFFI bindings |
| argon2-cffi | 25.1.0 | ✅ x86_64, ARM64 | CFFI bindings |
| cffi | 2.0.0 | ✅ x86_64, ARM64 | Foundation for all CFFI packages |

These packages use CFFI (Foreign Function Interface) and work well on PyPy.

#### Group 3: Serialization (Mixed Native)

| Package | Version | Type | PyPI Wheels | PyPy | Notes |
|---------|---------|------|-------------|------|-------|
| cbor2 | 5.7.1 | Native+Fallback | ✅ x86_64, ARM64 | ✅ | Has pure Python fallback |
| msgpack | 1.1.2 | Native | ✅ x86_64, ARM64 | ⚠️ | CPyExt, slower on PyPy |
| ujson | 5.11.0 | Native | ✅ x86_64, ARM64 | ⚠️ | CPyExt, can use json instead |
| py-ubjson | 0.16.1 | Native+Fallback | ✅ x86_64 | ✅ | Has pure Python fallback |
| PyYAML | 6.0.3 | Native | ✅ x86_64, ARM64 | ⚠️ | libyaml bindings |

**PyPy Note**: Use PYUBJSON_NO_EXTENSION=1 and CBOR2_FORCE_PYTHON=1 for pure Python mode.

#### Group 4: Twisted Ecosystem

| Package | Version | Type | PyPI Wheels | PyPy |
|---------|---------|------|-------------|------|
| Twisted | 25.5.0 | Pure Python | ✅ py3-none-any | ✅ |
| attrs | 25.4.0 | Pure Python | ✅ py3-none-any | ✅ |
| Automat | 25.4.16 | Pure Python | ✅ py3-none-any | ✅ |
| constantly | 23.10.4 | Pure Python | ✅ py3-none-any | ✅ |
| hyperlink | 21.0.0 | Pure Python | ✅ py3-none-any | ✅ |
| incremental | 24.7.2 | Pure Python | ✅ py3-none-any | ✅ |
| zope.interface | 8.1.1 | Native | ✅ x86_64, ARM64 | ⚠️ |
| treq | 25.5.0 | Pure Python | ✅ py3-none-any | ✅ |
| txtorcon | 24.8.0 | Pure Python | ✅ py3-none-any | ✅ |

#### Group 5: Ethereum/XBR Stack

| Package | Version | Type | PyPI Wheels | PyPy |
|---------|---------|------|-------------|------|
| web3 | 7.14.0 | Pure Python | ✅ py3-none-any | ✅ |
| eth-abi | 5.1.0 | Pure Python | ✅ py3-none-any | ✅ |
| eth-account | 0.13.7 | Pure Python | ✅ py3-none-any | ✅ |
| eth-typing | 5.2.1 | Pure Python | ✅ py3-none-any | ✅ |
| eth-utils | 5.3.1 | Pure Python | ✅ py3-none-any | ✅ |
| eth-hash | 0.7.1 | Pure Python | ✅ py3-none-any | ✅ |
| eth-keyfile | 0.8.1 | Pure Python | ✅ py3-none-any | ✅ |
| eth-keys | 0.7.0 | Pure Python | ✅ py3-none-any | ✅ |
| eth-rlp | 2.2.0 | Pure Python | ✅ py3-none-any | ✅ |
| rlp | 4.1.0 | Pure Python | ✅ py3-none-any | ✅ |
| hexbytes | 1.3.1 | Pure Python | ✅ py3-none-any | ✅ |
| py-eth-sig-utils | 0.4.0 | Pure Python | ✅ py3-none-any | ✅ |
| py-ecc | 8.0.0 | Pure Python | ✅ py3-none-any | ✅ |
| ckzg | 2.1.5 | Native | ✅ x86_64, ARM64 | ⚠️ |
| pycryptodome | 3.23.0 | Native | ✅ x86_64, ARM64 | ⚠️ |
| bitarray | 3.8.0 | Native | ✅ x86_64, ARM64 | ⚠️ |
| cytoolz | 1.1.0 | Native | ✅ x86_64, ARM64 | ⚠️ |
| pydantic-core | 2.41.5 | Native | ✅ x86_64, ARM64 | ⚠️ |

#### Group 6: HTTP/Async Stack

| Package | Version | Type | PyPI Wheels | PyPy |
|---------|---------|------|-------------|------|
| aiohttp | 3.13.2 | Native | ✅ x86_64, ARM64 | ⚠️ |
| multidict | 6.7.0 | Native | ✅ x86_64, ARM64 | ⚠️ |
| frozenlist | 1.8.0 | Native | ✅ x86_64, ARM64 | ⚠️ |
| yarl | 1.22.0 | Native | ✅ x86_64, ARM64 | ⚠️ |
| propcache | 0.4.1 | Native | ✅ x86_64, ARM64 | ⚠️ |
| requests | 2.32.5 | Pure Python | ✅ py3-none-any | ✅ |
| urllib3 | 1.26.20 | Pure Python | ✅ py3-none-any | ✅ |
| h2 | 3.2.0 | Pure Python | ✅ py3-none-any | ✅ |
| hpack | 3.0.0 | Pure Python | ✅ py3-none-any | ✅ |
| hyperframe | 5.2.0 | Pure Python | ✅ py3-none-any | ✅ |
| priority | 1.3.0 | Pure Python | ✅ py3-none-any | ✅ |

#### Group 7: Core Utilities with Native Extensions (CPyExt)

| Package | Version | PyPI Wheels | Notes |
|---------|---------|-------------|-------|
| numpy | 2.3.5 | ✅ x86_64, ARM64 | CPyExt, but has PyPy wheels |
| psutil | 7.1.3 | ✅ x86_64, ARM64 | CPyExt |
| regex | 2025.11.3 | ✅ x86_64, ARM64 | CPyExt |
| setproctitle | 1.3.7 | ✅ x86_64, ARM64 | CPyExt |
| wsaccel | 0.6.7 | ✅ x86_64 | CPyExt, accelerates WebSocket |
| greenlet | 3.2.4 | ✅ x86_64, ARM64 | CPyExt |
| MarkupSafe | 3.0.3 | ✅ x86_64, ARM64 | CPyExt |
| rpds-py | 0.29.0 | ✅ x86_64, ARM64 | Rust-based |

#### Group 8: Pure Python Utilities

| Package | Version | Notes |
|---------|---------|-------|
| click | 8.3.1 | CLI framework |
| Jinja2 | 3.1.6 | Templating |
| Flask | 3.1.2 | Web framework |
| Werkzeug | 3.1.3 | WSGI toolkit |
| jsonschema | 4.25.1 | JSON validation |
| colorama | 0.4.6 | Terminal colors |
| tabulate | 0.9.0 | Table formatting |
| passlib | 1.7.4 | Password hashing |
| netaddr | 1.3.0 | Network address manipulation |
| iso8601 | 2.1.0 | Date/time parsing |
| humanize | 4.14.0 | Human-readable formatting |
| watchdog | 6.0.0 | Filesystem monitoring |
| docker | 7.1.0 | Docker API client |
| cookiecutter | 2.6.0 | Project templating |
| prompt_toolkit | 3.0.52 | Interactive CLI |
| Pygments | 2.19.2 | Syntax highlighting |

### Native Extension Summary

#### CFFI-based (Recommended for PyPy)

These packages use CFFI and run efficiently on both CPython and PyPy:

```
✅ autobahn         - [OWN] WebSocket accelerators (_nvx_utf8validator, _nvx_xormasker)
✅ zlmdb            - [OWN] LMDB bindings (_lmdb_cffi)
✅ cryptography     - Crypto primitives via Rust/CFFI
✅ PyNaCl           - libsodium via CFFI
✅ bcrypt           - bcrypt via CFFI
✅ argon2-cffi      - Argon2 via CFFI
✅ cffi             - Foundation
```

#### CPyExt-based (Limited PyPy Performance)

These packages use CPython Extension API and may be slower on PyPy:

```
⚠️ numpy            - Numeric computing (has PyPy wheels though)
⚠️ pydantic-core    - Rust-based validation
⚠️ aiohttp          - Async HTTP (C speedups)
⚠️ multidict        - C speedups
⚠️ yarl             - C speedups
⚠️ msgpack          - C speedups
⚠️ ujson            - C speedups
⚠️ regex            - C speedups
⚠️ lmdb             - Use LMDB_FORCE_CFFI=1
⚠️ psutil           - System info
⚠️ greenlet         - Coroutines
⚠️ cytoolz          - Functional utilities
⚠️ zope.interface   - Interface definitions
⚠️ setproctitle     - Process title
⚠️ wsaccel          - WebSocket acceleration
⚠️ MarkupSafe       - String escaping
⚠️ rpds-py          - Rust data structures
⚠️ ckzg             - KZG commitments
⚠️ pycryptodome     - Crypto primitives
⚠️ bitarray         - Bit manipulation
```

### PyPy Compatibility Environment Variables

For optimal PyPy performance, set these environment variables:

```bash
export LMDB_FORCE_CFFI=1        # Force CFFI bindings for lmdb
export SODIUM_INSTALL=bundled   # Use bundled libsodium
export PYUBJSON_NO_EXTENSION=1  # Use pure Python UBJSON
export CBOR2_FORCE_PYTHON=1     # Use pure Python CBOR2 (optional)
```

### Wheel Availability Matrix

| Architecture | CPython 3.11 | CPython 3.12 | CPython 3.13 | PyPy 3.11 |
|--------------|--------------|--------------|--------------|-----------|
| x86_64 Linux | ✅ All | ✅ All | ✅ Most | ⚠️ Most |
| ARM64 Linux | ✅ All | ✅ All | ✅ Most | ⚠️ Most |
| x86_64 macOS | ✅ All | ✅ All | ✅ Most | ⚠️ Most |
| ARM64 macOS | ✅ All | ✅ All | ✅ Most | ⚠️ Most |
| x86_64 Windows | ✅ All | ✅ All | ✅ Most | ⚠️ Most |

**Legend**: ✅ = Wheels available, ⚠️ = Some packages may need compilation

### Full Dependency List (Alphabetical)

<details>
<summary>Click to expand full dependency list (160+ packages)</summary>

```
accessible-pygments==0.0.5
aiohappyeyeballs==2.6.1
aiohttp==3.13.2
aiosignal==1.4.0
annotated-types==0.7.0
argon2-cffi==25.1.0
argon2-cffi-bindings==25.1.0
arrow==1.4.0
attrs==25.4.0
autobahn==25.11.1  [WAMP, NATIVE:CFFI]
Automat==25.4.16
base58==2.1.1
bcrypt==5.0.0  [NATIVE:CFFI]
bitarray==3.8.0  [NATIVE:CPyExt]
bitstring==4.3.1
binaryornot==0.4.4
blinker==1.9.0
brotli==1.2.0  [NATIVE:CPyExt]
cbor2==5.7.1  [NATIVE:CPyExt+Fallback]
certifi==2025.11.12
cffi==2.0.0  [NATIVE:CFFI]
cfxdb==25.11.1  [WAMP, Pure Python]
chardet==5.2.0
charset-normalizer==3.4.4  [NATIVE:CPyExt]
ckzg==2.1.5  [NATIVE:CPyExt]
click==8.3.1
colorama==0.4.6
constantly==23.10.4
cookiecutter==2.6.0
cryptography==46.0.3  [NATIVE:CFFI]
cytoolz==1.1.0  [NATIVE:CPyExt]
docker==7.1.0
ecdsa==0.19.1
eth-abi==5.1.0
eth-account==0.13.7
eth-hash==0.7.1
eth-keyfile==0.8.1
eth-keys==0.7.0
eth-rlp==2.2.0
eth-typing==5.2.1
eth-utils==5.3.1
Flask==3.1.2
frozenlist==1.8.0  [NATIVE:CPyExt]
greenlet==3.2.4  [NATIVE:CPyExt]
h2==3.2.0
hexbytes==1.3.1
hkdf==0.0.3
hpack==3.0.0
humanize==4.14.0
hyperframe==5.2.0
hyperlink==21.0.0
idna==2.5
importlib_resources==6.5.2
incremental==24.7.2
iso8601==2.1.0
itsdangerous==2.2.0
Jinja2==3.1.6
jinja2-highlight==0.6.1
jsonschema==4.25.1
jsonschema-specifications==2025.9.1
lmdb==1.7.5  [NATIVE:CPyExt] ⚠️ REDUNDANT - zlmdb vendors CFFI LMDB, remove from deps!
MarkupSafe==3.0.3  [NATIVE:CPyExt]
mistune==3.1.4
mnemonic==0.21
morphys==1.0
msgpack==1.1.2  [NATIVE:CPyExt]
multidict==6.7.0  [NATIVE:CPyExt]
netaddr==1.3.0
numpy==2.3.5  [NATIVE:CPyExt]
packaging==25.0
parsimonious==0.10.0
passlib==1.7.4
priority==1.3.0
prompt_toolkit==3.0.52
propcache==0.4.1  [NATIVE:CPyExt]
psutil==7.1.3  [NATIVE:CPyExt]
py-ecc==8.0.0
py-eth-sig-utils==0.4.0
py-multihash==2.0.1
py-ubjson==0.16.1  [NATIVE:CPyExt+Fallback]
pyasn1==0.6.1
pyasn1_modules==0.4.2
pycparser==2.23
pycryptodome==3.23.0  [NATIVE:CPyExt]
pydantic==2.12.4
pydantic_core==2.41.5  [NATIVE:Rust]
Pygments==2.19.2
PyNaCl==1.6.1  [NATIVE:CFFI]
pyOpenSSL==25.3.0
PyQRCode==1.2.1
PyTrie==0.4.0
PyYAML==6.0.3  [NATIVE:CPyExt]
referencing==0.37.0
regex==2025.11.3  [NATIVE:CPyExt]
requests==2.32.5
rich==14.2.0
rlp==4.1.0
rpds-py==0.29.0  [NATIVE:Rust]
sdnotify==0.3.2
service-identity==24.2.0
setproctitle==1.3.7  [NATIVE:CPyExt]
setuptools==80.9.0
six==1.17.0
sortedcontainers==2.4.0
spake2==0.9
stringcase==1.2.0
tabulate==0.9.0
toolz==1.1.0
treq==25.5.0
Twisted==25.5.0
txaio==25.9.2  [WAMP, Pure Python]
txtorcon==24.8.0
typing_extensions==4.15.0
u-msgpack-python==2.8.0
ujson==5.11.0  [NATIVE:CPyExt]
urllib3==1.26.20
validate_email==1.3
watchdog==6.0.0
wcwidth==0.2.14
web3==7.14.0
Werkzeug==3.1.3
wsaccel==0.6.7  [NATIVE:CPyExt]
xbr==25.11.1  [WAMP, Pure Python]
yarl==1.22.0  [NATIVE:CPyExt]
zlmdb==25.10.2  [WAMP, NATIVE:CFFI]
zope.interface==8.1.1  [NATIVE:CPyExt]
```

</details>

### Recommendations

1. **For PyPy Deployment**:
   - Set CFFI-forcing environment variables
   - Consider avoiding optional native serializers (msgpack, ujson)
   - Test thoroughly with target PyPy version

2. **For RHEL9/Enterprise**:
   - All critical packages have manylinux wheels
   - No compilation required for standard deployment
   - Consider vendoring for air-gapped environments

3. **For ARM64 (Apple Silicon, AWS Graviton)**:
   - All major packages have ARM64 wheels
   - Twisted, Autobahn, WAMP stack fully supported
   - Some minor packages may need compilation

4. **Security Scanning**:
   - Use `pip-audit` or `safety` for vulnerability scanning
   - Critical packages (cryptography, PyNaCl) are actively maintained
   - Review transitive dependencies regularly

---

Last updated: 2025-11-27
Status: Phase 1.2.2 complete, Phase 1.2.3 in progress
