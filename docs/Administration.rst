:orphan:

Administration Manual
=====================

This is the Crossbar.io **Administration Manual**. The documentation
here discusses the configuration and administration of the different
features that come with Crossbar.io.

    For developers, we provide a :doc:`Programming Guide <Programming-Guide>` that provides documentation about
    programming aspects related to Crossbar.io.

Node Configuration
~~~~~~~~~~~~~~~~~~

A Crossbar.io node runs from a :doc:`Node Configuration<Node-Configuration>` and starts a number of
:doc:`Processes <Processes>` which can be configured:

-  :doc:`Router Configuration <Router-Configuration>`

   -  :doc:`Router Realms <Router-Realms>`
   -  :doc:`Router Components <Router-Components>`
   -  :doc:`Proxy Workers <Proxy-Workers>`

-  :doc:`Container Configuration <Container-Configuration>`
-  :doc:`Guest Configuration <Guest-Configuration>`
-  :doc:`Controller Configuration <Controller-Configuration>`

The router processes run :doc:`Router Transports <Router-Transports>`

-  :doc:`Transport Endpoints <Transport-Endpoints>`
-  :doc:`Web Transport and Services <Web-Transport-and-Services>`
-  :doc:`WebSocket Transport <WebSocket-Transport>`
-  :doc:`RawSocket Transport <RawSocket-Transport>`
-  :doc:`MQTT Broker <MQTT-Broker>`

Here is a complete example of a node configuration with router and container workers:

-  :doc:`Node Configuration Example <Node-Configuration-Example>`

Authentication and Authorization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  :doc:`Authentication <Authentication>`
-  :doc:`Authorization <Authorization>`

Web Services
~~~~~~~~~~~~

-  :doc:`Web Transport and Services <Web-Transport-and-Services>`
-  :doc:`Web Services <Web-Services>`
-  :doc:`HTTP Bridge <HTTP-Bridge>`

More
~~~~

-  :doc:`The Command Line <Command-Line>`
-  :doc:`Logging <Logging>`
-  :doc:`Going to Production <Going-to-Production>`
