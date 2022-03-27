# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import sys
import argparse

import txaio
txaio.use_twisted()

import web3
import autobahn
from autobahn import xbr


def main(accounts):
    print('\nTest accounts - ETH/XBR balances and XBR data markets:\n')
    for acct in accounts:
        balance_eth = w3.eth.getBalance(acct)
        balance_xbr = xbr.xbrtoken.functions.balanceOf(acct).call()
        count_markets = xbr.xbrmarket.functions.countMarketsByOwner(acct).call()

        print('acct {}: {:>28} ETH, {:>28} XBR, {:>4} markets'.format(acct, balance_eth, balance_xbr, count_markets))

    print()


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
    main(w3.eth.accounts)
