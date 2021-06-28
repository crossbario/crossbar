.. _XBRAPI:

XBR API Reference
=================

Market Maker API: Overview
--------------------------

URI prefix: ``xbr.marketmaker``

**Common API**

For any XBR delegate component to use:

* :meth:`MarketMaker.status <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.status>`
* :meth:`MarketMaker.get_market <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_market>`
* :meth:`MarketMaker.get_actor <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_actor>`
* :meth:`MarketMaker.open_channel <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.open_channel>`
* :meth:`MarketMaker.close_channel <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.close_channel>`

-------

**Seller side API**

XBR seller delegates (data service providers) will commonly use the following market maker API:

* :meth:`MarketMaker.place_offer <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.place_offer>`
* :meth:`MarketMaker.revoke_offer <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.revoke_offer>`
* :meth:`MarketMaker.query_offers <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.query_offers>`
* :meth:`MarketMaker.get_offer <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_offer>`

and

* :meth:`MarketMaker.get_paying_channel <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_paying_channel>`
* :meth:`MarketMaker.get_paying_channel_balance <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_paying_channel_balance>`

-------

**Buyer side API**

XBR buyer delegates (data service consumers) will commonly use the following market maker API:

* :meth:`MarketMaker.query_offers <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.query_offers>`
* :meth:`MarketMaker.get_quote <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_quote>`
* :meth:`MarketMaker.buy_key <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.buy_key>`

and

* :meth:`MarketMaker.get_payment_channel <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_payment_channel>`
* :meth:`MarketMaker.get_payment_channel_balance <crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_payment_channel_balance>`


Market Maker API: Procedures
----------------------------

xbr.marketmaker.status
......................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.status

xbr.marketmaker.open_channel
............................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.open_channel

xbr.marketmaker.close_channel
.............................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.close_channel

xbr.marketmaker.place_offer
...........................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.place_offer

xbr.marketmaker.revoke_offer
............................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.revoke_offer

xbr.marketmaker.get_offer
.........................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_offer

xbr.marketmaker.query_offers
............................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.query_offers

xbr.marketmaker.get_quote
.........................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_quote

xbr.marketmaker.buy_key
.......................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.buy_key

xbr.marketmaker.get_payment_channel
...................................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_payment_channel

xbr.marketmaker.get_payment_channel_balance
...........................................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_payment_channel_balance

xbr.marketmaker.get_paying_channel
..................................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_paying_channel

xbr.marketmaker.get_paying_channel_balance
..........................................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_paying_channel_balance

xbr.marketmaker.get_active_payment_channel
..........................................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_active_payment_channel

xbr.marketmaker.get_active_paying_channel
.........................................

.. automethod:: crossbarfx.edge.worker.xbr._marketmaker.MarketMaker.get_active_paying_channel
