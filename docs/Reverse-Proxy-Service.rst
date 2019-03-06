:orphan:


Reverse Proxy Service
=====================

Configuration
-------------

To configure a Web Reverse Proxy Service, attach a dictionary element to
a path in your  :doc:`Web transport <Web-Transport-and-Services>` :

+--------+-------------------------------------------------------------------------+
| option | description                                                             |
+========+=========================================================================+
| type   | must be "reverseproxy"                                                  |
+--------+-------------------------------------------------------------------------+
| host   | the host of the web server to proxy, e.g. "www.example.com".            |
+--------+-------------------------------------------------------------------------+
| port   | the port of the web server to proxy (default: 80)                       |
+--------+-------------------------------------------------------------------------+
| path   | the base path to fetch data from with no trailing slashes (default: "") |
+--------+-------------------------------------------------------------------------+



Example
-------
Here is how you define a Web Transport that do reverse proxy to example.com/my_path:

.. code:: javascript

    {
    "type": "web",
    "endpoint": {
        "type": "tcp",
        "port": 80
    },
    "paths": {
        "/": {
            "type": "reverseproxy",
            "host": "example.com",
            "path": "/my_path"
        }
    }
    }

In this example, an incoming request POST /login would be proxied to domain example.com as POST /my_path/login
