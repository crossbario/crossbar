title: SCRAM Authentication
toc: [Documentation, Administration, Authentication, SCRAM Authentication]

# SCRAM Authentication

WAMP-SCRAM is a WAMP-level authentication mechanism which uses SCRAM (Salted Challenge Response Authentication Mechanism). This is based on [RFC 5802](https://tools.ietf.org/html/rfc5802) which standardizes SCRAM.

**NOTE** this authentication method is still under specification and development; see [wamp-proto issue 135](https://github.com/wamp-proto/wamp-proto/issues/135).

SCRAM uses a slow "key derivation function" (KDF) to hash a secret known only to the client; Crossbar only ever sees secret data *derived* from this secret. This means that even if the entire credential database was stolen from the Crossbar server, an attacker still doesn't learn the actual client secret (that is, their password). SCRAM also includes a step where the client verifies the server.

The process of deriving and sharing the secret data with the server ("user registration") is not specified and that is currently up to application developers.

The draft WAMP specification includes [Argon2id](https://en.wikipedia.org/wiki/Argon2) and PBKDF2 as possible KDFs and uses SHA256 as the hash function (for operations that require hashing). We **do not yet support channel-binding**. We recommend using Argon2id.

We currently have Autobahn|Python implementated and have an example of its use [in the Autobahn|Python repository](https://github.com/crossbario/autobahn-python/blob/master/examples/twisted/wamp/component/frontend_scram.py).
