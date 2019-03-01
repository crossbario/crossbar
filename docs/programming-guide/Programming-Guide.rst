:orphan:

Programming Guide
=================

Programming WAMP application components is tied to the particular client
library you're using. The `Autobahn </autobahn>`__ family of WAMP client
libraries is provided by us, whereas you can find more WAMP client
libraries `here <http://wamp.ws/implementations/#libraries>`__.

We also operate a public :doc:`Crossbar.io Demo Instance <../installation/Demo-Instance>`
and offer a range of materials for `IoT devices, components and
applications <http://crossbario.com/iotcookbook>`__.

    For administrators, we provide a :doc:`Administration Manual <../administration/Administration>` that provides documentation about
    administration aspects related to Crossbar.io.

The following introduces different areas of WAMP application programming
with Crossbar.io:

Usage
~~~~~

-  :doc:`Starting and Stopping Crossbar.io <Starting-and-Stopping-Crossbar.io>`
-  :doc:`Configuring Crossbar.io's Logging <Configuring-Crossbario-Logging>`

General
~~~~~~~

-  :doc:`URI Format <general/URI-Format>`
-  :doc:`Logging in Crossbar.io <Logging-in-Crossbar.io>`
-  :doc:`Error Handling <Error-Handling>`
-  :doc:`Session Meta Events and Procedures <general/Session-Metaevents-and-Procedures>`
-  :doc:`Development with External Devices <Development-with-External-Devices>`

Publish and Subscribe
~~~~~~~~~~~~~~~~~~~~~

-  :doc:`How Subscriptions Work <pubsub/How-Subscriptions-Work>`
-  :doc:`Basic Subscriptions <pubsub/Basic-Subscriptions>`
-  :doc:`Subscriber Black- and Whitelisting <pubsub/Subscriber-Black-and-Whitelisting>`
-  :doc:`Publisher Exclusion <pubsub/Publisher-Exclusion>`
-  :doc:`Publisher Identification <pubsub/Publisher-Identification>`
-  :doc:`Pattern-Based Subscriptions <pubsub/Pattern-Based-Subscriptions>`
-  :doc:`Subscription Meta Events and Procedures <pubsub/Subscription-Meta-Events-and-Procedures>`
-  :doc:`Event History <pubsub/Event-History>`

Remote Procedure Calls
~~~~~~~~~~~~~~~~~~~~~~

-  :doc:`How Registrations Work <rpc/How-Registrations-Work>`
-  :doc:`Basic Registrations <rpc/Basic-Registrations>`
-  :doc:`Caller Identification <rpc/Caller-Identification>`
-  :doc:`Progressive Call Results <rpc/Progressive-Call-Results>`
-  :doc:`Pattern-Based Registrations <rpc/Pattern-Based-Registrations>`
-  :doc:`Shared Registrations <rpc/Shared-Registrations>`
-  :doc:`Registration Meta Events and Procedures <rpc/Registration-Meta-Events-and-Procedures>`

Specific Usages
~~~~~~~~~~~~~~~

-  :doc:`Adding Real-Time to Django  Applications <framework/Adding-Real-Time-to-Django-Applications>`
-  :doc:`AngularJS Application Components  <framework/AngularJS-Application-Components>`
-  :doc:`Database Programming with  PostgreSQL <framework/Database-Programming-with-PostgreSQL>`

Specific Languages
~~~~~~~~~~~~~~~~~~

Details of programming depend on the `specific WAMP
library </about/Supported-Languages/>`__ you are using. You may find
more information in the documentation for the respective libraries, e.g.

-  `Programming with
   Autobahn\|Python <http://autobahn.readthedocs.io/en/latest/wamp/programming.html>`__
-  `Programming with
   Autobahn\|JavaScript <https://github.com/crossbario/autobahn-js/blob/master/doc/programming.md>`__
