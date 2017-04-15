title: Features
toc: [Documentation, Features]

# Features

Crossbar.io implements all features from the [WAMP basic profile](), from the [WAMP advanced profile](), as well as Crossbar.io specific features.

## Transports

Crossbar.io is a multi-protocol router with native support for the following application level protocols:

* WAMP
* HTTP/REST
* MQTT

Crossbar.io has native protocol and cross-protocol bridging capabilities, and the multi-protocol support shields application developers from the complexities of different underlying network plumbing.

In addition, Crossbar.io also can serve as a Web server providing Web resources to HTTP(S) clients. Web resources can be configured into a resource tree mapping to URLs, with different Web resources to choose from:

* static Web resource
* CGI and WSGI Web resource
* reverse Web proxy resource
* redirect resource
* WebSocket-WAMP transport resource
* HTTP/Long-poll-WAMP transport resource
* node information resource


## WAMP Transports

Crossbar.io supports 72 WAMP transports in total: any combination of the 4 serializers, 3 message channels and 3 endpoints below, and each in **batched** and **unbatched** mode.

> In batched-mode, multiple WAMP messages may be combined in the payload of one message of the underlying message channels (eg a WebSocket message can carry multiple WAMP messages). This can increase message channel efficiency.

### Supported Serializers

* JSON (with transparent binary-base64 conversion)
* MessagePack
* CBOR
* UBJSON

### Supported Message Channels

* WebSocket
* RawSocket
* HTTP/Long-poll

with WebSocket supporting

* 100% spec compliance (tested with the industry standard Autobahn WebSocket Testsuite, also created by us)
* message compression (per-message deflate extension)

### Supported Endpoints

* TCP
* TLS
* Unix Domain Socket

with TLS supporting:

* latest TLS features
* A+ rating on SSLLabs
* secure-by-default configuration

## Web Transports

## MQTT Transports

## Universal Transports

## Remote Procedure Calls

## Publish and Subscribe
