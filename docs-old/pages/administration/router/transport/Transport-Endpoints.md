title: Transport Endpoints
toc: [Documentation, Administration, Router Transports, Transport Endpoints]

# Transport Endpoints

Quick Links: **[WebSocket Transport](WebSocket Transport)** - **[RawSocket Transport](RawSocket Transport)** - **[Web Transport](Web Transport and Services)**

An Endpoint describes the network connection over which data is transmitted. Endpoints are used as part of Transport definitions. Crossbar.io currently implements three types of Endpoints: **TCP**, **TLS**, **Tor** and **Unix Domain Socket** which each come in two flavors: **listening endpoint** and **connecting endpoint**:

**Listening Endpoints**:

* [TCP Listening Endpoints](#tcp-listening-endpoints)
* [TLS Listening Endpoints](#tls-listening-endpoints)
* [Unix Domain Listening Endpoints](#unix-domain-listening-endpoints)
* [Universal Listening Endpoints(#universal-listening-endpoints)
* [Tor Onion Service Endpoints](#tor-onion-service-endpoints)

**Connecting Endpoints**:

* [TCP Connecting Endpoints](#tcp-connecting-endpoints)
* [TLS Connecting Endpoints](#tls-connecting-endpoints)
* [Unix Domain Connecting Endpoints](#unix-domain-connecting-endpoints)
* [Tor Client Endpoints](#tor-client-endpoints)

> Endpoints are used in different places for Crossbar.io configuration. E.g. a Router Transport will (usually) specify at least one listening Endpoint for clients to connect. A component Container must specify the Router to connect to, and hence will provide configuration for a connecting Endpoint.

## TCP Endpoints

TCP *Endpoints* come in two flavors: listening and connecting *Endpoints*.

A listening TCP *Endpoint* accepts incoming connections over TCP (or TLS) from clients. A connecting TCP *Endpoint* establishes a connection over TCP (or TLS) to a server.

### TCP Listening Endpoints

Here is an *Endpoint* that is listening on TCP port `8080` (on all network interfaces):

```json
{
   "endpoint": {
      "type": "tcp",
      "port": 8080
   }
}
```

TCP listening *Endpoints* can be configured using the following parameters:

Option | Description
-----|------
**`type`** | must be `"tcp"` (*required*)
**`port`** | the TCP port to listen on (*required*)
**`version`** | the IP protocol version to speak - either `4` or `6` (default: **4**)
**`interface`** | optional interface to listen on, e.g. `127.0.0.1` to only listen on IPv4 loopback or `::1` to only listen on IPv6 loopback.
**`backlog`** | optional accept queue depth of listening endpoints (default: **50**)
**`shared`** | flag which controls sharing the socket between multiple workers - this currently only works on Linux >= 3.9 (default: **false**)
**`tls`** | optional endpoint TLS configuration (see below)

---

### TLS Listening Endpoints

Here is a listening *Endpoint* that uses TLS (note there's "interface" instead of "host"):

```json
{
   "endpoint": {
      "type": "tcp",
      "interface": "127.0.0.1",
      "port": 443,
      "tls": {
         "key": "server.key",
         "certificate": "server.crt"
      }
   }
}
```

Option | Description
---|---
**`key`** |
**`certificate`** |
**`dhparam`** |
**`ciphers`** |

---

### TCP Connecting Endpoints

Here is an *Endpoint* that is connecting over TCP to `localhost` on port `8080`:

```json
{
   "endpoint": {
      "type": "tcp",
      "host": "localhost",
      "port": 8080
   }
}
```

TCP connecting *Endpoints* can be configured using the following parameters:

Option | Description
-----|------
**`type`** | must be `"tcp"` (*required*)
**`host`** | the host IP or hostname to connect to (*required*)
**`port`** | the TCP port to connect to (*required*)
**`version`** | the IP protocol version to speak - either `4` or `6` (default: **4**)
**`timeout`** | optional connection timeout in seconds (default: **10**)
**`tls`** | optional endpoint TLS configuration (**not yet implemented**)

---

### TLS Connecting Endpoints

Not yet implemented.

---

## Unix Domain Sockets

Unix domain socket *Endpoints* come in two flavors: listening and connecting *Endpoints*.

A listening Unix domain socket *Endpoint* accepts incoming connections over a Unix domain socket from clients. A connecting Unix domain socket *Endpoint* establishes a connection a Unix domain socket to a server.

### Unix Domain Listening Endpoints

Here is an *Endpoint* that is listening on Unix domain socket `/tmp/socket1`:

```json
{
   "endpoint": {
      "type": "unix",
      "path": "/tmp/socket1"
   }
}
```

Unix domain socket listening *Endpoints* can be configured using the following parameters:

Option | Description
-----|------
**`type`** | must be `"unix"` (*required*)
**`path`** | absolute or relative path (relative to node directory) of Unix domain socket (*required*)
**`backlog`** | optional accept queue depth of listening endpoints (default: **50**)

---

### Unix Domain Connecting Endpoints

Here is an *Endpoint* that is connecting over Unix domain socket `/tmp/socket1`:

```json
{
   "endpoint": {
      "type": "unix",
      "path": "/tmp/socket1"
   }
}
```

Unix domain socket *Endpoints* can be configured using the following parameters:

Option | Description
-----|------
**`type`** | must be `"unix"` (*required*)
**`path`** | absolute or relative path (relative to node directory) of Unix domain socket (*required*)
**`timeout`** | optional connection timeout in seconds (default: **10**)

---

### Universal Listening Endpoints

So-called "universal" endpoints use some simple tricks to allow a single socket to listen for WebSocket, "norlam" HTTP **OR** Raw socket requests. This examines the first byte of the request for the magic Raw Socket byte; if it doesn't find that, it reads enough HTTP headers to determine if it's a WebSocket request or not.

This allows you to have a single listening socket that responds to any of the requests. We also use this to serve up a "user-readable" page if someone points their Web browser at a WebSocket endpoint.

The configuration for these is a simple combination of all of the possible configurations inside a dict keyed by their name. It looks like this:

```json
    "type": "universal",
    "endpoint": {
        "type": "tcp",
        "port": 8080
    },
    "rawsocket": {
    },
    "websocket": {
    },
    "web": {
    }
```

The valid configuration inside each of `rawsocket`, `websocket`, or `web` keys correspond to the same items found in the respective "individual" configurations. We won't repeat that here. There is a good example [in the Autobahn Python repository](https://github.com/crossbario/autobahn-python/blob/master/examples/router/.crossbar/config.json#L93).


---

## Tor Services

The [Tor Project](https://torproject.org) runs an Internet overlay network that provides location anonymity. This can be used for "normal" client-type TCP connections as well as for servers to provide listening services on the network (known as "Onion services").

Onion services hide a service-provider's network location from clients. They also have additional benefits:

- self-certifying domain names (a hash of the private key controlling the service);
- outbound-only connections means:
    - no NAT traversal issues
    - can firewall off all incoming connections
- packets do not leave the Tor network (no "exit" node)
- end-to-end encryption without trusting Certificate Authorities (CAs).


### Tor Onion Service Endpoints

To create a Tor onion service, we need two things: a tor instance to talk to and a private key. You must arrange for Tor to be running and configure crossbar to connect to it -- a control connection is required to add an Onion service.  You must also provide a "private key file" location -- if it already contains a private key, the same service will be re-launched. Otherwise, a new one will be created (and the private key saved in the provided file).

Explaining how to run and configure Tor is beyond the scope of this documentation. The Tor Project provides instructions for [installing and running Tor from their repositories](https://www.torproject.org/download/download-unix.html.en). We recommend using Unix sockets with "cookie" authentication for the control connection (if your platform supports it); the default configuration on Debian for example will provide a Unix socket in `/var/run/tor/control`.

Here is an example *Endpoint* that keeps the private keys in a subdirectory of our current "crossbar directory" (in this case in `.crossbar/service_key`). You may also provide an absolute path (anywhere on the filesystem) if you prefer.


```json
    "endpoint": {
        "type": "onion",
        "port": 8080,
        "private_key_file": "service_key",
        "tor_control_endpoint": {
            "type": "unix",
            "path": "/var/run/tor/control"
        }
    }
```

When you start crossbar with the above configuration:

- a Tor "control protocol" connection is established
- assuming `.crossbar/service_key` doesn't exist, a new onion service is created
- a public descriptor is uploaded to the Tor network (can take more than 30s)
- the private key for the service is written to `.crossbar/service_key`
- a `127.0.0.1`-only listener on a random port will get traffic from Tor
- the Onion URI (something like `m6dazoly4sqnoqrm.onion`) will be logged

Any client services would then connect to `ws://m6dazoly4sqnoqrm.onion:8080/` (if this is a WebSocket endpoint). Anyone with the private key can create an onion service on this address so you **must keep the private key secret**. If you lose it, you will have to create a new one (and re-distribute the now different `.onion` address to clients) so keeping a backup is a good idea.


Summary of all the available options:

Option | Description
-----|------
**`type`** | must be `"onion"` (*required*)
**`port`** | integer port to advertise on the network (*required*)
**`private_key_file`** | an absolute or relative path to store private key data in (*required*)
**`tor_control_endpoint`** | how to establish a control connection to Tor (*required*)


### Tor Client Endpoints

A Tor client connection traverses the Tor network and then is sent to its ultimate destination via an "exit node" **unless** it is connecting to an Onion service, in which case there is no "exit node" (the traffic arrives encrypted at a Tor client in use by the service itself). This is described in more detail in the [Overview of Tor](https://www.torproject.org/about/overview.html.en) provided by Tor Project.

It is vital to note that if you're connecting to "normal" Internet services over Tor the exit node can see all your traffic so it is **critical to use end-to-end encryption** for these connections. That means TLS-only or Onion services only; a malicious exit node can see and modify traffic of unencrypted protocols (for example, plain HTTP).

See the "Onion services" section above for pointers on how to run a Tor service; you need one running. The only information Crossbar needs is the SOCKS5 port (by default, this is 9050). So to connect to the example service we used above, configuration such as the following is used:

```json
    "transport": {
        "type": "websocket",
        "endpoint": {
            "type": "tor",
            "host": "m6dazoly4sqnoqrm.onion",
            "port": 8080,
            "tor_socks_port": 9050
        },
        "url": "ws://m6dazoly4sqnoqrm.onion:8080/"
    }
```
