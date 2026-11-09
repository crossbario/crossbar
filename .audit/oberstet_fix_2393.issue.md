Issue:    crossbario/crossbar#2393
Title:    test-pytest leaves six test directories in the repository root, and `just docs` rewrites docs/_static/favicon.ico
URL:      https://github.com/crossbario/crossbar/issues/2393
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-11-09T22:16:09Z
Comments: 0
Frozen:   2026-11-09T23:16:22Z by `just new-branch`
SHA-256:  d0296352f438ffefa6751d4a6b3fd80dc44b735a4df1ba624d6b9c012f5c7a67 (of everything below the line)

---

## Why

A CI job that ends with a dirty tree builds from something other than the commit. A runner never shows it, because it is thrown away after the job. A replay of `main.yml` at `0700aac` that checks `git status` after every job found two causes.

1. **`just test-pytest` leaves six untracked directories in the repository root.** Each `test` and `test-locked` CPython leg ended with:

   ```
   ?? crossbar.bridge.mqtt.test.test_w/
   ?? crossbar.common.twisted.test.tes/
   ?? crossbar.router.test.test_tls_au/
   ?? crossbar.test.test_key/
   ?? crossbar.test.test_lmdb_format/
   ?? crossbar.worker.test.test_max_co/
   ```

   These are Twisted's `TestCase.mktemp()` paths (`<module, cut to 32 characters>/<class>/<method>/...`). They are relative to the working directory. Under `trial` that is `_trial_temp/`, which `.gitignore` lists. `test-pytest` runs the same trial test cases under pytest, from the repository root, so they land there (e.g. `test_key.py:49`, `test_lmdb_format.py:37`).
2. **`just docs` changes a tracked file.** `docs` depends on `optimize-images`, which regenerates `docs/_static/favicon.ico` from the logo SVG with ImageMagick. The new file has the same size (15086 bytes), but about 2300 of its bytes differ from the committed one, presumably because the ImageMagick version differs. So every docs build on a different ImageMagick leaves ` M docs/_static/favicon.ico`.

## The change

1. **`test-pytest` runs from an ignored working directory**, as trial does: `cd` into `_trial_temp/` (already in `.gitignore`) and pass the source path from there. Then a test's `mktemp()` lands in an ignored directory. A `.gitignore` entry for the six names would hide the next one, so it is not the fix.
2. **`docs` no longer depends on `optimize-images`.** Generating the favicon is a one-time asset step: run it by hand when the logo changes, and commit the result.

## Done when

- After `just test-pytest cpy311`, `git status --porcelain` is empty.
- After `just docs cpy311`, `git status --porcelain` is empty.

---

## Comments at freeze (0)

