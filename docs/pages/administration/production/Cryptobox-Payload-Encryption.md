[Documentation](.) > [Administration](Administration) > [Going to Production](Going to Production) > Cryptobox Payload Encryption

# Cryptobox Payload Encryption

> Note: This feature is experimental at present. Feedback is highly welcome!

> Note: This feature presently only works with Autobahn|Python as a client library.

Crossbar.io is normally seen as trusted, and transport encryption provides security for data in transit.

In some situations, you may want to reduce the access the router has to the information users transmit, e.g. when you are using a hosted Crossbar.io instance and want to minimize information leakage to the hosting provider.

Cryptobox payload encryption allows this.

## Basics

Cryptobox uses curve25519-based asymetric key encryption.

Both the sender of a message and its recipient(s) have a key pair, which is set per-URI. The sender uses the recipient's public key to encrypt the message payload, and its own private key to sign it. This allows to separate the possibility to e.g. publish to a topic from being able to unencrpyt publishes to the topic.

> Note: Key distribution is presently outside of the scope of Cryptobox.

Crpytobox relies on **payload transparency**: The entire encrypted payload is transmitted as a new, additional argument in the WAMP message. 

## Disadvantages

This does not render client traffic fully opaque to the router. By necessity, the router needs to have routing information (registrations, subscriptions, URIs in the messages). Depending on the application, this may still represent an inacceptable amount of information leakage when using a third-party controlled Crossbar.io instance.

> Note: We are thinking of implementing URI scrambling, which would further avoid the information leakage from nice, human readable and systematically assigned URIs.

Since the payload is encrypted, the router can no longer access the content.

This presently prevents the use of different serializations between the sender of a message and Crossbar.io and Crossbar.io and the recipient(s).

It will further prevent payload validation (which is on the roadmap).

As is always the case, security and convenience are a trade off.

## Examples

There is an example in the [Crossbarexamples](https://github.com/crossbario/crossbarexamples/tree/master/encryption/cryptobox) which will track the progress on Cryptobox. Until we have a final version, this example will provide more up-to-date information than this documentation page.
