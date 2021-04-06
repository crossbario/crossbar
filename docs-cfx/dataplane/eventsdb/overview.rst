Overview
========

Crossbar.io (OSS) implements transient WAMP message history from the WAMP advanced profile.

Using WAMP message history, WAMP clients can (when authorized) query the *past* event
history on topics, eg to catch up with any events they might have missed while
being offline.

Crossbar.io does not normally store PubSub events. To enable event history for a topic, you
need to configure an event store as part of the Crossbar.io config.

Let's assume you want to make events on topic ``com.example.oncounter`` for retrieval
via event history. Here is part of a Crossbar.io node confguration to enable an
*event store* of type ``memory``:

.. code-block:: json

    {
        "type": "router",
        "realms": [
            {
                "name": "realm1",
                "roles": [
                ],
                "store": {
                    "type": "memory",
                    "limit": 100,
                    "event-history": [
                        {
                            "uri": "com.example.oncounter",
                            "match": "exact",
                            "limit": 1000
                        }
                    ]
                }
            }
        ],
        "transports": [
        ]
    }

The above configures a store on the realm `realm1` which resides in memory, and which stores the
last 1000 events for the topic ``com.example.oncounter``.

The ``event-history`` configuration element takes a list of URI matching filters for the events
to be captured.


Configuration
-------------

To configure a persistent event store, use the store type ``cfxdb`` in the node configuration:

.. code-block:: json

    {
        "store": {
            "type": "cfxdb",
            "path": "../.testdb",
            "maxsize": 1073741824,
            "event-history": [
                {
                    "uri": "com.example.oncounter",
                    "match": "exact"
                }
            ]
        }
    }

.. note::

    Currently only a single event store can be configured. This will be extended to a list of
    even stores, which allows to have different configuration and paths (locations) for
    different sets of topics being persisted.

Here is a more extensive example configuration:

.. code-block:: json

    {
        "store": {
            "type": "cfxdb",
            "path": "../exampledb",
            "maxsize": 5242880,
            "maxbuffer": 100,
            "buffertime": 200,
            "readonly": false,
            "sync": true,
            "event-history": [
                {
                    "uri": "com.example.apps.",
                    "match": "prefix"
                },
                {
                    "uri": "com.example.demo.",
                    "match": "prefix"
                }
            ]
        }
    }

The configuration parameters for ``cfxdb`` stores currently are:

==============  ===========     ===========
Parameter       Type            Description
==============  ===========     ===========
``type``        string          Type of store, must be ``"cfxdb"``.
``path``        string          Path to database directory. If no database exists at the given path, create a new one.
``maxsize``     int             Maximum size the database may grow to in bytes. Default is 10MB.
``buffertime``  int             Time in ms to buffer events, storing the full set in one transaction.
``maxbuffer``   int             Maximum number of events to buffer until storing events in a DB transaction even (before a ``buffertime`` timeout).
``readonly``    bool            Open database read-only. No writing database operations are allow.
``sync``        bool            Synchronize (flush) to disk upon database commits. Disabling this is dangerous.
==============  ===========     ===========

The ``event-history`` is a list of event filters to match routed events against
and determine if to store the event:

* ``uri`` (string) - The WAMP topic URI or URI pattern
* ``match`` (string) - The URI matching mode: ``"exact"``, ``"prefix"``, ``"wildcard"``


Procedural Access
-----------------

Events persisted in a store for an application realm can be retrieved again
via the WAMP meta API procedures

* ``wamp.subscription.get_events(subscription_id, limit)``

and

* ``wamp.subscription.lookup(topic, options=None)``
* ``wamp.subscription.list(session_id=None)``
* ``wamp.subscription.get(subscription_id)``


**Calling to Get the Events**

Here is example code in JavaScriptThe actual call to retrieve events is

.. code-block:: javascript

    session.call('wamp.subscription.get_events', [subcriptionID, 20]).then(
        function (history) {
            console.log("got history for " + history.length + " events");
            for (var i = 0; i < history.length; ++i) {
                console.log(history[i].timestamp, history[i].publication, history[i].args[0]);
            }
        },
        function (err) {
            console.log("could not retrieve event history", err);
        }
    );

where the arguments are the subscription ID to retrieve events for and the number of past events to be retrieved.

The event history is returned as an array of event objects.

**Required Client Permissions**

To actually allow clients to use this feature, clients need to be authorized to publish, subscribe
and query. To be able to retrieve event history, a client needs to have two permissions:

* It must be allowed to call the retrieval procedure ('wamp.subscription.get_events').
* It must be allowed to subscribe to the subscription (as identified by the subscription ID

given in the call). This requirement is necessary to prevent clients for circumeventing the
subscription permissions by simply periodically retrieving events for a subscription.

Here is an example configuration:

.. code-block:: json

    {
        "name": "anonymous",
        "permissions": [
            {
                "uri": "com.example.oncounter",
                "match": "exact",
                "allow": {
                    "publish": true,
                    "subscribe": true
                },
                "disclose": {
                    "publisher": true
                },
                "cache": true
            },
            {
                "uri": "wamp.subscription.get_events",
                "match": "exact",
                "allow": {
                    "call": true
                },
                "disclose": {
                    "caller": true
                },
                "cache": true
            }
        ]
    }


.. note::

    For the time being, the only way to get that subscription ID locally is to actually subscribe
    to to the topic. (We are thinking about implementing a call to retrieve the subscription ID
    without subscribing, or an extra argument for the subscribe request to allow this.)


Database Access
---------------

The event store is storing data in LMDB database files, and those files when shared with
application components, containers or tools like Spark or Jupyter, can directly access
events stored in LMDB.

To access CFXDB from Python, we provide a convenient to use wrapper library on
PyPi `here <https://pypi.org/project/cfxdb/>`_.

CFXDB can be installed from the Python Package Index (PyPI):

.. code-block:: console

    pip install cfxdb

Using CFXDB is 3 steps. Open the event store database file providing the path
you configured in the CrossbarFX node configuration (see above):

.. code-block:: python

    import zlmdb

    DBFILE = '../../crossbar/.testdb'

    db = zlmdb.Database(DBFILE, maxsize=2**30, readonly=True)

Attach the database to the CrossbarFX database schema:

.. code-block:: python

    from cfxdb import Schema

    schema = Schema.attach(db)

Now you can run database transactions like this:

.. code-block:: python

    with db.begin() as txn:
        cnt = schema.events.count(txn)
        print('{} events currently stored'.format(cnt))

.. note::

    Above is using Python context managers to automatically manage transaction commit/rollback.
    In this case, the transaction is read-only, so there isn't anything stored, but even read-only
    transactions can fail and that has to be covered in the code.
