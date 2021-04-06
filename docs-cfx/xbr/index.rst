Data Pools
==========

XBR data pools are user defined pools of data that is end-to-end encrypted
with data encryption keys under user control only.

A XBR data pool is backed by an appliacation realm, and a key center component
running in the realm.

The key center component mediates the exchange of data encryption keys used in
application data encryption between participants of the WAMP action (caller/callee in
case of RPC or subscriber/publisher in case of PubSub).

The data encryption key is transmitted end-to-end encrypted between the participants
of the WAMP action, but the transfer is sealed and stored in the off-chain state channels
of participants in the pool. If a non-zero transaction price is involved, the key
exchange involves montery value transfers in two state channels (buyer and seller side).

Multilevel System Security

* Application session authentication and authorization
* Application payload end-to-end data encryption

Decentralized Middleware

* Nodes and Router-to-router links
* Application realms and data pools
* Key exchange components

Two-layer Architecture

* Ethereum 2.0
* State Channels

.. centered:: :download:`CrossbarFX System Layers </_static/crossbarfx-xbr-layers.pdf>`

.. toctree::
    :maxdepth: 2

    programming-guide
    api-reference
    admin-guide
    network-reference
    network-onboarding
