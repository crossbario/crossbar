Issue:    crossbario/crossbar#2231
Title:    [BUG] Restore build-ID stamping (`CROSSBAR_BUILD_ID`) lost in the tox→just migration
URL:      https://github.com/crossbario/crossbar/issues/2231
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-06-21T14:22:40Z
Comments: 0
Frozen:   2026-10-20T13:35:53Z by `just new-branch`
SHA-256:  a9ec8524e1c04bd91a91821fa7fa4237682b7f0f55c06b062789b851f5518029 (of everything below the line)

---

## Problem

`crossbar version` shows a build ID next to the version:

```
:::::::::::::::::   Crossbar.io v26.6.1 — Resistance Is Futile [19000101-0000000]
```

`[19000101-0000000]` is a **placeholder that is never replaced** — so released
artifacts ship with this dummy build ID.

See:

<img width="1180" height="970" alt="Image" src="https://github.com/user-attachments/assets/dcb3fe88-c77b-4805-89f9-c9a9a837ed74" />

The stamping mechanism still exists in the tree but is **orphaned / dead**, left
behind by the tox → justfile+uv/hatch modernization:

- `versions.sh` — sets `CROSSBAR_BUILD_ID=$(date --utc +%Y%m%d)-$(git rev-parse --short HEAD)`
- `inject-build-id.py` — replaces the `__build__` placeholder in
  `src/crossbar/_version.py` with `$CROSSBAR_BUILD_ID`
- `tox.ini.orig` — the only caller (`python inject-build-id.py`), and it is
  disabled (`.orig`)

Nothing in the current `justfile`, `pyproject.toml` (hatch), or GitHub Actions
invokes any of these (confirmed: zero references). It was a **build-time
injection** (transient, in the build env — never committed, not tied to PyPI
publish).

`inject-build-id.py` is also **stale and buggy**:
- it searches for `__build__ = '00000000-0000000'` (single quotes, `00000000`),
  but `_version.py` now has `__build__ = "19000101-0000000"` (double quotes,
  `19000101`) — no match;
- `if contents.find(_SEARCH):` is wrong — `str.find` returns `-1` (truthy) when
  not found, so the replace path runs even on no-match and falsely reports "Ok".

## Proposed fix

Re-wire build-ID stamping into the current build, as a **build-time injection**
(do NOT commit the stamped value):

1. Compute `CROSSBAR_BUILD_ID` as `$(date -u +%Y%m%d)-$(git rev-parse --short HEAD)`
   (e.g. `20260621-bc6337c`).
2. Inject it into `src/crossbar/_version.py`'s `__build__` immediately before the
   wheel/sdist build, in the `just dist` / `just build` recipe and/or the
   `main.yml` "Build Distribution Packages" job (so the published artifact -
   which flows through the chain-of-custody verified upload/download - carries
   the real build ID).
3. Replace the broken `inject-build-id.py` with either a fixed version (correct
   search string incl. double quotes, robust to current placeholder; fix the
   `find()` bug) or a small `sed` in the recipe. Prefer a single, simple,
   well-tested approach.
4. Clean up the orphans no longer needed (`tox.ini.orig`, and `versions.sh` /
   `inject-build-id.py` if folded into the recipe).

### Notes / considerations

- **Chain of custody:** inject in the same job that builds the artifact
  (`main.yml` build job), so the verified artifact published to PyPI has the
  stamped ID. Don't stamp in `release.yml` (it now downloads the already-built
  artifact, per #2227).
- **Reproducibility:** the date+shortsha scheme is deterministic per commit
  (date is build-day). If fully reproducible builds are desired later, the build
  ID could be derived from the commit date instead of the wall clock — out of
  scope here.
- **Local/dev builds:** when `CROSSBAR_BUILD_ID` is unset (plain `just install`),
  keep the placeholder (current behavior) — only stamp in CI release builds.

### Acceptance

- A release/nightly artifact's `crossbar version` shows a real
  `YYYYMMDD-<shortsha>` build ID, not `19000101-0000000`.
- Local `just install` still works with the placeholder (no hard dependency on
  the env var).
- A small test covering the injection (placeholder present → replaced when env
  var set; left intact when unset).

---

_Note: This work was completed with AI assistance (Claude Code)._


## Checklist

- [x] I have searched existing issues to avoid duplicates
- [x] I have provided a minimal reproducible example
- [x] I have included version information
- [x] I have included error messages/logs


---

## Comments at freeze (0)

