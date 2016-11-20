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
