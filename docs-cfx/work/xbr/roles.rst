.. _xbr-roles:

XBR Roles
=========

Overview
--------

The goal of the XBR role model is to

- enable networks of digital value chains, where all stakeholders participate in the realized value
- map the main types of stakeholder business interests and capabilities in digital value chains to roles
- allow any party to become a stakeholder under any role (non-discriminatory)

We believe these features are essential for any truly decentralized, trustless open data markets platform.
For this, XBR defines the following five roles:

1. **XBR Consumer**: buys data services in XBR Markets from XBR Providers and data carriage from XBR Carriers.
2. **XBR Provider**: sells data services in XBR Markets to XBR Consumers, uses XBR Carrier for data carriage towards XBR Consumers.
3. **XBR Market**: defines market and data handling rules, operates real-time XBR token balances and acts as XBR token payment channel to the blockchain.
4. **XBR Carrier**: operates Crossbar.io Fabric nodes providing data carriage and routing for data services (paid by XBR Data Consumers).
5. **XBR Network**: the XBR project itself, creates and maintains the technology, sponsors the community and fosters XBR ecosystem interests.

.. note::

    A given entity or party may have multiple roles, e.g. being a *XBR Provider* in a first *XBR Market*, while at the same time being a *XBR Consumer* in a second *XBR Market*. The *XBR Network* is the XBR project itself, and hence this role cannot be assigned.

--------------


Who pays whom?
..............

The *XBR Consumer* realizes the economic value from the data, and hence should pay all other stakeholders for their share in providing the data service:

2. The seller of the data (*XBR Provider*),
3. the market that matched data service buyer and seller (*XBR Market*),
4. any carriers that routed data when using data services (*XBR Carrier*) and
5. the XBR project as maintainers of the technology (*XBR Network*).

While the *XBR Consumer* pays all other stakeholders, the interests of the data consumer is best addressed when there are lots of alternatives to choose of data carriers, markets and providers. This will encourage competitive data quality and prices.

--------------


Role Relations
..............

.. note::

    The base goal for the XBR project development roadmap is to allow many XBR Carriers, each operating many XBR Markets, but one XBR Market not to span multiple XBR Carriers.
    A moonshot goal for the XBR development roadmap is to also completely decouple XBR Carriers and XBR Markets - please see below.

The relations between the roles for the *base goal* of XBR are as follows:

.. code-block:: console

    XBR Network
        ^
        |
 [is registered]
        |
        +-- XBR Consumer
        |
        +-- XBR Provider
        |
        +-- XBR Market
        |
        +-- XBR Carrier
                  ^
                  |
            [uses carriage]
                  |
                  +--< XBR Market
                          ^
                          |
                          +--[provides data]-- XBR Provider
                          |
                          +--[consumes data]-- XBR Consumer

All *XBR Consumers* *XBR Providers*, *XBR Markets* and *XBR Carriers* register with the *XBR Network*.

Each *XBR Market* is operated by one *XBR Carrier*, and all *XBR Consumers* and *XBR Providers* in that market must **both** connect to **that** *XBR Carrier*.

Each *XBR Consumer* can connect to more than one *XBR Market* (and hence possibly different *XBR Carriers*) to consume data services, and each *XBR Provider* can offer its data services is multiple *XBR Markets*.

In this model for role relations, the cost of data carriage could priced into the cut that the data market takes, the integration of roles (carriage and market) and carrier participation at the realized business value of data can have risk benefits for data consumers, providers and markets.

.. note::

    There is no trust put into the *XBR Network*, neither monetary, nor data privacy wise, nor operationally. However, by registering, the use of the XBR software stack is licensed under the accepted terms. Pseudo-anonymous IDs and public keys may be stored on the Ethereum blockchain.

--------------


The relations between the roles for the *moonshot goal* of XBR are flat and completely decoupled:

.. code-block:: console

    XBR Network
        |
 [is registered]
        |
        +-- XBR Consumer
        |
        +-- XBR Provider
        |
        +-- XBR Market
        |        ^
        |        |
        |        +--[provides data]-- XBR Provider
        |        |
        |        +--[consumes data]-- XBR Consumer
        |
        +-- XBR Carrier
                 ^
                 |
           [uses carriage]
                 |
                 +-- XBR Provider
                 |
                 +-- XBR Consumer

*XBR Provider* and *XBR Consumers* - once registered with the *XBR Network* - can **automatically** use **any** *XBR Carrier* as the underlying provider of WAMP routing connectivity. and infrastructure.

All *XBR Carriers* effectively involved in carrying the data between *XBR Providers* and *XBR Consumer* are paid by a share from the income of the *XBR Providers*.

This models is serving the interests of *XBR Consumers* best, in that it will produce the most competitive alternative offerings for the different elements a data consumers needs: data carriage, markets and providers.

--------------


XBR Consumer
-----------------

Write me.

--------------


XBR Provider
-----------------

*Data Providers* in XBR expose views onto datasets. They provide *Services* which implements *Interfaces* in a market.
The interfaces a service implements defines the views onto the dataset and the actions that can be taken on the dataset.
A data service consists of

* service interface ("API")
* service implementation ("code")
* service database ("data")

and is implemented as a WAMP based microservice.
For example, a data service could be implemented in Python using AutobahnPython, and wrapped as a Docker container or Ubuntu Core snap.

The API for the data service might be authored by the data provider, in case the API is proprietary to the data provider or very specific, or the API might be authored by a third party (e.g. an open-source project), in case of broadly shared APIs that are implemented by many data providers.

The code for the data service might be authored and proprietary to the data provider, or the code might be written by an independent software vendor and licensed by the data provider, or the code might be written by an open-source project and used freely by the data provider.

The data for the data service ..

A data provider is in control of the full stack of a data service.
Keeping a data service up and running is the responsibility of the data provider.
For example, the data service could be run wrapped as a Docker container in a Kubernetes cluster hosted by the data provider.
Or the data service could run as an app on some smartphone of an end user. In both cases, the data service will connect (over WAMP) to a Crossbar.io Fabric router run by the market maker to offer its services in the market.

--------------


XBR Market
---------------

*XBR Market* set the rules, terms and legal framework for data exchange, control membership and operate the real-time balances (state channels) for each market member needed for off-chain transactions.

*XBR Market* also promotes the data market, fosters communication between market participants, and can also enforce sanctions upon market rule violations.

Each market maker operates its own CFC cluster under its own CFC/XBR administrative domain and full control.

Each market maker, within its CFC/XBR administrative domain, can operate one or more XBR Markets.

Data providers and consumers need to register with market makers, and then join or or multiple data markets.

Data providers and consumers need to open payment and incoming channels with makers.

--------------


XBR Carrier
----------------

Write me.

--------------


XBR Network
----------------

Write me.
