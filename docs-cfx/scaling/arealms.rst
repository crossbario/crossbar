Application realms
==================

Managing Application Realms
---------------------------

Create a new Application Realm
..............................

Create a new application realm for WAMP routing:

.. code-block:: console

    crossbarfx shell --realm default create arealm myrealm1 --config='{"enable_meta_api": true, "bridge_meta_api": true}'


List and show details about Application Realms
..............................................

List all application realms defined:

.. code-block:: console

    crossbarfx shell --realm default list arealms --names

Show details about an application realm:

.. code-block:: console

    crossbarfx shell --realm default show arealm myrealm1

Start and stop Application Realms
.................................

Start an application realm on the given router cluster, router worker group and web cluster:

.. code-block:: console

    crossbarfx shell --realm default start arealm myrealm1 cluster2 mygroup1 cluster1

Stop an application realm:

.. code-block:: console

    crossbarfx shell --realm default stop arealm myrealm1


Managing Application Roles
--------------------------

Create a new Application Role
.............................

Create a new role for use with application routers:

.. code-block:: console

    crossbarfx shell --realm default create role myrole1 \
        --config='{}'


List and show details about Application Roles
.............................................

List all roles defined in the management realm "default" (*NOT YET IMPLEMENTED*):

.. code-block:: console

    crossbarfx shell --realm default list roles

Show details about a role defined:

.. code-block:: console

    crossbarfx shell --realm default show role myrole1


Add a Permission to an Application Role
.......................................

Add a WAMP-level routing permission to a previously defined role:

.. code-block:: console

    crossbarfx shell --realm default add role-permission myrole1 "com.example." \
        --config='{"match": "prefix", "allow_call": true, "allow_register": true, "allow_publish": true, "allow_subscribe": true, "disclose_caller": true, "disclose_publisher": true, "cache": true}'


List and show details about Role Permissions
............................................

List all permissions added to a role (*NOT YET IMPLEMENTED*):

.. code-block:: console

    crossbarfx shell --realm default list role-permissions myrole1

Show details about a permission (*NOT YET IMPLEMENTED*):

.. code-block:: console

    crossbarfx shell --realm default show role-permission myrole1 "com.example."


Attach Application Roles to Realms
..................................

Attach the given role to the application realm:

.. code-block:: console

    crossbarfx shell --realm default add arealm-role myrealm1 myrole1 --config='{"authmethod": "anonymous"}'

Show details about a role attached to an application realm:

.. code-block:: console

    crossbarfx shell --realm default show arealm-role myrealm1 myrole1
