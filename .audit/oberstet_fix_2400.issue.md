Issue:    crossbario/crossbar#2400
Title:    dist/build/build-sourcedist: restore _version.py's build-ID placeholder after the build
URL:      https://github.com/crossbario/crossbar/issues/2400
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-11-10T10:49:16Z
Comments: 0
Frozen:   2026-11-11T00:45:37Z by `just new-branch`
SHA-256:  e884c4bb40cec48ebcce39cd2ab91d83e638c3a1af4d30a16762dcdb8f068c74 (of everything below the line)

---

## Why

`just dist`, `just build` and `just build-sourcedist` run `inject-build-id.py` before `python -m build`. When `CROSSBAR_BUILD_ID` is set, it writes the ID into the tracked `src/crossbar/_version.py` in place (#2231). Nothing puts the placeholder back afterwards. The script's header says "the stamped value is never committed", but after the build the file is changed in the working tree:

```
$ git status --porcelain
 M src/crossbar/_version.py
```

On a GitHub runner this goes unnoticed, because the runner is thrown away. It shows up anywhere the clone is kept:

- **The tree is dirty after a build.** The stamped file can be committed by accident. A CI replay on a persistent machine that checks for a clean tree after each job reports the `build` job as having changed tracked files. It is the only job that does.
- **The next build with a different ID fails.** The placeholder is gone, so the second stamp finds nothing to replace:
  ```
  $ CROSSBAR_BUILD_ID=20261110-9f918c3 python inject-build-id.py v.py
  Ok: stamped build ID "20261110-9f918c3" into "v.py"
  $ CROSSBAR_BUILD_ID=20261111-abcdef1 python inject-build-id.py v.py
  Error: build ID placeholder __build__ = "19000101-0000000" not found once in "v.py"
  ```

## The change

In each of the three recipes, put the placeholder back once the build is done, whether the build passed or failed, e.g. with a `trap` that runs `git checkout -- src/crossbar/_version.py` when `CROSSBAR_BUILD_ID` was set. The built wheel and sdist keep the stamped ID, which is what `Check build ID in packages` in `main.yml` verifies.

## Done when

- With `CROSSBAR_BUILD_ID` set, `just dist cpy311` builds packages that carry the ID, and `git status --porcelain` is empty afterwards.
- A second `just dist cpy311` with a different ID passes too.
- A failed build also leaves the file unchanged.
- `main.yml`'s `build` job stays green.

---

## Comments at freeze (0)

