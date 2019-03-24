:orphan:

Cryptosign Authentication
=========================

WAMP-Cryptosign is a WAMP-level authentication mechanism which uses
Curve25519-based cryptography - Ed25519 private signing keys.

It allows authentication from both sides (client-router and
router-client) to prevent MITM attacks.

Like TLS, it is a public-key authentication mechanism.

Unlike TLS, it does not rely on the broken CA infrastructure.

Additionally, the curve used was generated outside of the NIST standards
process, so the likelihood of a nation-state backdoor is much lower.
(The specification of this curve for use in TLS is currently underway.)

And, last but not least, high-quality and performant implementations of
the curve are available with the `NaCl
libraries <https://nacl.cr.yp.to/>`__.

    Note: Cryptosign is currently available when using Autobahn\|Python
    and Autobahn\|JS. Other WAMP client libraries may have implemented
    it, so check with the respective documentation.

    Note: Cryptosign is currently still under active development, so
    some features may be missing or not be stable yet.

We provide examples of using Cryptosign for `static
configuration <https://github.com/crossbario/crossbar-examples/tree/master/authentication/cryptosign/>`__.


Cryptosign Configuration
------------------------

Inside of a transport's `"auth"` key a dict contains options for
Cryptosign configuration. You must specify `"type"` as either
`"static"` or `"dynamic"`.

Using `"static"` configuration, you add a `"principals"` dict that
maps usernames to details:

+-----------------+-----------------------------------------------------------------------------------------------------------------------+
| Option          | Description                                                                                                           |
+=================+=======================================================================================================================+
| realm           | the realm to assign this user (required)                                                                              |
+-----------------+-----------------------------------------------------------------------------------------------------------------------+
| role            | the role to assign this user (required)                                                                               |
+-----------------+-----------------------------------------------------------------------------------------------------------------------+
| authorized_keys | a list of strings of valid public-keys for this user (each key encoded in ASCII hex)                                  |
+-----------------+-----------------------------------------------------------------------------------------------------------------------+

Here is an example configuration using static credentials taken from `this fully-worked example <https://github.com/crossbario/crossbar-examples/tree/master/authentication/cryptosign/>`_::

    ...
    "auth": {
        "cryptosign": {
            "type": "static",
            "principals": {
               "client01@example.com": {
                  "realm": "devices",
                  "role": "device",
                  "authorized_keys": [
                     "545efb0a2192db8d43f118e9bf9aee081466e1ef36c708b96ee6f62dddad9122"
                  ]
               },
               "client02@example.com": {
                  "realm": "devices",
                  "role": "device",
                  "authorized_keys": [
                     "9c194391af3bf566fc11a619e8df200ba02efb35b91bdd98b424f20f4163875e",
                     "585df51991780ee8dce4766324058a04ecae429dffd786ee80839c9467468c28"
                  ]
               }
            }
        }
    }
    ...
