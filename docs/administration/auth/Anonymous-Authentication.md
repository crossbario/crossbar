[Documentation](.) > [Administration](Administration) > [Authentication](Authentication) > Anonymous Authentication

# Anonymous Authentication


Anonymous Authentication allows you to explicitly define a role which is assigned to clients which connect without credentials.

You need to explicitly allow Anonymous Authentication for a particular transport  - as a default this is not allowed. Clients may explicitly request Anonymous Authentication, but this is attempted absent any explicit defined authentication scheme as well.

The following is part of a config which allows Anonymous Authentication for a WebSocket endpoint on a Web transport:

```javascript
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
```

Any client using Anonymous Authentication on this endpoint is then assigned the role `public`.

The permissions for this role are configured just like for any other role.

For a full working example of Anonymous Authentication using static configuration, see [Crossbarexamples](https://github.com/crossbario/crossbarexamples/tree/master/authentication/anonymous/static).

## Dynamic authentication

Just as for other authentication methods, you can define a dynamic authenticator component for Anonymous Authentication:

```javascript
"auth": {
   "anonymous": {
      "type": "dynamic",
      "authenticator": "com.example.authenticate"
   }
}
```

Here the authenticator function which is registered for `com.example.authenticate` is called for each attempted Anonymout Authentication.

For a full working example of Anonymous Authentication using a dynamic authenticator, see [Crossbarexamples](https://github.com/crossbario/crossbarexamples/tree/master/authentication/anonymous/dynamic).

For more on dynamica authenticators read [this documentation page](Dynamic Authenticators).
