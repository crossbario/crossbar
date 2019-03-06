:orphan:



Reverse WebSocket Proxy Service
===============================

Configuration
-------------

To configure a Reverse WebSocket Proxy Service, attach a dictionary element to a path in your :doc:`Web transport <Web-Transport-and-Services>` :

+-------------------+-----------------------------------------------------------------------------------+
| option            | description                                                                       |
+===================+===================================================================================+
| **``type``**      | must be ``"websocket-reverseproxy"``                                              |
+-------------------+-----------------------------------------------------------------------------------+
| **``url``**       | WebSocket server URL to announce (default: **``null``**)                          |
+-------------------+-----------------------------------------------------------------------------------+
| **``options``**   | please see `WebSocket Options <WebSocket%20Options>`__ for frontend connections   |
+-------------------+-----------------------------------------------------------------------------------+
| **``backend``**   | backend WebSocket connecting transport configuration                              |
+-------------------+-----------------------------------------------------------------------------------+

Example
-------

Here is Web transport that runs a reverse WebSocket proxy resource on
the path ``/proxy1``:

.. code:: javascript

    {
       "type": "web",
       "endpoint": {
          "type": "tcp",
          "port": 8080
       },
       "paths": {
          "/": {
             "type": "static",
             "directory": "../web"
          },
          "proxy1": {
             "type": "websocket-reverseproxy",
             "backend": {
                "type": "websocket",
                "endpoint": {
                   "type": "tcp",
                   "host": "127.0.0.1",
                   "port": 9000
                },
                "url": "ws://localhost:9000"
             }
          }
       }
    }
