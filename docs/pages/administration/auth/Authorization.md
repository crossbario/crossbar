title: Authorization
toc: [Documentation, Administration, Authorization]

# Authorization

This chapter is about WAMP **authorization** concepts and configuration with Crossbar.io.

See also:

 * [Authentication](Authentication)

## Introduction

**Authentication** with Crossbar.io determines if a WAMP *Client* is allowed to connect and which identity it is assigned, while **authorization** determines which permissions a *Client* is granted for specific actions based on its identity.

Authorization is URI-based and separate for the four main interactions

* call
* register
* publish
* subscribe

E.g. A client may be allowed to **call** procedure `com.example.proc1`, **subscribe** topic `com.example.topic1`, but not **publish** to this topic.

Crossbar.io provides two mechanisms for authorization:

1. [Static Authorization](#static-authorization)
2. [Dynamic Authorization](#dynamic-authorization)

*Static Authorization* is a simple, yet flexible permissions scheme which can be setup via the Crossbar.io configuration.

*Dynamic Authorization* enables the addition of custom authorization code which is called by Crossbar.io to determine client permissions.

The idea is to have the majority of scenarios covered using *Static Authorization* and to handle special requirements and scenarios using *Dynamic Authorization*.

> Note: WAMP uses URIs to identify topics and registrations, with some [specific rules regarding formatting](URI Format).


## Authorization Procedure

A *Client* connects to a *Router* establishing a WAMP session by joining a *Realm*. Based on the authentication data, the *Router* then determines a *Role* for the *Client*.

The set of *Permissions* a *Client* gets is then determined by the *Realm-Role* combination and possibly other information from the authenticated WAMP session.

For example, a client that joined realm `realm1` with role `role1` might have the following set of permissions:

1. Allow to **call** any procedure
2. Disallow to **register** procedures
3. Allow to **subscribe** to any topic
4. Allow to **publish** to any topic that starts with URI `com.example.frontend`

## Static Authorization

With *Static Authorization*, the permissions are set as part of the Crossbar.io configuration.

For the above example client, the relevant part of the configuration would be:

```javascript
"realms": [
   {
      "name": "realm1",
      "roles": [
         {
            "name": "role1",
            "permissions": [
               {
                  "uri": "*",
                  "allow": {
                     "call": true,
                     "register": false,
                     "subscribe": true,
                     "publish": false
                  }
               },
               {
                  "uri": "com.example.frontend.*",
                  "allow": {
                     "call": true,
                     "register": false,
                     "subscribe": true,
                     "publish": true
                  }                  
               }
            ]
         }
      ]
   }
]
```

Here, `realms[0].roles` defines a list of roles for realm `"realm1"`. The permissions of a client that joined realm `"realm1"` with role `"role1"` is then given in `realms[0].roles[0].permissions`, which is a list of permission rules.

Each permission rule, like

```javascript
{
   "uri": "*",
   "allow": {
      "call": true,
      "register": false,
      "subscribe": true,
      "publish": false
   }   
}
```

is a dictionary an attribute having the URI as a string value, and at least another attribute `allow`. This in turn contains a dictionary with 4 boolean attributes (one for each WAMP interaction).

The above rule, using the wildcard URI pattern `"*"` would apply to *any* URI.

> When a given concrete URI matches more than one rule, the rule with the longest matching URI (pattern) wins.

In the above example configuration, a publication to `com.example.fronted.action1` would thus be allowed, since the URI pattern of the second defined rule which matches the publication URI, and which allows publication, is longer than that of the first, which disallows publication.


## Dynamic Authorization

Besides *Static Authorization* using the URI-pattern based authorization scheme above, Crossbar.io also provides a mechanism to hook up arbitrary custom code which is dynamically called by Crossbar.io for authorization.

With *Dynamic Authorization* your application will provide a WAMP procedure (with a defined signature) that Crossbar.io will then call to determine the permissions of other clients.

The method must accept three arguments: `(session, uri, action)` and must return a `dict` with the following keys:

 - `allow` (required) a bool indicating if the action is allowed
 - `disclose` (optional, default `False`) a bool indicating if callee's session-id should be disclosed to callers
 - `cache` (optional, default `False`) a bool indicating if the router can cache this answer

As a shortcut and for backwards compatibility you can instead return a single `bool` which is the same as just specifying `allow` (that is, returning True is the same as returning `dict(allow=True)`.

The arguments to the call are:

 - `session`: a `dict` containing session details
 - `uri`: A string, the WAMP URI of the action being authorized
 - `action`: A string, one of `publish`, `subscribe`, `register`, or `call` indicating what is being authorized

For fully working examples, see [crossbarexample/authorization](https://github.com/crossbario/crossbar-examples/tree/master/authorization/dynamic.

E.g. consider the following Python function

```python
@wamp.register('com.example.authorize')
def custom_authorize(session, uri, action):
   ## your custom authorization logic to determine whether client
   ## session should be allowed to perform action on uri
   if ...
      ## allow action
      return True
   else:
      ## deny action
      return False
```

This function can be called from Crossbar.io to determine whether a client should be allowed the specified action on the given URI. Here, the return value of your authorizing function must be a boolean.

The `session` argument is a dictionary with details on the session that wishes to perform the action:

```python
{
   "realm": "realm1",
   "authprovider": None,
   "authid": "VA-TKRAaIT44meQKZ6n5y7wk",
   "authrole": "frontend",
   "authmethod": "anonymous",
   "session": 1849286409148650
}
```

You can then configure Crossbar.io to use this custom authorizing function:

```javascript
"realms": [
   {
      "name": "realm1",
      "roles": [
         {
            "name": "approver",
            "permissions": [
               {
                  "uri": "com.example.authorize",
                  "allow": {
                     "register": true
                  }
               }
            ]
         },
         {
            "name": "user",
            "authorizer": "com.example.authorize"
         }
      ]
   }
]
```

The above configuration defines two roles:

 * `"approver"`
 * `"user"`

The `"approver"` role is for the application component that contains the custom authorization function (`custom_authorize()`).

The `"user"` role is for application components that should be authorized using the custom authorization function. Hence, it does not define a `permissions` attribute, but an `authorize` attribute giving the URI of the custom authorization function to call.

## Example

Here is a Python based custom authorizer:

```python
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.wamp import ApplicationSession


class MyAuthorizer(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):
       print("MyAuthorizer.onJoin({})".format(details))
       try:
           yield self.register(self.authorize, 'com.example.auth')
           print("MyAuthorizer: authorizer registered")
       except Exception as e:
           print("MyAuthorizer: failed to register authorizer procedure ({})".format(e))

    def authorize(self, session, uri, action):
       print("MyAuthorizer.authorize({}, {}, {})".format(session, uri, action))
       return True
```

This is only there to illustrate the principle, since it does nothing but log the request and authorize it.

> Note: The example here returns just a boolean which indicates whether the action is allowed or not. Authorizers can configure additional aspects, e.g. whether a caller's or publisher's identity is disclosed to the callee or subscribers. In this case, a dictionary is returned, e.g. `{"allow": true, "disclose": false}`.

Above could be used in a node configuration like this:

```javascript

{
   "controller": {
   },
   "workers": [
      {
         "type": "router",
         "options": {
            "pythonpath": [".."]
         },
         "realms": [
            {
               "name": "realm1",
               "roles": [
                  {
                     "name": "backend",
                     "permissions": [
                        {
                           "uri": "com.example.*",
                           "allow": {
                              "publish": true,
                              "subscribe": true,
                              "call": true,
                              "register": true
                           }
                        }
                     ]
                  },
                  {
                     "name": "authorizer",
                     "permissions": [
                        {
                           "uri": "com.example.auth",
                           "allow": {
                              "register": true
                           }
                        }
                     ]
                  },
                  {
                     "name": "frontend",
                     "authorizer": "com.example.auth"
                  }
               ]
            }
         ],
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
                     "directory": "../hello/web"
                  },
                  "ws": {
                     "type": "websocket",
                     "auth": {
                        "anonymous": {
                           "role": "frontend"
                        }
                     }
                  }
               }
            }
         ],
         "components": [
            {
               "type": "class",
               "classname": "hello.auth.MyAuthorizer",
               "realm": "realm1",
               "role": "authorizer"
            },
            {
               "type": "class",
               "classname": "hello.hello.AppSession",
               "realm": "realm1",
               "role": "backend"
            }
         ]
      }
   ]
}
```
