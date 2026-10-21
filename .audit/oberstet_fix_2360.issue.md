Issue:    crossbario/crossbar#2360
Title:    [BUG] TLS client certificate auth and cryptosign channel binding: autobahn 26.10.2 floor, tests, rlink and fail-open fixes
URL:      https://github.com/crossbario/crossbar/issues/2360
State:    OPEN at freeze
Author:   @oberstet
Updated:  2026-10-21T11:01:58Z
Comments: 0
Frozen:   2026-10-21T11:06:58Z by `just new-branch`
SHA-256:  5a9f8ed772e91c90c9df9b257139f5fc6f4251f71613587202d46e558c885468 (of everything below the line)

---


# TLS client certificate auth and cryptosign channel binding

## Why

autobahn 26.10.2 fixes WAMP over TLS (crossbario/autobahn-python#2014, release #2016):
- **Peer certificate, Twisted WebSocket and RawSocket:** it was always `None`, because it was read before the TLS handshake. That broke authmethod `tls` since 2022. With pyOpenSSL 26.2.0 and later, reading it raised as well.
- **`tls-unique` channel ID:** Twisted now computes it as RFC 5929 says, matching Python's `ssl` module (asyncio).
- **RawSocket client side:** its `tls-unique` channel ID was wrong.

Crossbar has to require autobahn 26.10.2 to get these fixes. Two gaps in crossbar itself let the breakage go unnoticed:
- No crossbar test covers WAMP authmethod `tls` (`src/crossbar/router/auth/tls.py`), over WebSocket or RawSocket. `test/functests/cbtests/test_cb_ssl.py` only tests server certificate verification.
- No crossbar test covers WAMP-cryptosign with `tls-unique` channel binding (`src/crossbar/router/auth/cryptosign.py`).

Reviewing crossbar's channel binding code also turned up two problems, described below.

## Problems

1. **Two MQTT TLS tests skipped.** `test_tls_auth` and `test_tls_auth_denied` in `src/crossbar/bridge/mqtt/test/test_wamp.py` are skipped with `_SKIP_TLS` (#2048), waiting for the autobahn fix.
   - Checked locally: crossbar master against autobahn master (26.10.2), with the skips removed.
   - Checked locally, the tests need two fixes:
     - **Wrong key:** the test's dynamic authenticator reads the certificate from `details["transport"]["client_cert"]`, but the transport details give it as `peer_cert`. So `test_tls_auth` hangs waiting for a CONNACK that never comes. `test_tls_auth_denied` passes, but for the wrong reason: "no client certificate presented", not "certificate denied".
     - **Test cleanup:** the test has to wait until the TLS client connection is closed, or trial reports an unclean reactor.

     With both fixes, all six tests in `test_wamp.py` pass on CPython 3.11 and PyPy 3.11.
2. **Dynamic TLS authenticators use the old key `client_cert`.** Crossbar passed the certificate to dynamic authenticators as `details["transport"]["client_cert"]` before the switch to `TransportDetails` in 2022 (crossbario/autobahn-python#1552); `TransportDetails.marshal()` gives it as `peer_cert`. The documented example still uses `client_cert` (crossbar-examples `authentication/tls/dynamic/authenticator.py:51-58`), so every authenticator written from it denies every client.
   - **To decide:** pass `client_cert` again as an alias of `peer_cert` in the details crossbar sends to dynamic authenticators (`src/crossbar/router/auth/pending.py:54`), or document `peer_cert` and fix the example.
3. **rlink signs the wrong channel ID (suspected, to be shown by a red test).**
   - The rlink client requests `"channel_binding": "tls-unique"` (`src/crossbar/worker/rlink.py:613`).
   - But `onChallenge` reads the channel ID from `self._router_controller._transport.transport_details` (`rlink.py:645`). That is the worker's connection to the node controller, not the rlink's connection to the remote router.
   - The expected effect: the rlink signs without a channel ID. Over a TLS rlink, the remote router has a channel ID, expects the signed message to include it, and denies the login. Over plain `ws://` neither side has a channel ID, and it works.
4. **Cryptosign drops a requested channel binding silently.** `PendingAuthCryptosign._compute_challenge` (`cryptosign.py:104-107`) does this when the router has no `tls-unique` channel ID, for example on a non-TLS transport:
   - it ignores the client's `channel_binding: "tls-unique"`;
   - it builds the challenge without binding;
   - the client's request for binding is not honoured, and nothing tells the client.

   Secure by default: deny with a clear message instead.

## Steps (red → green)

1. **Red:**
   - remove the two `_SKIP_TLS` skips, and fix the test's key (`peer_cert`) and its cleanup;
   - add a test for a dynamic TLS authenticator that reads `client_cert` (problem 2), if the alias is the decision;
   - add router tests for authmethod `tls` over WebSocket and RawSocket (accepted principal, unknown certificate, no certificate);
   - add tests for cryptosign with `tls-unique` channel binding (client and router agree on the channel ID, and a wrong channel ID is denied);
   - add a test for a cryptosign rlink over TLS (problem 3);
   - add a test that requesting `tls-unique` on a transport without a channel ID is denied (problem 4).

   These run against autobahn 26.10.1 from PyPI (the current floor), where the TLS tests fail.
2. **Green:**
   - require `autobahn>=26.10.2` and relock `uv.lock`;
   - pass `client_cert` as an alias of `peer_cert` to dynamic authenticators, or document `peer_cert` and fix the crossbar-examples authenticator;
   - make the rlink read the channel ID from its own transport;
   - make `PendingAuthCryptosign` deny instead of dropping the binding.
3. **Changelog:**
   - one entry per fix;
   - a ⚠ behaviour-change entry for problem 4;
   - a ⚠ compatibility entry for the `tls-unique` change: crossbar on autobahn 26.10.2 and Twisted clients on autobahn 26.10.1 or older no longer agree on the channel ID over WebSocket, and neither do rlinks between new and old crossbar versions. Only connections using channel binding are affected; upgrade both sides.
   - Also fix the #2048 changelog entry, which nests ``` ``tls`` ``` inside `**...**` (RST renders it literally).

## Blocks / blocked by

- Blocked by: autobahn 26.10.2 on PyPI (crossbario/autobahn-python#2016).
- Blocks: crossbar 26.10.1 (#2356).

_This work is being completed with AI assistance (Claude Code)._

---

## Comments at freeze (0)

