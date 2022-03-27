# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import sys
import argparse

import txaio
txaio.use_twisted()

import web3
import autobahn
from autobahn import xbr

from config1 import ACCOUNTS, OWNER, MARKETS


def main(accounts, owner):
    print('Using XBR token contract address: {}'.format(xbr.xbrtoken.address))
    print('Using XBR network contract address: {}'.format(xbr.xbrnetwork.address))

    #
    # Register XBR network members
    #
    print('-' * 120)
    for ak in [
            'marketop1',
            'seller1',
            'seller3',
            'buyer1',
            'buyer3',
            'marketop2',
            'seller2',
            'buyer2',
    ]:
        acct = accounts[ak]
        joined, eula, profile, level, _ = xbr.xbrnetwork.functions.members(acct.address).call()
        if not joined:
            eula = xbr.xbrnetwork.functions.eula().call()
            profile = ''
            xbr.xbrnetwork.functions.registerMember(eula, profile).transact({'from': acct.address, 'gas': 200000})
            print('New member {} address registered in the XBR Network (eula={}, profile={})'.format(
                acct.address, eula, profile))
        else:
            print('Address {} is already a member (level={}, eula={}, profile={})'.format(
                acct.address, level, eula, profile))

    #
    # Open XBR markets and join XBR market actors
    #
    print('-' * 120)
    for market in MARKETS:

        _created, _marketSeq, _owner, _coin, _terms, _terms, _maker, _providerSecurity, _consumerSecurity, _marketFee, _signature = xbr.xbrmarket.functions.markets(
            market['id']).call()

        gas = 2000000
        if _created:
            if _owner != market['owner']:
                print('Market {} already exists, but has wrong owner!! Expected {}, but owner is {}'.format(
                    market['id'], market['owner'], _owner))
            else:
                print('Market {} already exists and has expected owner {}'.format(market['id'], _owner))
        else:
            providerSecurity = market['providerSecurity'] * 10**18
            consumerSecurity = market['consumerSecurity'] * 10**18
            coin = xbr.xbrtoken.address
            print('Using coin {}'.format(coin))

            xbr.xbrmarket.functions.createMarket(market['id'], coin, market['terms'], market['meta'], market['maker'],
                                                 providerSecurity, consumerSecurity, market['marketFee']).transact({
                                                     'from':
                                                     market['owner'],
                                                     'gas':
                                                     gas
                                                 })

            print('Market {} created with owner {} and market maket {}'.format(market['id'], market['owner'],
                                                                               market['maker']))

        print('Market actors:')
        for actor in market['actors']:

            is_actor = xbr.xbrmarket.functions.isActor(market['id'], actor['addr'], actor['type']).call()
            if is_actor:
                print('   Account {} is already actor (type={}) in the market'.format(actor['addr'], actor['type']))
            else:
                channel_amount = actor['amount']
                if channel_amount:
                    result = xbr.xbrtoken.functions.approve(xbr.xbrnetwork.address, channel_amount).transact({
                        'from':
                        actor['addr'],
                        'gas':
                        gas
                    })
                    print('   Approved market security amount {})'.format(int(channel_amount / 10**18)))
                    if not result:
                        print('   Failed to allow transfer of {} tokens for market security!\n{}'.format(
                            int(channel_amount / 10**18), result))
                    else:
                        print('   Allowed transfer of {} XBR from {} to {} as security for joining market'.format(
                            int(channel_amount / 10**18), actor['addr'], xbr.xbrnetwork.address))

                security_bytes = xbr.xbrmarket.functions.joinMarket(market['id'], actor['type'],
                                                                    actor['meta']).transact({
                                                                        'from': actor['addr'],
                                                                        'gas': gas
                                                                    })
                if security_bytes:
                    security = web3.Web3.toInt(security_bytes)

                    print('   Actor {} joined market {} as actor type {} (meta {}) with security {}!'.format(
                        actor['addr'], market['id'], actor['type'], actor['meta'], security))


if __name__ == '__main__':
    if not xbr.HAS_XBR:
        raise RuntimeError('fatal: missing xbr support in autobahn (install using "pip install autobahn [xbr]")')
    else:
        print('using autobahn v{}, web3.py v{}'.format(autobahn.__version__, web3.__version__))

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--gateway',
        dest='gateway',
        type=str,
        default=None,
        help='Ethereum HTTP gateway URL or None for auto-select (default: -, means let web3 auto-select).')

    args = parser.parse_args()

    if args.gateway:
        w3 = web3.Web3(web3.Web3.HTTPProvider(args.gateway))
    else:
        # using automatic provider detection:

        # we need to do this because mypy is stupid:
        from web3.auto import w3 as _w3
        w3 = _w3

    # check we are connected, and check network ID
    if not w3.isConnected():
        print('could not connect to Web3/Ethereum at: {}'.format(args.gateway or 'auto'))
        sys.exit(1)
    else:
        print('connected via provider "{}"'.format(args.gateway or 'auto'))

    # set new provider on XBR library
    xbr.setProvider(w3)

    # now enter main ..
    main(ACCOUNTS, OWNER)
