Domain Controller API
=====================

The global realm ``com.crossbario.fabric`` on the master node exposes the following
**Domain Controller API** to management clients.

.. contents:: :local:

-----------


Domain
------

General, domain wide procedures and topics.

crossbarfabriccenter.domain.get_status
......................................

.. automethod:: crossbarfx.master.node.controller.DomainManager.get_status

crossbarfabriccenter.domain.get_version
.......................................

.. automethod:: crossbarfx.master.node.controller.DomainManager.get_version

crossbarfabriccenter.domain.get_license
.......................................

.. automethod:: crossbarfx.master.node.controller.DomainManager.get_license


Organizations
-------------

crossbarfabriccenter.user.list_organizations
............................................

.. automethod:: crossbarfx.master.node.user.UserManager.list_organizations

crossbarfabriccenter.user.get_organization
..........................................

.. automethod:: crossbarfx.master.node.user.UserManager.get_organization

crossbarfabriccenter.user.create_organization
.............................................

.. automethod:: crossbarfx.master.node.user.UserManager.create_organization

crossbarfabriccenter.user.modify_organization
.............................................

.. automethod:: crossbarfx.master.node.user.UserManager.modify_organization

crossbarfabriccenter.user.delete_organization
.............................................

.. automethod:: crossbarfx.master.node.user.UserManager.delete_organization


crossbarfabriccenter.user.list_users_by_organization
....................................................

.. automethod:: crossbarfx.master.node.user.UserManager.list_users_by_organization


Users
-----

crossbarfabriccenter.user.get_user
..................................

.. automethod:: crossbarfx.master.node.user.UserManager.get_user

crossbarfabriccenter.user.modify_user
.....................................

.. automethod:: crossbarfx.master.node.user.UserManager.modify_user

crossbarfabriccenter.user.list_organizations_by_user
....................................................

.. automethod:: crossbarfx.master.node.user.UserManager.list_organizations_by_user

crossbarfabriccenter.user.set_roles_on_organization_for_user
............................................................

.. automethod:: crossbarfx.master.node.user.UserManager.set_roles_on_organization_for_user


Management Realms
-----------------

crossbarfabriccenter.mrealm.list_mrealms
........................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.list_mrealms

crossbarfabriccenter.mrealm.get_mrealm
......................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.get_mrealm

crossbarfabriccenter.mrealm.create_mrealm
.........................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.create_mrealm

crossbarfabriccenter.mrealm.modify_mrealm
.........................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.modify_mrealm

crossbarfabriccenter.mrealm.delete_mrealm
.........................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.delete_mrealm

crossbarfabriccenter.mrealm.set_roles_on_mrealm_for_user
........................................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.set_roles_on_mrealm_for_user


Nodes
-----

crossbarfabriccenter.mrealm.list_nodes
......................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.list_nodes

crossbarfabriccenter.mrealm.get_node
....................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.get_node

crossbarfabriccenter.mrealm.modify_node
.......................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.modify_node

crossbarfabriccenter.mrealm.delete_node
.......................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.delete_node

crossbarfabriccenter.mrealm.pair_node
.....................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.pair_node

crossbarfabriccenter.mrealm.unpair_node
.......................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.unpair_node

crossbarfabriccenter.mrealm.list_nodes_by_mrealm
................................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.list_nodes_by_mrealm

crossbarfabriccenter.mrealm.stat_node
.....................................

.. automethod:: crossbarfx.master.mrealm.mrealm.MrealmManager.stat_node
