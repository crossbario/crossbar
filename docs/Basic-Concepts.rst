:orphan:

Basic Concepts
==============

In this section we explain the basics of the use of Crossbar.io: basic
WAMP concepts, the structure of a Crossbar.io node and the basics of
configuring it. This should give you the understanding required to
navigate the reference documentation to find out more about specifc
aspects.

**It is strongly recommended that you read this section in its entirety
before starting your use of Crossbar.io. Investing the time here will
make getting started a lot easier and save you time down the road!**

WAMP
----

Crossbar.io uses the open `Web Application Messaging Protocol
(WAMP) <https://wamp-proto.org>`__. It accepts connections from WAMP
clients and routes calls and events between them. As such it is the core
of a connectivity fabric for components in distributed applications /
between microservices.

WAMP client libraries are currently available for `12
languages </about/Supported-Languages>`__ (all open source).
Applications can be constructed from components written in any
combination of these languages.

Clients connect to Crossbar.io, and WAMP uses WebSocket as its default
transport. This means that components can be run anywhere where outgoing
HTTP connections are possible. This includes the browser and mobile
devices. There is no need for you to control the runtime environment
enough to be able to open and forward ports, and there are no NAT
problems!

Once a connection is established it is bi-directional, allowing the
router to push events and calls immediately.

WAMP has two communication patterns for connecting application
components:

-  Publish and Subscribe (PubSub)
-  routed Remote Procedure Calls (rRPC)

Publish & Subscribe
~~~~~~~~~~~~~~~~~~~

Publish & Subscribe (PubSub) allows the efficient distribution of
information across the components in a distributed application.

Components inform Crossbar.io of their interest in particular areas of
information (they subscribe to topics). When a component wants to inform
of an update to a topic, it only needs to send this to Crossbar.io (it
publishes). Crossbar.io then distributes the event to all subscribers.

PubSub is an established communication pattern. It decouples sender and
receiver (sender needs no knowledge of receivers) and scales well since
all communication is via the single connection to Crossbar.io.

Routed Remote Procedure Calls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

WAMP and Crossbar.io adapt the decoupling of PubSub to Remote Procedure
Calls.

With routed Remote Procedure Calls (rRPC), a component notifies the
router that it provides a procedure for remote calling by other
components (it registers the procedure). The procedure is identified by
a URI.

To call the procedure, a component issues a call to Crossbar.io using
the procedure URI. Crossbar.io then invokes the procedure on the client
which has registered it (the callee) and returns the result to the
caller. This means that the caller does not need to know the identity of
the callee or be able to establish a direct connection to it.

WAMP Roles
~~~~~~~~~~

At the WAMP level, all components are equal in their abilities: they can
subscribe, publish, register and call. This means that you can e.g. have
functionality in a browser which is called from a component running on
the server, and are generally free to distribute your application's
functionality where it best fits.

Realms
^^^^^^

A WAMP session between a client and a router is connected to a realm on
the side of the router. A realm is a routing context, i.e.
registrations, calls, subscriptions and publications only work within
the same realm. As an example, a publication to the topic
"com.example.topic1" sent by a publisher connected to a realm "realm1"
will be dispatched to all subscribers to said topic within this realm,
but not to any subscribers for the identical topic URI which are
connected to a "realm2".

Realms are primarily intended as a simple namespacing mechanism to
separate the traffic of different applications or different users.

Crossbar.io Node
----------------

A Crossbar.io node itself consists of components which communicate using
WAMP. (This recursiveness can lead to headaches when thinking about it,
but here we'll just cover the basics which are easy enough to
understand.)

At startup, a node controller and a node management router are started.
The node controller then reads the configuration file and executes it.

It will typically instantiate at least one application router worker and
may instantiate container workers which host application components.

The node management router is there for communication between the node
controller and the workers, e.g. for the command to start or shut down a
worker. Application components themselves connect to an application
router.

The configuration of the Crossbar.io node resides in a file and is read
once upon node startup. Changes to the configuration require a restart
of the node.

The node will expose the management API it uses to execute the
configuration to an upcoming management and monitoring service
(Crossbar.io DevOps Center), allowing full runtime configuration.

At the moment each application router stands on its own, but connecting
application routers for scale-out is upcoming.

Configuration
-------------

Crossbar.io is presently only configured via a static configuration file
which is read on node startup.

The basic structure is:

.. code:: js

    {
        "version": 2,
        "controller": {},
        "workers": [
          "-- configuration work is done here --"      
        ]
    }

The controller part is there for the connection to the upcoming
`Crossbar.io DevOps Center <https://crossbario.com>`__ and is irrelevant
for running a single Crossbar.io instance configured via the
configuration file.

You need to configure one or more workers which provide functionality to
you as a user.

There are two ways of classifying workers:

-  **functional**: router workers vs. component hosting workers
-  **technical**: native workers vs. guest workers

On the **functional level**, a router worker provides WAMP routing
functionality, while each component host contains one or more WAMP
components. The typical use case will be for a Crossbar.io node to
contain at least one (application) router worker.

On the **technical level** the distinction is about the implementing
technology used for a worker. Crossbar.io itself is written in Python
using the `Twisted framework <https://twistedmatrix.com/>`__. Workers
which use this technology can run in a special native worker container.
This is the case for router workers. When you implement WAMP components
using the same technology stack as Crossbar.io, you can run them as
native workers. Any WAMP component not written in Python and Twisted
needs to run in a guest worker.

Router Configuration
~~~~~~~~~~~~~~~~~~~~

The main part of configuration work will be for the router worker(s).
Here you configure realms and transports.

.. code:: js

    "workers": [
        {
            "type": "router",
            "realms": [
            ],
            "transports": [
            ]
        }
    ]

All routing is within **routing realms**, i.e. a client connection is to
a routing realm and events, and calls are only routed between clients
connected to the same realm.

**Transports** are how clients can connect with the node. The default
transport for WAMP is WebSocket, but there is also RawSocket and HTTP
long-poll. Other transports can be added. The basic requirements are
that the transport is reliable, bi-directional, ordered and message
based (and as HTTP long-poll shows, some of these can be added on top of
the actual transport layer).

Realms
^^^^^^

At least one realm needs to be configured on an application router
worker in order for WAMP components to be able to connect to it. You can
configure multiple realms, e.g. to separate several client applications
served by the same application router.

Authorization configuration is per realm.

Clients are authenticated for a role (this happens at the transport
level, see below). You can then configure which actions are allowed for
a particular role.

The system here is based on URIs, which are used for both subscription
topics and registrations. For each role, you can define what actions are
allowed for a particular URI. URIs can be matched exactly or
pattern-based, and each of the four actions (publish, subscribe,
register, call) can be allowed or forbidden separately. You can set a
custom authorizer component, which receives information about the
attempted action and allows for even more fine-grained authorization
management and integration with existing solutions.

A sample realm configuration is:

.. code:: js

    "realms": [
       {
          "name": "realm_1",
          "roles": [
             {
                "name": "role_1",
                "permissions": [
                   {
                      "uri": "com.myapp.myprocedure1",
                      "allow": {
                         "call": false,
                         "register": true,
                         "publish": false,
                         "subscribe": false
                      }
                   },
                   {
                      "uri": "com.myapp.*",
                      "allow": {
                         "call": false,
                         "register": false,
                         "publish": true,
                         "subscribe": true
                      }
                   }               
                ]
             }
          ]
       }
    ],

This defines a realm ``realm_1`` and a single role: ``role_1``. For this
role, two sets of permissions are defined: A client successfully
connected as ``role1`` can register a procedure under the URI
'com.myapp.myprocedure1'. For any URI starting with ``com.myapp.``
that client can publish and subscribe. All other actions are not
authorized.

Transports
^^^^^^^^^^

At least one transport needs to be configured on an application router worker
in order for WAMP components to be able to connect to it. You can
configure multiple transports, e.g. so that some clients can connect via
WebSockets and others via RawSocket, or using the same protocol but via
different ports.

The **transport configuration determines which authentication method**
to require from clients attempting to connect to the transport.
Crossbar.io offers several authentication methods, including via HTTP
cookie, ticket, a challenge-response mechanism or cryptographic
certificates.

The transport configuration can contain the full information for this,
e.g. a dictionary of users and the secrets they use for the
challenge-response. In this case the **authentication is handled fully
by Crossbar.io**.

It is also possible to define a **custom authenticator component** which
receives the full set of data about the authentication request from the
client and can return not just whether the client is authenticated, but
also set e.g. the client's role. Besides giving you more control, custom
authenticators allow you to integrate an existing authentication
solution into your WAMP application.

The **Web transport** is a special case among transports. It is first of
all there to determine the paths under which to serve Web content. You
can also configure paths which in turn contain a transport. This allows
you to e.g. serve a Web application's files and have that Web
application components connect on the same port (and have this be the
standard ``80`` or ``443``).

A sample transport configuration is:

.. code:: js

    "transports": [
        {
            "type": "websocket",
            "endpoint": {
                "type": "tcp",
                "port": 7000
            },
            "auth": {
                "ticket": {
                    "type": "static",
                    "principals": {
                        "joe": {
                            "ticket": "secret!!!",
                            "role": "role_1"
                        }
                    }
                }
            }
      }
    }
        },
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
                    "type": "websocket"
                }
            }
        }
    ]

This creates two transport:

-  A **WebSocket transport** which is listening on port ``7000``. To
   connect to this, a client is required to use Ticket authentication.
   The authentication is handled entirely by Crossbar.io, and works just
   for a single user (``joe``). This user is then authenticated for the
   role ``role_1``.
-  A **Web transport**, which is listening on port ``8080``. This does
   two things: for HTTP connections to the root path it serves the
   content of the ``web`` directory; for the path ``ws`` it accepts
   WebSocket connections where, absent an explicit authentication
   definition, clients will be connected for the default role ``anonymous``.

Installation
------------

We recommend getting started using Docker (see :doc:`Getting Started <../Getting-Started>`  ), but Crossbar.io runs across a wide 
range of devices, some of which we provide  :doc:`installation instructions <Installation>` for.
