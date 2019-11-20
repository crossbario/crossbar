:tocdepth: 1

.. _changelog:

Changelog
=========

19.11.2
-------

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
