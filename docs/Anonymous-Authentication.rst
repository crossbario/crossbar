:orphan:

Anonymous Authentication
========================

Anonymous Authentication allows you to explicitly define a role which is
assigned to clients which connect without credentials.

By default, Anonymous Authentication is not allowed; you must
exmplicitly enable it. Clients can explicitly ask for Anonymous
Authentication but note that they will also attempt Anonymous
Authentication if there is no authentication configuration at all.

The following is part of a config which allows Anonymous Authentication
for a WebSocket endpoint on a Web transport:

.. code:: javascript

    "transports": [
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
             "ws": {
                "type": "websocket",
                "auth": {
                   "anonymous": {
                      "type": "static",
                      "role": "public"
                   }
                }
             }
          }
       }

Any client using Anonymous Authentication on this endpoint is then
assigned the role ``public``.

The permissions for this role are configured just like for any other
role.

For a full working example of Anonymous Authentication using static
configuration, see
`Crossbarexamples <https://github.com/crossbario/crossbar-examples/tree/master/authentication/anonymous/static>`__.

Dynamic authentication
----------------------

Just as for other authentication methods, you can define a dynamic
authenticator component for Anonymous Authentication:

.. code:: javascript

    "auth": {
       "anonymous": {
          "type": "dynamic",
          "authenticator": "com.example.authenticate"
       }
    }

Here the authenticator function which is registered for
``com.example.authenticate`` is called for each attempted Anonymout
Authentication.

For a full working example of Anonymous Authentication using a dynamic
authenticator, see
`Crossbarexamples <https://github.com/crossbario/crossbar-examples/tree/master/authentication/anonymous/dynamic>`__.
For more on dynamic authenticators read :doc:`this documentation page <Dynamic-Authenticators>`
