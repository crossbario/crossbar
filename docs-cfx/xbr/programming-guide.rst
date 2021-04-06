XBR Programming Guide
=====================

Within each XBR data market, there are three primary roles:

* XBR data providers
* XBR data consumers
* XBR market maker

All three XBR roles are technically realized by WAMP clients connected to a CrossbarFX WAMP router,
and joined on an application realm for the specific market.

There can be potentially many XBR data providers and consumers, but there is only one XBR market maker
per market.

Technically, that market maker can run one or many XBR market maker workers, but those will act as a logical
unit.

The market maker holds state channels with each of the market participants and is the gateway to the blockchain.


Interfaces
----------

The XBR market maker has three run-time interfaces required and optimized for different aspects of XBR
data transaction processing:

1. **XBR WAMP API**: :ref:`XBRAPI`
2. **XBR smart contracts**: `The XBR Protocol <https://xbr.network/docs/index.html>`_
3. **CrossbarFX events database**: FIXME
4. **XBR market maker database**: FIXME


Configuration
-------------

XBR Market Makers run as special workers of type `xbrmm`, and a CrossbarFX node can host multiple
market makers.

Here is a example of a worker configuration item:

.. code-block:: json

        {
            "id": "xbrmm1",
            "type": "xbrmm",
            "options": {
                "env": {
                    "inherit": true
                }
            },
            "makers": [
                {
                    "id": "maker1",
                    "store": {
                        "type": "cfxdb",
                        "path": "../.xbrdb-transactions",
                        "maxsize": 1073741824
                    },
                    "blockchain": {
                        "type": "ethereum",
                        "gateway": {
                            "type": "user",
                            "http": "http://127.0.0.1:8545"
                        }
                    },
                    "connection": {
                        "realm": "realm1",
                        "transport": {
                            "type": "rawsocket",
                            "endpoint": {
                                "type": "unix",
                                "path": "xbrmm.sock"
                            },
                            "serializer": "cbor"
                        }
                    }
                }
            ]
        }

The market maker connects to a router worker, in this case using RawSocket-CBOR over Unix domain socket
as a WAMP transport. The router worker needs a listening transport:

.. code-block:: json

    {
        "type": "rawsocket",
        "endpoint": {
            "type": "unix",
            "path": "xbrmm.sock"
        },
        "max_message_size": 1048576,
        "serializers": ["cbor"],
        "auth": {
            "anonymous": {
                "type": "static",
                "role": "xbrmm"
            }
        }
    }

Finally, the static WAMP authentication role the market maker is authenticated for, in this case ``"xbrmm"``
has to have permissions on the URI prefix `xbr.maker.` assigned:

.. code-block:: json

    {
        "name": "xbrmm",
        "permissions": [
            {
                "uri": "xbr.marketmaker.",
                "match": "prefix",
                "allow": {
                    "call": true,
                    "register": true,
                    "publish": true,
                    "subscribe": true
                },
                "disclose": {
                    "caller": true,
                    "publisher": true
                },
                "cache": true
            },
            {
                "uri": "xbr.provider.",
                "match": "prefix",
                "allow": {
                    "call": true,
                    "register": false,
                    "publish": false,
                    "subscribe": true
                },
                "disclose": {
                    "caller": true,
                    "publisher": true
                },
                "cache": true
            }
        ]
    }

To be able to communicate with a XBR market maker, XBR data consumers and providers need the following
permissions assigned:

.. code-block:: json

    {
        "uri": "xbr.marketmaker.",
        "match": "prefix",
        "allow": {
            "call": true,
            "register": false,
            "publish": false,
            "subscribe": true
        },
        "disclose": {
            "caller": true,
            "publisher": true
        },
        "cache": true
    }


Example Consumer (Buyer)
------------------------

.. code-block:: python

    from xbr import SimpleBuyer

    private_key = b'...'

    buyer = SimpleBuyer(private_key)

    balance = await buyer.start_buying(session)


here we let our XBR buyer unwrap the encrypted application payload

.. code-block:: python

    async def on_event(key_id, enc_ser, ciphertext, details=None):
        payload = await buyer.unwrap(key_id, enc_ser, ciphertext)

    sub = await session.subscribe(on_event, 'com.example.topic1')

.. code-block:: python

    key_id, enc_ser, ciphertext = await session.call('com.example.add2', 2, 3)

    payload = await buyer.unwrap(key_id, enc_ser, ciphertext)


Example Provider (Seller)
-------------------------

start selling (rotating the key every 10 seconds and sell new keys for 35 XBR each)


.. code-block:: python

    from xbr import SimpleSeller

    private_key = b'...'

    seller = SimpleSeller(private_key)

    await seller.start_selling(self, details, 10, 35)


.. code-block:: python

    topic = 'com.example.topic1'
    payload = {
        'id': 23,
        'msg': 'Hello, world!'
    }

    key_id, enc_ser, ciphertext = await seller.wrap(topic, payload)

    await self.publish(topic, key_id, enc_ser, ciphertext, options=PublishOptions(acknowledge=True))


.. code-block:: python

    def add2(x, y, details=None):
        payload = {
            'sum': x + y
        }
        key_id, enc_ser, ciphertext = await seller.wrap(details.procedure, payload)
        return key_id, enc_ser, ciphertext

    await session.register(add2, 'com.example.add2')
