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
            ],
             "dhparam": "dhparam.pem",
             "ciphers": "ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+3DES:DH+3DES:RSA+AES:RSA+3DES:!ADH:!AECDH:!MD5:!DSS"
          }
       },
       "url": "wss://example.com"
    }

where \* ``key`` is the filesystem path to the server private key file
(PEM format, no passphrase) (**mandatory**) \* ``certificate`` is the
filesystem path to the server certificate file (PEM format)
(**mandatory**) \* ``ca_certificates`` when set requires that a
connecting client's certificate be issued by one of the listed CAs,
otherwise the connection establishment will be denied (**optional**) \*
``dhparam`` is the filesystem path to a Diffie-Hellman parameter file -
see explanation below (**optional**) \* ``ciphers`` is a list of ciphers
the server is willing to use with a client - see explanation below
(**optional**)

Diffie-Hellman
~~~~~~~~~~~~~~

To use
`Diffie-Hellman <https://en.wikipedia.org/wiki/Diffie%E2%80%93Hellman_key_exchange>`__
based key exchange, you need to generate a parameter file:

::

    openssl dhparam -2 4096 -out .crossbar/dhparam.pem

The use of Diffie-Hellman key exchange is desirable, since this provides
`Perfect Forward Secrecy
(PFS) <https://en.wikipedia.org/wiki/Forward_secrecy>`__. Without a DH
parameter file, no Diffie-Hellman based ciphers will be used, even if
configured to do so.

Elliptic Curve Ciphers
~~~~~~~~~~~~~~~~~~~~~~

Using elliptic curve based ciphers ("ECDH/ECDHE") is generally
considered desirable, since shorter keys than RSA support strong
encryption already consuming less CPU cycles.

Prerequisites for EC Support
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

EC crypto is fully supported by Crossbar.io, if the underlying OpenSSL
library supports EC **and** you have pyOpenSSL >= 0.15 running.

You can check like this:

::

    openssl ecparam -list_curves

Crossbar.io uses the ``prime256v1`` curve by default.

``prime256v1``\ (X9.62/SECG) is an elliptic curve over a 256 bit prime
field. This is elliptic curve "NIST P-256" from
`here <https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.186-4.pdf>`__.

This seems to be the most `widely used
curve <https://crypto.stackexchange.com/questions/11310/with-openssl-and-ecdhe-how-to-show-the-actual-curve-being-used>`__
and researchers
`think <https://twitter.com/hyperelliptic/status/394258454342148096>`__
it is "ok" (other than wrt timing attacks etc that might lurk inside
OpenSSL itself).

Ciphers
~~~~~~~

Crossbar.io will by default run a very strong and conservative set of
ciphers:

.. code:: text

    ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:DHE-RSA-AES128-SHA

Above configuration activates exactly 6 ciphers to be used, all of which
provide **Forward Secrecy**.

**Note that the default configuration does not support Windows XP!**. If
you must support XP, you will need to modify the ciphers configuration.

In general, you should only change the ``ciphers`` if you know what you
are doing.

The ``ciphers`` parameter must be in the format as used by OpenSSL, and
the OpenSSL library version installed on the system must support the
ciphers configured to make same actually available. If your OpenSSL
version installed does not support a configured cipher (e.g. ECDH
elliptic curve based), the ciphers not available will simply be skipped.

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

-  `OpenSSL man page <https://linux.die.net/man/1/dhparam>`__
-  `OpenSSL API
   documentation <https://linux.die.net/man/3/ssl_ctx_set_tmp_dh>`__
-  `The Most Common OpenSSL
   Commands <https://www.sslshopper.com/article-most-common-openssl-commands.html>`__
