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

### Phase 1.2: Build Tooling

**Objective**: Modernize build systems to use pyproject.toml, ruff, uv, just, pytest, mypy.

**Tasks per repository**:
1. [ ] Audit current build system status
2. [ ] Add/update ruff configuration in pyproject.toml
3. [ ] Remove flake8 configuration (replaced by ruff)
4. [ ] Add/update mypy configuration in pyproject.toml
5. [ ] Remove tox configuration (replaced by justfile)
6. [ ] Add/update pytest configuration in pyproject.toml
7. [ ] Add/update coverage configuration in pyproject.toml
8. [ ] Verify justfile has all necessary recipes (test, check-format, check-typing, build, etc.)
9. [ ] Remove/minimize setup.py (keep minimal shim if needed for editable installs)
10. [ ] Remove setup.cfg if exists
11. [ ] Remove requirements.txt (move to pyproject.toml)
12. [ ] Run `just check cpy314` to verify all checks pass
13. [ ] Commit changes and push to bare repo

**Deliverables per repository**:
- pyproject.toml with complete modern configuration
- No legacy build files (setup.py minimized, setup.cfg/requirements.txt removed)
- ruff, mypy, pytest configured
- justfile with comprehensive recipes
- All checks passing

**Blockers**: Requires Phase 1.1 complete

#### Phase 1.2 Completion Summary

**Status**: ⏳ **IN PROGRESS** (2025-11-26)

All repositories tracking Phase 1.2 build tooling modernization:

| Repository | Branch | Issue | PR | Status |
|------------|--------|-------|----|----|
| txaio | modernization-phase-1.2 | [#202](https://github.com/crossbario/txaio/issues/202) | [#203](https://github.com/crossbario/txaio/pull/203) | ⏳ In progress |
| autobahn-python | modernization-phase-1.2 | [#1787](https://github.com/crossbario/autobahn-python/issues/1787) | [#1788](https://github.com/crossbario/autobahn-python/pull/1788) | ⏳ In progress |
| zlmdb | modernization-phase-1.2 | [#79](https://github.com/crossbario/zlmdb/issues/79) | [#80](https://github.com/crossbario/zlmdb/pull/80) | ⏳ In progress |
| cfxdb | modernization-phase-1.2 | [#102](https://github.com/crossbario/cfxdb/issues/102) | [#103](https://github.com/crossbario/cfxdb/pull/103) | ⏳ In progress |
| wamp-xbr | modernization-phase-1.2 | [#154](https://github.com/wamp-proto/wamp-xbr/issues/154) | [#155](https://github.com/wamp-proto/wamp-xbr/pull/155) | ⏳ In progress |
| crossbar | modernization-phase-1.2 | [#2140](https://github.com/crossbario/crossbar/issues/2140) | [#2141](https://github.com/crossbario/crossbar/pull/2141) | ⏳ In progress |

**Scope**:
- Modernize build systems to use pyproject.toml (PEP 621)
- Add/update ruff configuration (replacing flake8)
- Add/update mypy configuration
- Add/update pytest/coverage configuration
- Remove legacy build files (setup.py minimized, setup.cfg, requirements.txt removed)
- Ensure all checks pass: `just check cpy314`

### Phase 1.3: Wheel Building

**Objective**: Ensure native wheels for all platforms (x86-64, ARM64) and Python implementations (CPython, PyPy).

**Tasks per repository**:
1. [ ] Audit current wheel building status
2. [ ] Verify CFFI usage (not CPyExt) for native extensions
3. [ ] Add/update GitHub Actions for wheel building
4. [ ] Test wheel building locally: `just build cpy314`
5. [ ] Test wheel building for PyPy: `just build pypy311`
6. [ ] Configure ARM64 wheel building (GitHub Actions or cross-compile)
7. [ ] Verify wheels are manylinux2014 compatible
8. [ ] Test wheels on different platforms
9. [ ] Configure PyPI publishing workflow
10. [ ] Commit changes and push to bare repo

**Deliverables per repository**:
- Native wheels for x86-64 (CPython 3.11-3.14, PyPy 3.11)
- Native wheels for ARM64 (CPython 3.11-3.14, PyPy 3.11)
- GitHub Actions for automated wheel building
- PyPI publishing workflow ready

**Blockers**: Requires Phase 1.2 complete

### Phase 1.4: Documentation

**Objective**: Modernize documentation with Sphinx + Furo theme + RTD integration.

**Tasks per repository**:
1. [ ] Audit current documentation status
2. [ ] Update Sphinx to latest version
3. [ ] Migrate to Furo theme (from sphinx_rtd_theme)
4. [ ] Update docs/conf.py configuration
5. [ ] Verify all documentation builds: `just docs cpy314`
6. [ ] Update API documentation (sphinx-autoapi or autodoc)
7. [ ] Add/update README.md with badges, quick start
8. [ ] Verify RTD integration (readthedocs.yml)
9. [ ] Test documentation locally
10. [ ] Commit changes and push to bare repo

**Deliverables per repository**:
- Modern Sphinx documentation with Furo theme
- Comprehensive API documentation
- RTD integration configured
- Professional README.md

**Blockers**: Requires Phase 1.3 complete

### Phase 1.5: Unit Test Coverage

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

**Blockers**: Requires Phase 1.4 complete

### Phase 1.6: CI/CD

**Objective**: Comprehensive GitHub Actions workflows for automated testing, building, publishing.

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

**Blockers**: Requires Phase 1.5 complete

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
- Phase 1.2 (Build tooling): 0.5-1 day per repo × 7 = 3.5-7 days
- Phase 1.3 (Wheels): 0.5-1 day per repo × 7 = 3.5-7 days
- Phase 1.4 (Documentation): 0.5 day per repo × 7 = 3.5 days
- Phase 1.5 (Test coverage): 0.5-1 day per repo × 7 = 3.5-7 days
- Phase 1.6 (CI/CD): 0.5-1 day per repo × 7 = 3.5-7 days
- **Subtotal**: 18-35 days

**Phase 2** (Integration Testing):
- Integration test infrastructure: 2-3 days
- Test implementation: 3-5 days
- **Subtotal**: 5-8 days

**Total Estimated**: 24-45 days (5-9 weeks)

**Note**: Estimates assume sequential execution. Some parallelization possible (e.g., different repos in same sub-phase).

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

Last updated: 2025-11-26
Status: Phase 1.2 in progress
