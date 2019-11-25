:orphan:

Session Statistics
==================

Crossbar.io WAMP routers are able to track usage on a per WAMP session basis.

When enabled, Crossbar.io will meter and track the number of WAMP messages
received and sent to the respective client that opened the WAMP session.

When a configurable number of (rated) messages was sent or received, or a
configurable duration of (wallclock) time has passed - whichever happens first -
this will trigger publishing a WAMP meta event to

* ``wamp.session.on_stats (session, stats)``

For example, for ``session``:

.. code:: javascript

    {'authid': 'QWKN-EVF9-STW3-UUJ6-67KF-9UG4',
    'authrole': 'anonymous',
    'realm': 'realm1',
    'session': 2732929752539294}

and for ``stats``:

.. code:: javascript

    {'bytes': 425,
    'cycle': 2,
    'duration': 2006344494,
    'first': False,
    'last': False,
    'messages': 10,
    'rated_messages': 10,
    'serializer': 'json',
    'timestamp': 1574688364518998111}


.. note::

    In addition to ``wamp.session.on_stats``, there are also WAMP meta events ``wamp.session.on_join``
    and ``wamp.session.on_leave`` which are (always) published by Crossbar.io
    whenever an application WAMP session joins or leave.


Example
-------

You can find a complete example `here <https://github.com/crossbario/crossbar-examples/tree/master/stats>`__.


Configuration
-------------

The following (partial) node configuration enables WAMP session statistics tracking on realm ``realm1``:

.. code:: javascript

    "realms": [
        {
            "name": "realm1",
            "roles": [
                {
                    "name": "anonymous",
                    "permissions": [
                        {
                            "uri": "",
                            "match": "prefix",
                            "allow": {
                                "call": true,
                                "register": true,
                                "publish": true,
                                "subscribe": true
                            },
                            "disclose": {
                                "caller": false,
                                "publisher": false
                            },
                            "cache": true
                        }
                    ]
                },
            ],
            "stats": {
                "rated_message_size": 256,
                "trigger_after_rated_messages": 10,
                "trigger_after_duration": 0,
                "trigger_on_join": true,
                "trigger_on_leave": true
            }
        }
    ]

The configuration options available in the session statistics section in a node configuration are:

+---------------------------------------+-----------------------------------------------------------------------------------------------------+
| parameter                             | description                                                                                         |
+=======================================+=====================================================================================================+
| ``rated_message_size|int``            | Size of a rated message, must be a power of two (default: ``512``)                                  |
+---------------------------------------+-----------------------------------------------------------------------------------------------------+
| ``trigger_after_rated_messages|int``  | Trigger statistics publication after this many rated messages or ``0`` to disable (default: ``0``). |
+---------------------------------------+-----------------------------------------------------------------------------------------------------+
| ``trigger_after_duration|int``        | Trigger statistics publication after this many seconds or ``0`` to disable (default: ``0``).        |
+---------------------------------------+-----------------------------------------------------------------------------------------------------+
| ``trigger_on_join|bool``              | Trigger statistics publication immediately when session joins (default: ``true``).                  |
+---------------------------------------+-----------------------------------------------------------------------------------------------------+
| ``trigger_on_leave|bool``             | Trigger statistics publication when session leaves (default: ``true``).                             |
+---------------------------------------+-----------------------------------------------------------------------------------------------------+


Monitoring statistics events
----------------------------

Example the demonstrates how to subscribe to and receive WAMP session meta events, including statistics:

* ``wamp.session.on_join``
* ``wamp.session.on_leave``
* ``wamp.session.on_stats``

Here is a complete client that can be run outside of Crossbar.io connecting to the router via WebSocket/TCP,
or can be hosted in a container worker started by Crossbar.io:

.. code:: python

    import six
    import argparse
    from pprint import pformat

    import txaio
    txaio.use_twisted()

    from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner


    class ClientSession(ApplicationSession):

        async def onJoin(self, details):
            print('('>>>>>> MONITOR session joined: {}'.format(details))

            def on_session_join(session_details):
                self.log.info('>>>>>> MONITOR : session joined\n{session_details}\n',
                              session_details=pformat(session_details))

            await self.subscribe(on_session_join, 'wamp.session.on_join')

            def on_session_stats(session_details, stats):
                self.log.info('>>>>>> MONITOR : session stats\n{session_details}\n{stats}\n',
                              session_details=pformat(session_details), stats=pformat(stats))

            await self.subscribe(on_session_stats, 'wamp.session.on_stats')

            def on_session_leave(session_id):
                self.log.info('>>>>>> MONITOR : session {session_id} left',
                              session_id=session_id)

            await self.subscribe(on_session_leave, 'wamp.session.on_leave')


    if __name__ == '__main__':

        parser = argparse.ArgumentParser()

        parser.add_argument('-d',
                            '--debug',
                            action='store_true',
                            help='Enable debug output.')

        parser.add_argument('--url',
                            dest='url',
                            type=six.text_type,
                            default="ws://localhost:8080/ws",
                            help='The router URL (default: "ws://localhost:8080/ws").')

        parser.add_argument('--realm',
                            dest='realm',
                            type=six.text_type,
                            default="realm1",
                            help='The realm to join (default: "realm1").')

        args = parser.parse_args()

        if args.debug:
            txaio.start_logging(level='debug')
        else:
            txaio.start_logging(level='info')

        runner = ApplicationRunner(url=args.url, realm=args.realm)
        runner.run(ClientSession, auto_reconnect=True)
