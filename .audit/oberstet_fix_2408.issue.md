Issue:    crossbario/crossbar#2408
Title:    gh-actions rollout 20261111-gh-actions: crossbar
URL:      https://github.com/crossbario/crossbar/issues/2408
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-11-11T20:54:12Z
Comments: 0
Frozen:   2026-11-11T20:55:34Z by `just new-branch`
SHA-256:  6b045ce51fe615d35a7f8c2aa7f5274991b63e55bd63b81654f97bb23989fdd9 (of everything below the line)

---


## Why

The `gh-actions` aspect rollout `20261111-gh-actions` brings `crossbar` in line
with its declared aspects. Computed by the aspect's `reconcile.py`
(`wamp-proto/wamp-ai@dab2b9c8a861`) against apex
`930035bc3727`, applied mechanically by the fleet driver.

## Changes (5 file(s))

- `aspects.toml`
- `.ai`
- `.github/workflows/main.yml`
- `.github/workflows/release-post-comment.yml`
- `.github/workflows/release.yml`

### `aspects.toml` (membership, rendered from the apex)

```diff
--- a/aspects.toml
+++ b/aspects.toml
@@ -1,8 +1,12 @@
 # Materialized aspect membership for this repository.
 # Rendered from the apex inventory (all.yml); NOT a source of truth.
-aspects = ["way-a", "pypi-release", "python-package", "sphinx-docs", "rtd-release"]
+aspects = ["way-a", "gh-actions", "pypi-release", "python-package", "sphinx-docs", "rtd-release"]
 
 [provider.way-a]
+repo = "wamp-proto/wamp-ai"
+path = ".ai"
+
+[provider.gh-actions]
 repo = "wamp-proto/wamp-ai"
 path = ".ai"
 
```

### Aspect ChangeSet (33 op(s))

- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/main.yml`
- `line_replace` `.github/workflows/release-post-comment.yml`
- `line_replace` `.github/workflows/release-post-comment.yml`
- `line_replace` `.github/workflows/release.yml`
- `line_replace` `.github/workflows/release.yml`
- `line_replace` `.github/workflows/release.yml`
- `line_replace` `.github/workflows/release.yml`
- `line_replace` `.github/workflows/release.yml`
- `line_replace` `.github/workflows/release.yml`

## Acceptance

- The branch carries exactly the files above; re-running the aspect reconcile reports 0 changes.
- Tracked in the fleet rollout record `rollouts/20261111-gh-actions/rollout.toml` (crossbario/autobahn-crossbar-fleet).

---

## Comments at freeze (0)

