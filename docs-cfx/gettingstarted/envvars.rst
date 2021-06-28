Environment Variables
=====================

Important environment variables that can be used to control Crossbar.io/CrossbarFX behavior:

============================    ====================    ===================================================================================================================================
Variable                        Personality             Description
============================    ====================    ===================================================================================================================================
``CROSSBAR_REACTOR``            Crossbar.io
``CROSSBAR_PERSONALITY``        Crossbar.io
``CROSSBAR_DIR``                Crossbar.io
``COVERAGE_PROCESS_START``      Crossbar.io
``CROSSBAR_FABRIC_URL``         CrossbarFX (Edge)       Configure uplink management URL for node, eg ``wss://access.xbr.network/ws`` or ``ws://localhost:9000/ws``.
``XBR_DEBUG_TOKEN_ADDR``        CrossbarFX (Edge)
``XBR_DEBUG_NETWORK_ADDR``      CrossbarFX (Edge)
``IPFS_GATEWAY_URL``            CrossbarFX (Edge)       Configure an IPFS gateway URL. Default: ``https://ipfs.infura.io:5001``
``ETCD_URL``                    CrossbarFX (Master)
``MAILGUN_KEY``                 CrossbarFX (Master)
``MAILGUN_URL``                 CrossbarFX (Master)
``WEB3_PROVIDER_URI``           CrossbarFX (Edge)       `Web3 automatic provider detection <https://web3py.readthedocs.io/en/stable/providers.html#provider-via-environment-variable>`__
``INFURA_API_KEY``              CrossbarFX (Edge)       `Web3 Infura mainnet auto configuration <https://web3py.readthedocs.io/en/stable/providers.html#infura-mainnet>`__
============================    ====================    ===================================================================================================================================
