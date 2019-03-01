:orphan:

Authentication
==============

**Authentication** with Crossbar.io determines if a WAMP *Client* is
allowed to connect and which identity it is assigned, while
**authorization** determines which permissions a *Client* is granted for
specific actions based on its identity.

See also:

-  :doc:`Authorization <Authorization>`

Introduction
------------

Authentication is about *identifying* WAMP clients to Crossbar.io. A
WAMP session connected to a **realm** is authenticated under an
**authid** and **authrole**.

The **authrole** is then used for the static *authorization* of actions
(publish, subscribe, call, register) for the client. (Dynamic
authorization may base the authorization on more factors.)

Crossbar.io provides a range of authentication methods.

1. :doc:`WAMP-Anonymous <Anonymous-Authentication>`
2. :doc:`WAMP-Ticket <Ticket-Authentication>`
3. :doc:`WAMP-CRA <Challenge-Response-Authentication>`
4. :doc:`WAMP-Cryptosign <Cryptosign-Authentication>`
5. :doc:`WAMP-Cookie <Cookie-Authentication>`
6. :doc:`WAMP-TLS <TLS-Client-Certificate-Authentication>`
7. :doc:`WAMP-SCRAM <SCRAM-Authentication>` **experimental**

These can be classed according to whether:

-  they use transport or session level mechanisms
-  they are based on a shared secret or on public key cryptography

...and allow both static and dynamic authentication (i.e. credentials
stored in the Crossbar.io config or using an authentication component
which contains custom rules).

Session vs Transport Level
--------------------------

**WAMP session level authentications** use WAMP messages at the WAMP
session opening handshake, and can be used over any transport.

-  :doc:`WAMP-Anonymous <Anonymous-Authentication>`
-  :doc:`WAMP-Ticket <Ticket-Authentication>`
-  :doc:`WAMP-CRA <Challenge-Response-Authentication>`
-  :doc:`WAMP-Cryptosign <Cryptosign-Authentication>`
-  :doc:`WAMP-SCRAM <SCRAM-Authentication>` **experimental**

**WAMP transport level authentications** use the underlying transport
for the WAMP session, and the result of the authentication is then
passed on to the WAMP session level (i.e. the resulting ``authid`` and
``authrole`` are passed there).

-  :doc:`WAMP-Cookie <Cookie-Authentication>`
-  :doc:`WAMP-TLS <TLS-Client-Certificate-Authentication>`

Shared Secret vs. Public Key
----------------------------

**Shared secret authentication** is based on the client and the router
(or the authentication component) having access to a common secret.

-  :doc:`WAMP-Ticket <Ticket-Authentication>`
-  :doc:`WAMP-CRA <Challenge-Response-Authentication>`
-  :doc:`WAMP-Cookie <Cookie-Authentication>`
-  :doc:`WAMP-SCRAM <SCRAM-Authentication>` **experimental**

**Public Key based authentication** relies on asymetric key pairs, i.e.
the router (or authentication componenet) only has knowledge of the
client's public key (and vice versa). This has the advantage that a
compromised store of keys does not enable impersonation of the other
participant(s).

-  :doc:`WAMP-Cryptosign <Cryptosign-Authentication>`
-  :doc:`WAMP-TLS <TLS-Client-Certificate-Authentication>`

Static, Dynamic and Database Authentication
-------------------------------------------

It is possible to configure an authentication methods

-  **statically** - the credentials stored in the Crossbar.io
   configuration, or
-  **dynamically** - an authorizer component is specified which is
   called and returns an authentication or denial (:doc:`read
   more <Dynamic-Authenticators>`).

The latter allows full flexibility, e.g. integration with external
authorization mechanisms, storing larger sets of authentication data in
a database of your choice.

We are planning the implementation of a storage mechanism for
credentials within Crossbar.io. This will be a secure, transactional
database which can be managed via the node management API and which
spans all authentication methods.

Authentication Per Transport
----------------------------

Authentication methods are set for a WAMP transport endpoint, and it is
possible to define multiple methods per endpoint.

As an example, the following extract from a configuration file allows
anonymous authentication (and assigns this a role ``public``) as well as
authentication via WAMP-CRA (and defines two roles here depending on the
``authid`` used during authentication):

.. code:: javascript

    "auth": {
       "wampcra": {
          "type": "static",
          "users": {
             "joe": {
                "secret": "secret2",
                "role": "admin"
             },
             "peter": {
                "secret": "secret3",
                "role": "dataentry"
             }
          }
       },
       "anonymous": {
          "type": "static",
          "role": "public"
       }
    }
