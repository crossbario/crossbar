:tocdepth: 1

.. _changelog:

Changelog
=========

master
------

* ...

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
