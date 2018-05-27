title: Challenge Response Authentication
toc: [Documentation, Administration, Authentication, Challenge Response Authentication]

# Challenge-Response Authentication

## Introduction

Crossbar.io supports authenticating WAMP sessions using different mechanisms. One of those is WAMP-Challenge-Response-Authentication ([see the WAMP spec](http://wamp-proto.org/spec/)), or WAMP-CRA in short.

WAMP-CRA is a [challenge-response authentication](http://en.wikipedia.org/wiki/Challenge%E2%80%93response_authentication) mechanism using a secret shared between the client and server side:

* The secret never travels the wire, hence WAMP-CRA can be used via non-TLS connections. Also, WAMP-CRA is protected from replay attacks.
* WAMP-CRA also supports the use of [salted passwords](http://en.wikipedia.org/wiki/Salt_%28cryptography%29), using the [PBKDF2](http://en.wikipedia.org/wiki/PBKDF2) key derivation algorithm.
* The actual pre-sharing of the secret is outside the scope of the WAMP-CRA authentication mechanism.

Further, Crossbar.io allows two ways of providing the credentials needed for WAMP-CRA authentication:

1. Static Credentials
2. Dynamic Credentials

With *static credentials*, you configure users and secrets in the Crossbar.io node configuration. This comes in handy in many simple scenarios where nothing more than a bunch of static credentials are needed.

With *dynamic credentials*, you specify the URI of a regular WAMP procedure in the Crossbar.io node configuration. The procedure will then be called to actually retrieve the secret for a given user at authentication time. You can use this to hook into your application's user database.

## Authenticating Components

### JavaScript

Here is a WAMP component written in JavaScript/AutobahnJS that authenticates via WAMP-CRA (unsalted passwords).

```javascript
var user = "joe";
var key = "secret2";

// this callback is fired during WAMP-CRA authentication
//
function onchallenge (session, method, extra) {
   if (method === "wampcra") {
     return autobahn.auth_cra.sign(key, extra.challenge);
   }
}

var connection = new autobahn.Connection({
   url: 'ws://127.0.0.1:8080/ws',
   realm: 'realm1',

   // the following attributes must be set of WAMP-CRA authentication
   //
   authmethods: ["wampcra"],
   authid: user,
   onchallenge: onchallenge
});

connection.onopen = function (session, details) {
   ... details contains authid, authrole, ...
};

connection.open();
```

### Python Frontend

Here is a WAMP component written in Python/AutobahnPython that authenticates via WAMP-CRA (unsalted passwords).

```python
class MyFrontendComponent(wamp.ApplicationSession):

   def onConnect(self):
      self.join(u"realm1", [u"wampcra"], u"joe")

   def onChallenge(self, challenge):
      if challenge.method == u"wampcra":
         signature = auth.compute_wcs(u"secret2".encode('utf8'),
                                      challenge.extra['challenge'].encode('utf8'))
         return signature.decode('ascii')
      else:
         raise Exception("don't know how to handle authmethod {}".format(challenge.method))

   def onJoin(self, details):
      print("ok, session joined!")
```


## Static Credentials

With *static credentials*, you configure users and secrets in the Crossbar.io node configuration.

You can find a complete example [here](https://github.com/crossbario/crossbarexamples/tree/master/authentication/wampcra/static).

E.g. here is part of a Crossbar.io node configuration:

```json
{
   "workers": [
      {
         "type": "router",
         ...
         "transports": [
            {
               "type": "web",
               ...
               "paths": {
                  ...
                  "ws": {
                     "type": "websocket",
                     "auth": {
                        "wampcra": {
                           "type": "static",
                           "users": {
                              "joe": {
                                 "secret": "secret2",
                                 "role": "frontend"
                              },
                              "peter": {
                                 "secret": "prq7+YkJ1/KlW1X0YczMHw==",
                                 "role": "frontend",
                                 "salt": "salt123",
                                 "iterations": 100,
                                 "keylen": 16
                              }
                           }
                        }
                     }
                  }
               }
            }
         ]
      }
      ...
   ]
}
```

This node runs a Web transport. Part of the Web transport is a WebSocket path service running on path `ws`. We configure WAMP-CRA on this transport by adding an `auth` attribute, which must be a dictionary with one key per authentication method.

The `auth.wampcra` again needs to be a dictionary with one mandatory `type` attribute which can be

* `static`
* `dynamic`

When `wamp.wampcra.type == 'static'`, then the user credentials against which new incoming WAMP connection will get authenticated is provided within the configuration in a `users` dictionary, indexed by `authid`:

```json
"users": {
   "joe": {
      "secret": "secret2",
      "role": "frontend"
   },
   "peter": {
      "secret": "prq7+YkJ1/KlW1X0YczMHw==",
      "role": "frontend",
      "salt": "salt123",
      "iterations": 100,
      "keylen": 16
   }
}
```

Here we define two users: `joe` and `peter`. The mandatory attributes are:

* `secret`: The secret shared with the client.
* `role`: The `authrole` a successfully authenticated client with be assigned.

Optional attributes are all related to the (optional) pbkdf2-based password salting:

* `authid`: The authentication ID which will be assigned to the client
* `salt`: If the secret is salted (i.e. is not stored in cleartext), the salt used for computing the derived secret provided in `secret`.
* `iterations`: An integer parameter of the pbkdf2 algorithm.
* `keylen`: An integer parameter of the pbkdf2 algorithm.


## Dynamic Credentials

With *dynamic credentials*, you specify the URI of a regular WAMP procedure in the Crossbar.io node configuration. The procedure will then be called by Crossbar.io during authentication of (other) users.

You can find complete examples for different languages [here](https://github.com/crossbario/crossbarexamples/tree/master/authentication/wampcra/dynamic).

Here is part of a Crossbar.io node configuration:

```json
{
   "workers": [
      {
         "type": "router",
         ...
         "transports": [
            {
               "type": "web",
               ...
               "paths": {
                  ...
                  "ws": {
                     "type": "websocket",
                     "auth": {
                        "wampcra": {
                           "type": "dynamic",
                           "authenticator": "com.example.authenticate"
                        }
                     }
                  }
               }
            }
         ]
      }
      ...
   ]
}
```

Instead of a static list of user credentials, we now simply provide the URI `com.example.authenticate` of the procedure we want to be called to retrieve the credentials in attribute `auth.wampcra.authenticator`.

The procedure will be called with two arguments, the `realm` and the `authid` of the WAMP session that wants to authenticate via WAMP-CRA:

```python
def authenticate(realm, authid, details):
   ## return credentials (secret + role) for user 'authid'
   return {'secret': 'mypassword', 'role': 'sales'}
```

The arguments are:

* `realm`: The realm the client wishes to join
* `authid`: The authentication ID the client announced (e.g. username).
* `details`: Additional information on the WAMP client that wishes to authenticate (such as transport level data, e.g. IP address or HTTP headers)

The return value must be a dictionary with two mandatory attributes:

* `secret`: The secret shared with the client (possibly after salting)
* `role`: The `authrole` to assign to the client *if* successfully authenticated

The dictionary can have these optional attributes:

* `authid`: The authentication ID which will be assigned to the client
* `salt`: If `secret` was salted, the salt used (with pbkdf2)
* `iterations`: If `secret` was salted, the iterations during salting (a parameter of the pbkdf2 algorithm used).
* `keylen`: If `secret` was salted, the keylen of the derived key (a parameter of the pbkdf2 algorithm used).

To deny a user, just raise an exception in the procedure.

Here is a complete custom authenticator (this is implemented in Python, but you can write custom authenticators in any WAMP support language):

```python
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError



class MyAuthenticator(ApplicationSession):

   USERDB = {
      'joe': {
         'secret': 'secret2',
         'role': 'frontend'
      },
      'peter': {
         # autobahn.wamp.auth.derive_key(secret.encode('utf8'), salt.encode('utf8')).decode('ascii')
         'secret': 'prq7+YkJ1/KlW1X0YczMHw==',
         'role': 'frontend',
         'salt': 'salt123',
         'iterations': 100,
         'keylen': 16
      }
   }

   @inlineCallbacks
   def onJoin(self, details):

      def authenticate(realm, authid, details):
         print("authenticate called: realm = '{}', authid = '{}', details = '{}'".format(realm, authid, details))

         if authid in self.USERDB:
            return self.USERDB[authid]
         else:
            raise ApplicationError("com.example.no_such_user", "could not authenticate session - no such user {}".format(authid))

      try:
         yield self.register(authenticate, 'com.example.authenticate')
         print("custom WAMP-CRA authenticator registered")
      except Exception as e:
         print("could not register custom WAMP-CRA authenticator: {0}".format(e))
```

## Examples

* [Static Challenge-Response Authentication](https://github.com/crossbario/crossbarexamples/tree/master/authentication/wampcra/static)
* [Dynamic/Custom Challenge-Response Authentication](https://github.com/crossbario/crossbarexamples/tree/master/authentication/wampcra/dynamic)

For more on dynamic authenticators read [this documentation page](Dynamic Authenticators).

## Configuration

```json
{
    "auth": {
        "wampcra": {
            "type": "static",
            "users": {
                "foobar83": {
                    "secret": "Xy$h2l-D",
                    "role": "user"
                }
            }
        }
    }
}
```

### Static

parameter | description
---|---
**`type`** | `"static"`
**`users`** | A dictionary of names mapping to values being dictionaries as below.

Each user has this associated dictionary:

attribute | description
---|---
**`secret`** | Arbitrary text value used as shared secret (**required**).
**`role`** | Optional `authrole` a client using this ticket will be authenticated under.
**`salt` |
**`iterations` |
**`keylen` |


### Dynamic

parameter | description
---|---
**`type`** | `"dynamic"`
**`authenticator`** | URI of custom authenticator to call.
