# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

from eth_account import Account

__all__ = ('ACCOUNTS', 'OWNER', 'MARKETS')

_INITDATA = [
    ('0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1',
     '0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d', 'crossbar',
     'XBR Smart Contracts Developers (deployer and owner).'),
    ('0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0',
     '0x6cbed15c793ce57650b9877cf6fa156fbef513c4e6134f022a85b1ffdd59b2a1', 'seller1',
     'Example XBR Seller (service provider).'),
    ('0x22d491bde2303f2f43325b2108d26f1eaba1e32b',
     '0x6370fd033278c143179d81c5526140625662b8daa446c22ee2d73db3707e620c', 'buyer1',
     'Example XBR Buyer (service consumer).'),
    ('0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d',
     '0x646f1ce2fdad0e6deeeb5c7e8e5543bdde65e86029e2fd9fc169899c440a7913', 'marketop1',
     'Example XBR Market (marketplace operator).'),

    # ABPy seller
    ('0xd03ea8624C8C5987235048901fB614fDcA89b117',
     '0xadd53f9a7e588d003326d1cbf9e4a43c061aadd9bc938c843a79e7b4fd2ad743', 'seller1-delegate1',
     'XBR Seller 1 Delegate 1'),

    # ABPy buyer
    ('0x95cED938F7991cd0dFcb48F0a06a40FA1aF46EBC',
     '0x395df67f0c2d2d9fe1ad08d1bc8b6627011959b79c53d7dd6a3536a33ab8a4fd', 'buyer1-delegate1', 'XBR Buyer 1 Delegate 1'
     ),

    # Market Maker
    ('0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9',
     '0xe485d098507f54e7733a205420dfddbe58db035fa577fc294ebd14db90767a52', 'marketop1-marketmaker1',
     'XBR Market Maker 1 (of marketop1)'),

    # ABJS NodeJS seller
    ('0x28a8746e75304c0780E011BEd21C72cD78cd535E',
     '0xa453611d9419d0e56f499079478fd72c37b251a94bfde4d19872c44cf65386e3', 'seller1-delegate2',
     'XBR Seller 1 Delegate 2'),

    # ABJS NodeJS buyer
    ('0xACa94ef8bD5ffEE41947b4585a84BdA5a3d3DA6E',
     '0x829e924fdf021ba3dbbc4225edfece9aca04b929d6e75613329ca6f1d31c0bb4', 'buyer1-delegate2', 'XBR Buyer 1 Delegate 2'
     ),
    ('0x1dF62f291b2E969fB0849d99D9Ce41e2F137006e',
     '0xb0057716d5917badaf911b193b12b910811c1497b5bada8d7711f758981c3773', 'marketop2',
     'Example XBR Market (marketplace operator).'),
    ('0x610Bb1573d1046FCb8A70Bbbd395754cD57C2b60',
     '0x77c5495fbb039eed474fc940f29955ed0531693cc9212911efd35dff0373153f', 'marketop2-marketmaker1',
     'XBR Market Maker 1 (of marketop2)'),
    ('0x855FA758c77D68a04990E992aA4dcdeF899F654A',
     '0xd99b5b29e6da2528bf458b26237a6cf8655a3e3276c1cdc0de1f98cefee81c01', 'seller2',
     'Example XBR Seller (service provider).'),
    ('0xfA2435Eacf10Ca62ae6787ba2fB044f8733Ee843',
     '0x9b9c613a36396172eab2d34d72331c8ca83a358781883a535d2941f66db07b24', 'buyer2',
     'Example XBR Buyer (service consumer).'),

    # ABJS Browser seller
    ('0x64E078A8Aa15A41B85890265648e965De686bAE6',
     '0x0874049f95d55fb76916262dc70571701b5c4cc5900c0691af75f1a8a52c8268', 'seller2-delegate1',
     'XBR Seller Delegate 1 (of seller2)'),

    # ABJS Browser buyer
    ('0x2F560290FEF1B3Ada194b6aA9c40aa71f8e95598',
     '0x21d7212f3b4e5332fd465877b64926e3532653e2798a11255a46f533852dfe46', 'buyer2-delegate1',
     'XBR Buyer Delegate 1 (of buyer2)'),
    ('0xf408f04F9b7691f7174FA2bb73ad6d45fD5d3CBe',
     '0x47b65307d0d654fd4f786b908c04af8fface7710fc998b37d219de19c39ee58c', 'seller3',
     'Example XBR Seller (service provider).'),
    ('0x66FC63C2572bF3ADD0Fe5d44b97c2E614E35e9a3',
     '0x66109972a14d82dbdb6894e61f74708f26128814b3359b64f8b66565679f7299', 'buyer3',
     'Example XBR Buyer (service consumer).'),
    ('0xF0D5BC18421fa04D0a2A2ef540ba5A9f04014BE3',
     '0x2eac15546def97adc6d69ca6e28eec831189baa2533e7910755d15403a0749e8', 'seller3-delegate1',
     'XBR Seller Delegate 3 (of seller1)'),
    ('0x325A621DeA613BCFb5B1A69a7aCED0ea4AfBD73A',
     '0x2e114163041d2fb8d45f9251db259a68ee6bdbfd6d10fe1ae87c5c4bcd6ba491', 'buyer3-delegate1',
     'XBR Buyer Delegate 3 (of buyer1)'),
]

ACCOUNTS = {}
for adr, privkey, name, notes in _INITDATA:
    ACCOUNTS[name] = Account.privateKeyToAccount(privkey)
OWNER = ACCOUNTS['crossbar']

MARKETS = [
    {
        'id':
        '0xa1b8d6741ae8492017fafd8d4f8b67a2',
        'owner':
        ACCOUNTS['marketop1'].address,
        'maker':
        ACCOUNTS['marketop1-marketmaker1'].address,
        'terms':
        '',
        'meta':
        '',
        'providerSecurity':
        0,
        'consumerSecurity':
        0,
        'marketFee':
        0,
        'actors': [
            # seller 1
            {
                'addr':
                ACCOUNTS['seller1'].address,
                'type':
                1,
                'meta':
                '',
                'amount':
                1000 * 10**18,
                'delegates': [
                    # ABPy seller
                    ACCOUNTS['seller1-delegate1'].address,

                    # ABJS NodeJS seller
                    ACCOUNTS['seller1-delegate2'].address,
                ]
            },
            # buyer 1
            {
                'addr':
                ACCOUNTS['buyer1'].address,
                'type':
                2,
                'meta':
                '',
                'amount':
                500 * 10**18,
                'delegates': [
                    # ABPy buyer
                    ACCOUNTS['buyer1-delegate1'].address,

                    # ABJS NodeJS buyer
                    ACCOUNTS['buyer1-delegate2'].address,
                ]
            },
            # seller 2
            {
                'addr': ACCOUNTS['seller2'].address,
                'type': 1,
                'meta': '',
                'amount': 1000 * 10**18,
                'delegates': [
                    # ABJS Browser seller
                    ACCOUNTS['seller2-delegate1'].address,
                ]
            },
            # buyer 2
            {
                'addr': ACCOUNTS['buyer2'].address,
                'type': 2,
                'meta': '',
                'amount': 500 * 10**18,
                'delegates': [
                    # ABJS Browser buyer
                    ACCOUNTS['buyer2-delegate1'].address,
                ]
            },
            # seller 3
            {
                'addr': ACCOUNTS['seller3'].address,
                'type': 1,
                'meta': '',
                'amount': 1000 * 10**18,
                'delegates': [
                    ACCOUNTS['seller3-delegate1'].address,
                ]
            },
            # buyer 3
            {
                'addr': ACCOUNTS['buyer3'].address,
                'type': 2,
                'meta': '',
                'amount': 500 * 10**18,
                'delegates': [
                    ACCOUNTS['buyer3-delegate1'].address,
                ]
            },
        ]
    },
    # {
    #     'id': '0x4e0ae926edbecce1d983bea725f749df',
    #     'owner': ACCOUNTS['marketop2'].address,
    #     'maker': ACCOUNTS['marketop2-marketmaker1'].address,
    #     'terms': '',
    #     'meta': '',
    #     'providerSecurity': 0,
    #     'consumerSecurity': 0,
    #     'marketFee': 0,
    #     'actors': [
    #         {
    #             'addr': ACCOUNTS['seller2'].address,
    #             'type': 1,
    #             'meta': '',
    #             'amount': 1000 * 10 ** 18,
    #             'delegates': [
    #                 ACCOUNTS['seller2-delegate1'].address,
    #             ]
    #         },
    #         {
    #             'addr': ACCOUNTS['buyer2'].address,
    #             'type': 2,
    #             'meta': '',
    #             'amount': 500 * 10 ** 18,
    #             'delegates': [
    #                 ACCOUNTS['buyer2-delegate1'].address,
    #             ]
    #         },
    #     ]
    # },
]
