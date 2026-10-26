Issue:    crossbario/crossbar#2379
Title:    Dependencies: relock brotli 1.2.1 / brotlicffi 1.2.1.0 (CVE-2026-111497), then raise the autobahn floor
URL:      https://github.com/crossbario/crossbar/issues/2379
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-10-26T16:44:47Z
Comments: 0
Frozen:   2026-10-26T19:47:12Z by `just new-branch`
SHA-256:  5b6ba3a62a14dbdd6f6638b523d344cb51e38b1698842b91264c8f138fcec81e (of everything below the line)

---


## Why

CVE-2026-111497 is an out-of-bounds write in the **brotli decoder** that permits remote code execution. It is fixed in brotli 1.2.1 and brotlicffi 1.2.1.0 (both on PyPI since 2026-10-22, with wheels for every Python crossbar supports, so no C compiler is needed). Details and the upstream fix are in https://github.com/crossbario/autobahn-python/issues/2024.

crossbar gets brotli through `autobahn[all]` (the `compress` extra). On master `a579f270`, `uv.lock` pins the **vulnerable** versions:

```
brotli      1.2.0
brotlicffi  1.2.0.0
```

## Exposure

- **The router's WebSocket transports do not use brotli.** Listening WebSocket transports only ever accept `permessage-deflate` (`src/crossbar/router/protocol.py:94-123`), and outgoing WebSocket connections offer no compression (`perMessageCompressionOffers=None`, `protocol.py:171`). A WAMP client cannot make the router decode brotli.
- **Outgoing HTTP can.** urllib3 2.x (locked: 2.8.0), and so `requests`, asks for `Content-Encoding: br` and decodes the response when brotli is installed; aiohttp (in the lock via web3) does the same. A malicious or hijacked HTTP server that crossbar's `requests`/aiohttp users talk to (network/master/xbr code) reaches the vulnerable decoder. Which endpoints those are has not been traced yet.
- **Native WAMP components** running in container or guest workers can use autobahn's `PerMessageBrotli` themselves (opt-in), and run in crossbar's environment.

## Change

**Step 1 (now):**

- `uv lock --upgrade-package brotli --upgrade-package brotlicffi`, so the lock pins brotli 1.2.1 and brotlicffi 1.2.1.0, and nothing else changes.
- An entry in the 26.11.1 changelog naming the CVE.

pip installs already resolve to the fixed versions (they are the latest), but lock-based installs and existing environments do not.

**Step 2 (after the autobahn release with the new floors):**

- Raise `autobahn[all]>=26.10.2` to the autobahn release that carries https://github.com/crossbario/autobahn-python/issues/2024, and relock.

No direct brotli dependency in crossbar: the floor comes through autobahn.

## Testing (GREEN-RED-GREEN)

- **RED:** a test, next to `src/crossbar/test/test_dependencies.py`, that the installed `brotli` (CPython) or `brotlicffi` (PyPy) is at least 1.2.1 / 1.2.1.0. It fails on master with the current lock.
- **GREEN:** the relock, and the test passes on CPython and PyPy.

## Done when

- `uv.lock` pins brotli 1.2.1 and brotlicffi 1.2.1.0, and the lock diff changes nothing else.
- The new test passes on CPython 3.11–3.14 and PyPy 3.11, and CI is green.
- After the autobahn release: crossbar requires that autobahn release.

Note: This issue was drafted with AI assistance (Claude Code).

---

## Comments at freeze (0)

