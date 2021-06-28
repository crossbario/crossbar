XBR Administration Guide
========================

Market Maker Log Messages
-------------------------

Market Marker Worker
....................

To operate a XBR data market, you need to run a CrossbarFX edge node with at least one worker process of type ``xbrmm``
and one market maker defined:

.. code-block:: console

    cfx edge node
        |
        + xbrmm worker
            |
            + xbr market maker

Here is (part of) an example edge node configuration:

.. code-block:: json

    {
        "workers": [
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
                        "key": "../.xbrmm.key",
                        "store": {
                            "type": "cfxdb",
                            "path": "../.xbrdb-transactions",
                            "maxsize": 1073741824
                        },
                        "blockchain": {
                            "type": "ethereum",
                            "gateway": {
                                "type": "user",
                                "http": "http://localhost:1545"
                            },
                            "from_block": 1,
                            "chain_id": 5777
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
        ]
    }

Above will start a worker process with one market maker defined (``"maker1"``) which connects back to a running router worker
via Unix domain socket:

.. code-block:: console

    2020-02-05T09:34:16+0100 [Controller  14320] Starting xbrmm worker xbrmm1 <crossbar.node.controller.NodeController.start_worker>

Market Maker Key
................

Once the XBR worker has started, the configured market maker(s) ``maker1`` will start:

.. code-block:: console

    2020-02-05T09:34:18+0100 [XBRMrktMkr  14343] Existing XBR Market Maker Ethereum private key loaded from "/home/oberstet/scm/crossbario/project-continental-cloud/conti-rws/teststack/cfxedge/.xbrmm.key"
    2020-02-05T09:34:18+0100 [XBRMrktMkr  14343] XBR Market Maker Ethereum (canonical/checksummed) address is 0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9:

Every XBR market maker must have its own private Ethereum key (32 random bytes) read from the file key configured.

Market Maker Database
.....................

During startup, the market maker will attach to or freshly create an embedded database to store all XBR data:

.. code-block:: console

    2020-02-05T09:34:18+0100 [XBRMrktMkr  14343] Attached XBR Market Maker database [dbpath="../.xbrdb-transactions", maxsize=1073741824]

The base path pointing to the embedded database is configured in the market maker configuration.

Non-associated Market Maker
...........................

When the market maker starts, it will connect to the blockchain and look if its public address is already defined to be associated
with any XBR market defined on the blockchain.

If not, the market maker will log:

.. code-block:: console

    2020-02-05T10:22:18+0100 [XBRMrktMkr  16994] Scanning blockchain (current block is 26) beginning with block 1 ..
    2020-02-05T10:22:18+0100 [XBRMrktMkr  16994] Market maker is NOT associated with (working for) any XBR data market! Will sit idle waiting to be associated with a market ..

Obviously, no XBR transactions can be executed in this case, and a XBR market needs to be defined first, providing the XBR market maker
address.

Associated Market Maker
.......................

If there is an XBR market that has the address of the market maker defined as the associated one, the market maker will log and continue booting
and process any XBR related information stored in the blockchain:

.. code-block:: console

    2020-02-05T10:21:04+0100 [XBRMrktMkr  16755] Scanning blockchain (current block is 47) beginning with block 1 ..
    2020-02-05T10:21:04+0100 [XBRMrktMkr  16755] Ok, XBR market maker is associated on-chain and will be working for market=a1b8d674-1ae8-4920-17fa-fd8d4f8b67a2!

Processing the blockchain starts at either block 1 (default) or the block number configured in the node configuration or the last block
already processed (the market maker will persist the last block number up to which it already processed blocks).

During block processing, the marker maker will encounter XBR related information on the blockchain and perform suitable actions.

The log lines printed typically during (successful) processing of various XBR related event types is listed below.

--------

Token Transfer
..............

When XBR tokens are transfered between Ethereum addresses, the market maker will log:

.. code-block:: console

    2020-02-05T10:24:40+0100 [XBRMrktMkr  17086] _process_Token_Transfer processing block 16 / txn 0xb894dee9230233d5aec9f75c53a679cbe8bb83f61a01bafd9f08b7fa11949c7d with args AttributeDict({'from': '0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1', 'to': '0x1dF62f291b2E969fB0849d99D9Ce41e2F137006e', 'value': 20000000000000000000000})
    2020-02-05T10:24:40+0100 [XBRMrktMkr  17086] <XBRToken.Transfer>: processing event (tx_hash=0xb894dee9230233d5aec9f75c53a679cbe8bb83f61a01bafd9f08b7fa11949c7d, block_hash=0xa4a844ae38eab8ba4fe5377a3a5443cd27ab016ad2ecf521ffbe63b97e189c72) - 20000 XBR token transferred (on-chain) from 0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1 to 0x1dF62f291b2E969fB0849d99D9Ce41e2F137006e)
    2020-02-05T10:24:40+0100 [XBRMrktMkr  17086] new <TokenTransfer>(tx_hash=0xb894dee9230233d5aec9f75c53a679cbe8bb83f61a01bafd9f08b7fa11949c7d) record stored database!
    2020-02-05T10:24:40+0100 [XBRMrktMkr  17086] Processed blockchain block 16: processed 1 XBR events

Token Approval
..............

When XBR tokens are approved to be transfered between Ethereum addresses, the market maker will log:

.. code-block:: console

    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] _process_Token_Approval processing block 42 / txn 0x8132671fe89f842392cd8df395a6890a38460cf2dbaa094e9b449ec8e3a72a71 with args AttributeDict({'owner': '0xfA2435Eacf10Ca62ae6787ba2fB044f8733Ee843', 'spender': '0xC89Ce4735882C9F0f0FE26686c53074E09B0D550', 'value': 500000000000000000000})
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] <XBRToken.Approval>: processing event (tx_hash=0x8132671fe89f842392cd8df395a6890a38460cf2dbaa094e9b449ec8e3a72a71, block_hash=0x9283ab5ffa2cf643e7994a54cdf2b754061883ef1a0e8365eef327577a79fbff) - 500 XBR token approved (on-chain) from owner 0xfA2435Eacf10Ca62ae6787ba2fB044f8733Ee843 to spender 0xC89Ce4735882C9F0f0FE26686c53074E09B0D550)
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] new <TokenApproval>(tx_hash=0x8132671fe89f842392cd8df395a6890a38460cf2dbaa094e9b449ec8e3a72a71) record stored database!
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] Processed blockchain block 42: processed 1 XBR events

Member Created
..............

When a new member joins the XBR Network, the market maker will log:

.. code-block:: console

    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] _process_Network_MemberCreated processing block 28 / txn 0x5e9c7a06bf214c01f7c14545368645a415237f62acaccec59f5586056517997b with args AttributeDict({'member': '0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0', 'registered': 1580894656, 'eula': 'QmV1eeDextSdUrRUQp9tUXF8SdvVeykaiwYLgrXHHVyULY', 'profile': '', 'level': 1})
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] <XBRNetwork.MemberCreated>: processing event (tx_hash=0x5e9c7a06bf214c01f7c14545368645a415237f62acaccec59f5586056517997b, block_hash=0x6a730e1be4a9e02ec3f02e6bad7c6301b558c4b449ca7c302dc53d512d4d9a94) - XBR member created at address 0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0)
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] new <MemberCreated>(member_adr=0xffcf8fdee72ac11b5c542428b35eef5769c409f0) record stored database!
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] Processed blockchain block 28: processed 1 XBR events

Market Created
..............

When a new market is created, the market maker will log:

.. code-block:: console

    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] _process_Network_MarketCreated processing block 35 / txn 0x62b8e51a545fd0feadcae3dec73feac7d57e4f2845178c4f2e6c681a4879c58c with args AttributeDict({'marketId': b'\xa1\xb8\xd6t\x1a\xe8I \x17\xfa\xfd\x8dO\x8bg\xa2', 'created': 1580894657, 'marketSeq': 2, 'owner': '0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d', 'terms': '', 'meta': '', 'maker': '0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9', 'providerSecurity': 0, 'consumerSecurity': 0, 'marketFee': 0})
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] <XBRNetwork.MarketCreated>: processing event (tx_hash=0x62b8e51a545fd0feadcae3dec73feac7d57e4f2845178c4f2e6c681a4879c58c, block_hash=0xeb3cdfbaf69bc5748f3de5c9c1eff716bba9889829ca4bf5319268f7731413e5) - XBR market created with ID a1b8d674-1ae8-4920-17fa-fd8d4f8b67a2)
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] new <MarketCreated>(market_id=a1b8d674-1ae8-4920-17fa-fd8d4f8b67a2) record stored database!
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] Processed blockchain block 35: processed 1 XBR events

.. note::

    A given market maker is responsible for at most one market. However, every market maker also persists a list of *all* markets
    together with basic meta data.

Market Actor Joined
...................

When a XBR member joins a XBR market, the member becomes an actor in that market, and the market maker will log:

.. code-block:: console

    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] _process_Network_ActorJoined processing block 45 / txn 0x6b98eb42d8a80f428a254eb472811d8fc5268b3771c446905194f29b3a8c281e with args AttributeDict({'marketId': b'\xa1\xb8\xd6t\x1a\xe8I \x17\xfa\xfd\x8dO\x8bg\xa2', 'actor': '0xf408f04F9b7691f7174FA2bb73ad6d45fD5d3CBe', 'actorType': 1, 'joined': 1580894657, 'security': 0, 'meta': ''})
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] <XBRNetwork.ActorJoined>: processing event (tx_hash=0x6b98eb42d8a80f428a254eb472811d8fc5268b3771c446905194f29b3a8c281e, block_hash=0xed3e8e5189a6e548744fcd217e6afa2864c4b2fe91232cd47c672783df8fec1e) - XBR market actor 0xf408f04F9b7691f7174FA2bb73ad6d45fD5d3CBe joined market a1b8d674-1ae8-4920-17fa-fd8d4f8b67a2)
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] new <ActorJoined>(market_id=a1b8d674-1ae8-4920-17fa-fd8d4f8b67a2, actor_adr=0xf408f04f9b7691f7174fa2bb73ad6d45fd5d3cbe, actor_type=1) record stored database!
    2020-02-05T10:24:41+0100 [XBRMrktMkr  17086] Processed blockchain block 45: processed 1 XBR events

Buyer (Payment) Channel
.......................

When a buyer channel (aka "payment channel") is created by a buyer, the node will log:

.. code-block:: console

    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] _process_Network_ChannelCreated processing block 49 / txn 0xe130e492dcce6017a340c155037613185461d6e8bff2a4fa1a3d2d3255d2bc63 with args AttributeDict({'marketId': b'\xa1\xb8\xd6t\x1a\xe8I \x17\xfa\xfd\x8dO\x8bg\xa2', 'sender': '0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b', 'delegate': '0x95cED938F7991cd0dFcb48F0a06a40FA1aF46EBC', 'recipient': '0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d', 'channel': '0x141f5fCa84Cc82EF0A6751241019471731289456', 'channelType': 1})
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] _process_Network_ChannelCreated running:
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] <PaymentChannel>(channel=0x141f5fca84cc82ef0a6751241019471731289456, market=0xa1b8d6741ae8492017fafd8d4f8b67a2, sender=0x22d491bde2303f2f43325b2108d26f1eaba1e32b, delegate=0x95ced938f7991cd0dfcb48f0a06a40fa1af46ebc, recipient=0xe11ba2b4d45eaed5996cd0823791e0c93114882d) stored in database (type=1)!
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] _process_Token_Transfer processing block 49 / txn 0xe130e492dcce6017a340c155037613185461d6e8bff2a4fa1a3d2d3255d2bc63 with args AttributeDict({'from': '0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b', 'to': '0x141f5fCa84Cc82EF0A6751241019471731289456', 'value': 500000000000000000000})
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] <XBRToken.Transfer>: processing event (tx_hash=0xe130e492dcce6017a340c155037613185461d6e8bff2a4fa1a3d2d3255d2bc63, block_hash=0x2579b01421a750ed023f812147410ae8a5afa2184c8e997e860db7097d1cd4a3) - 500 XBR token transferred (on-chain) from 0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b to 0x141f5fCa84Cc82EF0A6751241019471731289456)
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] <TokenTransfer>(tx_hash=0xe130e492dcce6017a340c155037613185461d6e8bff2a4fa1a3d2d3255d2bc63) record already stored in database.
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] _process_Token_Approval processing block 49 / txn 0xe130e492dcce6017a340c155037613185461d6e8bff2a4fa1a3d2d3255d2bc63 with args AttributeDict({'owner': '0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b', 'spender': '0xC89Ce4735882C9F0f0FE26686c53074E09B0D550', 'value': 0})
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] <XBRToken.Approval>: processing event (tx_hash=0xe130e492dcce6017a340c155037613185461d6e8bff2a4fa1a3d2d3255d2bc63, block_hash=0x2579b01421a750ed023f812147410ae8a5afa2184c8e997e860db7097d1cd4a3) - 0 XBR token approved (on-chain) from owner 0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b to spender 0xC89Ce4735882C9F0f0FE26686c53074E09B0D550)
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] <TokenApproval>(tx_hash=0xe130e492dcce6017a340c155037613185461d6e8bff2a4fa1a3d2d3255d2bc63) record already stored in database.
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] _process_Network_ChannelCreated processing block 49 / txn 0xe130e492dcce6017a340c155037613185461d6e8bff2a4fa1a3d2d3255d2bc63 with args AttributeDict({'marketId': b'\xa1\xb8\xd6t\x1a\xe8I \x17\xfa\xfd\x8dO\x8bg\xa2', 'sender': '0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b', 'delegate': '0x95cED938F7991cd0dFcb48F0a06a40FA1aF46EBC', 'recipient': '0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d', 'channel': '0x141f5fCa84Cc82EF0A6751241019471731289456', 'channelType': 1})
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] _process_Network_ChannelCreated running:
    2020-02-05T12:14:55+0100 [XBRMrktMkr  22255] <Channel>(channel=0x141f5fca84cc82ef0a6751241019471731289456) already stored (type=1)

Seller (Paying) Channel
.......................

When a seller channel (aka "paying channel") is created by a seller, this is a two-step process. First the seller submits
a *paying channel request*, which will appear in the log like this:

.. code-block:: console

    2020-02-05T12:14:57+0100 [XBRMrktMkr  22255] _process_Network_PayingChannelRequestCreated processing block 72 / txn 0x73cc559726166cedc1bb42737413c5e8a3761af75c544ce116a784db0c9dcf23 with args AttributeDict({'marketId': b'\xa1\xb8\xd6t\x1a\xe8I \x17\xfa\xfd\x8dO\x8bg\xa2', 'sender': '0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0', 'recipient': '0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0', 'delegate': '0xd03ea8624C8C5987235048901fB614fDcA89b117', 'amount': 1000000000000000000000, 'timeout': 60})
    2020-02-05T12:14:57+0100 [XBRMrktMkr  22255] _process_Network_PayingChannelRequestCreated running:
    2020-02-05T12:14:57+0100 [XBRMrktMkr  22255] <PayingChannelRequest>(request=0x032ddca664f91a1960f389cdf5a53209) newly stored in database!
    2020-02-05T12:14:57+0100 [XBRMrktMkr  22255] Processed blockchain block 72: processed 1 XBR events

When the marker maker see above transaction committed to the blockchain, it will then submit a second transction by itself
to the blockchain:

.. code-block:: console

    2020-02-05T12:14:57+0100 [XBRMrktMkr  22255] Submitting Ethereum transaction from from_adr="0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9", gas=1300000 ..
    2020-02-05T12:14:57+0100 [XBRMrktMkr  22255] Allowed transfer of 1000000000000000000000 XBR from 0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9 to 0xC89Ce4735882C9F0f0FE26686c53074E09B0D550 for opening a payment channel from market maker "0xa1b8d6741ae8492017fafd8d4f8b67a2" to seller delegate 0xd03ea8624c8c5987235048901fb614fdca89b117
    2020-02-05T12:14:57+0100 [XBRMrktMkr  22255] Paying channel request persisted (request=0x032ddca664f91a1960f389cdf5a53209, channel=0x79e7654eaae77cdff937ec7b6f3156f7dea4fc4c)

.. note::

    Technically, a seller channel (aka "paying channel") is initially charged up with tokens transfered (paid) by the market maker, and payable to the
    receipient defined by the seller (who ultimately earns tokens collected in the channel by selling data/services).

Only after this second blockchain transaction is committed to the blockchain and seen by the market maker, it will actually create
the seller channel (aka "paying channel"):

.. code-block:: console

    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] <PayingChannel>(channel=0x79e7654eaae77cdff937ec7b6f3156f7dea4fc4c, market=0xa1b8d6741ae8492017fafd8d4f8b67a2, sender=0x3e5e9111ae8eb78fe1cc3bb8915d5d461f3ef9a9, delegate=0xd03ea8624c8c5987235048901fb614fdca89b117, recipient=0xffcf8fdee72ac11b5c542428b35eef5769c409f0) stored in database (type=2)!
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] _process_Token_Transfer processing block 85 / txn 0x4cf7c606b867e7bafee0d7b7f7c9a92966faee0010163bdb8e00f0b498a0e482 with args AttributeDict({'from': '0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9', 'to': '0x79e7654EaAE77cDFF937EC7b6F3156F7dEa4fC4C', 'value': 1000000000000000000000})
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] <XBRToken.Transfer>: processing event (tx_hash=0x4cf7c606b867e7bafee0d7b7f7c9a92966faee0010163bdb8e00f0b498a0e482, block_hash=0x0e94a0430d49ade4563dbc5000e43be7f66ea39a9fcf96c82cc1aa5521dc7528) - 1000 XBR token transferred (on-chain) from 0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9 to 0x79e7654EaAE77cDFF937EC7b6F3156F7dEa4fC4C)
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] <TokenTransfer>(tx_hash=0x4cf7c606b867e7bafee0d7b7f7c9a92966faee0010163bdb8e00f0b498a0e482) record already stored in database.
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] _process_Token_Approval processing block 85 / txn 0x4cf7c606b867e7bafee0d7b7f7c9a92966faee0010163bdb8e00f0b498a0e482 with args AttributeDict({'owner': '0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9', 'spender': '0xC89Ce4735882C9F0f0FE26686c53074E09B0D550', 'value': 0})
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] <XBRToken.Approval>: processing event (tx_hash=0x4cf7c606b867e7bafee0d7b7f7c9a92966faee0010163bdb8e00f0b498a0e482, block_hash=0x0e94a0430d49ade4563dbc5000e43be7f66ea39a9fcf96c82cc1aa5521dc7528) - 0 XBR token approved (on-chain) from owner 0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9 to spender 0xC89Ce4735882C9F0f0FE26686c53074E09B0D550)
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] <TokenApproval>(tx_hash=0x4cf7c606b867e7bafee0d7b7f7c9a92966faee0010163bdb8e00f0b498a0e482) record already stored in database.
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] _process_Network_ChannelCreated processing block 85 / txn 0x4cf7c606b867e7bafee0d7b7f7c9a92966faee0010163bdb8e00f0b498a0e482 with args AttributeDict({'marketId': b'\xa1\xb8\xd6t\x1a\xe8I \x17\xfa\xfd\x8dO\x8bg\xa2', 'sender': '0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9', 'delegate': '0xd03ea8624C8C5987235048901fB614fDcA89b117', 'recipient': '0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0', 'channel': '0x79e7654EaAE77cDFF937EC7b6F3156F7dEa4fC4C', 'channelType': 2})
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] _process_Network_ChannelCreated running:
    2020-02-05T12:15:00+0100 [XBRMrktMkr  22255] <Channel>(channel=0x79e7654eaae77cdff937ec7b6f3156f7dea4fc4c) already stored (type=2)
