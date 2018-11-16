:orphan:

WebSocket Transport
===================

Quick Links: **`WebSocket Options <WebSocket%20Options>`__** -
**`WebSocket Compression <WebSocket%20Compression>`__** - **`Cookie
Tracking <Cookie%20Tracking>`__** - **`Transport
Endpoints <Transport%20Endpoints>`__**

The **WebSocket Transport** is the default and most common way for
running WAMP. In particular, WAMP-over-WebSocket is the protocol used to
communicate with browsers that natively support WebSocket.

Crossbar.io supports all the favors of WAMP-over-WebSocket, including
different serialization formats (JSON and MsgPack) as well as
**listening transports**

-  `Listening WebSocket Transport
   Configuration <#listening-transports>`__
-  `Listening WebSocket Transport
   Example <#example---listening-transport>`__

as well as **connecting transports**

-  `Connecting WebSocket Transport
   Configuration <#connecting-transports>`__
-  `Connecting WebSocket Transport
   Example <#example---connecting-transport>`__

    The difference between the WebSocket Transport here, and the
    `WebSocket Service <WebSocket%20Service>`__, which is a feature of
    the `Web Transport <Web%20Transport%20and%20Services>`__ is that the
    transport here is **only** able to serve WAMP-over-WebSocket and
    nothing else, whereas the Web Transport allows to combine multiple
    Web services all running on one port.

Configuration
-------------

Crossbar.io supports both **listening** as well as **connecting**
WAMP-over-WebSocket transports.

Listening transports are used with `routers <Router%20Configuration>` to allow WAMP clients connect to Crossbar.io, whereas connecting
transports are used with `containers <Container%20Configuration>` to allow hosted components to connect to their upstream router.

Listening Transports
~~~~~~~~~~~~~~~~~~~~

Listening transports are used with `routers <Router%20Configuration>`__
to allow WAMP clients connect to Crossbar.io. The available parameters
for WebSocket listening transports are:


In addition to running a listening WAMP-over-WebSocket *Endpoint* on its
own port, an *Endpoint* can share a listening port with a *Web
Transport*. For more information on this, take a look at [[Web Transport
and Services]].

+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| parameter   | description                                                                                                                                            |
+=============+========================================================================================================================================================+
| id          | The (optional) transport ID - this must be unique within the router this transport runs in (default: "transportN" where N is numbered starting with 1) |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| type        | Type of transport - must be "websocket".                                                                                                               |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| endpoint    | A network connection for data transmission - see listening :doc:`Transport Endpoints<Transport-Endpoints>`  (required)                                 |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| url         | The WebSocket server URL to use (default: null)                                                                                                        |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| serializers | List of WAMP serializers to announce/speak, must be from "json" and "msgpack" (default: all available)                                                 |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| options     | Please see :doc:`WebSocket Options<WebSocket-Options>`                                                                                                 |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| debug       | Enable transport level debug output. (default: false)                                                                                                  |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| auth        | Authentication to be used for this Endpoint - see :doc:`Authentication<../../auth/Authentication>`.                                                    |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| cookie      | See see :doc:`Cookie Tracking<Cookie-Tracking>`                                                                                                        |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+

Connecting Transports
~~~~~~~~~~~~~~~~~~~~~

Connecting transports are used with
`containers <Container%20Configuration>`__ to allow hosted components to
connect to their upstream router. The available parameters for WebSocket
connecting transports are:

+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| parameter   | description                                                                                                                                            |
+=============+========================================================================================================================================================+
| id          | The (optional) transport ID - this must be unique within the router this transport runs in (default: "transportN" where N is numbered starting with 1) |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| type        | Type of transport - must be "websocket".                                                                                                               |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| endpoint    | A network connection for data transmission - see listening :doc:`Transport Endpoints<Transport-Endpoints>`  (required)                                 |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| url         | The WebSocket server URL to use (default: null)                                                                                                        |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| serializers | List of WAMP serializers to announce/speak, must be from "json" and "msgpack" (default: all available)                                                 |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| options     | Please see :doc:`WebSocket Options<WebSocket-Options>`                                                                                                 |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+
| debug       | Enable transport level debug output. (default: false)                                                                                                  |
+-------------+--------------------------------------------------------------------------------------------------------------------------------------------------------+


Example
-------

Example - Listening Transport
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To expose its WAMP routing services you can run an *Endpoint* that talks
WAMP-over-WebSocket. Here is an example (part of a Crossbar.io
configuration):

.. code:: javascript

    {
       "type": "websocket",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       }
    }


Example - Connecting Transport
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Write me.
