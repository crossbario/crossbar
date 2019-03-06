:orphan:

Router Realms
=============

Crossbar.io uses *Realms* as domains for separation of routing and
administration.

Every WAMP session between Crossbar.io and a *Client* is always attached
to a specific *Realm*. Since the routing of calls and events is separate
for each realm, sessions attached to different realms won't "see" each
other.

For example, consider

-  Client 1 attached to ``realm1``
-  Client 2 attached to ``realm1``
-  Client 3 attached to ``realm2``

on the *same* Crossbar.io router, and both Client 2 and Client 3
subscribed to topic ``com.example.mytopic``, when Client 1 publishes an
event to ``com.example.mytopic``, only Client 2, which is attached to
the *same realm* as Client 1, will receive this event.

The realm for the session is selected as part of session establishment.

For example, when creating a new connection to a WAMP router using
`Autobahn\|JS <https://crossbar.io/autobahn/>`__, the realm the session (running
over the connection) should attach to is specified like this:

.. code:: javascript

    var connection = new autobahn.Connection({url: 'ws://127.0.0.1:9000/', realm: 'realm1'});

Configuring Realms on a Router
------------------------------

Realms are created on a *Router* as part of the *Router*
configuration\`:

.. code:: javascript

    {
       "version": 2,
       "controller": {
       },
       "workers": [
          {
             "type": "router",
             "options": {
                // any router options
             },
             "realms": [
                {
                   "name": "realm1",
                   "roles": [
                      {
                         "name": "anonymous",
                         "permissions": [
                            {
                               "uri": "*",
                               "allow": {
                                  "call": true,
                                  "register": true,
                                  "publish": true,
                                  "subscribe": true
                               }
                            }
                         ]
                      }
                   ]
                }
             ],
             "transports": [
                // transports run by this router
             ],
             "components": [
                // app components running side-by-side with this router
             ]
          }
       ]
    }

In the above example configuration, the *Router* starts up with a single
*Realm* (``realm1``).

Authorization is configured on a per-realm basis. Authorization is
role-based. Above, clients connecting as anonymous have full permissions
for all URIs. (This makes sense for starting out development of a WAMP
application.)

Realm Options
-------------

Crossbar.io allows to tune its routing core on a per-realm basis using
*realm options*.

For example, consider this part of a node configuration for a realm:

.. code:: javascript

    {
       // realm name
       "name": "realm1",

       "options": {
          // if true (default), enable WAMP meta API
          "enable_meta_api": true,

          // if true, bridge the WAMP meta API also to the node management side
          "bridge_meta_api": false,

          // dispatch this many events before reentering the event loop
          "event_dispatching_chunk_size": 100,

          // checking policy for URIs (can be "strict" or "loose")
          "uri_check": "strict"
       },

       "roles": [
          // role definitions ...
       ]
    }

The realm options change the default behavior of Crossbar.io for the
whole realm. Other realms in the same router worker are unaffected
though.

The options are provided at startup time of the realm within the router
worker, and are unchanged during the lifetime of that realm.

Changing an option requires to restart the respective realm. However,
the router worker within the realm is started, does not need to be
restarted itself. Restarting a realm is a quick and cheap operation.

*Read more:*

-   :doc:`Router Configuration <Router-Configuration>` 
-   :doc:`Authorization <Authorization>` 
