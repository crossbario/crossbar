:tocdepth: 1

.. _changelog:

Changelog
=========

Unreleased
----------

* new: Adopt the contribution workflow shared by all WAMP projects: ``CONTRIBUTING.md``, the pull request template and ``.audit/README.md`` are deployed byte-identically from wamp-cicd (GitHub issue first, red → green tests, AI-assistance disclosure) and kept in sync by a CI drift check; project-specific notes moved to a new ``DEVELOPMENT.md``. ``.cicd`` and ``.ai`` are pinned to the same commits across the WAMP fleet, and the shared workflow recipes (``just where``, ``new-branch``, ``publish``, ``land``) are imported; the release meta-recipe ``publish`` is renamed ``publish-release`` (#2288)

26.7.1
------

* new: release codename for the **26.7 series — "Shields Up"** — this release raises the router's shields against oversized and decompression-bomb payloads (`#2254 <https://github.com/crossbario/crossbar/issues/2254>`_)
* new: coordinated WAMP **26.7.1 release train** — pin ``autobahn>=26.7.1`` for the WebSocket permessage-deflate decompression-bomb fix (advisory ``GHSA-hxp9-w8x3-p566``) and relock ``uv.lock`` to the coordinated set (autobahn 26.7.1, zlmdb 26.7.1); ``cfxdb`` and ``txaio`` remain at 26.6.1 (`#2250 <https://github.com/crossbario/crossbar/issues/2250>`_)
* **⚠ behaviour change** — ``max_message_size`` now **defaults to 16 MB** (``2**24``) on **both** the WebSocket and RawSocket transports (secure by default). Previously the WebSocket default was ``0`` (unlimited) while RawSocket already defaulted to 16 MB, so a WebSocket transport that did not set the option accepted messages of any size — leaving the router unbounded by default and the ``GHSA-hxp9-w8x3-p566`` protection effectively opt-in. Messages larger than 16 MB on a WebSocket transport with no explicit ``max_message_size`` are now rejected (close code 1009, ``MESSAGE_TOO_BIG``). Set ``max_message_size`` explicitly if you need more — ``0`` allows any size, and WebSocket permits up to 64 MB (RawSocket cannot exceed 16 MB by protocol) (`#2251 <https://github.com/crossbario/crossbar/issues/2251>`_)
* fix: range-validate WebSocket ``max_frame_size`` (``[0, 64 MB]``, ``0`` = unlimited). It was type-checked only, so a negative value passed ``crossbar check`` and — because autobahn enforces frames with ``0 < maxFramePayloadSize < length`` — silently *disabled* the frame limit instead of tightening it (`#2253 <https://github.com/crossbario/crossbar/issues/2253>`_)
* fix: accept ``max_message_size: 0`` (= unlimited) on WebSocket transports, matching the documented "0 = allow any size"; the range validator previously rejected ``0`` (`#2254 <https://github.com/crossbario/crossbar/issues/2254>`_)
* fix: validate RawSocket ``max_message_size`` over its actual protocol range ``[512, 16 MB]`` with a dedicated validator. It previously reused the WebSocket-shaped ``[1, 64 MB]`` check, so a RawSocket config with ``max_message_size`` below 512 or above 16 MB passed ``crossbar check`` but then raised ``AssertionError`` at transport start (autobahn's factory asserts the WAMP RawSocket handshake range ``2**(9+n)``, i.e. ``[512, 16 MB]``). Also corrects ``docs/RawSocket-Transport.rst``: the documented range (``1–64 MB``) and default (``128 kB``) were both wrong — the real default is 16 MB (`#2252 <https://github.com/crossbario/crossbar/issues/2252>`_)
* fix: validate WebSocket ``compression`` transport configuration. ``check_websocket_compression()`` was an empty stub yet wired into ``check_websocket_options()``, so unknown codecs, unknown or mis-typed deflate attributes and out-of-range ``request_max_window_bits`` / ``max_window_bits`` / ``memory_level`` were all silently accepted and only surfaced (if at all) as a run-time error deep inside the compression backend (`#2250 <https://github.com/crossbario/crossbar/issues/2250>`_)
* new: functional test asserting the router rejects a decompression ("zip") bomb — a payload tiny on the wire but inflating far past the transport's ``max_message_size`` — on its *uncompressed* reassembled size (close code 1009). Verified a genuine regression test: it fails against autobahn < 26.7.1 and passes against 26.7.1 (`#2250 <https://github.com/crossbario/crossbar/issues/2250>`_)
* docs: clarify the ``max_frame_size`` (on-the-wire, per-frame) versus ``max_message_size`` (reassembled and decompressed, per-message) semantics on the WebSocket and RawSocket transports, and document ``max_message_size`` as the decompression-bomb guard in the WebSocket Compression docs (`#2250 <https://github.com/crossbario/crossbar/issues/2250>`_)

26.6.1
------

* docs: document the test-driven Bug Fix Workflow and the PR AI-assistance disclosure (audit file) requirement in ``CONTRIBUTING.md``; refresh stale ``tox`` references to ``just`` (`#2152 <https://github.com/crossbario/crossbar/issues/2152>`_)
* fix: ``crossbar version`` now reports the LMDB version from the binding vendored in zlmdb (the line was blank on clean installs, which have no top-level ``lmdb``); LMDB is now shown nested under zLMDB (`#2156 <https://github.com/crossbario/crossbar/issues/2156>`_)
* new: ``crossbar version`` reports the vendored FlatBuffers version for both data-in-transit (autobahn) and data-at-rest (zlmdb), nested under their respective packages, so an admin can verify which version is active and that both agree (`#2156 <https://github.com/crossbario/crossbar/issues/2156>`_)
* new: per-release codenames (e.g. Crossbar.io 26.6.1 — "Resistance Is Futile"), shown in the ``crossbar version`` banner (`#2227 <https://github.com/crossbario/crossbar/issues/2227>`_)
* fix: filter the benign NumPy 1.x/2.x ABI notice printed by bjdata's C extension (autobahn's UBJSON backend) under NumPy 2.x, so it no longer pollutes ``crossbar`` CLI output (short-term shim until bjdata ships a NumPy 2.x build) (`#2227 <https://github.com/crossbario/crossbar/issues/2227>`_)
* fix: use an absolute path for the verified artifact download in ``release.yml`` so the development/production release jobs find ``dist/`` (`#2227 <https://github.com/crossbario/crossbar/issues/2227>`_)
* new: coordinated WAMP **26.6.x release train** — pin the coordinated dependency floor: ``autobahn>=26.6.2`` (cryptosign import fix), ``txaio>=26.6.1``, ``zlmdb>=26.6.1``, ``cfxdb>=26.6.1``, ``xbr>=26.6.1`` (`#2224 <https://github.com/crossbario/crossbar/issues/2224>`_)
* new: track the application ``uv.lock`` for reproducible builds (`#2224 <https://github.com/crossbario/crossbar/issues/2224>`_)
* new: Crossbar.io 26.6 release key (``crossbar-26-6.pub``)
* fix: CI/CD release publishes the exact artifacts built and verified in the ``main`` workflow (download-artifact-verified) instead of rebuilding, preserving the chain of custody (`#2224 <https://github.com/crossbario/crossbar/issues/2224>`_)
* fix: converge release Discussions posting on the shared ``release-post-comment.yml`` (category resolved by name) (`#2224 <https://github.com/crossbario/crossbar/issues/2224>`_)
* new: sync shared ``.ai`` and ``.cicd`` submodules to the group-wide canonical revisions (`#2224 <https://github.com/crossbario/crossbar/issues/2224>`_)
* fix: add missing ``@inlineCallbacks`` decorator on ``RouterWebServiceWebhook.create()`` (`#2164 <https://github.com/crossbario/crossbar/issues/2164>`_)
* fix: add missing ``@inlineCallbacks`` decorator on ``MarketMaker.revoke_offer()`` (`#2164 <https://github.com/crossbario/crossbar/issues/2164>`_)
* fix: replace deprecated ``pkg_resources`` with ``importlib.resources`` in test code (`#2167 <https://github.com/crossbario/crossbar/issues/2167>`_)
* new: add ``bump-dev`` justfile recipe for auto CalVer versioning (`#2166 <https://github.com/crossbario/crossbar/issues/2166>`_)
* fix: handle ``ty`` rule name differences across versions in ``check-typing`` recipe

25.12.1
-------

**Build Infrastructure Modernization (Phase 1.4)**

* new: Migrated to ``pyproject.toml`` with Hatchling build backend (removed ``setup.py``, ``setup.cfg``, ``MANIFEST.in``)
* new: Added ``uv.lock`` for reproducible dependency installations
* new: Added ``justfile`` with comprehensive task recipes (~80 recipes)
* new: Added ``.readthedocs.yaml`` for RTD v2 configuration
* new: Modernized GitHub Actions workflows (``main.yml``, ``release.yml``)
* new: Added integration tests running Autobahn examples against Crossbar.io
* new: Added smoke tests for CLI, init, and lifecycle commands
* new: Added ``docs/uvlock.rst`` documentation for uv.lock usage
* new: Expanded Python version matrix: CPython 3.11-3.14, PyPy 3.11
* new: Added ``py.typed`` marker for PEP 561 type checking support
* fix: Removed outdated workflow files (``deploy-docs.yml``, ``test-management.yml``)
* fix: Documentation restructured with Furo theme and sphinx-autoapi

21.11.1
-------

* fix: subscription forwarding (#1915)
* fix: RLink fixes (#1913)
* fix: make standalone the default personality (#1900)
* new: implement dynamic node key (#1906)
* fix: Python 3.10 compatibility issues (#1897)
* fix: add systemd-notify support to docs (#1883)
* fix: assign authid to router components to work with rlinks (#1893)
* fix: install from source (#1884)
* new: depend on Autobahn v21.11.1
* new: expand WAP web service (#1878)
* fix: various adjustments and fixes after integration of FX code base
* new: open-source code for "Crossbar.io" (~26k LOC), incl. router-to-router links
* new: changed license from AGPLv3 to [EUPLv1.2](https://eupl.eu/1.2/en) (under IP ownership of typedef int GmbH)

21.3.1
------

* fix: depend on hotfix in Autobahn for Twisted v21.2.0 (see: https://github.com/crossbario/autobahn-python/issues/1470)

21.2.1
------

* new: minimum supported Python version now is 3.7
* new: output more version infos on "crossbar(fx) version"
* fix: pin to pip v19.3.1 because of "new resolver" and confluent dependencies with conflicts
* fix: do _not_ use wsaccel on PyPy (the JIT is faster)
* fix: Docker image baking scripts and CI automation for PyPy 3

21.1.1
------

* new: callback user component function "check_config" on container/router components
* fix: support Docker images for ARM (32 bit and 64 bit)
* fix: bake Docker multi-arch images
* fix: PyPy3 CI
* new: enable autobahn client unit tests

20.12.3
-------

* fix: update and migrate CI/CD pipeline to GitHub issues
* fix: depend on Autobahn v20.12.3 - this fixes a potential security issue when enabling the Web status page (`enable_webstatus`) on WebSocket-WAMP listening transports-

20.12.2
-------

* fix: depend on Autobahn v20.12.2
* fix: CI/CD - disable MacOS CI, update Docker imaging scripts

20.12.1
-------

* new: bump dependencies
* new: CI use newer ubuntu and newer pypy
* fix: copy license file to root folder (#1825)
* fix: check for io_counters feature - macos (#1826)
* new: proxy improvements (maintain and RR multiple backend connections)
* new: function-based custom authenticators (for more authmethods)
* fix: proxy/rlink management API

20.8.1
------

* fix: "crossbar stop" subcommand crashes on Windows (#1802)
* new: use core20 for snap runtime (#1798)
* new: include node authid in generated node key file
* new: web+router+proxy worker mgmt api polish + docs
* new: refactor/cleanup IRealmContainer
* fix: management API of proxy workers
* fix: improve and polish log output of nodes

20.7.1
------

* new: various fixes and improvements to rlinks
* new: proxy worker management API
* fix: turn down log noise

20.6.2
------

* fix: management procedure "get_router_realm_links" return value not serializable (#1781)
* fix: we always have publisher/caller information (#1778)
* fix: attribute name (removed underscore)
* fix: webservice of type "path"

20.6.1
------

* new: bump CI to py 3.8
* fix: rlink fixups (#1777)
* fix: node shutdown option processing
* new: Configurable cookie headers  #issue-1511 (#1753)
* fix: fix backend closing behavior for proxy worker (#1754)
* new: proxy class authenticator 2 (#1764)
* new: add mgmt api to lookup realms by name in router workers
* fix: varies proxy worker fixes and cleanups
* fix: backend closing behavior for proxy worker

20.4.2
------

* new: proxy worker backends support wamp-cryptosign backend authentication using node key
* new: proxy workers fully support all authentication methods for frontend session
* fix: rectify proxy worker glitches and refactor proxy worker code

20.4.1
------

* new: support forwarding of options.extra to native workers
* fix: error in wamp.session.list and wamp.session.count (#1721)
* fix: ticket #1725 log on disconnect; don't bother checking before close (#1726)
* fix: close not propagated properly from backend (for websocket and rawsocket) (#1723)
* fix: handle disconnected transport during stop notification (#1716)
* new: Support Fallback Resource from packages (#1711)

20.2.1
------

* new: allow running reverse web proxy service on root path ("/")
* new: set reverse web proxy HTTP forwarding headers
* new: extend WAP web service: allow loading Jinja templates from Python package,
    check service configuration, allow running service on root path
* new: first-cut dealer timeout/cancel implementation (#1694)
* new: expand reverse WAMP proxy worker docs
* fix: depend on autobahn (and xbr) v20.2.1 and refreeze all deps
* fix: improve logging for router transport starts
* fix: remove python 2 compatibility code / remove unicode strings (#1693)
* fix: ticket #1567 mocks (#1692)
* fix: use cpy3.7 docker base images (#1690)

20.1.2
------

* fix: use time_ns/perf_counter_ns shims from txaio and remove duplicate code here
* fix: CPython 3.8 on Windows (#1682)
* new: comprehensive node configuration example / doc page

20.1.1
------

* new: OSS proxy workers refactor (#1671)
* fix: handle websocket vs rawsocket proxy clients (#1663)
* fix: use python3.8 from ubuntu archives (#1659)
* fix: snap ensurepip failure (#1658)
* new: configurable stats tracking (#1665)
* new: WAMP session statistics via WAMP meta API events (``wamp.session.on_stats``)

19.11.1
-------

* new: authrole configuration for WAP web services
* new: revise/improve WAMP proxy workers
* new: snap improvements + use py3.8
* fix: add Web-Archive service docs
* fix: remove legacy python 2 imports

19.10.1
-------

* new: router-to-router links (aka "rlinks", aka "r2r links") - enables WAMP router clustering and HA
* new: WAMP proxy workers - enables WAMP clustering and HA
* new: WAP-webservice (WAP = WAMP Application Page)
* new: Archive-webservice

19.9.1
------

* new: #1607 component restart behaviors (#1623)
* fix: bump Twisted to v19.7.0 because of CVE-2019-12855

19.7.1
------

* fix: wait for onJoin to run in start_router_component (#1613)
* fix: worker disabling from env var (#1612)
* new: load node cryptosign key on all native workers
* new: `max_message_size` for both listening and connecting transports
* fix: improve reading config values from env vars
* new: worker option `disabled` to skip starting of worker
* new: router statistics tracking and management API (`get_router_realm_stats`)

19.6.2
------

* new: WAMP meta & CB mgmt API - close router sessions by authid/authrole
* fix: turn down log noise for detaching sessions already gone
* new: allow setting authid in anonymous auth; remove setting authid/authrole from client params on anonymous auth
* fix: system/host monitor typo in stats attribute
* fix: REST bridge (#1597)
* fix: WAMP meta API guard session attribute access (#1594)
