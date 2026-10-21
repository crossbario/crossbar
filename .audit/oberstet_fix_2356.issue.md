Issue:    crossbario/crossbar#2356
Title:    [FEATURE] Release Crossbar.io 26.10.1
URL:      https://github.com/crossbario/crossbar/issues/2356
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-10-21T11:05:27Z
Comments: 1
Frozen:   2026-10-21T12:25:58Z by `just new-branch`
SHA-256:  113a4de53a0657b83c318eb67df20ac040900190ce91dff07eaadc59374706c7 (of everything below the line)

---


Part of the coordinated 26.10.1 release train (autobahn -> zlmdb -> xbr -> crossbar).
LAST in the train. All prerequisites are met: autobahn 26.10.1, zlmdb 26.10.1 and
xbr 26.10.1 are on PyPI (txaio and cfxdb stay at 26.6.1), and every issue planned for
this release is merged.

## Why

Cut the 26.10.1 stable release (codename **"Poke The Bear"**). This issue anchors the
release-preparation changes (version, changelog, release notes) so they land as one
reviewed PR, like #2254 did for 26.7.1.

## What's in it (already on master)

From the "Unreleased" section of `docs/changelog.rst`:

- #2326: 26.10.1 release train dependency floors (autobahn, zlmdb, xbr >= 26.10.1,
  autobahn carries the fix for advisory GHSA-pjh6-c8mg-3x7m), 26.10 release key,
  codename "Poke The Bear"
- #2325 **⚠ behaviour change**: TLS listening endpoints accept TLS 1.3 only
- #2324 **⚠ behaviour change**: `max_connections` per listening port (default 50000)
- #2334: `twisted>=26.4.0` (TLS Web transports failed the handshake with Twisted 25.5.0
  and pyOpenSSL 26.2+)
- #2320 **⚠ downgrade**: new databases are created in LMDB 1.0 format, which
  Crossbar.io 26.7.1 and older cannot open; `crossbar version` reports both engines
- #2323, #2172, #2159: node key file created `0600`, legacy key files without an
  Ethereum key no longer crash the node
- #2321: MQTT bridge parses packets again (stdlib parser, no `bitstring`)
- #2290 **⚠ behaviour change**: two input checks that never ran now reject bad input
- #2291: `just verify-pypi`, urllib3 upper bound lifted (now urllib3 2.x)
- #2231: released packages carry their real build ID again
- #2288: shared WAMP contribution workflow

Not in the changelog: #2302, #2305, #2307, #2310, #2313, #2316 (rollout chores:
`aspects.toml`, license headers, `.cicd` bumps; no change to the shipped code).

## Steps

1. Branch `fix_<this issue>` off master.
2. `just prep-release`: `26.10.1.dev1` -> `26.10.1` in `pyproject.toml` and
   `src/crossbar/_version.py`, relocks `uv.lock`. Do not hand-edit.
3. `docs/changelog.rst`: rename the "Unreleased" heading to `26.10.1`, and add a line
   for this issue. Decide whether the rollout chores above get one "other:" line.
   **Correct the #2321 entry**: "the MQTT bridge parses packets again" reads as "MQTT
   works", but an MQTT client still cannot get a WAMP session. `RouterSession.onOpen()`
   asserts the transport type (`src/crossbar/router/session.py:472-475`, added in
   33f48c81 / #1991, 2022), and the MQTT bridge's `WampTransport`
   (`src/crossbar/bridge/mqtt/wamp.py:151`) is not one of the allowed types. Running the
   disabled `_test_basic_publish` (`bridge/mqtt/test/test_wamp.py`; all six tests there
   are disabled) fails with
   `AssertionError: unexpected router transport type <class 'crossbar.bridge.mqtt.wamp.WampTransport'>`.
   Either say so in the entry (pointing to #2048, which is probably the same breakage)
   or fix it before the release in its own issue.
4. `docs/releases.rst`: add a `26.10.1` entry (GitHub release, PyPI, docs links).
   `just draft-release 26.10.1` fails without it. The file also has no entries for
   26.6.1 and 26.7.1 (it starts at 25.12.1). Decide whether to backfill them.
5. Already done, check only: the release key
   `src/crossbar/common/keys/crossbar-26-10.pub` exists (the key file name comes from
   the version, and there is no fallback) and `_codename.py` has `(26, 10)`.
6. `just draft-release 26.10.1` passes.
7. PR -> CI green -> merge to master.
8. **Human**: tag `v26.10.1`, push the tag, approve the manual `pypi` gate.

## Verification

Before tagging: install in a clean venv from PyPI (autobahn, zlmdb, xbr 26.10.1, not
local checkouts), run `crossbar version` and the functional tests.

After publishing:

- `just verify-pypi 26.10.1`: every file on PyPI has a PEP 740 attestation from
  `github.com/crossbario/crossbar`.
- `pip install crossbar==26.10.1` in a clean venv (CPython and PyPy), then
  `crossbar version`: it shows "Poke The Bear", the LMDB engines, and a real build ID
  `[YYYYMMDD-<sha>]` (the first release with #2231; until now it showed
  `[19000101-0000000]`).
- GitHub release and the docs on Read the Docs.

## After the release

- `just bump-next 26.10.2.dev1` in crossbar, autobahn and zlmdb.
- Then the release-workflow hardening (wamp-cicd #56: SHA pins, job-level
  `id-token`, a post-release provenance check), which needs a real tag to exercise.

## Release notes

The GitHub release and the announcement should put the ⚠ items first:

- TLS 1.3 only on listening endpoints
- `max_connections`
- LMDB 1.0 format for new databases, and no downgrade to 26.7.1 or older
- the two input checks that now reject bad input

_This work is being completed with AI assistance (Claude Code)._

---

## Comments at freeze (1)

### @oberstet, 2026-10-21T11:05:27Z

Update: this release now also waits for autobahn 26.10.2.

- **New blocker:** autobahn 26.10.2 (crossbario/autobahn-python#2016) fixes WAMP over TLS (crossbario/autobahn-python#2014):
  - the TLS client certificate was never available on Twisted WebSocket and RawSocket connections, so authmethod `tls` was broken;
  - reading the certificate failed with pyOpenSSL 26.2.0 and later;
  - `tls-unique` channel binding was broken between Twisted and asyncio peers.

  Crossbar 26.10.1 has to require it. That change, the crossbar tests for `tls` auth and cryptosign channel binding, and three crossbar fixes go into #2360:
  - dynamic TLS authenticators written from the documented example (`client_cert`) deny every client, since the certificate is passed as `peer_cert`;
  - rlinks sign the wrong channel ID;
  - cryptosign silently drops a requested channel binding.
- **"What's in it":** the floors line (#2326) becomes `autobahn>=26.10.2`; zlmdb and xbr stay at `>=26.10.1`. Add #2048 (MQTT clients get a WAMP session again) and #2360.
- **Step 3:** the requested correction of the #2321 entry ("an MQTT client still cannot get a WAMP session") is done: #2048 fixed that and has its own changelog entry. Step 3 only needs the 26.10.1 heading, the line for this issue, and the "other:" line for the rollout chores.
- **Verification:** the clean-venv check before tagging installs autobahn 26.10.2 from PyPI.
- **Release notes, add to the ⚠ items:**
  - **`tls-unique` channel ID:** it now follows RFC 5929. Crossbar 26.10.1 and Twisted clients on autobahn 26.10.1 or older no longer agree on it over WebSocket, and neither do rlinks between crossbar 26.10.1 and older versions. Only connections using WAMP-cryptosign channel binding are affected; upgrade both sides.
  - **Cryptosign:** a client requesting channel binding on a transport without a TLS channel ID is denied instead of authenticated without binding (pending #2360).

_This work is being completed with AI assistance (Claude Code)._


