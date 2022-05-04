##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import os
import binascii
from binascii import b2a_hex
from pprint import pformat
import uuid
from typing import Optional, List

import cfxdb.xbr
import cfxdb.xbr.actor
import cfxdb.xbr.block
import cfxdb.xbrmm.channel
import cfxdb.xbr.market
import cfxdb.xbr.member
import cfxdb.xbrmm.offer
import cfxdb.xbr.schema
import cfxdb.xbr.token
import cfxdb.xbrmm.transaction

import pyqrcode
import numpy as np

import web3
import eth_keys
from eth_account import Account

import requests
from requests.exceptions import ConnectionError
from hexbytes import HexBytes

import txaio

txaio.use_twisted()  # noqa
from txaio import time_ns

from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure
from twisted.internet.threads import deferToThread

from autobahn import wamp
from autobahn.twisted.component import Component
from autobahn.wamp import component
from autobahn.wamp.types import RegisterOptions, PublishOptions
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.message import _URI_PAT_STRICT_LAST_EMPTY
from autobahn.wamp.types import CallDetails
from autobahn.xbr import unpack_uint256, pack_uint256, recover_eip712_consent, \
    is_address
from autobahn.util import without_0x

from crossbar._util import hl, hlid, hltype
from crossbar.edge.worker.xbr._util import hlval, hlcontract
from crossbar.edge.worker.xbr._authenticator import Authenticator

from autobahn import xbr
import zlmdb
import cfxdb
from cfxdb.xbr import ActorType

__all__ = ('MarketMaker', )


def extract_member_adr(details: CallDetails):
    """
    Extract the XBR network member adress from the WAMP session authid
    (eg ``member_oid==0x90f8bf6a479f320ead074411a4b0e7944ea8c9c1`` from ``authid=="member-0x90f8bf6a479f320ead074411a4b0e7944ea8c9c1"``

    :param details: Call details.

    :return: Extracted XBR network member address.
    """
    if details and details.caller_authrole == 'user' and details.caller_authid:
        adr = details.caller_authid[7:]
        return without_0x(adr)
    else:
        raise RuntimeError('no XBR member adress in call details\n{}'.format(details))


class MarketMaker(object):
    """
    XBR Market Maker. This is the off-chain delegate software component running for the market operator.
    A market maker is always started for a specific XBR data market identified by the market ID (a 16 bytes UUID)
    which is stored on-chain (inside the ``XBRNetwork`` contract). There can be at most one market maker
    running for a given XBR data market.

    The following WAMP events are published by the market maker:

    * ``xbr.marketmaker.on_status``
    * ``xbr.marketmaker.delegate.<seller-delegate-adr>.on_offer_placed``
    * ``xbr.marketmaker.delegate.<seller-delegate-adr>.on_offer_revoked``
    * ``xbr.marketmaker.delegate.<buyer-delegate-adr>.on_payment_channel_open``
    * ``xbr.marketmaker.delegate.<buyer-delegate-adr>.*``
    * ``xbr.marketmaker.delegate.<seller-delegate-adr>.on_paying_channel_open``
    * ``xbr.marketmaker.delegate.<seller-delegate-adr>.*``

    .. note::

        The market ID is *not* part of the URIs above since each XBR data market is run on its own
        dedicated realm, so there is no need to duplicate that information in the URI.
    """

    STATUS_NONE = 0
    STATUS_RUNNING = 1
    STATUS_SHUTDOWN_IN_PROGRESS = 2
    STATUS_STOPPED = 3

    log = txaio.make_logger()

    def __init__(self, controller, maker_id, config, xbrmm_db, ipfs_files_dir):
        """

        :param controller: Controller session (WAMP session from the native worker on node router)
        """
        self._inventory = {}

        # market maker ID and configuration
        self._id = maker_id
        self._config = config
        self._status = self.STATUS_NONE

        # market maker private Ethereum key file
        keypath = os.path.abspath(config['key'])
        if os.path.exists(keypath):
            with open(keypath, 'rb') as f:
                self._eth_privkey_raw = f.read()
                assert type(self._eth_privkey_raw) == bytes and len(self._eth_privkey_raw) == 32
                self.log.info('Existing XBR Market Maker Ethereum private key loaded from "{keypath}"',
                              keypath=hlid(keypath))
        else:
            self._eth_privkey_raw = os.urandom(32)
            with open(keypath, 'wb') as f:
                f.write(self._eth_privkey_raw)
                self.log.info('New XBR Market Maker Ethereum private key generated and stored as {keypath}',
                              keypath=hlid(keypath))

        # make sure the private key file has correct permissions
        if os.stat(config['key']).st_mode & 511 != 384:  # 384 (decimal) == 0600 (octal)
            os.chmod(config['key'], 384)
            self.log.info('File permissions on market maker private Ethereum key fixed')

        # make a private key object from the raw private key bytes
        self._eth_privkey = eth_keys.keys.PrivateKey(self._eth_privkey_raw)
        self._eth_acct = Account.privateKeyToAccount(self._eth_privkey_raw)

        # get the canonical address of the account
        self._eth_adr_raw = self._eth_privkey.public_key.to_canonical_address()
        self._eth_adr = web3.Web3.toChecksumAddress(self._eth_adr_raw)
        qr = pyqrcode.create(self._eth_adr, error='L', mode='binary')
        self.log.info('XBR Market Maker Ethereum (canonical/checksummed) address is {eth_adr}:\n{qrcode}',
                      eth_adr=hlid(self._eth_adr),
                      qrcode=qr.terminal())

        # market maker database
        cfg = self._config['database']

        dbpath = cfg.get('path', None)
        assert type(dbpath) == str, "dbpath must be a string, was {}".format(type(dbpath))

        maxsize = cfg.get('maxsize', 1024 * 2**20)
        assert type(maxsize) == int, "maxsize must be an int, was {}".format(type(maxsize))
        # allow maxsize 128kiB to 128GiB
        assert maxsize >= 128 * 1024 and maxsize <= 128 * 2**30, "maxsize must be >=128kiB and <=128GiB, was {}".format(
            maxsize)

        readonly = cfg.get('readonly', False)
        assert type(readonly) == bool, "readonly must be a bool, was {}".format(type(readonly))

        sync = cfg.get('sync', True)
        assert type(sync) == bool, "sync must be a bool, was {}".format(type(sync))

        self._db = zlmdb.Database(dbpath=dbpath, maxsize=maxsize, readonly=readonly, sync=sync)
        self._db.__enter__()
        self._schema = cfxdb.xbr.Schema.attach(self._db)

        self.log.info('Attached XBR Market Maker database [dbpath="{dbpath}", maxsize={maxsize}]',
                      dbpath=hlid(dbpath),
                      maxsize=hlid(maxsize))

        self._xbrmm_db = xbrmm_db
        self._xbr = cfxdb.xbr.Schema.attach(self._xbrmm_db)

        # controller session (an ApplicationSession object)
        self._controller_session = controller
        self._reactor = self._controller_session._reactor

        # target realm (where the maker should do its duty)
        connection = self._config['connection']
        transport = connection['transport']
        realm = connection['realm']

        # market maker component on the target realm
        market = Component(transports=[transport], realm=realm)

        # blockchain gateway
        self._w3 = controller._w3
        self._chain_id = self._controller_session._chain_id

        # for EIP712 signatures, we include the chain ID and on-chain contract address into the
        # data to be signed to avoid replay attacks. this is filled in start() ..
        self._verifying_chain_id = None
        self._verifying_contract_adr = None
        self._verifying_contract = None

        # URI prefix under which the market maker registers procedures and publishes
        # event in the managed data market.
        self._uri_prefix = 'xbr.marketmaker.'

        self._ipfs_files_dir = ipfs_files_dir

        @market.on_join
        async def market_attached(session, details):
            # FIXME: maker is attached to market: initialize

            self.log.info(
                'XBR Market Maker session attached to data market (realm="{realm}", session="{session}", authid="{authid}", authrole="{authrole}")',
                realm=hlid(details.realm),
                session=hlid(details.session),
                authid=hlid(details.authid),
                authrole=hlid(details.authrole))

            regs = await session.register(
                self,
                prefix=self._uri_prefix,
                options=RegisterOptions(details_arg='details'),
            )
            self.log.info('XBR Market Maker registered {len_reg} procedures in data market realm "{realm}"',
                          len_reg=hlid(len(regs)),
                          realm=hlid(details.realm))
            for reg in regs:
                if isinstance(reg, Failure):
                    self.log.error("Failed to register: {f}", f=reg, log_failure=reg)
                else:
                    self.log.debug('  {proc}', proc=reg.procedure)

            regs = await session.register(Authenticator(xbrmm_db, session, self._reactor, self._market_oid),
                                          options=RegisterOptions(details_arg='call_details'))
            for reg in regs:
                self.log.info('{klass} registered procedure {proc}', klass=self.__class__.__name__, proc=reg.procedure)

            self._market_session = session

        @market.on_leave
        def market_detached(session, details):
            # FIXME: maker
            self.log.info(
                'XBR Market Maker session detached from data market (realm="{realm}", reason="{reason}", message="{message}")',
                realm=hlid(session._realm),
                reason=hlid(details.reason),
                message=hlid(details.message))

        self._market = market
        self._market_session = None

        # FIXME: deprecate market_id (replace with market_oid)
        self._market_id = None
        self._market_oid = None

        self._owner = None
        self._coin = None

    @property
    def db(self):
        """
        Market maker database.

        :return: Handle to the embedded zLMDB database.
        :rtype: object
        """
        return self._db

    @property
    def schema(self):
        """
        Market maker database schema.

        :return: Schema of the embedded zLMDB database.
        :rtype: object
        """
        return self._schema

    @property
    def address(self):
        """
        Market maker address.

        :return: Checksum address of market maker.
        :rtype: str
        """
        return self._eth_adr

    @property
    def market(self):
        """
        Market ID.

        :return: UUID of market.
        :rtype: uuid.UUID
        """
        return self._market_oid

    @property
    def owner(self):
        """
        Market owner address.

        :return: Checksum address of market owner.
        :rtype: str
        """
        return self._owner

    @property
    def coin(self):
        """
        Market coin address.

        :return: Checksum address of market coin (an ERC20 token).
        :rtype: str
        """
        return self._coin

    def _send_openChannel(self, ctype: int, openedAt: int, marketId: bytes, channelId: bytes, actor: bytes,
                          delegate: bytes, marketmaker: bytes, recipient: bytes, amount: int, signature: bytes):
        # FIXME: estimate gas required for call
        gas = 1300000
        gasPrice = self._w3.toWei('10', 'gwei')

        # each submitted transaction must contain a nonce, which is obtained by the on-chain transaction number
        # for this account, including pending transactions (I think ..;) ..
        nonce = self._w3.eth.getTransactionCount(self._eth_acct.address, block_identifier='pending')
        self.log.info('{klass}._send_openChannel[1/4] - Ethereum transaction nonce: nonce={nonce}',
                      klass=hl(self.__class__.__name__),
                      nonce=nonce)

        # serialize transaction raw data from contract call and transaction settings
        raw_transaction = xbr.xbrchannel.functions.openChannel(
            ctype, openedAt, marketId, channelId, actor, delegate, marketmaker, recipient, amount,
            signature).buildTransaction({
                'from': self._eth_acct.address,
                'gas': gas,
                'gasPrice': gasPrice,
                'chainId': self._chain_id,  # https://stackoverflow.com/a/57901206/884770
                'nonce': nonce,
            })
        self.log.info(
            '{klass}._send_openChannel[2/4] - Ethereum transaction created: raw_transaction=\n{raw_transaction}\n',
            klass=hl(self.__class__.__name__),
            raw_transaction=raw_transaction)

        # compute signed transaction from above serialized raw transaction
        signed_txn = self._w3.eth.account.sign_transaction(raw_transaction, private_key=self._eth_privkey_raw)
        self.log.info('{klass}._send_openChannel[3/4] - Ethereum transaction signed: signed_txn=\n{signed_txn}\n',
                      klass=hl(self.__class__.__name__),
                      signed_txn=hlval(binascii.b2a_hex(signed_txn.rawTransaction).decode()))

        # now send the pre-signed transaction to the blockchain via the gateway ..
        # https://web3py.readthedocs.io/en/stable/web3.eth.html  # web3.eth.Eth.sendRawTransaction
        txn_hash = self._w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        txn_hash = bytes(txn_hash)
        self.log.info('{klass}._send_openChannel[4/4] - Ethereum transaction submitted: txn_hash=0x{txn_hash}',
                      klass=hl(self.__class__.__name__),
                      txn_hash=hlval(binascii.b2a_hex(txn_hash).decode()))

        return txn_hash

    def _send_closeChannel(self, channelId: bytes, closeAt: int, channelSeq: int, balance: int, isFinal: bool,
                           delegateSignature: bytes, marketmakerSignature: bytes):
        # FIXME: estimate gas required for call
        gas = 1300000
        gasPrice = self._w3.toWei('10', 'gwei')

        # each submitted transaction must contain a nonce, which is obtained by the on-chain transaction number
        # for this account, including pending transactions (I think ..;) ..
        nonce = self._w3.eth.getTransactionCount(self._eth_acct.address, block_identifier='pending')
        self.log.info('{klass}._send_closeChannel[1/4] - Ethereum transaction nonce: nonce={nonce}',
                      klass=hl(self.__class__.__name__),
                      nonce=nonce)

        # serialize transaction raw data from contract call and transaction settings
        raw_transaction = xbr.xbrchannel.functions.closeChannel(
            channelId, closeAt, channelSeq, balance, isFinal, delegateSignature,
            marketmakerSignature).buildTransaction({
                'from': self._eth_acct.address,
                'gas': gas,
                'gasPrice': gasPrice,
                'chainId': self._chain_id,  # https://stackoverflow.com/a/57901206/884770
                'nonce': nonce,
            })
        self.log.info(
            '{klass}._send_closeChannel[2/4] - Ethereum transaction created: raw_transaction=\n{raw_transaction}\n',
            klass=hl(self.__class__.__name__),
            raw_transaction=raw_transaction)

        # compute signed transaction from above serialized raw transaction
        signed_txn = self._w3.eth.account.sign_transaction(raw_transaction, private_key=self._eth_privkey_raw)
        self.log.info('{klass}._send_closeChannel[3/4] - Ethereum transaction signed: signed_txn=\n{signed_txn}\n',
                      klass=hl(self.__class__.__name__),
                      signed_txn=hlval(binascii.b2a_hex(signed_txn.rawTransaction).decode()))

        # now send the pre-signed transaction to the blockchain via the gateway ..
        # https://web3py.readthedocs.io/en/stable/web3.eth.html  # web3.eth.Eth.sendRawTransaction
        txn_hash = self._w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        txn_hash = bytes(txn_hash)
        self.log.info('{klass}._send_closeChannel[4/4] - Ethereum transaction submitted: txn_hash=0x{txn_hash}',
                      klass=hl(self.__class__.__name__),
                      txn_hash=hlval(binascii.b2a_hex(txn_hash).decode()))

        return txn_hash

    def _send_setConsent(self, marketId: bytes, delegate: bytes, delegateType: int, apiCatalog: bytes, consent: bool,
                         servicePrefix: str):
        # FIXME: estimate gas required for call
        gas = 1300000
        gasPrice = self._w3.toWei('10', 'gwei')

        # each submitted transaction must contain a nonce, which is obtained by the on-chain transaction number
        # for this account, including pending transactions (I think ..;) ..
        nonce = self._w3.eth.getTransactionCount(self._eth_acct.address, block_identifier='pending')
        self.log.info('{klass}._send_setConsent[1/4] - Ethereum transaction nonce: nonce={nonce}',
                      klass=hl(self.__class__.__name__),
                      nonce=nonce)

        # serialize transaction raw data from contract call and transaction settings
        raw_transaction = xbr.xbrmarket.functions.setConsent(
            marketId, delegate, delegateType, apiCatalog, consent, servicePrefix).buildTransaction({
                'from':
                self._eth_acct.address,
                'gas':
                gas,
                'gasPrice':
                gasPrice,
                'chainId':
                self._chain_id,  # https://stackoverflow.com/a/57901206/884770
                'nonce':
                nonce
            })
        self.log.info(
            '{klass}._send_setConsent[2/4] - Ethereum transaction created: raw_transaction=\n{raw_transaction}\n',
            klass=hl(self.__class__.__name__),
            raw_transaction=raw_transaction)

        # compute signed transaction from above serialized raw transaction
        signed_txn = self._w3.eth.account.sign_transaction(raw_transaction, private_key=self._eth_privkey_raw)
        self.log.info('{klass}._send_setConsent[3/4] - Ethereum transaction signed: signed_txn=\n{signed_txn}\n',
                      klass=hl(self.__class__.__name__),
                      signed_txn=hlval(binascii.b2a_hex(signed_txn.rawTransaction).decode()))

        # now send the pre-signed transaction to the blockchain via the gateway ..
        # https://web3py.readthedocs.io/en/stable/web3.eth.html  # web3.eth.Eth.sendRawTransaction
        txn_hash = self._w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        txn_hash = bytes(txn_hash)
        self.log.info('{klass}._send_setConsent[4/4] - Ethereum transaction submitted: txn_hash=0x{txn_hash}',
                      klass=hl(self.__class__.__name__),
                      txn_hash=hlval(binascii.b2a_hex(txn_hash).decode()))

        return txn_hash

    @inlineCallbacks
    def start(self):
        """

        :return:
        """
        self.log.info('{klass}.start() ..', klass=self.__class__.__name__)

        # get the market the market maker is supposed to work for:
        xbr_market_id = xbr.xbrmarket.functions.marketsByMaker(self._eth_adr).call()
        if xbr_market_id != b'\x00' * 16:
            assert (len(xbr_market_id) == 16)
            self._market_id = xbr_market_id
            self._market_oid = uuid.UUID(bytes=xbr_market_id)
            self.log.info('Ok, {mmsg} and will be working for market {market_oid}.',
                          mmsg=hl('XBR market maker is associated on-chain', bold=True),
                          market_oid=hlid(self._market_oid))
        else:
            raise RuntimeError('FATAL: market maker is not associated with any market')

        self._owner = xbr.xbrmarket.functions.getMarketOwner(self._market_oid.bytes).call()

        # FIXME: cannot serialize unknown object: <Function getMarketCoin(bytes16) ..
        # self._coin = xbr.xbrmarket.functions.getMarketCoin(self._market_oid.bytes)

        self._verifying_chain_id = xbr.xbrnetwork.functions.verifyingChain().call()
        self._verifying_contract_adr = xbr.xbrnetwork.functions.verifyingContract().call()
        self._verifying_contract = binascii.a2b_hex(self._verifying_contract_adr[2:])

        self.log.info(
            'Verifying chain ID {verifying_chain_id} and verifying contract address {verifying_contract_adr}',
            verifying_chain_id=hlid(self._verifying_chain_id),
            verifying_contract_adr=hlid(self._verifying_contract_adr))

        @inlineCallbacks
        def done(reactor, result):
            self.log.info('market maker component done: {result}', result=result)
            self._status = MarketMaker.STATUS_RUNNING
            if self._market_session:
                yield self._market_session.publish('{}on_status'.format(self._uri_prefix),
                                                   self._market_id,
                                                   self._status,
                                                   options=PublishOptions(acknowledge=True))

        d = component._run(self._reactor, self._market, done)

        yield d

    @inlineCallbacks
    def stop(self):
        """

        :return:
        """
        self.log.info('{klass}.stop() ..', klass=self.__class__.__name__)

        self._status = MarketMaker.STATUS_SHUTDOWN_IN_PROGRESS
        if self._market_session:
            yield self._market_session.publish('{}on_status'.format(self._uri_prefix),
                                               self._id,
                                               self._status,
                                               options=PublishOptions(acknowledge=True))

        self._status = MarketMaker.STATUS_STOPPED
        if self._market_session:
            yield self._market_session.publish('{}on_status'.format(self._uri_prefix),
                                               self._id,
                                               self._status,
                                               options=PublishOptions(acknowledge=True))
        self._id = None

    # FIXME: remove after refactoring
    @wamp.register(None, check_types=True)
    async def status(self, details: Optional[CallDetails]) -> dict:
        """
        Get market maker status and blockchain synchronization information.

        :param details: Caller details.
        :return: Market maker status and blockchain synchronization information.
        """
        def do_status():
            res = {
                'status': {
                    0: 'NONE',
                    1: 'RUNNING',
                    2: 'SHUTDOWN_IN_PROGRESS',
                    3: 'STOPPED'
                }.get(self._status, None),
                'current_block_no': self._w3.eth.blockNumber
            }

            # res['current_block'] = self._w3.eth.getBlock('latest')

            accounts = {}
            for account in self._w3.eth.accounts:
                accounts[account] = self._w3.eth.getBalance(account)

            res['accounts'] = accounts

            return res

        status = await deferToThread(do_status)
        return status

    @wamp.register(None, check_types=True)
    async def get_transaction_receipt(self, transaction: bytes, details: Optional[CallDetails] = None) -> dict:
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        def do_get_transaction_receipt(transaction: bytes):
            # get the full transaction receipt given the transaction hash
            receipt = self._w3.eth.getTransactionReceipt(transaction)
            return receipt

        r = await deferToThread(do_get_transaction_receipt, transaction)

        # copy over all information returned, all but two: "logs", "logsBloom"
        receipt = {}
        receipt['transactionHash'] = r['transactionHash']
        receipt['transactionIndex'] = r['transactionIndex']
        receipt['blockNumber'] = r['blockNumber']
        receipt['from'] = r['from']
        receipt['to'] = r['to']
        receipt['gasUsed'] = r['gasUsed']
        receipt['cumulativeGasUsed'] = r['cumulativeGasUsed']
        receipt['contractAddress'] = r['contractAddress']
        receipt['status'] = r['status']

        # transform HexBytes so the result can be serialized
        for k in receipt:
            if isinstance(receipt[k], HexBytes):
                receipt[k] = bytes(receipt[k])
        return receipt

    @wamp.register(None, check_types=True)
    async def get_gas_price(self, details: Optional[CallDetails] = None) -> bytes:
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        def do_get_gas_price():
            # FIXME: read from eth gas station
            return self._w3.toWei('10', 'gwei')

        gas_price = await deferToThread(do_get_gas_price)
        return gas_price

    @wamp.register(None, check_types=True)
    async def get_config(self, include_eula_text: bool = False, details: Optional[CallDetails] = None) -> dict:
        assert type(include_eula_text) == bool, 'include_eula_text must be bool, was {}'.format(
            type(include_eula_text))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        self.log.debug('{func}(include_eula_text={include_eula_text}, details={details})',
                       func=hltype(self.get_config),
                       include_eula_text=hlval(include_eula_text),
                       details=details)

        def do_get_config(include_eula_text=False):
            now = time_ns()
            chain_id = int(self._w3.net.version)

            # on-chain calls
            verifying_chain_id = int(xbr.xbrnetwork.functions.verifyingChain().call())
            verifying_contract_adr = str(xbr.xbrnetwork.functions.verifyingContract().call())
            eula_hash = str(xbr.xbrnetwork.functions.eula().call())

            # http request
            eula_url = 'https://raw.githubusercontent.com/crossbario/xbr-protocol/master/ipfs/xbr-eula/XBR-EULA.txt'
            if include_eula_text:
                resp = requests.get(eula_url)
                eula_text = resp.content.decode('utf8')
            else:
                eula_text = None

            result = {
                'now': now,
                'chain': chain_id,
                'verifying_chain_id': verifying_chain_id,
                'verifying_contract_adr': verifying_contract_adr,
                'contracts': {
                    'xbrtoken': str(xbr.xbrtoken.address),
                    'xbrnetwork': str(xbr.xbrnetwork.address),
                    'xbrcatalog': str(xbr.xbrcatalog.address),
                    'xbrmarket': str(xbr.xbrmarket.address),
                    'xbrchannel': str(xbr.xbrchannel.address),
                },
                'eula': {
                    'url': eula_url,
                    'hash': eula_hash,
                    'text': eula_text,
                },
                'coin': self.coin,
                'owner': self.owner,
                'market': str(self.market),
                'marketmaker': self.address,
            }
            self.log.debug('{func}::do_get_config() ->\n{result}',
                           func=hltype(self.get_config),
                           result=pformat(result))
            return result

        config = await deferToThread(do_get_config, include_eula_text=include_eula_text)
        self.log.debug('{func}() ->\n{result}', func=hltype(self.get_config), result=pformat(config))
        return config

    @wamp.register(None, check_types=True)
    async def get_status(self, details: Optional[CallDetails] = None) -> dict:
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        def do_get_status():
            now = time_ns()
            chain_id = int(self._w3.net.version)
            block_info = self._w3.eth.getBlock('latest')
            block_number = int(block_info['number'])
            block_hash = bytes(block_info['hash'])
            block_gas_limit = int(block_info['gasLimit'])
            status = {
                'now': now,
                'chain': chain_id,
                'block': {
                    'number': block_number,
                    'hash': block_hash,
                    'gas_limit': block_gas_limit,
                },
            }
            return status

        status = await deferToThread(do_get_status)
        status['status'] = self._status
        return status

    @wamp.register(None, check_types=True)
    async def place_offer(self,
                          key_id,
                          api_id,
                          uri,
                          valid_from,
                          delegate_adr,
                          delegate_signature,
                          privkey=None,
                          price=None,
                          categories=None,
                          expires=None,
                          copies=None,
                          provider_id=None,
                          details: Optional[CallDetails] = None):
        """
        Called by a XBR Provider (XBR Seller delegate) to offer a data encryption key for sale. A key is offered
        as applying to a specific API, and the key price, and the URI under which the data is provided must
        be specified.

        The offer can either use **uniform pricing** or **dynamic pricing**. With uniform pricing, a price must be
        specified. The price can be zero or more XBR tokens. With dynamic pricing (``price==None``), the market maker
        will call into the XBR seller delegate whenever quoted by a buyer, or to get a binding quotes requested
        by the market maker itself so ensure sufficicient balance before executing a key buying transaction for
        a buyer.

        Optionally, a seller (delegate) may specify app or user defined categories under which the key is to be
        offered. The category or categories allow buyers to filter offers for keys for data they might be interested in.

        Further, optionally a seller can specify a key expiration date as well as a maximum number of copies a
        key is to be sold.

        :param key_id: UUID of the data encryption key offered.
        :type key_id: bytes

        :param api_id: UUID of the API the encrypted data (this key is for) is provided under.
        :type api_id: bytes

        :param uri: URI (prefix) under which the data encrypted with the key offered is provided under.
        :type uri: str

        :param valid_from: Timestamp from which the offer is valid.
        :type valid_from: int

        :param delegate_adr: Seller delegate address.
        :type delegate_adr: bytes

        :param delegate_signature: Seller delegate signature.
        :type delegate_signature: bytes

        :param privkey: Optional actual data encryption private key sold. This is when the market maker is trusted
            with the actual selling (eg to save on the otherwise resulting calls into the seller delegate). When no
            private key is submitted with the offer, the market maker will call into the seller delegate during
            key buying transactions.
        :type privkey: bytes

        :param price: Price of data encryption key in XBR tokens.
        :type price: bytes

        :param categories: Optional user defined categories the specific data that is provided falls under.
        :type categories: dict

        :param expires: Optional data at which this offer expires (epoc time in ns).
        :type expires: int

        :param copies: Optional maximum number of times this data encryption key is to be sold or 0 for unlimited.
        :type copies: int

        :param details: Caller details. In this case XBR data providers (XBR seller delegates)
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Offer placement information, including offer ID assigned.
        :rtype: dict
        """
        assert type(key_id) == bytes and len(key_id) == 16, 'key_id must be bytes[16], but was "{}"'.format(key_id)
        assert type(api_id) == bytes and len(api_id) == 16, 'api_id must be bytes[16], but was "{}"'.format(api_id)
        assert type(uri) == str, 'uri must be str, but was "{}"'.format(uri)
        assert type(valid_from) == int, 'valid_from must be int, but was "{}"'.format(valid_from)
        assert type(delegate_adr) == bytes and len(
            delegate_adr) == 20, 'delegate_adr must be bytes[20], but was "{}"'.format(delegate_adr)
        assert type(delegate_signature) == bytes and len(
            delegate_signature) == 65, 'delegate_signature must be bytes[65]. but was "{}"'.format(delegate_signature)
        assert privkey is None or type(privkey) == bytes and len(
            privkey) == 32, 'privkey must be bytes[32], but was "{}"'.format(privkey)
        assert price is None or (type(price) == bytes
                                 and len(price) == 32), 'price must be bytes[32], but was "{}"'.format(price)
        assert categories is None or (
            type(categories) == dict and (type(k) == str for k in categories.keys()) and (type(v) == str
                                                                                          for v in categories.values())
        ), 'invalid categories type (must be dict) or category key or value type (must both be string)'
        assert expires is None or type(expires) == int, 'expires must be int, but was "{}"'.format(expires)
        assert copies is None or type(copies) == int, 'copies must be int, but was "{}"'.format(copies)

        try:
            key_id = uuid.UUID(bytes=key_id)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid key_id: {}'.format(str(e)))

        try:
            api_id = uuid.UUID(bytes=api_id)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid api_id: {}'.format(str(e)))

        if price is not None:
            price = unpack_uint256(price)

        assert details

        # prefix matching URI pattern
        uri_is_valid = _URI_PAT_STRICT_LAST_EMPTY.match(uri)
        # uri_is_valid = _URI_PAT_LOOSE_LAST_EMPTY.match(uri)
        if not uri_is_valid:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid uri (must be exact or prefix)')

        now = time_ns()
        max_future_time = now + (24 * 60 * 60 * 10**9)
        min_validity = 5 * 60 * 10**9
        # FIXME: ABJS!
        if False:
            if type(valid_from) != int or valid_from < (now - min_validity) or valid_from > max_future_time:
                raise ApplicationError('wamp.error.invalid_argument', 'invalid valid_from type or value')

        if expires is not None and (type(expires) != int or expires <= valid_from or expires > max_future_time or
                                    (expires - valid_from) < min_validity):
            raise ApplicationError('wamp.error.invalid_argument', 'invalid expires type or value')

        # FIXME: XBRSIG - check the supplied offer information to match the delegate signature according to the delegate address

        with self._db.begin(write=True) as txn:

            # sanity check that offer keys are unique
            offer_id = self._schema.idx_offer_by_key[txn, key_id]
            if offer_id:
                raise Exception('key already offered')

            # ok, all good, create and persist the key offer:
            offer = cfxdb.xbrmm.Offer()
            offer.timestamp = np.datetime64(now, 'ns')
            offer.offer = uuid.uuid4()

            # FIXME: finally nail what/how we track/map
            offer.seller = delegate_adr
            # offer.seller_authid = details.caller_authid
            offer.seller_authid = provider_id
            offer.seller_session_id = details.caller

            offer.key = key_id
            offer.api = api_id
            offer.uri = uri
            offer.valid_from = np.datetime64(valid_from, 'ns') if valid_from else None
            offer.signature = delegate_signature
            offer.price = price
            offer.categories = categories
            offer.expires = np.datetime64(expires, 'ns') if expires else None
            offer.copies = copies
            offer.remaining = copies

            self._schema.offers[txn, offer.offer] = offer

        offer_created = offer.marshal()

        # publish market maker event: new offer placed
        if self._market_session:
            await self._market_session.publish('{}on_offer_placed'.format(self._uri_prefix),
                                               offer_created,
                                               options=PublishOptions(acknowledge=True))

        self.log.info('{operation}: key {key_id} offered for {price} XBR',
                      operation=hlcontract('{}.on_offer_placed'.format(self.__class__.__name__)),
                      price=hlval(int(price / 10**18)),
                      key_id=hlid(key_id))

        return offer_created

    @wamp.register(None, check_types=True)
    def get_offer(self, offer_id, details: Optional[CallDetails] = None):
        """
        Get detail information on a data encryption key offer previously placed by a XBR seller (delegate).

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Detail information about the offer requested.
        :rtype: dict
        """
        assert type(offer_id) == bytes and len(offer_id) == 16, 'offer_id must be bytes[16], was "{}"'.format(offer_id)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        try:
            offer_id = uuid.UUID(bytes=offer_id)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid offer_id: {}'.format(str(e)))

        with self._db.begin() as txn:
            offer = self._schema.offers[txn, offer_id]
            if not offer:
                raise ApplicationError('crossbar.error.no_such_object', 'no offer with ID "{}"'.format(offer_id))

        return offer.marshal()

    @wamp.register(None, check_types=True)
    def query_offers(self,
                     api_id,
                     from_ts,
                     until_ts=None,
                     uri=None,
                     categories=None,
                     seller_id=None,
                     limit=None,
                     details: Optional[CallDetails] = None):
        """
        Return data encryption key offers for the given API and timerange, optionally filtered
        by one or more categories.

        .. note::

            Only offers that have not expired and that still have copies remaining to be sold are
            returned, if the original key offer did have an expiration date and/or maximum copies specified.

        Here is an example that retrieves all key offers in Python for some API within the last hour:

        .. code-block:: python

            last_hour = time_ns() - 60 * 60 * 10**9

            offers = await session.call('xbr.marketmaker.query_offers', api_id, last_hour)

        To filter for categories, here is how to retrieve all key offers that match a specific category:

        .. code-block:: python

            categories = {'vehicle_id': '92123a39-6422-4892-adf0-932892dc0c17}

            offers = await session.call('xbr.marketmaker.query_offers', api_id, last_hour, categories=categories)

        Filters can be given for more than one category, and combined with time filtering:

        .. code-block:: python

            from_ts = int(datetime(2019, 2, 10).timestamp() * 10**9)
            until_ts = int(datetime(2019, 2, 11).timestamp() * 10**9)
            categories = {'xtile': 132115, 'ytile': 95682, 'zoom': 18})

            offers = await session.call('xbr.marketmaker.query_offers', api_id, from_ts, until_ts=until_ts,
                                        categories=categories)

        :param api_id: UUID of the API the offers are for.
        :type api_id: bytes

        :param from_ts: Return offers since this date (Unix epoch time in ns).
        :type from_ts: int

        :param until_ts: If given, only return offers up to this date (Unix epoch time in ns), otherwise return
            all order up till now.
        :type until_ts: int

        :param uri: Optional URI prefix to filter offers for.
        :type uri: str

        :param categories: Optional user defined categories to filter offers for.
        :type categories: dict

        :param seller_id: Optional UUID of a specific seller to filter offers for.
        :type seller_id: bytes

        :param limit: If given, return at most this many offers. Default: 10. The maximum value for limit
            that can be specified is 1000.
        :type limit: int

        :param details: Caller details. In this case XBR data consumer (XBR buyer delegates)
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Returns a list of data encryption key offers.
        :rtype: list
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        raise NotImplementedError()

    @wamp.register(None, check_types=True)
    def revoke_offer(self, key_id, details: Optional[CallDetails] = None):
        """
        Called by XBR Provider to revoke (on-going) sale of a key. The market maker will stop
        accepting purchase requests for the given key and buyers attempting to buy the key
        will get a key expiration error.

        .. note::

            Only the original seller (delegate) that offered the key may revoke a key offering.

        :param key_id: UUID of the data encryption key to revoke.
        :type key_id: bytes

        :param details: Caller details. In this case XBR data provider (XBR seller delegates)
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Offer revocation information.
        :rtype: dict
        """
        assert type(key_id) == bytes and len(key_id) == 16, 'key_id must be bytes[16], was "{}"'.format(key_id)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        try:
            key_id = uuid.UUID(bytes=key_id)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid key_id: {}'.format(str(e)))

        with self._db.begin(write=True) as txn:

            offer_id = self._schema.idx_offer_by_key[txn, key_id]
            if not offer_id:
                raise ApplicationError('crossbar.error.no_such_object', 'no offer for key with ID "{}"'.format(key_id))

            # FIXME: check the caller is the same as the original caller that placed the offer - or, at least
            # that the authid or XBR delegate or publisher matches
            offer = self._schema.offers[txn, offer_id]
            assert offer

            # we won't delete the offer (that would destroy information), but set the offered expired
            offer.expires = np.datetime64(time_ns(), 'ns')

        offer_revoked = offer.marshal()
        if self._market_session:
            yield self._market_session.publish('{}on_offer_revoked'.format(self._uri_prefix),
                                               offer_revoked,
                                               options=PublishOptions(acknowledge=True))

        return offer_revoked

    @wamp.register(None, check_types=True)
    def get_quote(self, key_id, details: Optional[CallDetails] = None):
        """
        Called by a XBR Consumer to get a price quote for a key. The market maker will forward
        the call to the XBR Provider selling the key if the price is dynamic. When the price
        is static, the XBR Market Maker will cache the price and return the cached value
        subsequently.

        :param key_id: UUID of the data encryption key to quote the price for.
        :type key_id: bytes

        :param details: Caller details. In this case XBR data consumer (XBR buyer delegates)
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: The price quotation.
        :rtype: dict
        """
        assert type(key_id) == bytes and len(key_id) == 16, 'key_id must be bytes[16], was "{}"'.format(key_id)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        try:
            key_id = uuid.UUID(bytes=key_id)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid key_id: {}'.format(str(e)))

        with self._db.begin() as txn:

            offer_id = self._schema.idx_offer_by_key[txn, key_id]
            if not offer_id:
                raise ApplicationError('crossbar.error.no_such_object', 'no offer for key with ID "{}"'.format(key_id))

            offer = self._schema.offers[txn, offer_id]
            assert offer

        if not offer.price:
            raise NotImplementedError('dynamic key pricing not implemented')

        now = np.datetime64(time_ns(), 'ns')
        if offer.expires and offer.expires < now:
            expired_for = str(np.timedelta64(now - offer.expires, 's'))
            raise ApplicationError(
                'xbr.error.offer_expired', 'the offer for key with ID "{}" already expired {} ({} ago)'.format(
                    key_id, offer.expires, expired_for))

        # static pricing
        quote = {
            'timestamp': time_ns(),
            'key': key_id.bytes,
            'price': pack_uint256(offer.price),
            'expires': int(offer.expires),
        }
        return quote

    @wamp.register(None, check_types=True)
    async def buy_key(self,
                      delegate_adr,
                      buyer_pubkey,
                      key_id,
                      channel_oid,
                      channel_seq,
                      amount,
                      balance,
                      signature,
                      details: Optional[CallDetails] = None):
        """
        Called by a XBR Consumer to buy a key. The market maker will (given sufficient balance)
        forward the purchase request and call into the XBR Provider selling the key.

        :param delegate_adr: The buyer delegate Ethereum address. The technical buyer is usually the
            XBR delegate of the XBR consumer/buyer of the data being bought.
        :type delegate_adr: bytes of length 20

        :param buyer_pubkey: The buyer delegate Ed25519 public key.
        :type buyer_pubkey: bytes of length 32

        :param key_id: The UUID of the data encryption key to buy.
        :type key_id: bytes of length 16

        :param channel_oid: The on-chain channel contract address.
        :type channel_oid: bytes of length 20

        :param channel_seq: Payment channel off-chain transaction sequence number.
        :type channel_seq: int

        :param amount: Amount signed off to pay. The actual amount paid is always less than or
            equal to this, but the amount must be greater than or equal to the price in the
            offer for selling the data encryption key being bought.
        :type amount: bytes

        :param balance: Balance remaining in the payment channel (from the buyer delegate to
            the market maker) after successfully buying the key.
        :type balance: bytes

        :param signature: Signature over the supplied buying information, using the Ethereum
            private key of the buyer delegate.
        :type signature: bytes

        :param details: Caller details. The call will come from the XBR buyer delegate.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Buying receipt, including the actual data encryption key that was bought. The
            data encryption key is itself encrypted (sealed) to the ``buyer_pubkey``.
        :rtype: dict
        """
        assert type(delegate_adr) == bytes and len(delegate_adr) == 20, 'delegate_adr must be bytes[20]'
        assert type(buyer_pubkey) == bytes and len(buyer_pubkey) == 32, 'buyer_pubkey must be bytes[32]'
        assert type(key_id) == bytes and len(key_id) == 16, 'key_id must be bytes[16]'
        assert type(channel_oid) == bytes and len(channel_oid) == 16, 'channel_oid must be bytes[20]'
        assert type(channel_seq) == int, 'channel_seq must be int, but was {}'.format(type(channel_seq))
        assert type(amount) == bytes and len(amount) == 32, 'amount must be bytes[32], but was {}'.format(type(amount))
        assert type(balance) == bytes and len(balance) == 32, 'balance must be bytes[32], but was {}'.format(
            type(balance))
        assert type(signature) == bytes, 'signature must be bytes, but was {}'.format(type(signature))
        assert len(signature) == (32 + 32 + 1), 'signature must be bytes[65], but was bytes[{}]'.format(len(signature))
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        channel_oid = uuid.UUID(bytes=channel_oid)
        amount = unpack_uint256(amount)
        balance = unpack_uint256(balance)
        is_final = False

        self.log.debug(
            'EIP712 verifying signature for channel_oid={channel_oid}, channel_seq={channel_seq}, balance={balance}, is_final={is_final}',
            klass=self.__class__.__name__,
            channel_oid=hlid(channel_oid),
            channel_seq=hlval(channel_seq),
            amount=hlval(amount),
            balance=hlval(balance),
            is_final=hlval(is_final))

        # FIXME
        close_at = 1
        # close_at = self._w3.eth.blockNumber

        # XBRSIG[2/8]: check the signature (over all input data for the buying of the key)
        signer_address = xbr.recover_eip712_channel_close(self._verifying_chain_id, self._verifying_contract, close_at,
                                                          self._market_oid.bytes, channel_oid.bytes, channel_seq,
                                                          balance, is_final, signature)
        if signer_address != delegate_adr:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, delegate_adr={delegate_adr}',
                          signer_address=signer_address,
                          delegate_adr=delegate_adr)
            raise ApplicationError('xbr.error.invalid_signature',
                                   'EIP712 signature invalid or not signed by buyer delegate')

        # FIXME: check that the delegate_adr fits what we expect for the buyer
        # FIXME: check that the channel_seq fits what we expect for the payment channel (payment_balance.seq)

        try:
            key_id = uuid.UUID(bytes=key_id)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid key_id: {}'.format(str(e)))

        if type(amount) != int or amount < 0:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid amount type or value: {}'.format(amount))

        if type(balance) != int or balance < 0:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid balance type or value: {}'.format(balance))

        if not self._market_session:
            raise Exception('no market maker session')

        self.log.debug(
            'BUY key: delegate_adr={delegate_adr}, buyer_pubkey={buyer_pubkey}, key_id={key_id}, amount={amount}, signature={signature}, details={details}',
            delegate_adr=hlid('0x' + binascii.b2a_hex(delegate_adr).decode()),
            buyer_pubkey=hlid('0x' + binascii.b2a_hex(buyer_pubkey).decode()),
            key_id=hlid(key_id),
            amount=hlval(amount),
            signature=hlid('0x' + binascii.b2a_hex(signature).decode()),
            details=details)

        is_free = None
        seller = None
        now = time_ns()

        #
        # DB transaction 1.1/2
        #
        with self._db.begin() as txn:

            payment_channel_oid = channel_oid
            payment_channel = self._schema.payment_channels[txn, payment_channel_oid]
            if not payment_channel:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no payment channel at address "{}"'.format(payment_channel_oid))

            if payment_channel.state == 1:
                payment_balance = self._schema.payment_balances[txn, payment_channel_oid]
                if payment_balance.remaining <= 0:
                    raise ApplicationError(
                        'crossbar.error.no_such_object',
                        'payment channel at address "{}" has no (positive) balance remaining'.format(
                            payment_channel_oid))
            else:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'payment channel at address "{}" not in state OPEN'.format(payment_channel_oid))

            offer_id = self._schema.idx_offer_by_key[txn, key_id]
            if not offer_id:
                raise ApplicationError('crossbar.error.no_such_object', 'no offer for key with ID "{}"'.format(key_id))

            # the original offer for the key the buyer delegate wants to buy
            offer = self._schema.offers[txn, offer_id]
            assert offer

            # FIXME: check offer is still valid (time and limits)

            # for non-free offers, we check the amount paid and the current active payment channel balance
            is_free = None
            if offer.price:
                if amount < offer.price:
                    raise ApplicationError(
                        'xbr.error.insufficient_amount',
                        'The amount offered to pay ({}) is less than the offer price {}'.format(amount, offer.price))

                if offer.price > payment_balance.remaining:
                    # FIXME: try to swap in an active payment channel usable by the
                    #     buyer delegate (the caller of this procedure)
                    raise ApplicationError(
                        'xbr.error.insufficient_payment_balance',
                        'Not enough remaining balance left ({}) in payment channel to buy key for {} from the market maker'
                        .format(payment_balance.remaining, offer.price))
                is_free = False
            else:
                self.log.info('Key {key_id} is free!', key_id=hlid(str(key_id)))
                is_free = True

            seller = bytes(offer.seller)

        # check if the seller has an active paying channel, that is open and with sufficient remaining amount
        auto_close_paying_channel = True
        while True:
            paying_channel, paying_balance = self._get_active_channel_and_balance(seller, 'paying')
            if paying_channel and paying_balance and offer.price > paying_balance.remaining:
                if auto_close_paying_channel:

                    # FIXME: paying_channel.close_balance/channel_seq appears to be None
                    # channel_seq = paying_channel.close_channel_seq
                    # channel_balance = paying_channel.close_balance
                    channel_seq = paying_balance.seq
                    channel_balance = paying_balance.remaining
                    channel_is_final = True

                    marketmaker_signature = xbr.sign_eip712_channel_close(
                        self._eth_privkey_raw, self._verifying_chain_id, self._verifying_contract, close_at,
                        self._market_oid.bytes, paying_channel.channel_oid.bytes, channel_seq, channel_balance,
                        channel_is_final)
                    # call into seller delegate to get close signature
                    proc_close = 'xbr.provider.{}.close_channel'.format(offer.seller_authid)
                    try:
                        receipt = await self._market_session.call(proc_close, self._eth_adr_raw,
                                                                  paying_channel.channel_oid.bytes, channel_seq,
                                                                  pack_uint256(channel_balance), channel_is_final,
                                                                  marketmaker_signature)
                        delegate_signature = receipt['signature']
                    except Exception as e:
                        self.log.failure()
                        raise ApplicationError(
                            'xbr.error.insufficient_paying_balance',
                            'not enough remaining balance {} XBR left in paying channel 0x{} to buy key for {} XBR from the seller delegate 0x{} - auto-close of paying channel failed:\n{}'
                            .format(
                                binascii.b2a_hex(paying_channel.channel_oid.bytes).decode(), paying_balance.remaining,
                                offer.price,
                                binascii.b2a_hex(seller).decode(), e))
                    else:
                        # FIXME: check delegate closing signature

                        self.log.info(
                            'Auto-closing paying channel {paying_channel_oid} (at seq={channel_seq}, balance={channel_balance}) ..',
                            paying_channel_oid=hlid('0x' +
                                                    binascii.b2a_hex(paying_channel.channel_oid.bytes).decode()),
                            channel_seq=hlval(channel_seq),
                            channel_balance=hlval(int(channel_balance / 10**18)))

                        # close the channel in market maker
                        await self.close_channel(paying_channel.channel_oid.bytes,
                                                 channel_seq,
                                                 pack_uint256(channel_balance),
                                                 channel_is_final,
                                                 delegate_signature,
                                                 details=details)

                        # notify the seller delegate of the closed channel
                        topic_close = 'xbr.provider.{}.on_channel_closed'.format(offer.seller_authid)
                        await self._market_session.publish(topic_close,
                                                           paying_channel.channel_oid.bytes,
                                                           channel_seq,
                                                           pack_uint256(channel_balance),
                                                           channel_is_final,
                                                           options=PublishOptions(acknowledge=True))

                        self.log.info(
                            'Auto-close of paying channel {paying_channel_oid} succeeded',
                            paying_channel_oid=hlid('0x' +
                                                    binascii.b2a_hex(paying_channel.channel_oid.bytes).decode()))
                else:
                    raise ApplicationError(
                        'xbr.error.insufficient_paying_balance',
                        'not enough remaining balance {} XBR left in paying channel 0x{} to buy key for {} XBR from the seller delegate 0x{}'
                        .format(
                            binascii.b2a_hex(paying_channel.channel_oid).decode(), paying_balance.remaining,
                            offer.price,
                            binascii.b2a_hex(seller).decode()))
            else:
                # we found an open paying channel for the seller with sufficient balance remaining
                paying_channel_oid = paying_channel.channel_oid
                break

        #
        # DB transaction 1.2/2
        #
        with self._db.begin(write=True) as txn:

            # the amount paid is what the original offer was, which might be less than
            # the amount offered to pay (the call parameter "amount" to this procedure), but
            # cannot by less than the offer price.
            amount_paid = offer.price
            balance_after = paying_balance.remaining - amount_paid
            seq_after = paying_balance.seq + 1

            # XBRSIG[3/8]: compute EIP712 typed data signature, signed by the market maker
            marketmaker_signature = xbr.sign_eip712_channel_close(self._eth_privkey_raw, self._verifying_chain_id,
                                                                  self._verifying_contract, close_at,
                                                                  self._market_oid.bytes, paying_channel_oid.bytes,
                                                                  seq_after, balance_after, False)

            self.log.debug(
                'EIP712 signature successfully created: delegate_adr={delegate_adr}, buyer_pubkey={buyer_pubkey}, key_id={key_id}, amount={amount}, balance={balance}',
                klass=self.__class__.__name__,
                delegate_adr=hlid(self._eth_adr),
                buyer_pubkey=hlid('0x' + binascii.b2a_hex(buyer_pubkey).decode()),
                key_id=hlid('0x' + binascii.b2a_hex(key_id.bytes).decode()),
                amount=hlval(amount_paid),
                balance=hlval(payment_balance.remaining))

            transaction = cfxdb.xbrmm.Transaction()
            transaction.tid = uuid.uuid4()
            transaction.created = np.datetime64(now, 'ns')
            transaction.created_payment_channel_seq = payment_balance.seq
            transaction.created_paying_channel_seq = paying_balance.seq
            transaction.amount = amount_paid
            transaction.payment_channel = payment_channel_oid
            transaction.paying_channel = paying_channel_oid
            transaction.status = cfxdb.xbrmm.Transaction.STATUS_INFLIGHT
            transaction.completed = None
            transaction.completed_payment_channel_seq = None
            transaction.completed_paying_channel_seq = None
            self._schema.transactions[txn, transaction.tid] = transaction

            # in this first transaction, we commit the amount paid as pending ("inflight") and
            # reduce the "remaining" amount accordingly. depending on the outcome of the key buy,
            # we later (in a 2nd transaction) proceed accordingly
            payment_balance.remaining -= amount_paid
            payment_balance.inflight += amount_paid

            # the payment balance sequence number is incremented (and never decreased)
            payment_balance.seq += 1

            self._schema.payment_balances[txn, payment_channel_oid] = payment_balance

            paying_balance.remaining -= amount_paid
            paying_balance.inflight += amount_paid

            # the paying balance sequence number is incremented (and never decreased)
            paying_balance.seq += 1

            self._schema.paying_balances[txn, paying_channel_oid] = paying_balance

            self.log.debug(
                'Balance of payment channel BEFORE call to provider: payment_balance.remaining={payment_balance_remaining}, payment_balance.inflight={payment_balance_inflight}',
                payment_balance_remaining=payment_balance.remaining,
                payment_balance_inflight=payment_balance.inflight,
            )
            self.log.debug(
                'Balance of paying channel BEFORE call to provider: paying_balance.remaining={paying_balance_remaining}, paying_balance.inflight={paying_balance_inflight}',
                paying_balance_remaining=paying_balance.remaining,
                paying_balance_inflight=paying_balance.inflight,
            )

        # now call into the XBR seller delegate (data provider) buying the data encryption key
        proc_buy = 'xbr.provider.{}.sell'.format(offer.seller_authid)
        try:
            seller_receipt = await self._market_session.call(proc_buy, self._eth_adr_raw, buyer_pubkey, key_id.bytes,
                                                             paying_channel_oid.bytes, seq_after,
                                                             pack_uint256(amount_paid), pack_uint256(balance_after),
                                                             marketmaker_signature)

            seller_signature = seller_receipt['signature']
            sealed_key = seller_receipt['sealed_key']

            # XBRSIG[6/8]: check seller signature
            signer_address = xbr.recover_eip712_channel_close(self._verifying_chain_id, self._verifying_contract,
                                                              close_at, self._market_oid.bytes,
                                                              paying_channel_oid.bytes, seq_after, balance_after,
                                                              False, seller_signature)
            if signer_address != paying_channel.delegate:
                self.log.warn('EIP712 signature invalid: signer_address={signer_address}, delegate_adr={delegate_adr}',
                              signer_address=signer_address,
                              delegate_adr=delegate_adr)
                raise ApplicationError('xbr.error.invalid_signature',
                                       'EIP712 signature invalid or not signed by seller delegate')

        except Exception as e:
            # the call to the provider failed, we rollback the logical transaction on both payment and paying channel
            if not is_free:
                #
                # DB transaction 2/2 (failure case)
                #
                with self._db.begin(write=True) as txn:
                    # fetch new current balance, as we are in a new transaction and concurrent
                    # balance updates could have happened
                    payment_balance = self._schema.payment_balances[txn, payment_channel_oid]
                    paying_balance = self._schema.paying_balances[txn, paying_channel_oid]

                    transaction.status = cfxdb.xbrmm.Transaction.STATUS_FAILED
                    transaction.completed = np.datetime64(time_ns(), 'ns')
                    transaction.completed_payment_channel_seq = payment_balance.seq
                    transaction.completed_paying_channel_seq = paying_balance.seq
                    transaction.result_len = None
                    transaction.result_sha256 = None
                    self._schema.transactions[txn, transaction.tid] = transaction

                    payment_balance.remaining += amount_paid
                    payment_balance.inflight -= amount_paid

                    paying_balance.remaining += amount_paid
                    paying_balance.inflight -= amount_paid

                    self._schema.payment_balances[txn, payment_channel_oid] = payment_balance
                    self._schema.paying_balances[txn, payment_channel_oid] = paying_balance

                self.log.debug(
                    'MM Key Buy ERROR: balance of payment channel AFTER call to provider: remaining={remaining}, inflight={inflight}',
                    remaining=hlid(payment_balance.remaining),
                    inflight=hlid(payment_balance.inflight))
                self.log.debug(
                    'MM Key Buy ERROR: balance of paying channel AFTER call to provider: paying_balance.remaining={paying_balance_remaining}, paying_balance.inflight={paying_balance_inflight}',
                    paying_balance_remaining=hlid(paying_balance.remaining),
                    paying_balance_inflight=hlid(paying_balance.inflight),
                )
            if isinstance(e, ApplicationError):
                raise e
            else:
                raise ApplicationError(
                    'xbr.error.transaction_failed',
                    'market maker could not buy key from seller delegate "{}": {}'.format(
                        binascii.b2a_hex(seller).decode(), e))

        # the call to the provider succeed, we commit the logical transaction on both payment and paying channel
        #
        # DB transaction 2/2 (success case)
        #
        payment_channel_ran_empty = False
        paying_channel_ran_empty = False

        with self._db.begin(write=True) as txn:
            # fetch new current balance, as we are in a new transaction and concurrent
            # balance updates could have happened
            payment_balance = self._schema.payment_balances[txn, payment_channel_oid]
            paying_balance = self._schema.paying_balances[txn, paying_channel_oid]

            transaction.status = cfxdb.xbrmm.Transaction.STATUS_SUCCESS
            transaction.completed = np.datetime64(time_ns(), 'ns')
            transaction.completed_payment_channel_seq = payment_balance.seq
            transaction.completed_paying_channel_seq = paying_balance.seq
            self._schema.transactions[txn, transaction.tid] = transaction

            payment_balance.inflight -= amount_paid
            paying_balance.inflight -= amount_paid

            self._schema.payment_balances[txn, payment_channel_oid] = payment_balance
            self._schema.paying_balances[txn, paying_channel_oid] = paying_balance

            if payment_balance.remaining + payment_balance.inflight <= 0:
                payment_channel_ran_empty = True
                # chn = self._schema.payment_channels[txn, payment_channel_oid]
                # chn.state = cfxdb.xbrmm.ChannelState.CLOSING
                # chn.closed_at = time_ns()

                # FIXME: we need bytes() here to overcome the assert in pmaps - as we do get a memory(view)
                # self._schema.payment_channels[txn, payment_channel_oid] = chn

            if paying_balance.remaining + paying_balance.inflight <= 0:
                paying_channel_ran_empty = True
                # chn = self._schema.paying_channels[txn, paying_channel_oid]
                # chn.state = cfxdb.xbrmm.ChannelState.CLOSING
                # chn.closed_at = time_ns()

                # FIXME: we need bytes() here to overcome the assert in pmaps - as we do get a memory(view)
                # self._schema.paying_channels[txn, paying_channel_oid] = chn

        if payment_channel_ran_empty and self._market_session:
            await self._market_session.publish('{}on_payment_channel_empty'.format(self._uri_prefix),
                                               payment_channel_oid.bytes,
                                               options=PublishOptions(acknowledge=True))

        if paying_channel_ran_empty and self._market_session:
            await self._market_session.publish('{}on_paying_channel_empty'.format(self._uri_prefix),
                                               paying_channel_oid.bytes,
                                               options=PublishOptions(acknowledge=True))
        self.log.debug(
            'MM Key Buy SUCCESS: balance of payment channel AFTER call to provider: remaining={remaining}, inflight={inflight}',
            remaining=hlid(payment_balance.remaining),
            inflight=hlid(payment_balance.inflight))

        self.log.debug(
            'MM Key Buy SUCCESS: balance of paying channel AFTER call to provider: paying_balance.remaining={paying_balance_remaining}, paying_balance.inflight={paying_balance_inflight}',
            paying_balance_remaining=hlid(paying_balance.remaining),
            paying_balance_inflight=hlid(paying_balance.inflight),
        )

        # XBRSIG[7/8]: compute EIP712 typed data signature, signed by the market maker
        marketmaker_signature = xbr.sign_eip712_channel_close(self._eth_privkey_raw, self._verifying_chain_id,
                                                              self._verifying_contract, close_at,
                                                              self._market_oid.bytes, payment_channel_oid.bytes,
                                                              payment_balance.seq, payment_balance.remaining, False)
        receipt = {
            # key ID that has been bought
            'key_id': key_id.bytes,

            # buyer delegate address that bought the key
            'delegate': delegate_adr,

            # buyer delegate Ed25519 public key with which the bought key was sealed
            'buyer_pubkey': buyer_pubkey,

            # finally return what the consumer (buyer) was actually interested in:
            # the data encryption key, sealed (public key Ed25519 encrypted) to the
            # public key of the buyer delegate
            'sealed_key': sealed_key,

            # the offer ID under which the key is sold
            'offer_id': offer.offer.bytes if (offer and offer.offer) else None,

            # whether this key was free rated (cost nothing)
            'free_rated': is_free,

            # amount originally offered to pay
            'amount': pack_uint256(amount),

            # amount the seller offered the key for - and hence the amount actually paid (always <= amount)
            'amount_paid': pack_uint256(amount_paid),

            # current payment channel sequence number (after tx)
            'channel_seq': payment_balance.seq,

            # the payment channel over which the XBR transaction ran - address of the payment channel (on-chain)
            'payment_channel': payment_channel_oid.bytes,

            # payment channel remaining real-time balance (off-chain)
            'remaining': pack_uint256(payment_balance.remaining),

            # payment channel in-flight real-time balance (off-chain)
            'inflight': pack_uint256(payment_balance.inflight),

            # market maker signature
            'signature': marketmaker_signature,

            # seller (delegate) signature
            # 'seller_signature': seller_signature,
        }

        # FIXME: publish on_transaction_complete event

        self.log.info('{operation}: transaction complete - delegate {delegate} bought key {key_id} for {amount} XBR',
                      operation=hlcontract('{}.on_transaction_complete'.format(self.__class__.__name__)),
                      amount=hlval(int(amount_paid / 10**18)),
                      delegate=hlid('0x' + binascii.b2a_hex(delegate_adr).decode()),
                      key_id=hlid(key_id))

        return receipt

    @wamp.register(None, check_types=True)
    async def open_channel(self,
                           member_adr: bytes,
                           market_oid: bytes,
                           channel_oid: bytes,
                           verifying_chain_id: int,
                           current_block_number: int,
                           verifying_contract_adr: bytes,
                           channel_type: int,
                           delegate: bytes,
                           marketmaker: bytes,
                           recipient: bytes,
                           amount: bytes,
                           signature: bytes,
                           attributes: Optional[dict] = None,
                           details: Optional[CallDetails] = None) -> dict:
        """
        Open a new XBR payment/paying channel for processing off-chain micro-transactions.

        :param member_oid: OID of the member that sets the XBR consent status.

        :param market_oid: OID of the market (the member must
            be actor in) in which the member set the consent status.

        :param channel_oid: New channel OID.

        :param verifying_chain_id: Blockchain ID.

        :param current_block_number: Blockchain current block number.

        :param verifying_contract_adr: Address of ``XBRNetwork`` smart contract.

        :param channel_type: Channel type: payment or paying channel.

        :param delegate: The delegate (off-chain) allowed to spend/earn-on
            this channel (off-chain) in the name of the actor (buyer/seller
            in the market).

        :param recipient: The address of the beneficiary for any channel payout when the channel is closed.

        :param amount: The amount initially transfered to and held in the channel until closed.

        :param signature: EIP712 signature for opening the channel.

        :param attributes: Object standard attributes like title, description and tags.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: XBR channel information.
        """
        assert type(member_adr) == bytes, 'member_adr must be bytes, was {}'.format(type(member_adr))
        assert len(member_adr) == 20, 'member_adr must be bytes[20], was bytes[{}]'.format(len(member_adr))
        assert type(market_oid) == bytes, 'market_oid must be bytes, was {}'.format(type(market_oid))
        assert len(market_oid) == 16, 'market_oid must be bytes[16], was bytes[{}]'.format(len(market_oid))
        assert type(channel_oid) == bytes, 'channel_oid must be bytes, was {}'.format(type(channel_oid))
        assert len(channel_oid) == 16, 'channel_oid must be bytes[16], was bytes[{}]'.format(len(channel_oid))
        assert type(verifying_chain_id) == int, 'verifying_chain_id must be int, was {}'.format(
            type(verifying_chain_id))
        assert type(current_block_number) == int, 'current_block_number mus be int, was {}'.format(
            type(current_block_number))
        assert type(verifying_contract_adr) == bytes and len(
            verifying_contract_adr) == 20, 'verifying_contract_adr mus be bytes[20], was {}'.format(
                type(verifying_contract_adr))
        assert type(channel_type) == int, 'channel_type must be int, was {}'.format(type(channel_type))
        assert channel_type in [ActorType.PROVIDER, ActorType.CONSUMER]
        assert type(delegate) == bytes, 'delegate must be bytes, was {}'.format(type(delegate))
        assert len(delegate) == 20, 'delegate must be bytes[20], was bytes[{}]'.format(len(delegate))
        assert type(marketmaker) == bytes, 'marketmaker must be bytes, was {}'.format(type(marketmaker))
        assert len(marketmaker) == 20, 'marketmaker must be bytes[16], was bytes[{}]'.format(len(marketmaker))
        assert type(recipient) == bytes, 'recipient must be bytes, was {}'.format(type(recipient))
        assert len(recipient) == 20, 'recipient must be bytes[16], was bytes[{}]'.format(len(recipient))
        assert type(amount) == bytes, 'amount must be bytes, was {}'.format(type(amount))
        assert len(amount) == 32, 'amount must be bytes[16], was bytes[{}]'.format(len(amount))
        assert type(signature) == bytes and len(signature) == 65, 'signature must be bytes[65], was {}'.format(
            type(signature))
        assert attributes is None or type(attributes) == dict, 'attributes must be dict, was {}'.format(
            type(attributes))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        market_oid_ = uuid.UUID(bytes=market_oid)
        channel_oid_ = uuid.UUID(bytes=channel_oid)
        amount_ = unpack_uint256(amount)

        try:
            signer_address = xbr.recover_eip712_channel_open(verifying_chain_id, verifying_contract_adr, channel_type,
                                                             current_block_number, market_oid_.bytes,
                                                             channel_oid_.bytes, member_adr, delegate, marketmaker,
                                                             recipient, amount_, signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed: {err}', err=str(e))
            raise ApplicationError('xbr.error.invalid_signature', 'EIP712 signature recovery failed ({})'.format(e))

        if signer_address != member_adr:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, member_adr={member_adr}',
                          signer_address=signer_address,
                          member_adr=member_adr)
            raise ApplicationError('xbr.error.invalid_signature', 'EIP712 signature invalid')

        self.log.info(
            '{klass}.open_channel(member_adr={member_adr}, market_oid={market_oid}, channel_oid={channel_oid}, '
            'delegate={delegate} recipient={recipient} details={details})',
            klass=self.__class__.__name__,
            member_adr=hlid(member_adr),
            market_oid=hlid(market_oid_),
            channel_oid=hlid(channel_oid_),
            delegate=hlid('0x' + b2a_hex(delegate).decode()),
            recipient=hlid('0x' + b2a_hex(recipient).decode()),
            details=details)

        def _set_allowance():
            xbr.xbrtoken.functions.approve(xbr.xbrchannel.address, amount_).transact({
                'from': marketmaker,
                'gas': 100000
            })
            return xbr.xbrtoken.functions.allowance(marketmaker, xbr.xbrchannel.address).call()

        if channel_type == cfxdb.xbrmm.ChannelType.PAYMENT:
            allowance = await deferToThread(
                lambda: xbr.xbrtoken.functions.allowance(member_adr, xbr.xbrchannel.address).call())
            assert allowance == amount_
        elif channel_type == cfxdb.xbrmm.ChannelType.PAYING:
            allowance = await deferToThread(_set_allowance)
            assert allowance == amount_

        try:
            txn_hash = await deferToThread(self._send_openChannel, channel_type, current_block_number,
                                           market_oid_.bytes, channel_oid_.bytes, member_adr, delegate, marketmaker,
                                           recipient, amount_, signature)
        except Exception as e:
            self.log.failure()
            # FIXME: we have to retry, but not in-line before returning from this call
            raise e
        else:
            # trigger blockchain to catch up with new data ..
            self._controller_session._trigger_monitor_blockchain()

            open_channel_submitted = {
                'transaction': txn_hash,
                'channel_oid': channel_oid_.bytes,
                'market_oid': market_oid_.bytes,
            }
            return open_channel_submitted

    @wamp.register(None, check_types=True)
    async def close_channel(self,
                            channel_oid: bytes,
                            verifying_chain_id: int,
                            current_block_number: int,
                            verifying_contract_adr: bytes,
                            closing_balance: bytes,
                            closing_seq: int,
                            closing_is_final: bool,
                            delegate_signature: bytes,
                            details: Optional[CallDetails] = None) -> dict:
        """
        Trigger closing this channel.

        When the first participant has triggered closing the channel, submitting its latest
        transaction/state, a timeout period begins during which the other participant in this
        channel can submit its latest transaction/state too.

        When both transaction have been submitted, and the submitted transactions/states agree,
        the channel immediately closes, and the consumed amount of token in the channel is
        transferred to the channel recipient, and the remaining amount of token is transferred
        back to the original sender.

        :param channel_oid: OID of the channel to close.

        :param verifying_chain_id: Blockchain ID.

        :param current_block_number: Blockchain current block number.

        :param verifying_contract_adr: Address of ``XBRNetwork`` smart contract.

        :param closing_balance: Close this channel at this remaining channel off-chain balance.

        :param closing_seq: Close this channel at this last transaction sequence number for the channel.

        :param closing_is_final: Flag indicating a promise by the signing participant (either delegate
            or market maker) that this is the latest transaction it will ever submit, regardless of
            any non-expired channel timeout. When both participants close a channel co-operatively,
            and both have submitted a last transaction with this flag set, the channel contract
            can close the channel without timeout ("instant cooperative channel close").

        :param delegate_signature: EIP712 delegate signature for closing the channel with the supplied data.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: XBR channel information.
        """
        assert type(channel_oid) == bytes, 'channel_oid must be bytes, was {}'.format(type(channel_oid))
        assert len(channel_oid) == 16, 'channel_oid must be bytes[16], was bytes[{}]'.format(len(channel_oid))
        assert type(verifying_chain_id) == int, 'verifying_chain_id must be int, was {}'.format(
            type(verifying_chain_id))
        assert type(current_block_number) == int, 'current_block_number mus be int, was {}'.format(
            type(current_block_number))
        assert type(verifying_contract_adr) == bytes and len(
            verifying_contract_adr) == 20, 'verifying_contract_adr mus be bytes[20], was {}'.format(
                type(verifying_contract_adr))
        assert type(closing_balance) == bytes and len(
            closing_balance) == 32, 'closing_balance must be bytes[32], was {}'.format(type(closing_balance))
        assert type(closing_seq) == int, 'closing_seq must be int, was {}'.format(type(closing_seq))
        assert type(closing_is_final) == bool, 'closing_final must be bool, was {}'.format(type(closing_is_final))
        assert type(delegate_signature) == bytes and len(
            delegate_signature) == 65, 'delegate_signature must be bytes[65], was {}'.format(type(delegate_signature))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        closing_balance_ = unpack_uint256(closing_balance)
        channel_oid_ = uuid.UUID(bytes=channel_oid)

        with self._db.begin() as txn:
            channel = self._schema.paying_channels[txn, channel_oid_]
            if not channel:
                channel = self._schema.payment_channels[txn, channel_oid_]
                if not channel:
                    raise ApplicationError("xbr.error.invalid_channel")

        delegate = channel.delegate

        self.log.info(
            '{operation}(channel_oid={channel_oid}, closing_seq={closing_seq}, closing_balance={closing_balance}, closing_is_final={closing_is_final})',
            operation=hlcontract('{}.close_channel'.format(self.__class__.__name__)),
            channel_oid=hlid(channel_oid_),
            closing_seq=closing_seq,
            closing_balance=hlval(int(closing_balance_ / 10**18)),
            closing_is_final=hlval(closing_is_final))

        try:
            signer_address = xbr.recover_eip712_channel_close(verifying_chain_id, verifying_contract_adr,
                                                              current_block_number, self.market.bytes,
                                                              channel_oid_.bytes, closing_seq, closing_balance_,
                                                              closing_is_final, delegate_signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed: {err}', err=str(e))
            raise ApplicationError('xbr.error.invalid_signature', 'EIP712 signature recovery failed ({})'.format(e))

        if signer_address != delegate:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, delegate_adr={delegate_adr}',
                          signer_address=signer_address,
                          delegate_adr=delegate)
            raise ApplicationError('xbr.error.invalid_signature', 'EIP712 signature invalid')

        # FIXME: check channel has no in-flight transactions currently

        with self._db.begin() as txn:
            channel = self._schema.payment_channels[txn, channel_oid_]

            channel_type = None
            if channel:
                channel_type = cfxdb.xbrmm.ChannelType.PAYMENT
            else:
                channel = self._schema.paying_channels[txn, channel_oid_]
                if channel:
                    channel_type = cfxdb.xbrmm.ChannelType.PAYING
            if not channel:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no channel with address "{}"'.format(channel_oid_))

        marketmaker_signature = None
        if closing_is_final:
            # create new signature with closing final flag set
            marketmaker_signature = xbr.sign_eip712_channel_close(self._eth_privkey_raw, verifying_chain_id,
                                                                  verifying_contract_adr, current_block_number,
                                                                  channel.market_oid.bytes, channel_oid_.bytes,
                                                                  closing_seq, closing_balance_, closing_is_final)

        # The payment channel is open (and operating off-chain)
        if channel.state != cfxdb.xbrmm.ChannelState.OPEN:
            raise ApplicationError(
                'xbr.error.channel_not_open',
                'channel {} of type {} exists, but is not open (channel is in state {})'.format(
                    channel_oid_, channel._channel_type, channel.state))

        # Set the payment channel to closing (one of the channel participants has requested to closed the channel)
        channel.state = cfxdb.xbrmm.ChannelState.CLOSING

        # FIXME: a) set current block number, and b) add UTC timestamp
        # channel.closing_at = None

        # market maker + delegate signatures over same set of typed data
        if marketmaker_signature:
            channel.close_mm_sig = marketmaker_signature
        channel.close_del_sig = delegate_signature

        # signed typed data:
        channel.close_channel_seq = closing_seq
        channel.close_balance = closing_balance_
        channel.close_is_final = closing_is_final

        # this will be set when the channel was finally closed on-chain ..
        # channel.closed_tx = None

        # update record in database
        with self._db.begin(write=True) as txn:
            if channel_type == cfxdb.xbrmm.ChannelType.PAYMENT:
                self._schema.payment_channels[txn, channel_oid_] = channel
            elif channel_type == cfxdb.xbrmm.ChannelType.PAYING:
                self._schema.paying_channels[txn, channel_oid_] = channel
            else:
                assert False, 'should not arrive here'

        # submit transaction to blockchain
        try:
            txn_hash = await deferToThread(self._send_closeChannel, channel.channel_oid.bytes, current_block_number,
                                           closing_seq, closing_balance_, closing_is_final, delegate_signature,
                                           marketmaker_signature)
        except Exception as e:
            self.log.failure()
            # FIXME: we have to retry, but not in-line before returning from this call
            raise e
        else:
            # trigger blockchain to catch up with new data ..
            self._controller_session._trigger_monitor_blockchain()

            closing = {
                'transaction': txn_hash,
                'market_oid': channel.market_oid.bytes,
                'channel_oid': channel.channel_oid.bytes,
                'state': channel.state,
                'balance': pack_uint256(channel.close_balance),
                'seq': channel.close_channel_seq,
                'is_final': channel.close_is_final,
            }

            # publish on_channel_closing event
            if self._market_session:
                if channel_type == 1:
                    # FIXME: xbr.marketmaker.buyer.<buyer-delegate-adr>.on_payment_channel_closing
                    topic = '{}on_payment_channel_closing'.format(self._uri_prefix)
                else:
                    # FIXME: xbr.marketmaker.seller.<seller-delegate-adr>.on_paying_channel_closing
                    topic = '{}on_paying_channel_closing'.format(self._uri_prefix)
                await self._market_session.publish(topic, closing, options=PublishOptions(acknowledge=True))

            self.log.info(
                '{operation}: channel {channel_oid} moved to {state} state - on-chain transaction will trigger asynchronously ..',
                operation=hlcontract('{}.on_channel_closing'.format(self.__class__.__name__)),
                state=hlval('CLOSING'),
                channel_oid=hlid(channel_oid))

            return closing

    @wamp.register(None, check_types=True)
    def get_payment_channel(self, channel_oid, details: Optional[CallDetails] = None):
        """
        Returns the (off-chain) payment channel given by the (on-chain) payment channel contract address.

        :param channel_oid: Payment channel contract address.
        :type channel_oid: bytes

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Payment channel information.
        :rtype: dict
        """
        assert type(channel_oid) == bytes and len(channel_oid) == 16, 'channel_oid must be bytes[16], was "{}"'.format(
            channel_oid)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        try:
            channel_oid_ = uuid.UUID(bytes=channel_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid channel_oid: {}'.format(str(e)))

        with self._db.begin() as txn:
            channel = self._schema.payment_channels[txn, channel_oid_]
            if not channel:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no payment channel {} found'.format(channel_oid_))

        return channel.marshal()

    @wamp.register(None, check_types=True)
    def get_channels_by_delegate(self,
                                 delegate_adr: bytes,
                                 channel_type: int,
                                 filter_open: Optional[bool] = True,
                                 details: Optional[CallDetails] = None):

        if channel_type not in [cfxdb.xbrmm.ChannelType.PAYMENT, cfxdb.xbrmm.ChannelType.PAYING]:
            raise ApplicationError("xbr.marketmaker.error.invalid_channel_type",
                                   "Channel type must be 1 (payment) or 2 (paying), was {}".format(channel_type))

        if not is_address(delegate_adr):
            raise ApplicationError("xbr.marketmaker.error.invalid_delegate_adr",
                                   "Delegate address must be if length 20 was {}".format(len(delegate_adr)))

        t_zero = np.datetime64(0, 'ns')
        t_now = np.datetime64(time_ns(), 'ns')
        channels = []
        with self._db.begin() as txn:
            if channel_type == cfxdb.xbrmm.ChannelType.PAYMENT:
                for channel_oid in self._schema.idx_payment_channel_by_delegate.select(txn,
                                                                                       from_key=(delegate_adr, t_zero),
                                                                                       to_key=(delegate_adr, t_now),
                                                                                       return_keys=False):
                    if filter_open:
                        # channel must be open with positive remaining off-chain balance
                        channel = self._schema.payment_channels[txn, channel_oid]
                        if channel.state == 1:
                            balance = self._schema.payment_balances[txn, channel_oid]
                            if balance.remaining > 0:
                                channels.append(channel_oid.bytes)
                    else:
                        channels.append(channel_oid.bytes)
            else:
                for channel_oid in self._schema.idx_paying_channel_by_delegate.select(txn,
                                                                                      from_key=(delegate_adr, t_zero),
                                                                                      to_key=(delegate_adr, t_now),
                                                                                      return_keys=False):
                    if filter_open:
                        # channel must be open with positive remaining off-chain balance
                        channel = self._schema.paying_channels[txn, channel_oid]
                        if channel.state == 1:
                            balance = self._schema.paying_balances[txn, channel_oid]
                            if balance.remaining > 0:
                                channels.append(channel_oid.bytes)
                    else:
                        channels.append(channel_oid.bytes)

        return channels

    @wamp.register(None, check_types=True)
    def get_channels_by_actor(self, member_adr, channel_type, filter_open=True, details: Optional[CallDetails] = None):
        if channel_type not in [cfxdb.xbrmm.ChannelType.PAYMENT, cfxdb.xbrmm.ChannelType.PAYING]:
            raise ApplicationError("xbr.marketmaker.error.invalid_channel_type",
                                   "Channel type must be 1 (payment) or 2 (paying), was {}".format(channel_type))

        if not is_address(member_adr):
            raise ApplicationError("xbr.marketmaker.error.invalid_member_adr",
                                   "Delegate address must be if length 20 was {}".format(len(member_adr)))

        t_zero = np.datetime64(0, 'ns')
        t_now = np.datetime64(time_ns(), 'ns')
        channels = []
        with self._db.begin() as txn:
            if channel_type == cfxdb.xbrmm.ChannelType.PAYMENT:
                for channel_oid in self._schema.idx_payment_channel_by_actor.select(txn,
                                                                                    from_key=(member_adr, t_zero),
                                                                                    to_key=(member_adr, t_now),
                                                                                    return_keys=False):
                    if filter_open:
                        # channel must be open with positive remaining off-chain balance
                        channel = self._schema.payment_channels[txn, channel_oid]
                        if channel.state == 1:
                            balance = self._schema.payment_balances[txn, channel_oid]
                            if balance.remaining > 0:
                                channels.append(channel_oid.bytes)
                    else:
                        channels.append(channel_oid.bytes)
            else:
                for channel_oid in self._schema.idx_paying_channel_by_recipient.select(txn,
                                                                                       from_key=(member_adr, t_zero),
                                                                                       to_key=(member_adr, t_now),
                                                                                       return_keys=False):
                    if filter_open:
                        # channel must be open with positive remaining off-chain balance
                        channel = self._schema.paying_channels[txn, channel_oid]
                        if channel.state == 1:
                            balance = self._schema.paying_balances[txn, channel_oid]
                            if balance.remaining > 0:
                                channels.append(channel_oid.bytes)
                    else:
                        channels.append(channel_oid.bytes)

        return channels

    @wamp.register(None, check_types=True)
    def get_payment_channel_balance(self, channel_oid, details: Optional[CallDetails] = None):
        """
        Returns the (off-chain, real-time) payment channel balance given by the (on-chain)
        payment channel contract address.

        :param channel_oid: Payment channel contract address.
        :type channel_oid: bytes

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Payment channel balance information.
        :rtype: dict
        """
        assert type(channel_oid) == bytes and len(channel_oid) == 16, 'channel_oid must be bytes[16], was "{}"'.format(
            channel_oid)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        try:
            channel_oid_ = uuid.UUID(bytes=channel_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid channel_oid: {}'.format(str(e)))

        with self._db.begin() as txn:
            balance = self._schema.payment_balances[txn, channel_oid_]
            if not balance:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no payment channel {} found'.format(channel_oid_))

        return balance.marshal()

    @wamp.register(None, check_types=True)
    def get_paying_channel(self, channel_oid, details: Optional[CallDetails] = None):
        """
        Returns the (off-chain) paying channel given by the (on-chain) paying channel contract address.

        :param channel_oid: Paying channel contract address.
        :type channel_oid: bytes

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Paying channel information.
        :rtype: dict
        """
        assert type(channel_oid) == bytes and len(channel_oid) == 16, 'channel_oid must be bytes[16], was "{}"'.format(
            channel_oid)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        try:
            channel_oid_ = uuid.UUID(bytes=channel_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid channel_oid: {}'.format(str(e)))

        with self._db.begin() as txn:
            channel = self._schema.paying_channels[txn, channel_oid_]
            if not channel:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no paying channel {} found'.format(channel_oid_))

        return channel.marshal()

    @wamp.register(None, check_types=True)
    def get_paying_channel_balance(self, channel_oid, details: Optional[CallDetails] = None):
        """
        Returns the (off-chain, real-time) paying channel balance given by the (on-chain)
        payment channel contract address.

        :param channel_oid: Paying channel contract address.
        :type channel_oid: bytes

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Paying channel balance information.
        :rtype: dict
        """
        assert type(channel_oid) == bytes and len(channel_oid) == 16, 'channel_oid must be bytes[20], was "{}"'.format(
            channel_oid)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        try:
            channel_oid_ = uuid.UUID(bytes=channel_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid channel_oid: {}'.format(str(e)))

        with self._db.begin() as txn:
            balance = self._schema.paying_balances[txn, channel_oid_]
            if not balance:
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no paying channel {} found'.format(channel_oid_))

        return balance.marshal()

    @wamp.register(None, check_types=True)
    def get_active_payment_channel(self, delegate_adr, details: Optional[CallDetails] = None):
        """
        Returns the currently active payment channel and balance for a buyer delegate.

        :param delegate_adr: XBR buyer delegate address.
        :type delegate_adr: bytes

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Payment channel and balance details: ``(channel, balance)``.
        :rtype: tuple
        """
        assert type(delegate_adr) == bytes and len(
            delegate_adr) == 20, 'delegate_adr must be bytes[20], but was "{}"'.format(delegate_adr)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        self.log.info('{operation}(delegate_adr={delegate_adr}) ..',
                      operation=hlcontract('{}.get_active_payment_channel'.format(self.__class__.__name__)),
                      delegate_adr=hlid('0x' + binascii.b2a_hex(delegate_adr).decode()))

        channel, _ = self._get_active_channel_and_balance(delegate_adr, channel_type='payment')

        if channel:
            self.log.info('{operation}(delegate_adr={delegate_adr}): found active payment channel {channel_oid}',
                          operation=hlcontract('{}.get_active_payment_channel'.format(self.__class__.__name__)),
                          delegate_adr=hlid('0x' + binascii.b2a_hex(delegate_adr).decode()),
                          channel_oid=hlid(channel.channel_oid))

            return channel.marshal()
        else:
            return None

    @wamp.register(None, check_types=True)
    def get_active_paying_channel(self, delegate_adr, details: Optional[CallDetails] = None):
        """
        Returns the currently active paying channel for a seller delegate.

        :param delegate_adr: XBR seller delegate address.
        :type delegate_adr: bytes

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Paying channel and balance details: ``(channel, balance)``.
        :rtype: tuple
        """
        assert type(delegate_adr) == bytes and len(
            delegate_adr) == 20, 'delegate_adr must be bytes[20], but was "{}"'.format(delegate_adr)
        assert details is None or isinstance(
            details, CallDetails), 'details must be autobahn.wamp.types.CallDetails, but was "{}"'.format(details)

        self.log.info('{operation}(delegate_adr={delegate_adr}) ..',
                      operation=hlcontract('{}.get_active_paying_channel'.format(self.__class__.__name__)),
                      delegate_adr=hlid('0x' + binascii.b2a_hex(delegate_adr).decode()))

        channel, _ = self._get_active_channel_and_balance(delegate_adr, channel_type='paying')

        if channel:

            self.log.info('{operation}(delegate_adr={delegate_adr}): found active paying channel {channel_oid}',
                          operation=hlcontract('{}.get_active_paying_channel'.format(self.__class__.__name__)),
                          delegate_adr=hlid('0x' + binascii.b2a_hex(delegate_adr).decode()),
                          channel_oid=hlid(channel.channel_oid))

            return channel.marshal()
        else:
            return None

    def _get_active_channel_and_balance(self, delegate_adr, channel_type):
        """
        Queries the database index tables

        * ``idx_payment_channel_by_delegate``
        * ``idx_paying_channel_by_recipient``

        which contain the currently active payment/paying channel per buyer/seller delegate address.
        """
        assert type(delegate_adr) == bytes and len(
            delegate_adr) == 20, 'delegate_adr must be bytes[20], but was "{}"'.format(delegate_adr)
        assert channel_type in ['payment', 'paying'], 'invalid channel_type "{}"'.format(channel_type)

        t_zero = np.datetime64(0, 'ns')
        t_now = np.datetime64(time_ns(), 'ns')
        channel_oid, channel, balance = None, None, None
        with self._db.begin() as txn:

            # find next open payment/paying channel (if any)
            channel_oid = None
            cnt_searched = 0
            if channel_type == 'payment':
                for adr in self._schema.idx_payment_channel_by_delegate.select(txn,
                                                                               from_key=(delegate_adr, t_zero),
                                                                               to_key=(delegate_adr, t_now),
                                                                               return_keys=False):
                    cnt_searched += 1
                    channel_oid = adr
                    channel = self._schema.payment_channels[txn, channel_oid]
                    # channel must be open with positive remaining off-chain balance
                    if channel.state == 1:
                        balance = self._schema.payment_balances[txn, channel_oid]
                        if balance.remaining > 0:
                            break
                    channel_oid, channel, balance = None, None, None
            else:
                for adr in self._schema.idx_paying_channel_by_delegate.select(txn,
                                                                              from_key=(delegate_adr, t_zero),
                                                                              to_key=(delegate_adr, t_now),
                                                                              return_keys=False):
                    cnt_searched += 1
                    channel_oid = adr
                    channel = self._schema.paying_channels[txn, channel_oid]
                    # channel must be open with positive remaining off-chain balance
                    if channel.state == 1:
                        balance = self._schema.paying_balances[txn, channel_oid]
                        if balance.remaining > 0:
                            break
                    channel_oid, channel, balance = None, None, None

            if not channel_oid:
                return None, None
            else:
                self.log.debug(
                    'active {channel_type}-channel at {channel_oid} found for delegate with address 0x{delegate_adr}',
                    channel_type=channel_type,
                    channel_oid=channel_oid,
                    delegate_adr=binascii.b2a_hex(delegate_adr).decode())

            assert channel, 'internal error: no channel object in table schema.payment_channels (or schema.paying_channels) for channel address "{}"'.format(
                channel_oid)
            assert balance, 'internal error: balance record for channel missing'

        return channel, balance

    def _transfer_tokens(self, sender, recipient, amount):
        """

        :param sender:
        :type sender: bytes

        :param recipient:
        :type recipient: bytes

        :param amount: XBR tokens to transfer
        :type amount: int
        :return:
        """
        # raw amount of XBR tokens (taking into account decimals)
        raw_amount = amount * 10**18

        sender_addr = web3.Web3.toChecksumAddress(sender)
        recipient_addr = web3.Web3.toChecksumAddress(recipient)

        balance_eth = self._w3.eth.getBalance(sender_addr)
        balance_xbr = xbr.xbrtoken.functions.balanceOf(sender_addr).call()

        if amount > balance_xbr:
            raise Exception('insufficient on-chain XBR token amount {} on sender address {}'.format(
                balance_xbr, sender_addr))

        self.log.info(
            'Submitting blockchain transaction for of {amount} XBR from {sender_addr} (on-chain: {balance_eth} ETH, {balance_xbr} XBR) to {recipient_addr} ..',
            amount=hl(amount),
            balance_eth=hl(balance_eth),
            balance_xbr=hl(balance_xbr),
            sender_addr=hl(sender_addr),
            recipient_addr=hl(recipient_addr))

        try:
            # send blockchain transaction from explicit sender account
            success = xbr.xbrtoken.functions.transfer(recipient_addr, raw_amount).transact({
                'from': sender_addr,
                'gas': 100000
            })
        except ConnectionError:
            raise Exception('failed to transfer tokens: request timeout for blockchain transaction')

        # FIXME
        except Exception as e:
            msg = str(e)
            if 'VM Exception while processing transaction: revert' in msg:
                raise Exception('insufficient on-chain XBR token amount {} on sender address {}'.format(
                    balance_xbr, sender_addr))

        # FIXME: wait for the transaction to be mined and safely engraved on-chain ..

        if success:
            self.log.info('Transferred {amount} XBR from {sender_addr} to {recipient_addr}',
                          amount=hl(amount),
                          sender_addr=hl(sender_addr),
                          recipient_addr=hl(recipient_addr))
        else:
            raise Exception('failed to transfer tokens [2]')

    @wamp.register(None, check_types=True)
    async def set_consent(self,
                          member_adr: bytes,
                          market_oid: bytes,
                          verifying_chain_id: int,
                          current_block_number: int,
                          verifying_contract_adr: bytes,
                          delegate: bytes,
                          delegate_type: int,
                          catalog_oid: bytes,
                          consent: bool,
                          service_prefix: str,
                          signature: bytes,
                          attributes: Optional[dict] = None,
                          details: Optional[CallDetails] = None) -> dict:
        """
        Set XBR data consent status.

        The consent must be signed by the member, and the member must have
        joined the market (the member must be a provider or consumer actor
        in the market).

        Consent is given by the member to the specified delegate within
        the specified market, to provide or consume data - depending on
        ``delegate_type`` - under any XBR data API published to the given
        XBR data catalog. The data is provided or consumed under the respective
        data market terms and data catalog terms.

        :param member_adr: Wallet address of the member that sets the XBR consent status.

        :param market_oid: OID of the market (the member must
            be actor in) in which the member set the consent status.

        :param verifying_chain_id: Blockchain ID.

        :param current_block_number: Blockchain current block number.

        :param verifying_contract_adr: Address of ``XBRNetwork`` smart contract.

        :param delegate: Address of delegate consent (status) applies to.

        :param delegate_type: The delegate type (consumer or provider) this consent applies to.
            Note that consent can be given to a delegate (identified by its address) as both
            consumer and provider, and also for different API catalogs and markets.

        :param catalog_oid: The OID of the XBR API catalog consent is given for. Depending on
            ``delegate_type``, the delegate may then - depending on consent granted or
            forbidden (which is the default) - consume or provide data under an
            API from the catalog.

        :param consent: Status flag indicating whether consent is granted or forbidden.

        :param service_prefix: The WAMP URI prefix of the delegate under which it provides
            services implementing the APIs in the catalog. This URI must be globally unique
            for the delegate. Consumers of the service will access the delegate by using
            its ``service_prefix`` and under the respective API definition (eg what WAMP
            procedures and topics are provided by the service, and the types of application
            payloads used in procedures and topics.

        :param signature: EIP712 signature for setting XBR consent (signed by member).

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: XBR Consent setting information.
        """
        assert type(verifying_chain_id) == int
        assert type(current_block_number) == int
        assert type(verifying_contract_adr) == bytes and len(verifying_contract_adr) == 20
        assert type(signature) == bytes and len(signature) == 65
        assert attributes is None or type(attributes) == dict
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        is_address(member_adr)

        member_adr_hex = binascii.b2a_hex(member_adr).decode()
        if member_adr_hex.startswith("0x"):
            member_adr_hex = member_adr_hex[2:]

        member_adr_authid = extract_member_adr(details)

        assert member_adr_hex == member_adr_authid

        _market_oid = uuid.UUID(bytes=market_oid)
        _catalog_oid = uuid.UUID(bytes=catalog_oid)

        if type(verifying_chain_id) != int:
            raise RuntimeError('verifying_chain_id must be int, was "{}"'.format(type(verifying_chain_id)))

        if type(current_block_number) != int:
            raise RuntimeError('current_block_number must be int, was "{}"'.format(type(current_block_number)))

        if type(verifying_contract_adr) != bytes and len(verifying_contract_adr) != 20:
            raise RuntimeError('Invalid verifying_contract_adr "{!r}"'.format(verifying_contract_adr))

        if type(delegate) != bytes and len(delegate) != 20:
            raise RuntimeError('Invalid delegate "{!r}"'.format(delegate))

        if type(delegate_type) != int:
            raise RuntimeError('Invalid delegate type "{}"'.format(delegate_type))

        assert type(consent) == bool
        assert type(service_prefix) == str

        if attributes and type(attributes) != dict:
            raise RuntimeError('attributes must be dict, was "{}"'.format(type(attributes)))

        if type(signature) != bytes:
            raise RuntimeError('Invalid type {} for signature'.format(type(signature)))

        if len(signature) != (32 + 32 + 1):
            raise RuntimeError('Invalid signature length {} - must be 65'.format(len(signature)))

        try:
            signer_address = recover_eip712_consent(verifying_chain_id, verifying_contract_adr, member_adr,
                                                    current_block_number, _market_oid.bytes, delegate, delegate_type,
                                                    _catalog_oid.bytes, consent, service_prefix, signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed (member_adr={}): {}', member_adr, str(e))
            raise ApplicationError('xbr.error.invalid_signature', f'EIP712 signature recovery failed ({e})')

        if member_adr != signer_address:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, member_adr={member_adr}',
                          signer_address, member_adr)
            raise ApplicationError('xbr.error.invalid_signature', 'EIP712 signature invalid')

        try:
            _txn_hash = await deferToThread(self._send_setConsent, _market_oid.bytes, delegate, delegate_type,
                                            _catalog_oid.bytes, consent, service_prefix)
            print(_txn_hash)
        except Exception as e:
            self.log.failure()
            raise ApplicationError("xbr.marketmaker.error.consent_set_fail", e.args)

        with self._db.begin(write=True) as txn:
            consent_ = cfxdb.xbr.consent.Consent()
            consent_.catalog_oid = _catalog_oid
            consent_.member = member_adr
            consent_.consent = consent
            consent_.delegate = delegate
            consent_.delegate_type = delegate_type
            consent_.updated = current_block_number
            consent_.service_prefix = service_prefix
            consent_.market_oid = market_oid
            consent_.synced = False

            self._xbr.consents[txn, (_catalog_oid, member_adr, delegate, delegate_type, _market_oid)] = consent_

            return consent_.marshal()

    @wamp.register(None, check_types=True)
    def get_consent(self,
                    market_oid: bytes,
                    member: bytes,
                    delegate: bytes,
                    delegate_type: int,
                    catalog_oid: bytes,
                    include_attributes: bool = False,
                    details: Optional[CallDetails] = None) -> dict:

        assert type(market_oid) == bytes and len(market_oid) == 16
        assert type(member) == bytes and len(member) == 20
        assert type(delegate) == bytes and len(delegate) == 20
        assert type(delegate_type) == int
        assert type(catalog_oid) == bytes and len(catalog_oid) == 16
        assert type(include_attributes), 'include_attributes must be bool, was {}'.format(type(include_attributes))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        _market_oid = uuid.UUID(bytes=market_oid)
        _catalog_oid = uuid.UUID(bytes=catalog_oid)

        assert type(include_attributes), 'include_attributes must be bool, was {}'.format(type(include_attributes))

        with self._db.begin() as txn:
            consent = self._xbr.consents[txn, (_catalog_oid, member, delegate, delegate_type, _market_oid)]
            if not consent:
                raise ApplicationError('crossbar.error.no_such_object', 'no consent {}'.format(consent))

            return consent.marshal()

    @wamp.register(None, check_types=True)
    async def find_consents(self,
                            created_from: Optional[int] = None,
                            limit: Optional[int] = None,
                            include_owners: Optional[List[bytes]] = None,
                            include_delegates: Optional[List[bytes]] = None,
                            include_markets: Optional[List[bytes]] = None,
                            include_apis: Optional[List[bytes]] = None,
                            include_titles: Optional[List[str]] = None,
                            include_descriptions: Optional[List[str]] = None,
                            include_tags: Optional[List[str]] = None,
                            details: Optional[CallDetails] = None) -> List[bytes]:
        """
        Search for XBR Consents by

        * owning member (the member that gave consent)
        * descriptive title, description and tags
        * delegates the consents were given to

        as well as specify range and limit of the searched blockchain blocks and returned catalogs.

        .. seealso:: Unit test `fixme.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/fixme.py/>`_

        .. note::
            When a specific filter is not provided, the filter remains un-applied and respective consents
            are *not* filtered in the results. Specifically, when called without any arguments, this procedure
            will return *all* existing consents. The pagination via ``created_from`` and ``limit`` still applies.

        :param created_from: Only return consents created within blocks not earlier than this block number.

        :param limit: Only return consents from this many blocks beginning with block ``created_from``.
            So ``limit`` is in number of blocks and must be a positive integer when provided.

        To search for consents, the following filters can be used:

        :param include_owners: If provided, only return consents owned by any of the owners specified.

        :param include_delegates: If provided, only return consents for any of the delegates specified.

        :param include_markets: If provided, only return consents in any of the markets specified.

        :param include_apis: If provided, only return consents for any of the APIs specified.

        :param include_titles: If provided, only return consents with a title that
            contains any of the specified titles.

        :param include_descriptions: If provided, only return consents with a description that
            contains any of the specified descriptions.

        :param include_tags: If provided, only return consents with a tag that contains any of the specified tags.

        *FOR INTERNAL USE*

        :param details: DO NOT USE. Caller details internally provided by the router and cannot be used
            as an application level parameter.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of OIDs of consents matching the search criteria.
        """
        raise NotImplementedError()

    @wamp.register(None, check_types=True)
    async def get_catalogs_by_owner(self, owner_adr: bytes, details: Optional[CallDetails] = None):
        """
        :param owner_adr: Wallet address of the owner of the catalogs

        *FOR INTERNAL USE*

        :param details: DO NOT USE. Caller details internally provided by the router and cannot be used
            as an application level parameter.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of OIDs of catalogs matching the search criteria.
        """
        assert is_address(owner_adr)

        owner_adr_hex = without_0x(binascii.b2a_hex(owner_adr).decode())

        owner_adr_authid = extract_member_adr(details)

        assert owner_adr_hex == owner_adr_authid

        t_zero = np.datetime64(0, 'ns')
        t_now = np.datetime64(time_ns(), 'ns')

        with self._xbrmm_db.begin() as txn:
            catalogs = self._xbr.idx_catalogs_by_owner.select(txn,
                                                              from_key=(owner_adr, t_zero),
                                                              to_key=(owner_adr, t_now),
                                                              return_keys=False)
            result = []
            for catalog in catalogs:
                _catalog = self._xbr.catalogs[txn, catalog]
                marshaled = _catalog.marshal()
                meta_file = os.path.join(self._ipfs_files_dir, marshaled['meta'])
                if os.path.exists(meta_file):
                    # Is there really async IO from file system ?
                    marshaled['meta_data'] = open(meta_file).read()
                else:
                    marshaled['meta_data'] = ''
                result.append(marshaled)
            return result


xbr.IMarketMaker.register(MarketMaker)
