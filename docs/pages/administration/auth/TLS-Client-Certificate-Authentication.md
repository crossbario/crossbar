[Documentation](.) > [Administration](Administration) > [Authentication](Authentication) > TLS Client Certificate Authentication

# TLS Client Certificate authentication

WAMP transports running over TLS can make use of TLS transport-level authentication.

This authentication takes place *after* the completion of the TLS handshake.

## Static

An example **static** configuration for this authentication is

```javascript
"auth": {
    "tls": {
        "type": "static",
        "principals": {
            "client_0": {
                "certificate-sha1": "B6:E5:E6:F2:2A:86:DB:3C:DC:9F:51:42:58:39:9B:14:92:5D:A1:EB",
                "role": "backend"
            }
        }
    }
}
```

Here, a client with the `authid` "client_0" needs to connect using TLS and using a certificate with the given fingerprint (`certificate-sha1`) in order to be able to authenticate. It is then assigned the `authrole` "backend".

We provide a [full working example](https://github.com/crossbario/crossbarexamples/tree/master/authentication/tls/static) for this.

## Dynamic

With dynamic authentication, the URI of an authenticator component is provided as part of the config, and this is then called on each authentication attempt.

```javascript
"auth": {
    "tls": {
        "type": "dynamic",
        "authenticator": "com.example.authenticate"
    }
}
```

We provide a [full working example](https://github.com/crossbario/crossbarexamples/tree/master/authentication/tls/dynamic) for this.

For more on dynamic authenticators read [this documentation page](Dynamic Authenticators).
