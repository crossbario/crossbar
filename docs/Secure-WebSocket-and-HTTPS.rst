:orphan:

Secure WebSocket and HTTPS
==========================

For production use, it is **strongly recommended** to always run
WebSocket over
`TLS <https://en.wikipedia.org/wiki/Transport_Layer_Security>`__
("secure WebSocket"). This is mainly for two reasons:

-  keeping your and your user's data confidential and untampered
-  avoiding issues with WebSocket on networks that employ so-called
   intermediaries (proxies, caches, firewalls)

    The latter is especially important in locked down enterprise
    environments and on mobile operator networks. By using secure
    WebSocket ("wss"), WebSocket will work in almost all circumstances
    (exceptions potentially being TLS interception / MITM proxies).

Crossbar.io has full support for running secure WebSocket and HTTPS. We
discuss configuration:

-  `WebSocket Transport
   Configuration <#websocket-transport-configuration>`__
-  `Endpoint TLS Configuration <#endpoint-tls-configuration>`__

To actually use TLS, you will need a **certificate** for your server.
This guide describes the three main options:

1. `Using self-signed certificates <#using-self-signed-certificates>`__
2. `Using certificates from commercial
   CAs <#using-commercial-certificates>`__
3. `Creating and using your own
   CA <#creating-your-own-certificate-authority>`__

We also **strongly recommend** to test your server using the `SSL Server
Test <https://www.ssllabs.com/ssltest/>`__ provided by Qualys SSL Labs.
This will point out weaknesses in your configuration or issues with your
certificate.

WebSocket Transport Configuration
---------------------------------

To configure a WebSocket transport for TLS, include a ``tls`` dictionary
with (mandatory) attributes ``key`` and ``certificate`` in your
transport configuration. Here is an example:

.. code:: javascript

    {
       "type": "websocket",
       "endpoint": {
          "type": "tcp",
          "port": 443,
          "tls": {
             "key": "server_key.pem",
             "certificate": "server_cert.pem"
          }
       },
       "url": "wss://example.com"
    }

The ``key`` must point to the server's private key file (PEM format, no
passphrase), and the ``certificate`` must point to the server's
certificate file (PEM format). The paths can be relative to the node
directory, or absolute.

To configure a Web transport for TLS, here is an example:

.. code:: javascript

    {
       "type": "web",
       "endpoint": {
          "type": "tcp",
          "port": 443,
          "tls": {
             "key": "server_key.pem",
             "certificate": "server_cert.pem"
          }
       },
       "paths": {
          "/": {
             "type": "static",
             "directory": ".."
          },
          "ws": {
             "type": "websocket",
             "url": "wss://example.com/ws"
          }
       }
    }

--------------

Endpoint TLS Configuration
--------------------------

The TLS configuration has a couple of options:

.. code:: javascript

    {
       "type": "websocket",
       "endpoint": {
          "type": "tcp",
          "port": 443,
          "tls": {
             "key": "server_key.pem",
             "certificate": "server_cert.pem",
             "ca_certificates": [
                "ca.cert.pem",
                "intermediate.cert.pem"
            ]
          }
       },
       "url": "wss://example.com"
    }

where \* ``key`` is the filesystem path to the server private key file
(PEM format, no passphrase) (**mandatory**) \* ``certificate`` is the
filesystem path to the server certificate file (PEM format)
(**mandatory**) \* ``ca_certificates`` when set requires that a
connecting client's certificate be issued by one of the listed CAs,
otherwise the connection establishment will be denied (**optional**)

TLS Version
~~~~~~~~~~~

Crossbar.io TLS listening endpoints accept **TLS 1.3 only**. Clients that
only speak TLS 1.2 or older cannot connect. There is no option to allow
older TLS versions.

TLS 1.3 uses only AEAD cipher suites with forward secrecy, and needs
neither a cipher list nor a Diffie-Hellman parameter file. Certificates
with RSA keys and with EC (ECDSA) keys both work.

``dhparam`` and ``ciphers`` were settings for TLS 1.2 and older. They are
still accepted in the configuration, so existing node configurations keep
working, but they have no effect: the node logs that it ignores them, and
does not read the ``dhparam`` file.

TLS Certificates
----------------

We provide help for creation and handling of TLS certificates on the
:doc:`TLS Certificates page <TLS-Certificates>`.

Examples
--------

-  `Sample
   configuration <https://github.com/crossbario/crossbar-examples/tree/master/encryption/tls>`__
-  `Python example for using TLS with
   Crossbar.io <https://github.com/crossbario/crossbar-examples/tree/master/wss/python>`__
-  `TLS Client Cert Authentication
   examples <https://github.com/crossbario/crossbar-examples/tree/master/authentication/tls>`__
-  `Crossbar.io demo instance production
   configuration <https://github.com/crossbario/crossbar-examples/blob/master/demos/_demo_launcher/.crossbar/config.json>`__
   - an example of recommended strongly secure settings

Resources
---------

-  `RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3
   <https://www.rfc-editor.org/rfc/rfc8446>`__
-  `The Most Common OpenSSL
   Commands <https://www.sslshopper.com/article-most-common-openssl-commands.html>`__
