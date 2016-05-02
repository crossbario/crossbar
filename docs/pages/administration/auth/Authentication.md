title: Authentication
toc: [Documentation, Administration, Authentication]

# Authentication

Authentication is about *identifying* WAMP clients to Crossbar.io. A WAMP session connected to a **realm** is authenticated under an **authid** and **authrole**.

The **authrole** is then used for the static *authorization* of actions (publish, subscribe, call, register) for the client. (Dynamic authorization may base the authorization on more factors.)

Crossbar.io provides a range of authentication methods.

1. [WAMP-Anonymous](Anonymous Authentication)
2. [WAMP-Ticket](Ticket Authentication)
3. [WAMP-CRA](Challenge-Response Authentication)
4. [WAMP-Cryptosign](Cryptosign Authentication)
5. [WAMP-Cookie](Cookie Authentication)
6. [WAMP-TLS](TLS Client Certificate Authentication)

These can be classed according to whether

* they use transport or session level mechanisms
* they are based on a shared secret or on public key cryptography

## Session vs Transport Level

**WAMP session level authentications** use WAMP messages at the WAMP session opening handshake, and can be used over any transport.

* [WAMP-Anonymous](Anonymous Authentication)
* [WAMP-Ticket](Ticket Authentication)
* [WAMP-CRA](Challenge-Response Authentication)
* [WAMP-Cryptosign](Cryptosign Authentication)

**WAMP transport level authentications** use the underlying transport for the WAMP session, and the result of the authentication is then passed on to the WAMP session level (i.e. the resulting `authid` and `authrole` are passed there).

* [WAMP-Cookie](Cookie Authentication)
* [WAMP-TLS](TLS Client Certificate Authentication)

## Shared Secret vs. Public Key

**Shared secret authentication** is based on the client and the router (or the authentication component) having access to a common secret.

* [WAMP-Ticket](Ticket Authentication)
* [WAMP-CRA](Challenge-Response Authentication)
* [WAMP-Cookie](Cookie Authentication)

**Public Key based authentication** relies on asymetric key pairs, i.e. the router (or authentication componenet) only has knowledge of the client's public key (and vice versa). This has the advantage that a compromised store of keys does not enable impersonation of the other participant(s).

* [WAMP-Cryptosign](Cryptosign Authentication)
* [WAMP-TLS](TLS Client Certificate Authentication)

## Static, Dynamic and Database Authentication

It is possible to configure an authentication methods

* **statically** - the credentials stored in the Crossbar.io configuration, or
* **dynamically** - an authorizer component is specified which is called and returns an authentication or denial ([read more](Dynamic Authenticators)).

The latter allows full flexibility, e.g. integration with external authorization mechanisms, storing larger sets of authentication data in a database of your choice.

We are planning the implementation of a storage mechanism for credentials within Crossbar.io. This will be a secure, transactional database which can be managed via the node management API and which spans all authentication methods.

## Authentication Per Transport

Authentication methods are set for a WAMP transport endpoint, and it is possible to define multiple methods per endpoint.

As an example, the following extract from a configuration file allows anonymous authentication (and assigns this a role `public`) as well as authentication via WAMP-CRA (and defines two roles here depending on the `authid` used during authentication):

```javascript
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
```