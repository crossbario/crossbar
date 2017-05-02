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


## Authentication

Crossbar.io support a comprehensive set of authentication methods:

* WAMP-CRA challenge-response (`wamp-cra`)
* WAMP-Ticket (`wamp-ticket`)
* WAMP-Cryptosign (`wamp-cryptosign`)
* TLS client certificate (`tls`)
* HTTP cookie based (`cookie`)
* Anonymous (`anonymous`)

All of above authentication methods can be configured **statically** with credentials from the node configuration file, or **dynamically** with credentials provided by a user WAMP procdeure, as so-called *dynamic authenticator procedure*.

All authenticators can return `authextra` auxiliary information that is returned both to the authenticating client, as well as clients which get disclosed the identity of a calling/publishing peer, as well as in the meta API when querying a session.

See the [examples](https://github.com/crossbario/crossbar-examples/tree/master/authentication) for complete working code.

## Authorization

Crossbar.io fully support role-based authorization on a per-realm basis.

The outcome of successful authentication is a pair of "realm" and "role". It is this pair (realm, role) that determines the permissions on a specific URI for an authenticated client.

Authorization rules can be configured in Crossbar.io using two methods:

* static authorization
* dynamic authorization

With *static authorization*, the node configuration contains a `permissions` item with static permissions for roles on a realm.

With *dynamica authorization*, Crossbar.io will call into user provided authorizer procedures to determine the permissions of a client on the certain URI. For performance reasons, it will also (usually) cache the authorization result, so that authorization only incurs a slightly bigger overhead on first use for a role on an URI.


## Caller and Publisher Disclosure

Crossbar.io allows to expose information about callers and publishers to callees and subscibers.

This is called caller/publisher disclosure, and can be configured on a URI pattern basis.


## Publisher Exclusion and Subscriber Black-/Whitelisting

Crossbar.io supports Publisher exclusion, which is the default, but can be disabled on a per-publication basis.

Further, Crossbar.io supports subscriber black-/whitelisting based on WAMP session ID as well as WAMP `authid` and `authrole`.

