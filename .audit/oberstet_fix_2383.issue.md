Issue:    crossbario/crossbar#2383
Title:    check-typing: ty 0.0.98+ fails on the renamed rule `unresolved-import` (now `import-not-found`)
URL:      https://github.com/crossbario/crossbar/issues/2383
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-11-06T19:20:47Z
Comments: 0
Frozen:   2026-11-06T19:22:49Z by `just new-branch`
SHA-256:  52ddf788106ea9b526bc9616a06a2930e29020efedc87b89dabb48ee6f147be4 (of everything below the line)

---

## What happens

ty 0.0.97 renamed the rule `unresolved-import` to `import-not-found` ([astral-sh/ruff#29960](https://github.com/astral-sh/ruff/pull/29960)). Since 0.0.98, ty warns when the old name is used ([astral-sh/ruff#30024](https://github.com/astral-sh/ruff/pull/30024)):

```
warning[renamed-rule]: Rule `unresolved-import` has been renamed to `import-not-found`
```

`check-typing` still passes `--ignore unresolved-import` (`justfile:587`), and ty exits with 1 on this warning. So the check fails without any real type error. CI installs ty unpinned (`uv tool install ty`, `.github/workflows/main.yml:55`).

## Evidence

Run on master with ty 0.0.97, 0.0.98 and 0.0.99 and the recipe's exact `--ignore` list:

- 0.0.97: passes (no warning);
- 0.0.98 / 0.0.99 as-is: `Found 1 diagnostic`, which is the `renamed-rule` warning, exit 1;
- 0.0.99 with `--ignore import-not-found` instead: `All checks passed!`.

All other rule names in the recipe are valid in 0.0.99; this is the only rename in ty 0.0.97 to 0.0.99.

## Fix

In `justfile:587`:

```diff
-        --ignore unresolved-import \
+        --ignore import-not-found \
```

No pin needed: CI keeps using the latest ty.

While there, optional cleanup: the probe at `justfile:576-583` tries `--ignore non-subscriptable` to pick between two names. ty 0.0.99 has no `non-subscriptable` (it answers `Unknown rule ... Did you mean not-subscriptable?`), so the probe always picks `not-subscriptable`. It still works, but it could be replaced by a plain `--ignore not-subscriptable`.

---

## Comments at freeze (0)

