:tocdepth: 1

.. _changelog:

Changelog
=========

19.7.1
------

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
