Issue:    crossbario/crossbar#2388
Title:    Dependencies: refresh uv.lock to latest stable (Twisted 26.10.0 with 7 CVEs), raise security floors, drop caps left over from 2017
URL:      https://github.com/crossbario/crossbar/issues/2388
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-11-07T22:10:03Z
Comments: 0
Frozen:   2026-11-07T22:16:12Z by `just new-branch`
SHA-256:  a804db3a4568792832ee711b5e0bb7ee982e5303af2c75aafa7bbb23a891ad60 (of everything below the line)

---

## Problem

crossbar is the application in the WAMP group: unlike the five libraries, it commits `uv.lock` and is supposed to follow the latest stable releases of its dependencies. On master `5d4e3299`, the lock has fallen far behind. Our CI never sees this, because CI does not install from the lock:

- **The lock has not been upgraded in months.** `just update-uvlock` runs `uv lock --python 3.11` **without `--upgrade`**. uv then keeps every existing pin that still satisfies `pyproject.toml`, so the lock only moves when someone bumps a single package by hand (as in #2379 for brotli). `MODERNIZATION.md` says the release workflow should "update all deps to latest stable", but no recipe does that.
- **CI does not test the lock.** `main.yml` runs `just install-dev`, which is `pip install -e .[dev]` and resolves fresh from `pyproject.toml`. So CI already tests Twisted 26.10.0, autobahn 26.11.1 and so on, while the lock (which `docs/uvlock.rst` presents as the strict production channel: "Install EXACTLY what was tested") pins older, vulnerable versions that no CI job installs.
- **Dependabot cannot fix this alone.** The grouped `uv` update job has ended in `failure` on almost every weekly run since at least 2026-09-29 (most recently run 42328241870 on 2026-11-07). It still opened #2386 (37 updates), but that PR is not mergeable as-is:
  - It rewrites the `pytest<9.2` cap from #2383, which would break `just test-pytest` (pytest-tap 3.5 crashes pytest 9.2.0).
  - It puts major bumps (hexbytes 1 → 2, eth-account 0.13 → 0.14) into the "minor-patch" group.
  - It does not include Twisted.

## Known vulnerabilities in the committed lock

Source: the PyPI JSON `vulnerabilities` field for each of the 273 locked versions, checked on 2026-11-07. These are leads for review, not proof that crossbar is exploitable. Runtime dependencies (the ones a `uv sync --frozen` deployment installs):

| Package | Locked | Advisories | Fixed in | Blocked by |
|---|---|---|---|---|
| **twisted** | 26.4.0 | 7: CVE-2026-83813, CVE-2023-44487 (HTTP/2 Rapid Reset, GHSA-vpp8), CVE-2026-115774/-115775/-115776/-115778, CVE-2026-115877 (header-value request smuggling) | 26.10.0 | lock only |
| **autobahn** | 26.10.2 | GHSA-2gqc (handshake header smuggling) | 26.11.1 | floor `>=26.10.2` (#2379 step 2) |
| **h2** | 3.2.0 | CVE-2025-57804 (request splitting), CVE-2026-71554 | 4.3.0 / 4.4.1 | cap `<4.0.0` |
| **hpack** | 3.0.0 | CVE-2026-59980 | 4.2.0 | h2 cap |
| **idna** | 2.5 | CVE-2024-3651, CVE-2026-45409 (DoS in `idna.encode()`) | 3.7 / 3.15 | cap `<2.6` |
| pyasn1 | 0.6.1 | 9 DoS advisories in the BER/DER decoders | 0.6.5 | lock only |
| ujson | 5.11.0 | CVE-2026-32874/-32875/-44660/-54911 (one interpreter crash) | 5.13.0 | lock only |
| werkzeug | 3.1.4 | 3 `safe_join` advisories (Windows device names) | 3.1.9 | lock only |
| msgpack | 1.1.2 | CVE-2026-57585, CVE-2026-114613 | 1.2.3 | lock only |
| ecdsa | 0.19.1 | CVE-2026-33936 (DER parsing); CVE-2024-23342 (Minerva, no fix) | 0.19.2 | lock only |
| flask | 3.1.2 | CVE-2026-27205 | 3.1.3 | lock only |
| requests | 2.32.5 | CVE-2026-25645 | 2.33.0 | lock only |
| pynacl | 1.6.1 | CVE-2025-69277 (libsodium) | 1.6.2 | lock only |
| pygments | 2.19.2 | CVE-2026-4539 | 2.20.0 | lock only |
| mistune | 3.2.1 | 11 (CPU exhaustion, include directive) | 3.3.0 | lock only |
| certifi | 2025.11.12 | GHSA-6q48 (emSign root removal) | 2026.10.18 | lock only |

Dev and docs tools in the lock have more (aiohttp 3.13.2 via web3, tornado, virtualenv, nbconvert, setuptools 80.9.0, pip 25.3, anyio 1.3.1 via httpx, filelock, soupsieve, bleach, wheel). They disappear with a plain `uv lock --upgrade`.

**Twisted 26.10.0** ([release notes](https://github.com/twisted/twisted/releases/tag/twisted-26.10.0)) matters most for crossbar:

- crossbar installs `twisted[tls,conch,http2]`, and 26.10.0 fixes HTTP/2 Rapid Reset in `twisted.web`'s HTTP/2 server and header-value request smuggling in `HTTPChannel`. Both are code paths crossbar's web transport uses.
- Also relevant to crossbar:
  - `twisted.web.websocket` now delivers complete messages (#12885);
  - the conch fixes (crossbar uses conch for the manhole);
  - 26.10.0 is the **last release supporting Python 3.10**. crossbar already requires `>=3.11`, so this does not matter for us.
- Twisted 26.10.0 still allows `h2<5.0,>=3.2` and `priority<2.0,>=1.1.0`, so it does not need our h2 3.x cap.

## Caps left over from 2017

`idna>=2.5,<2.6`, `h2>=3.2.0,<4.0.0`, `hyperframe>=5.2.0,<6.0.0` and `priority>=1.3.0,<2.0` came into `pyproject.toml` with the build-system modernization (d1bb018b, 2025-11-08). They match exactly the versions in the old frozen `requirements-pinned.txt` (d8bb741c, 2017-03-29: idna 2.5, hyperframe 5.2.0, priority 1.3.0), so they look like copied pins, not real compatibility limits. crossbar's own code imports neither `idna` nor `h2`. `.github/dependabot.yml` also ignores major updates for h2/hyperframe/priority, so Dependabot never offers these upgrades.

A resolve with the caps lifted works (`uv pip compile pyproject.toml --extra dev --python-version 3.11` with overrides `idna>=3.15`, `h2>=4.4.1,<5`, `hyperframe>=6.1`). It gives twisted 26.10.0 + h2 4.4.1 + hpack 4.2.0 + hyperframe 6.1.0 + priority 1.3.0 + idna 3.20 + requests 2.34.2, with no conflicts. `priority` 2.0.0 stays excluded by Twisted's own `<2.0`, so our `priority` cap is redundant.

`eth-abi>=5.1.0,<5.2.0` and `parsimonious>=0.9.0,<0.11.0` are different: eth-abi 6.0.0 still requires `parsimonious<0.11.0`, and `src/crossbar/__init__.py` monkey-patches `eth_abi.encode_abi`. Both caps need a real eth-abi 6 check, not a blind lift.

## Other direct dependencies behind latest stable

Within the current specifiers, `uv lock --upgrade` alone picks these up. Each is a **major** step and needs a look (changelog plus our usage):

- XBR stack: hexbytes 1.3.1 → 2.0.0 (eth-account 0.14 needs `hexbytes>=2`), eth-account 0.13.7 → 0.14.0, eth-typing 5.2.1 → 6.0.0
- ujson 5.11.0 → 6.1.0 (also clears the CVEs above)
- watchdog 6.0.0 → 7.1.0 (`crossbar.common.fswatcher`)
- pycryptodome 3.23.0 → 4.4.0 (released 2026-11-07)
- importlib-resources 6.5.2 → 7.1.0
- service-identity 24.2.0 → 26.1.0
- treq 25.5.0 → 26.7.0 and txtorcon 24.8.0 → 26.6.0
- numpy 2.3.5 → 2.5.4
- dev and docs tools: sphinx 8.2.3 → 9.2.0, myst-parser 4 → 5, setuptools 80 → 84, pip 25 → 26, twine 6.2.0 → 7.0.0 (6.2.0 rejects Metadata-Version 2.5, which the build now produces), tox, ruff 0.14 → 0.17

**Not bumped, on purpose:**

- **cryptography** stays at 50.0.2, which is the latest release. The next release matters for PyPy 8 / `pypy312` (pp80): 50.0.2 ships pp80 wheels only for win_amd64 and macOS arm64, so Linux `pypy312` has to build it from source (autobahn #1963). crossbar's floor `cryptography>=39.0.0` is moot anyway, because autobahn already requires `>=50`.
- **pytest** stays `<9.2` until pytest-tap releases python-tap/pytest-tap#139 (#2383).

## Proposal

1. **Relock and raise floors.** Relock with `uv lock --upgrade --python 3.11` and raise the security floors on direct dependencies, so the published wheel (which installs without the lock) cannot pick up the vulnerable versions either:
   - `twisted[...]>=26.10.0` (all three platform lines)
   - `autobahn[all]>=26.11.1`, which is #2379 step 2
   - optionally the "lock only" rows above as floors too, e.g. `pyasn1>=0.6.5`, `ujson>=5.13.0`, `werkzeug>=3.1.9`, `flask>=3.1.3`, `requests>=2.33.0`, `pynacl>=1.6.2`, `pygments>=2.20.0`, `mistune>=3.3.0`, `cryptography>=50`
2. **Lift the 2017 caps:** `idna>=3.15`, `h2>=4.4.1,<5`, `hyperframe>=6.1`, and drop our own `priority` cap (Twisted's `<2.0` already applies). Drop the matching `ignore:` entries in `.github/dependabot.yml`.
3. **Major bumps:** review the majors listed above with a full run (trial, pytest, functional, integration, smoke). Hold back any that break with a commented cap.
4. **Close the process gaps:**
   - `just update-uvlock` should upgrade (`uv lock --upgrade --python 3.11`), or a separate `just upgrade-uvlock` should exist, so that "follow latest stable" is one command.
   - CI should test what we ship. For example, one job installs with `uv sync --frozen --extra dev` and runs the unit tests, next to the existing fresh-resolution jobs. Otherwise the lock remains an untested artifact.
   - `.github/dependabot.yml` should ignore `pytest >=9.2` while the cap is in place, and keep known-major packages (hexbytes, eth-*) out of the minor-patch group.
   - Bring the documentation in line with what actually happens (see below).
5. Close #2386 (and #2378 pip, #2376 setuptools, which this relock includes) in favour of this issue.

## Documentation

The "app follows latest stable, libraries float" policy is currently spread over three places, and they contradict each other and the code:

- `docs/uvlock.rst`:
  - app vs library, two-lane Dependabot review;
  - lists `urllib3` as major-capped, but that cap was lifted in f26e142c (#2291);
  - "Install EXACTLY what was tested", but CI does not install from the lock.
- `MODERNIZATION.md`:
  - "Before release: `uv sync --upgrade`" (no recipe does that);
  - "CI/CD uses `uv sync --frozen`" (it does not).
- `.github/dependabot.yml` header comments.

**Suggestion:**

- Make `docs/uvlock.rst` the one authoritative place. Add a short "Dependency policy" section that states:
  - crossbar follows the latest stable releases;
  - when the lock gets upgraded;
  - which caps exist and why (each with a reason and an exit condition, like the pytest cap);
  - which CI job tests the lock.
- In `MODERNIZATION.md`, point to `docs/uvlock.rst` instead of restating the policy.

## Acceptance

- `uv.lock` resolves Twisted 26.10.0 and autobahn 26.11.1, and the PyPI vulnerability check over the lock shows no runtime-dependency advisory with a released fix.
- `pyproject.toml` floors exclude Twisted < 26.10.0 and autobahn < 26.11.1. The 2017 caps are gone or carry a written reason.
- Full CI (main, plus the new frozen-lock job) is green on CPython 3.11–3.14 and PyPy 3.11.
- `docs/uvlock.rst` describes the policy and the recipes as they are.

---

## Comments at freeze (0)

