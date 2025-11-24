# WAMP Python Stack Modernization

This document tracks the modernization effort across all WAMP Python packages, working from the foundation (txaio) up through the stack to Crossbar.io.

## Objective

Modernize the entire WAMP Python ecosystem to:
- Professional packaging and distribution (RHEL9 native packages)
- Modern build tooling (pyproject.toml, ruff, uv, just, pytest, mypy)
- Comprehensive CI/CD (GitHub Actions)
- High-quality documentation (Sphinx + RTD)
- Enterprise-grade stability and maintainability

## Dependency Chain

```
1. txaio              ← Foundation (Twisted/asyncio abstraction)
2. autobahn-python    ← WAMP client library
3. zlmdb              ← Database layer (LMDB + CFFI)
4. cfxdb              ← Crossbar DB access
5. wamp-xbr           ← XBR/Blockchain extensions
6. crossbar           ← WAMP Router (>160 transitive deps)
```

## Modernization Matrix

| Modernization Task | txaio | autobahn-python | zlmdb | cfxdb | wamp-xbr | crossbar | Notes |
|-------------------|-------|-----------------|-------|-------|----------|----------|-------|
| **Build System** | | | | | | | |
| ✅ pyproject.toml (PEP 621) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All have pyproject.toml |
| ❌ Remove setup.py | ⚠️ | ⚠️ | ⚠️ | ✅ | ⚠️ | ⚠️ | Keep minimal shim if needed |
| ❌ Remove setup.cfg | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Check if exists |
| ❌ Remove requirements.txt | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Move to pyproject.toml |
| **Task Runner** | | | | | | | |
| ✅ justfile | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | wamp-xbr missing |
| ❌ Remove Makefile | ❓ | ✅ | ❓ | ❓ | ❓ | ❓ | autobahn has Makefile.orig |
| ❌ Remove tox.ini | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Deprecate in favor of just |
| **Code Quality** | | | | | | | |
| ❌ ruff (lint + format) | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Replace flake8/black/isort |
| ❌ ruff.toml config | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Unified config |
| ❌ mypy (type checking) | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Static type analysis |
| ❌ mypy.ini / pyproject | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Type checking config |
| **Testing** | | | | | | | |
| ❌ pytest | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Modern test framework |
| ❌ pytest coverage | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Test coverage reporting |
| **Dependencies** | | | | | | | |
| ❌ uv support | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Fast dependency resolution |
| ❌ Dep version audit | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Review all constraints |
| **CI/CD** | | | | | | | |
| ❌ GitHub Actions | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Automated testing |
| ❌ Matrix testing | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | CPython + PyPy, multi-OS |
| ❌ Wheel building | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | x86-64 + ARM64 |
| ❌ PyPI publishing | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Automated releases |
| **Documentation** | | | | | | | |
| ❌ Modern Sphinx | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Update to latest |
| ❌ Furo theme | ❓ | ❓ | ❓ | ❓ | ❓ | ❌ | Modern RTD theme |
| ❌ RTD integration | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Read the Docs |
| ❌ API docs | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Comprehensive API ref |
| **Packaging** | | | | | | | |
| ❌ Native wheels | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Platform-specific |
| ❌ CFFI (not CPyExt) | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | PyPy compatible |
| ❌ RHEL9 RPM | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Enterprise packaging |
| **Code Cleanup** | | | | | | | |
| ❌ TODO/FIXME audit | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | 87 files in crossbar! |
| ❌ Type hints | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Modern type annotations |
| ❌ Docstrings | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | Comprehensive docs |

## Legend

- ✅ Complete
- ⚠️ Partially done / needs work
- ❌ Not started
- ❓ Status unknown / needs audit

## Phase 1: Foundation (txaio)

**Status**: Not started

**Tasks**:
1. [ ] Audit current modernization status
2. [ ] Remove/clean up legacy setup.py
3. [ ] Add ruff configuration and apply formatting
4. [ ] Add mypy configuration and type checking
5. [ ] Verify pytest integration
6. [ ] Update GitHub Actions workflows
7. [ ] Update documentation (Sphinx + Furo)
8. [ ] Verify wheel building (x86-64, ARM64, CPython, PyPy)
9. [ ] Publish updated version to PyPI

**Blockers**: None

## Phase 2: WAMP Client (autobahn-python)

**Status**: Mostly complete (recent FlatBuffers work)

**Tasks**:
1. [x] pyproject.toml migration (DONE)
2. [x] justfile integration (DONE)
3. [x] FlatBuffers serialization (DONE)
4. [x] Message refactoring (DONE)
5. [x] Test coverage improvements (DONE)
6. [ ] Final cleanup: remove legacy files
7. [ ] Verify all modernization items from matrix

**Blockers**: None (mostly done!)

## Phase 3: Database Layer (zlmdb → cfxdb)

**Status**: Not started

### zlmdb

**Tasks**:
1. [ ] Audit current modernization status
2. [ ] Verify CFFI usage (critical for PyPy)
3. [ ] Remove legacy setup.py
4. [ ] Apply full modernization checklist
5. [ ] Native wheel building
6. [ ] Publish to PyPI

**Blockers**: Requires txaio Phase 1 complete

### cfxdb

**Tasks**:
1. [ ] Audit current modernization status (looks good!)
2. [ ] Verify dependencies on zlmdb
3. [ ] Apply full modernization checklist
4. [ ] Publish to PyPI

**Blockers**: Requires zlmdb complete

## Phase 4: XBR Extensions (wamp-xbr)

**Status**: Needs significant work

**Tasks**:
1. [ ] Audit current modernization status
2. [ ] **ADD justfile** (missing!)
3. [ ] Clean up dependencies
4. [ ] Apply full modernization checklist
5. [ ] Publish to PyPI

**Blockers**: Requires cfxdb complete

## Phase 5: The Router (crossbar)

**Status**: Not started (the big one!)

**Tasks**:
1. [ ] Audit current modernization status
2. [ ] Clean up 87 files with TODO/FIXME markers
3. [ ] Review all 160+ transitive dependencies
4. [ ] Apply full modernization checklist
5. [ ] **RHEL9 native package building** (RPM)
6. [ ] Integration testing infrastructure
7. [ ] Documentation overhaul
8. [ ] Publish to PyPI

**Blockers**: Requires all previous phases complete

## Success Criteria

### Technical
- [ ] All packages use modern pyproject.toml (PEP 621)
- [ ] Consistent tooling across stack (ruff, mypy, just, pytest)
- [ ] Native wheels for x86-64 + ARM64, CPython + PyPy
- [ ] RHEL9 RPM packages available
- [ ] Comprehensive CI/CD via GitHub Actions
- [ ] Modern documentation (Sphinx + Furo + RTD)
- [ ] Zero legacy build files (setup.py, tox.ini, Makefile)

### Business
- [ ] Customer "peace of mind" - professional, stable foundation
- [ ] Easy deployment on RHEL9
- [ ] Clear upgrade path
- [ ] Professional documentation
- [ ] Enterprise-grade quality

## Timeline

- **Phase 1 (txaio)**: 1-2 days
- **Phase 2 (autobahn-python)**: 0.5 days (mostly done)
- **Phase 3 (zlmdb + cfxdb)**: 2-3 days
- **Phase 4 (wamp-xbr)**: 1-2 days
- **Phase 5 (crossbar)**: 5-7 days

**Total Estimated**: 2-3 weeks for complete stack modernization

## Notes

- This work is being done with AI assistance (Claude Code)
- All changes follow the multi-stage git workflow (asgard1 → bare repo → dev PC → GitHub)
- Each package will be updated incrementally with proper testing
- Backward compatibility maintained where possible
- Customer (US defense contractor) focus: robustness, professionalization, RHEL9 support

---

Last updated: 2025-11-24
Status: Phase 1 (txaio) - Ready to start
