[Documentation](.) > [Programming Guide](Programming Guide) > Crossbar.io Features > End-to-end Encryption

# End-to-end Encryption

**WARNING: This is an advanced (experimental) feature and this text is probably more oriented towards Crossbar.io hackers right now.**

> Crossbar.io **end-to-end application payload encryption** is available in versions 0.12.0 and above. This feature is currently EXPERIMENTAL. Do NOT use in production. Feedback welcome!

## Summary

With standard WAMP, and using best-practices, you'll be running everthing over TLS (such as via secure WebSocket). The bad guys won't be able to tap you. The application payload is secured from third parties.

The WAMP router itself, Crossbar.io, does have access to the application payload regardless of TLS though. On the plus side, it can do nice things like automatic conversion between serialization formats for clients, payload sanitization and payload validation for you. On the down side, the router is probably not operated by yourself, and you want to keep your privacy even then.

This is where WAMP application payload end-to-end encryption can help. Your application payload will be encrypted and decrypted on the WAMP clients only. The router only sees encrypted garbage. The private keys stay on the clients. Even if "forced to", a router operator cannot technically decrypt your application payload.


## Background

Whoa. So what exactly *is* end-to-end encryption? Well, here is what the Wired Hacker lexicon has to say about [end-to-end encryption](http://www.wired.com/2014/11/hacker-lexicon-end-to-end-encryption/):

> That "end-to-end" promise means that messages are encrypted in a way that allows only the unique recipient of a message to decrypt it, and not anyone in between.

Notably, the terminus suggest it's about "encrypting", and that there are two "ends" involved. And when there are ends, there is often stuff in between also. The evil guys of course, but there is more. Here is my attempt at defining "end-to-end encryption":

> **End-to-end encryption** is a mechanism that provides confidentiality, integrity and authenticity of the information exchanged between two communicating application ends versus **both** third-party adversaries **and** the operator of the infrastructure that enables the communication between the ends.

And Crossbar.io is "infrastructure" for WAMP applications. So anybody who runs a Crossbar.io router would classify as "operator" in above sense, and WAMP applications using the routing services provided by such a Crossbar.io router instance have to implicitly trust the router.

The **end-to-end application payload encryption** feature of Crossbar.io allows applications to reduce the level of trust required.

With payload encryption, the application payload of calls and events is encrypted and hidden from the router. Only the application components are able to read (or create) application payloads.

However, payload encryption is mutually exclusive with following other Crossbar.io features:

* app payload sanitization and validation
* multi-serialization format support

Further, payload encryption must be supported in WAMP client libraries too. Currently, only Autobahn|Python has support for application payload encryption.

---

### WAMP Transport Encryption

With WAMP, there are at least these kind of "ends" we can talk about:

1. clients and routers
2. caller and callees (and publishers and subscribers)

With the first one, a WAMP client (e.g. a Web UI running in the browser or an IoT component) establishes a WAMP transport to a WAMP router to hook up into a WAMP routing realm.

A WAMP transport is always point-to-point at the WAMP level: from the one client, to a specific router.

The WAMP transport might run over WebSocket, in which case it will be layered on TCP, and ultimately IP packets. These IP packets will be routed in hops between IP routers - and so there are (usually) multiple point-to-point (from IP router to IP router) sections on the way at the IP level from the WAMP client to the WAMP router. But the transport is still single-section, point-to-point when looking at a WAMP client talking to a WAMP router.

Finally, with Crossbar.io wide-area clustering, a WAMP event might indeed travel between WAMP routers (Crossbar.io), not only between WAMP clients and routers.

Now, Crossbar.io has first-class support for TLS, and WAMP transports like WebSocket, RawSocket or Long-poll can be transparently encrypted at the WAMP transport level using TLS.

> TLS is the TCP/IP standard protocol for encrypting stream-orientied transports at the transport level. TLS also provides authentication mechanisms for authenticating one or both ends of a transport.

Encrypting WAMP at the transport level should be considered not only "best-practice", but virtually a must for any serious production deployment. It will provide confidentiality, integrity and authenticity of the data transmitted between WAMP clients and Crossbar.io. Third parties and adversaries cannot intercept or manipulate the traffic.

**But** (yeah, there is a "but", otherwise this whole text would be pointless): the data transmitted via WAMP between two app components (a caller and a callee) can still be read and tampered with by the WAMP router *itself*.

Hey, why is that a problem?

Of course Crossbar.io does not fool with your data, is on the good guys side, we never write code with bugs, no one is going to break into your data-center and hack your Crossbar.io routers etc etc.

Yeah;) So why bother with this? Because there are scenarios where you can't afford even smallish chances of bad things happening, and you are willing to go an extra mile to achieve that.

Enter end-to-end WAMP payload encryption.


## WAMP Payload Encryption

Let's take an example. When a WAMP client publishes an event, a WAMP PUBLISH message will travel from the client to the router to ask the latter to distribute the event.

The PUBLISH message contains the topic URI being published to as well as the application payload that was attached (args and kwargs). The WAMP spec lists these formats for the PUBLISH message:

* `[PUBLISH, Request|id, Options|dict, Topic|uri]`
* `[PUBLISH, Request|id, Options|dict, Topic|uri, Arguments|list]`
* `[PUBLISH, Request|id, Options|dict, Topic|uri, Arguments|list, ArgumentsKw|dict]`

When a PUBLISH message was receive, the WAMP router will:

1. Parse and verify the PUBLISH message
2. Check application payload for valid serialization
3. Optionally authorize the action ("Is the client allowed publish to this topic?")
4. Optionally validate the payload ("Does the payload published match a defined schema associated with the URI?")
5. Create an EVENT message in all active serialization formats and reserializing application payloads cleaned form
6. Determine the list of subscriptions matching the topic and the (authorized) receivers of the event, possibly with black-/whitelisting of receivers
7. Send out EVENT message to list of clients
8. Optionally create and send an acknowledge to the publisher
9. Optionally store the event for event history

The core of the brokering is done in steps 6 and 7. In step 6, the topic being published to is central obviously. This topic URI cannot be hidden from the router without loosing the actual brokering or publish & subscribe messaging.

However, the application payload (Arguments, ArgumentsKw or `args` and `kwargs`) is only necessary for the steps 2, 4 and 5.

* In step 2, the application payload will be checked and sanitized at least at the serialization level. This protects clients from misbehaved client serialization libraries or using bugs in serialization libraries as an attack vector and allows to reserialize everything in one clean variant.
* With step 4, the application payload is verified against a type schema that is loaded into the router for the app, so that the router can enforce **application payload typing**. Without schema validation or payload typing, WAMP is essentially open and dynamically typed.
* With step 5, the serialization in different formats is necessary to concurrently support clients using different serialization mechanisms at the same time. Without translating between formats, clients cannot use different serialization formats, but must pre-agree on a common one

So if we keep `args` and `kwargs` encrypted, and opaque to the router, we will **loose**:

* app payload sanitization
* app payload validation / typing
* multi-serialization format support

But we will **win**:

* app payload become invisible and untamperable to the router

> Note however, that a rogue router can still *deny service*, e.g. not forward an event on some specific topic, whereas the router is expected to forward the event. If it fowards the event, it might exclude certain receivers. End-to-end encryption protects the application payload from being disclosed or tampered with, not from being "lost" completely.


# cryptobox

WAMP Payload End-to-End Encryption (cryptobox) is based on **cryptobox**, a public-key authenticated encryption scheme.

An authenticated ciphertext is computed from the message, a nonce, the sender's private key, and the receiver's public key.

The receiver recovers the original message from the authenticated ciphertext together with the nonce, his private key, and the sender's public key.

* Ed25519-SHA512
* Salsa20-Poly1305

ed25519-sha512-salsa20-poly1305

payload_transparency
payload_encryption_cryptobox

http://ed25519.cr.yp.to/
http://cr.yp.to/highspeed/naclcrypto-20090310.pdf
http://cr.yp.to/highspeed/coolnacl-20120725.pdf
https://cryptojedi.org/papers/naclhw-20150616.pdf
