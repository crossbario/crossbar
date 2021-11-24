:tocdepth: 1

.. _changelog:

Changelog
=========

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
* new: open-source code for "Crossbar.io FX" (~26k LOC), incl. router-to-router links
* new: changed license from AGPLv3 to [EUPLv1.2](https://eupl.eu/1.2/en) (under IP ownership of Crossbar.io Technologies GmbH)

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
