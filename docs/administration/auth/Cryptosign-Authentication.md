[Documentation](.) > [Administration](Administration) > [Authentication](Authentication) > Cryptosign Authentication

# WAMP-Cryptosing Authentication

WAMP-Cryptosign is a WAMP-level authentication mechanism which uses Curve25519-based cryptography - Ed25519 private signing keys.

It allows authentication from both sides (client-router and router-client) to prevent MITM attacks.

Like TLS, it is a public-key authentication mechanism.

Unlike TLS, it does not rely on the broken CA infrastructure.

Additionally, the curve used was generated outside of the NIST standards process, so the likelihood of a nation-state backdoor is much lower. (The specification of this curve for use in TLS is currently underway.)

And, last but not least, high-quality and performant implementations of the curve are available with the [NaCl libraries](https://nacl.cr.yp.to/).


> Note: Cryptosign is currently only available when using Autobahn|Python as a client library.

> Note: Cryptosign is currently still under active development, so some features may be missing or not be stable yet.


We provide examples of using Cryptosign for [static configuration](https://github.com/crossbario/crossbarexamples/tree/master/authentication/cryptosign/static).
