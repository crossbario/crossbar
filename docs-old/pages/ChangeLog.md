title: ChangeLog
toc: [Documentation, Programming Guide, ChangeLog]


Crossbar.io master (unreleased)
===============================

* bug: 1324 validate router IDs in config
* ...

Crossbar.io 18.3.1 (2018-03-05)
===============================

* new: manage web services at the resource level (fixes #1078)
* new: reverse WebSocket proxy (Web service)


Crossbar.io 17.11.1 (2017-11-03)
===============================

* fix: "crossbar check" command was broken
* new: refactor tracing code to enable trace_level==action
* new: forward node_id into worker


Crossbar.io 17.10.1 (2017-10-31)
===============================

* fix: edge-case of traced + batched messaging
* fix: stop retaining old authids and empty sets in router (memory leak!).
* new: 'crossbar keygen' command


Crossbar.io 17.9.2 (2017-09-24)
===============================

* fix: checking of onion-endpoint public ports + tests
* new: message tracing API
* new: router-realm options ("enable_meta_api", "bridge_meta_api")
* new: configurable container shutdown behavior ("shutdown-manual", "shutdown-on-last-worker-exit")


Crossbar 17.4.1 (2017-04-15)
=============================

* new: MQTT core protocol support in beta
* new: MQTT payload mapping modes (passthrough, native, dynamic)
* new: use WAMP payload transparency for MQTT
* new: Web resource type "nodeinfo"


Crossbar 17.3.1 (2017-03-31)
=============================

* new: subscriber black-/whitelisting based on authid/authrole
* fix: use version pinned dependencies
* fix: many doc fixes
* fix: improve session join/leave logging
* fix: rawsocket transport details now includes protocol/serializer in use
* fix: websocket transport details now includes websocket extensions in-use and full HTTP response lines
* fix: deprecated (outdated) app scaffolding templates other than default
* fix: include AutobahnJS built version in default app template
* fix: machine ID on OSX (#951)
* fix: increase worker spawning timeout (needed for PyPy on slowish ARMs)
* new: "nodeinfo" Web resource type ([example](https://github.com/crossbario/crossbar-examples/tree/master/nodeinfo))
* new: router option "event_dispatching_chunk_size" optimizing for large subscriber counts
* new: transport type "twisted" allowing to use any Twisted streaming transport (including Tor!) - THIS IS A DEVELOPER OPTION CURRENTLY!
* new: component type "function" allows "functional components"
* fix: multiple MQTT fixes (still alpha though!)
* new: allow automatic realm assigned by router (client provides no realm when joining)
* fix: various unicode/bytes issues (after Autobahn tightened up type checking)
* fix: router session closing with lost client transports (#956)
* new: hooks for Crossbar.io Fabric


Crossbar 17.2.1 (2017-02-25)
=============================

* fix: tighten up internal worker WAMP permissions on local node management router
* fix: CORS for static Web resources
* fix: some Py3 issues with WAMP-cryptosign
* fix: forward authid/authrole in session details for WAMP-cryptosign
* fix: remove old "CDC" code bits
* new: MQTT-to-WAMP bridging (alpha)
* new: WAMP event retention (alpha)
* new: WAMP session testaments (alpha)
* fix: authextra handling with cookie-based authentication (#895)
* fix: custom cookie name when using cookie tracking transports (#873)
* fix: loading of optimal (=kqueue) reactor on BSD/OSX
* fix: event history (#918)


Crossbar 16.10.1 (2016-11-08)
=============================

Bugfixes
--------

- Fix event history (#918)


Crossbar 16.10.0 (2016-11-07)
=============================

Features
--------

- add UBJSON support (#720)
- Universal transport: allows to run RawSocket, WebSocket and Web all
  on one listening endpoint (#732)
- add backwards-compatibility policy (#737)
- separate metadata from text in documentation (#772)
- removed exact version from ``Server:`` header and added
  ``show_server_version`` option (#778)
- use ``towncrier`` to write changelog/NEWS file (#780)
- Various documentation improvements (#789)

Bugfixes
--------

- Fix ReST caller error-logging (#604)
- use -m when invoking subprocesses (so *.pyc files alone still work)
  (#638)
- fix logging in WampLongPollResourceOpen (#702)
- Kernel version detection for sharedport improved (#710)
- if we have a PID file, but the PID is our own, don't exit (#717)
- Remove platform conditional dependencies (#719)
- announce ubjson "batched" mode + CLI support (#728)
- replace ``msgpack-python`` with ``u-msgpack`` and upgrade several
  other dependencies (#766)
- Serialization error with channel ID (#823)
- properly pass 'authextra' and 'authmethod' keys to all dynamic
  authenticators (#853)


Crossbar 0.14.0 (2016-05-26)
============================

Features
--------

- add UBJSON support (#720)
- add backwards-compatibility policy (#737)
- separate metadata from text in documentation (#772)
- removed exact version from ``Server:`` header and added
  ``show_server_version`` option (#778)
- use ``towncrier`` to write changelog/NEWS file (#780)
- Various documentation improvements (#789)

Bugfixes
--------

- Fix ReST caller error-logging (#604)
- use -m when invoking subprocesses (so *.pyc files alone still work)
  (#638)
- fix logging in WampLongPollResourceOpen (#702)
- Kernel version detection for sharedport improved (#710)
- if we have a PID file, but the PID is our own, don't exit (#717)
- Remove platform conditional dependencies (#719)
- announce ubjson "batched" mode + CLI support (#728)
- replace ``msgpack-python`` with ``u-msgpack`` and upgrade several
  other dependencies (#766)


Crossbar 0.13.2 (2016-05-26)
============================

Features
--------

- add UBJSON support (#720)
- add backwards-compatibility policy (#737)
- separate metadata from text in documentation (#772)
- removed exact version from ``Server:`` header and added
  ``show_server_version`` option (#778)
- use ``towncrier`` to write changelog/NEWS file (#780)
- Various documentation improvements (#789)

Bugfixes
--------

- Fix ReST caller error-logging (#604)
- use -m when invoking subprocesses (so *.pyc files alone still work)
  (#638)
- fix logging in WampLongPollResourceOpen (#702)
- Kernel version detection for sharedport improved (#710)
- if we have a PID file, but the PID is our own, don't exit (#717)
- Remove platform conditional dependencies (#719)
- announce ubjson "batched" mode + CLI support (#728)
- replace ``msgpack-python`` with ``u-msgpack`` and upgrade several
  other dependencies (#766)
