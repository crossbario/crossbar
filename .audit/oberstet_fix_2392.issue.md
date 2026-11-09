Issue:    crossbario/crossbar#2392
Title:    check-typing: follow ty 0.0.100's rule names, and decide on its two new rules
URL:      https://github.com/crossbario/crossbar/issues/2392
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-11-09T22:15:58Z
Comments: 0
Frozen:   2026-11-09T22:21:06Z by `just new-branch`
SHA-256:  b1c5abdb9e36a37f08c0c353d28909725d93e14c567c62bed44856bf7749bff1 (of everything below the line)

---

## Why

`check-typing` installs the newest ty (`uv tool install ty` in `main.yml`, no version). ty 0.0.100 was released on 2026-11-09 20:15 UTC. Since then, `just check cpy311` fails at master (`0700aac`) with 590 errors. CI run 42433160777 of the same commit passed with ty 0.0.99, and the next CI run will fail.

The recipe ignores 28 rules by name. In 0.0.100 several of those names no longer exist, so ty warns about them and the rules they used to silence are back on:

```
warning[unknown-rule]: Unknown rule `import-not-found`
warning[unknown-rule]: Unknown rule `not-subscriptable`. Did you mean `non-subscriptable`?
warning[unknown-rule]: Unknown rule `possibly-missing-submodule`
warning[unknown-rule]: Unknown rule `unused-type-ignore-comment`
warning[renamed-rule]: Rule `invalid-method-override` has been renamed to `incompatible-method-override`
warning[renamed-rule]: Rule `unresolved-attribute` has been renamed to `missing-attribute`
warning[renamed-rule-in-ignore-comment]: Rule `invalid-attribute-override` has been renamed to `incompatible-attribute-override`
```

Almost all of the errors come from two rules that `--ignore` does not name:

| rule | errors (without the venv's Python) | e.g. |
| :-- | --: | :-- |
| `missing-union-attribute` | 243 | `Attribute write is not defined on None in union ITransport \| None` (`src/crossbar/worker/testee.py:28`) |
| `lost-keyword-for-regular-parameter` | 3 | `Override of method onMessageFrameData disallows keyword arguments allowed by the method on the base class` (`testee.py:69`) |

We follow ty as it moves rather than pinning it, so the recipe has to keep up with it.

## The change

1. **In `check-typing`, rename the ignores to ty 0.0.100's names:**
   - `invalid-method-override` becomes `incompatible-method-override`;
   - `unresolved-attribute` becomes `missing-attribute`;
   - `not-subscriptable` becomes `non-subscriptable`.

   Remove the names ty no longer knows, or replace them with their successors where ty names one: `import-not-found`, `possibly-missing-submodule`, `unused-type-ignore-comment`. The goal is no `unknown-rule` or `renamed-rule` warning.
2. **Rename the rule in the one `ty: ignore[invalid-attribute-override]` comment** to `incompatible-attribute-override`.
3. **`missing-union-attribute` and `lost-keyword-for-regular-parameter`:** add them to the ignores, under the recipe's existing FIXME, as the other rules were. Then open one follow-up issue to fix the 246 sites, mostly `Optional` attributes used without a `None` check.
4. **`check-typing` fails on an `unknown-rule` or `renamed-rule` warning**, so the next rename shows up as a named failure, not as hundreds of errors from rules that came back on (`--error unknown-rule --error renamed-rule`, if ty takes those, or a grep on its output).

## Done when

- `just check cpy311` passes with the newest ty, and its output has no `unknown-rule` or `renamed-rule` warning.
- The follow-up issue for the 246 sites exists.

The same renames are expected in the other WAMP repositories' `check-typing` recipes: autobahn-python, txaio, zlmdb, cfxdb and wamp-xbr all ignore at least one of the names above.

---

## Comments at freeze (0)

