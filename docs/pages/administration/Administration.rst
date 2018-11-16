:orphan:

Administration Manual
=====================

This is the Crossbar.io **Administration Manual**. The documentation
here discusses the configuration and administration of the different
features that come with Crossbar.io.

    For developers, we provide a :doc:`Programming Guide <../programming-guide/Programming-Guide>` that provides documentation about
    programming aspects related to Crossbar.io.

Node Configuration
~~~~~~~~~~~~~~~~~~

A Crossbar.io node runs from a :doc:`Node Configuration<Node-Configuration>` and starts a number of
:doc:`Processes <worker/Processes>` which can be configured:

-  :doc:`Router Configuration <worker/Router-Configuration>`

   -  :doc:`Router Realms <router//Router-Realms>`
   -  :doc:`Router Components <router//Router-Components>`

-  :doc:`Container Configuration <worker/Container-Configuration>`
-  :doc:`Guest Configuration <worker/Guest-Configuration>`
-  :doc:`Controller Configuration <worker/Controller-Configuration>`

The router processes run :doc:`Router Transports <router/Router-Transports>`

-  :doc:`Transport Endpoints <router/transport/Transport-Endpoints>`
-  :doc:`Web Transport and Services <router/transport/Web-Transport-and-Services>`
-  :doc:`WebSocket Transport <router/transport/WebSocket-Transport>`
-  :doc:`RawSocket Transport <router/transport/RawSocket-Transport>`
-  :doc:`MQTT Broker <mqtt-broker/MQTT-Broker>`

Authentication and Authorization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  :doc:`Authentication <auth/Authentication>`
-  :doc:`Authorization <auth/Authorization>`

Web Services
~~~~~~~~~~~~

-  :doc:`Web Transport and Services <router/transport/Web-Transport-and-Services>`
-  :doc:`Web Services <web-service/Web-Services>`
-  :doc:`HTTP Bridge <http-bridge/HTTP-Bridge>`

More
~~~~

-  :doc:`The Command Line <Command-Line>`
-  :doc:`Logging <Logging>`
-  :doc:`Going to Production <production/Going-to-Production>`