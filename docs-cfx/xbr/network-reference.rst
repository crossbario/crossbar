XBR Network Reference
======================

The XBR Network Backend exposes two APIs:

1. WAMP programmatic interface
2. zLMDB database schema

Web application frontends can only use the former, while the latter can be used from
within CrossbarFX Workbench for interactive analysis of data stored by the backend.

WAMP API
--------

The backend exposes its WAMP API on the URI prefix ``xbr.network.*`` on the :class:`xbrnetwork._api.Network`.

Overview
........

The WAMP interface is exposed to WAMP clients that are authenticated under one of two roles:

1. **Anonymous** clients (``authrole == "anonymous"``)
2. **Member** (authenticated) clients ( ``authrole == "member"``)

For **Anonymous** clients (``authrole == "anonymous"``) the following API is exposed:

* [*TESTED*] :meth:`xbr.network.get_config <crossbarfx.network._api.Network.get_config>` - get backend configuration / settings
* [*TESTED*] :meth:`xbr.network.get_status <crossbarfx.network._api.Network.get_status>` - get backend status

For a _new_ member, the following on-board / on-board-verification procedures:

* [*TESTED*] :meth:`xbr.network.onboard_member <crossbarfx.network._api.Network.onboard_member>` - on-board a new XBR member
* [*TESTED*] :meth:`xbr.network.verify_onboard_member <crossbarfx.network._api.Network.verify_onboard_member>` - verify on-boarding of new member

For _existing_ members, the following member (client) login procedures:

* [*TESTED*] :meth:`xbr.network.login_member <crossbarfx.network._api.Network.login_member>` - login an existing XBR member
* [*TESTED*] :meth:`xbr.network.verify_login_member <crossbarfx.network._api.Network.verify_login_member>` - verify login of existing member
* [*TESTED*] :meth:`xbr.network.logout_member <crossbarfx.network._api.Network.logout_member>` - logout member client
* [*TESTED*] :meth:`xbr.network.get_member_logins <crossbarfx.network._api.Network.get_member_logins>` - get list of member logins
* [*TESTED*] :meth:`xbr.network.get_member_login <crossbarfx.network._api.Network.get_member_login>` - get member login details

as well as the following procedures for hosted wallet in particular:

* :meth:`xbr.network.recover_wallet <crossbarfx.network._api.Network.recover_wallet>` - recover a hosted wallet
* :meth:`xbr.network.verify_recover_wallet <crossbarfx.network._api.Network.verify_recover_wallet>` - verify recovery of hosted wallet

Essentially, the only thing anonymous clients may do is

* on-boarding a new member
* login of existing member
* recovery of hosted wallet

Once a member (and its first client public key) are known, new client connection will authenticate
as ``"user"``, and all functionality below becomes available.

For **Member** (authenticated) clients ( ``authrole == "member"``) *additionally* the following API is exposed:

* [*TESTED*] :meth:`xbr.network.echo <crossbarfx.network._api.Network.echo>`
* [*TESTED*] :meth:`xbr.network.get_member <crossbarfx.network._api.Network.get_member>`
* [*TESTED*] :meth:`xbr.network.get_member_by_wallet <crossbarfx.network._api.Network.get_member_by_wallet>`
* :meth:`xbr.network.backup_wallet <crossbarfx.network._api.Network.backup_wallet>`

API for *Data Markets*:

* [*TESTED*] :meth:`xbr.network.create_market <crossbarfx.network._api.Network.create_market>` - create a new XBR data market
* [*TESTED*] :meth:`xbr.network.verify_create_market <crossbarfx.network._api.Network.verify_create_market>` - verify creation of new XBR data market
* :meth:`xbr.network.remove_market <crossbarfx.network._api.Network.remove_market>`
* [*TESTED*] :meth:`xbr.network.get_market <crossbarfx.network._api.Network.get_market>`
* [*TESTED*] :meth:`xbr.network.get_markets_by_owner <crossbarfx.network._api.Network.get_markets_by_owner`>
* [*TESTED*] :meth:`xbr.network.find_markets <crossbarfx.network._api.Network.find_markets>` - find markets matching filters
* [*TESTED*] :meth:`xbr.network.join_market <crossbarfx.network._api.Network.join_market>` - join an existing XBR data market
* [*TESTED*] :meth:`xbr.network.verify_join_market <crossbarfx.network._api.Network.verify_join_market>` - verify joining an existing XBR data market

API for *Data Catalogs*:

* :meth:`xbr.network.create_catalog <crossbarfx.network._api.Network.create_catalog>` - create a new XBR data catalog (of APIs and Services)
* :meth:`xbr.network.remove_catalog <crossbarfx.network._api.Network.remove_catalog>`
* :meth:`xbr.network.get_catalog <crossbarfx.network._api.Network.get_catalog>`
* :meth:`xbr.network.get_catalogs_by_owner <crossbarfx.network._api.Network.get_catalogs_by_owner>`
* :meth:`xbr.network.find_catalogs <crossbarfx.network._api.Network.find_catalogs>`

API for *Cloud Domains*:

* :meth:`xbr.network.create_domain <crossbarfx.network._api.Network.create_domain>` - create a new XBR cloud domain
* :meth:`xbr.network.remove_domain <crossbarfx.network._api.Network.remove_domain>`
* :meth:`xbr.network.get_domain <crossbarfx.network._api.Network.get_domain>`
* :meth:`xbr.network.get_domains_by_owner <crossbarfx.network._api.Network.get_domains_by_owner>`
* :meth:`xbr.network.find_domains <crossbarfx.network._api.Network.find_domains>`


List of Procedures
..................

The following is an alphabetical sorted list of all URIs used by procedures
exposes by the XBR network backend:

* :meth:`xbr.network.backup_wallet <crossbarfx.network._api.Network.backup_wallet>`
* :meth:`xbr.network.create_catalog <crossbarfx.network._api.Network.create_catalog>`
* :meth:`xbr.network.create_coin <crossbarfx.network._api.Network.create_coin>`
* :meth:`xbr.network.create_domain <crossbarfx.network._api.Network.create_domain>`
* :meth:`xbr.network.create_market <crossbarfx.network._api.Network.create_market>` **[TESTED]**
* :meth:`xbr.network.echo <crossbarfx.network._api.Network.echo>` **[TESTED]**
* :meth:`xbr.network.find_apis <crossbarfx.network._api.Network.find_apis>`
* :meth:`xbr.network.find_catalogs <crossbarfx.network._api.Network.find_catalogs>`
* :meth:`xbr.network.find_coins <crossbarfx.network._api.Network.find_coins>`
* :meth:`xbr.network.find_domains <crossbarfx.network._api.Network.find_domains>`
* :meth:`xbr.network.find_markets <crossbarfx.network._api.Network.find_markets>` **[TESTED]**
* :meth:`xbr.network.get_actors_in_market <crossbarfx.network._api.Network.get_actors_in_market>` **[TESTED]**
* :meth:`xbr.network.get_api <crossbarfx.network._api.Network.get_api>`
* :meth:`xbr.network.get_catalog <crossbarfx.network._api.Network.get_catalog>`
* :meth:`xbr.network.get_catalogs_by_owner <crossbarfx.network._api.Network.get_catalogs_by_owner>`
* :meth:`xbr.network.get_coin <crossbarfx.network._api.Network.get_coin>` **[TESTED]**
* :meth:`xbr.network.get_coin_balance <crossbarfx.network._api.Network.get_coin_balance>` **[TESTED]**
* :meth:`xbr.network.get_coin_by_symbol <crossbarfx.network._api.Network.get_coin_by_symbol>` **[TESTED]**
* :meth:`xbr.network.get_config <crossbarfx.network._api.Network.get_config>` **[TESTED]**
* :meth:`xbr.network.get_domain <crossbarfx.network._api.Network.get_domain>`
* :meth:`xbr.network.get_domains_by_owner <crossbarfx.network._api.Network.get_domains_by_owner>`
* :meth:`xbr.network.get_gas_price <crossbarfx.network._api.Network.get_gas_price>` **[TESTED]**
* :meth:`xbr.network.get_market <crossbarfx.network._api.Network.get_market>` **[TESTED]**
* :meth:`xbr.network.get_markets_by_actor <crossbarfx.network._api.Network.get_markets_by_actor>` **[TESTED]**
* :meth:`xbr.network.get_markets_by_coin <crossbarfx.network._api.Network.get_markets_by_coin>` **[TESTED]**
* :meth:`xbr.network.get_markets_by_owner <crossbarfx.network._api.Network.get_markets_by_owner>` **[TESTED]**
* :meth:`xbr.network.get_member <crossbarfx.network._api.Network.get_member>` **[TESTED]**
* :meth:`xbr.network.get_member_by_wallet <crossbarfx.network._api.Network.get_member_by_wallet>` **[TESTED]**
* :meth:`xbr.network.get_member_login <crossbarfx.network._api.Network.get_member_login>` **[TESTED]**
* :meth:`xbr.network.get_member_logins <crossbarfx.network._api.Network.get_member_logins>` **[TESTED]**
* :meth:`xbr.network.get_status <crossbarfx.network._api.Network.get_status>` **[TESTED]**
* :meth:`xbr.network.get_transaction_receipt <crossbarfx.network._api.Network.get_transaction_receipt>` **[TESTED]**
* :meth:`xbr.network.is_member <crossbarfx.network._api.Network.is_member>` **[TESTED]**
* :meth:`xbr.network.join_market <crossbarfx.network._api.Network.join_market>` **[TESTED]**
* :meth:`xbr.network.login_member <crossbarfx.network._api.Network.login_member>` **[TESTED]**
* :meth:`xbr.network.logout_member <crossbarfx.network._api.Network.logout_member>` **[TESTED]**
* :meth:`xbr.network.onboard_member <crossbarfx.network._api.Network.onboard_member>` **[TESTED]**
* :meth:`xbr.network.publish_api <crossbarfx.network._api.Network.publish_api>`
* :meth:`xbr.network.recover_wallet <crossbarfx.network._api.Network.recover_wallet>`
* :meth:`xbr.network.remove_catalog <crossbarfx.network._api.Network.remove_catalog>`
* :meth:`xbr.network.remove_domain <crossbarfx.network._api.Network.remove_domain>`
* :meth:`xbr.network.remove_market <crossbarfx.network._api.Network.remove_market>`
* :meth:`xbr.network.update_market <crossbarfx.network._api.Network.update_market>` **[TESTED]**
* :meth:`xbr.network.verify_create_catalog <crossbarfx.network._api.Network.verify_create_catalog>`
* :meth:`xbr.network.verify_create_coin <crossbarfx.network._api.Network.verify_create_coin>`
* :meth:`xbr.network.verify_create_market <crossbarfx.network._api.Network.verify_create_market>` **[TESTED]**
* :meth:`xbr.network.verify_join_market <crossbarfx.network._api.Network.verify_join_market>` **[TESTED]**
* :meth:`xbr.network.verify_login_member <crossbarfx.network._api.Network.verify_login_member>` **[TESTED]**
* :meth:`xbr.network.verify_onboard_member <crossbarfx.network._api.Network.verify_onboard_member>` **[TESTED]**
* :meth:`xbr.network.verify_recover_wallet <crossbarfx.network._api.Network.verify_recover_wallet>`


xbr.network.echo
........................

.. automethod:: xbrnetwork._api.Network.echo

xbr.network.get_config
..............................

.. automethod:: xbrnetwork._api.Network.get_config

xbr.network.get_status
..............................

.. automethod:: xbrnetwork._api.Network.get_status

xbr.network.get_gas_price
.................................

.. automethod:: xbrnetwork._api.Network.get_gas_price

xbr.network.get_transaction_receipt
...........................................

.. automethod:: xbrnetwork._api.Network.get_transaction_receipt



xbr.network.onboard_member
..................................

.. automethod:: xbrnetwork._api.Network.onboard_member

xbr.network.verify_onboard_member
.........................................

.. automethod:: xbrnetwork._api.Network.verify_onboard_member

xbr.network.is_member
.............................

.. automethod:: xbrnetwork._api.Network.is_member

xbr.network.get_member
..............................

.. automethod:: xbrnetwork._api.Network.get_member

xbr.network.get_member_by_wallet
........................................

.. automethod:: xbrnetwork._api.Network.get_member_by_wallet

xbr.network.login_member
................................

.. automethod:: xbrnetwork._api.Network.login_member

xbr.network.verify_login_member
.......................................

.. automethod:: xbrnetwork._api.Network.verify_login_member

xbr.network.logout_member
.......................................

.. automethod:: xbrnetwork._api.Network.logout_member

xbr.network.get_member_logins
.....................................

.. automethod:: xbrnetwork._api.Network.get_member_logins

xbr.network.get_member_login
....................................

.. automethod:: xbrnetwork._api.Network.get_member_login

xbr.network.backup_wallet
.............,,,,,,,,,,,,,,,,,,,,

.. automethod:: xbrnetwork._api.Network.backup_wallet

xbr.network.recover_wallet
..................................

.. automethod:: xbrnetwork._api.Network.recover_wallet

xbr.network.verify_recover_wallet
.........................................

.. automethod:: xbrnetwork._api.Network.verify_recover_wallet



xbr.network.create_coin
...............................

.. automethod:: xbrnetwork._api.Network.create_coin

xbr.network.verify_create_coin
......................................

.. automethod:: xbrnetwork._api.Network.verify_create_coin

xbr.network.get_coin
............................

.. automethod:: xbrnetwork._api.Network.get_coin

xbr.network.get_coin_by_symbol
......................................

.. automethod:: xbrnetwork._api.Network.get_coin_by_symbol

xbr.network.get_coin_balance
....................................

.. automethod:: xbrnetwork._api.Network.get_coin_balance

xbr.network.find_coins
..............................

.. automethod:: xbrnetwork._api.Network.find_coins



xbr.network.create_market
.................................

.. automethod:: xbrnetwork._api.Network.create_market

xbr.network.verify_create_market
........................................

.. automethod:: xbrnetwork._api.Network.verify_create_market

xbr.network.remove_market
.................................

.. automethod:: xbrnetwork._api.Network.remove_market

xbr.network.update_market
.................................

.. automethod:: xbrnetwork._api.Network.update_market

xbr.network.get_market
..............................

.. automethod:: xbrnetwork._api.Network.get_market

xbr.network.get_markets_by_owner
........................................

.. automethod:: xbrnetwork._api.Network.get_markets_by_owner

xbr.network.get_markets_by_actor
........................................

.. automethod:: xbrnetwork._api.Network.get_markets_by_actor

xbr.network.get_actors_in_market
........................................

.. automethod:: xbrnetwork._api.Network.get_actors_in_market

xbr.network.get_markets_by_coin
.......................................

.. automethod:: xbrnetwork._api.Network.get_markets_by_coin

xbr.network.find_markets
................................

.. automethod:: xbrnetwork._api.Network.find_markets

xbr.network.join_market
...............................

.. automethod:: xbrnetwork._api.Network.join_market

xbr.network.verify_join_market
......................................

.. automethod:: xbrnetwork._api.Network.verify_join_market



xbr.network.create_catalog
..................................

.. automethod:: xbrnetwork._api.Network.create_catalog

xbr.network.verify_create_catalog
.........................................

.. automethod:: xbrnetwork._api.Network.verify_create_catalog

xbr.network.remove_catalog
..................................

.. automethod:: xbrnetwork._api.Network.remove_catalog

xbr.network.get_catalog
...............................

.. automethod:: xbrnetwork._api.Network.get_catalog

xbr.network.get_catalogs_by_owner
.........................................

.. automethod:: xbrnetwork._api.Network.get_catalogs_by_owner

xbr.network.find_catalogs
.................................

.. automethod:: xbrnetwork._api.Network.find_catalogs



xbr.network.publish_api
...............................

.. automethod:: xbrnetwork._api.Network.publish_api

xbr.network.verify_publish_api
......................................

.. automethod:: xbrnetwork._api.Network.verify_publish_api

xbr.network.get_api
...........................

.. automethod:: xbrnetwork._api.Network.get_api

xbr.network.find_apis
.............................

.. automethod:: xbrnetwork._api.Network.find_apis
