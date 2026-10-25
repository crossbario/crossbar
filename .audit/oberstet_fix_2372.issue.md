Issue:    crossbario/crossbar#2372
Title:    Dependencies: drop wsaccel (replaced by autobahn-python's NVX), and require autobahn[all]
URL:      https://github.com/crossbario/crossbar/issues/2372
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-10-25T14:49:27Z
Comments: 0
Frozen:   2026-10-25T14:54:20Z by `just new-branch`
SHA-256:  d459ee45d31c0b8ef48cc531625cbf1808f8540b52ba8dd1d72b576ebeca49ca (of everything below the line)

---


## Why

Two runtime dependencies in `pyproject.toml` (at `bd5784f7`) no longer match how crossbar uses autobahn-python.

**1. `wsaccel` is declared but no longer used.**

```toml
"wsaccel>=0.6.4; platform_python_implementation=='CPython'",
```

- autobahn-python accelerates UTF-8 validation and XOR masking with its own NVX extension. It already dropped `wsaccel` (in its `accelerate` extra the line is commented out), and its code no longer imports it.
- crossbar's only reference is the version banner in `src/crossbar/node/main.py` (around line 344). It prints `wsaccel-<version>` when the UTF-8 validator or XOR masker class comes from `wsaccel`. With autobahn no longer importing `wsaccel`, that branch is dead.

The dependency still has a cost. `wsaccel` 0.6.7 has no wheel for CPython 3.14, so installing crossbar on 3.14 builds it from source, which needs a C compiler. On a host without one, the install fails:

```
error: Failed to build `wsaccel==0.6.7`
  ...
  error: [Errno 2] No such file or directory: 'cc'
hint: `wsaccel` (v0.6.7) was included because `crossbar` (v26.10.1) depends on `wsaccel`
```

(observed 2026-10-25, installing crossbar 26.10.1 with uv into a fresh Debian 13 image on CPython 3.14.7).

**2. crossbar lists autobahn's extras one by one.**

```toml
"autobahn[twisted,encryption,compress,serialization,scram]>=26.10.2",
```

autobahn-python's `all` extra is `twisted,accelerate,compress,serialization,encryption,scram,nvx`. That is crossbar's list plus `accelerate` and `nvx`, both empty today. So `autobahn[all]` installs the same packages now, and it keeps crossbar in step when autobahn adds or renames an extra. It is also what cfxdb already requires (`autobahn[all]>=26.6.1`), so a crossbar install resolves to `autobahn[all]` today anyway.

## Change

1. **Drop `wsaccel`:**
   - remove the `wsaccel` line from `[project] dependencies` in `pyproject.toml`;
   - in `src/crossbar/node/main.py`, remove the two dead `wsaccel` branches of the version banner (UTF-8 validator, XOR masker), and report what autobahn actually uses (NVX or pure Python), if autobahn exposes it;
   - remove `wsaccel` from the license tables (`src/crossbar/LICENSES-OSS`, `docs/oss_licenses_table.rst`, `docs/soss_licenses_table.rst`) and from the dependency inventory in `MODERNIZATION.md`.
2. **Require `autobahn[all]`:** replace the autobahn line in `[project] dependencies` with:

   ```toml
   "autobahn[all]>=26.10.2",
   ```

## Done when

- `uv pip install` of the branch, on CPython 3.14 on a host without a C compiler, succeeds and installs no `wsaccel`.
- The installed crossbar declares `autobahn[all]>=26.10.2` (`Requires-Dist` in its metadata), and the resolved set of autobahn's dependencies is the same as before the change.
- `crossbar version` shows the accelerators autobahn uses, without a `wsaccel` line.
- CI is green.

Note: This issue was drafted with AI assistance (Claude Code).

---

## Comments at freeze (0)

