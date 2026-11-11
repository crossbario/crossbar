Issue:    crossbario/crossbar#2396
Title:    check-typing: fix the 583 missing-union-attribute and 7 lost-keyword-for-regular-parameter sites, then stop ignoring both rules
URL:      https://github.com/crossbario/crossbar/issues/2396
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-11-09T23:31:23Z
Comments: 0
Frozen:   2026-11-11T05:30:54Z by `just new-branch`
SHA-256:  7ca04668a97e3f70fb7bc72ea7ee9ccb05de841ca30e7a4153c0311ae20b13f9 (of everything below the line)

---

## Why

ty 0.0.100 added two rules. #2392 put both on `check-typing`'s ignore list, under its FIXME, so CI could follow ty. With the venv's Python, at `f1bb9e39`, they report:

| rule | sites | what |
| :-- | --: | :-- |
| `missing-union-attribute` | 583 | an attribute used on a value whose type includes `None`, with no `None` check |
| `lost-keyword-for-regular-parameter` | 7 | an override that makes a keyword-capable parameter positional-only, e.g. `onMessageFrameData` in `src/crossbar/worker/testee.py:69` |

The union types behind `missing-union-attribute`:

| union | sites |
| :-- | --: |
| `Unknown \| None` / `None \| Unknown` | 335 |
| `ITransport \| None` | 66 |
| `None \| DockerClient` | 26 |
| `None \| Channels` | 22 |
| `None \| NodeController` | 21 |
| others | 113 |

The files with the most sites:

| file | sites |
| :-- | --: |
| `worker/proxy.py` | 39 |
| `master/mrealm/controller.py` | 38 |
| `edge/node/node.py` | 33 |
| `edge/worker/xbrmm.py` | 31 |
| `edge/worker/xbr/_marketmaker.py` | 28 |
| `node/node.py`, `network/_backend.py` | 26 each |
| `router/session.py` | 25 |

Most of them are one pattern: an attribute declared `Optional[...] = None` in `__init__` and set later, in `onJoin`, `start` and the like, then used without a check. ty is right that the type allows `None` there. Some of those uses could really hit `None`, for example a transport used after the session has been closed.

## The change

1. Fix each site by what it means:
   - an `assert x is not None`, or a local narrowed by a check, where the value is set by the time the code runs;
   - a real `None` check, where it may not be;
   - a declared type without `None`, where the attribute is always set before use.

   Go file by file, starting with the larger ones.
2. Fix the seven overrides so that they keep the base class's keyword parameters.
3. Remove `--ignore missing-union-attribute` and `--ignore lost-keyword-for-regular-parameter` from `check-typing`.

## Done when

- `just check cpy311` passes with the newest ty, without the two ignores.
- `just test-trial`, `just test-pytest` and `just test-functional` pass, so the changed `None` handling is covered.

---

## Comments at freeze (0)

