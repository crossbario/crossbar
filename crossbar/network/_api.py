# coding=utf8

##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import os
import threading
import re
from typing import List
import uuid
from pprint import pformat
from binascii import b2a_hex
from pathlib import Path
from typing import Optional, Dict

# txaio.use_twisted()  # noqa
from txaio import time_ns

from twisted.internet.threads import deferToThread

import numpy as np
import pyqrcode

from autobahn.wamp.types import RegisterOptions, CallResult, PublishOptions, CallDetails
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn import wamp
from autobahn import xbr
from autobahn.xbr import pack_uint256, make_w3, is_address, is_bytes16, is_chain_id, \
    is_block_number, is_signature, is_cs_pubkey

import treq
import zlmdb

from crossbar.common import checkconfig

from crossbar._version import __version__
from crossbar.network._util import extract_member_oid
from crossbar.edge.personality import check_blockchain

from twisted.web.client import ResponseNeverReceived

from ._util import hl, hlid, hlval, maybe_from_env, hltype

from hexbytes import HexBytes
import eth_keys
from eth_account import Account

import cfxdb
from cfxdb.xbr import ActorType
from ._backend import Backend
from ._mailgw import MailGateway


class Network(ApplicationSession):
    """
    XBR Network backend API exposed for client applications.

    .. note::

        This API covers the global parts of the XBR Network - APIs to individual XBR Data Markets, XBR Data Catalogs
        and XBR Cloud Domains are exposed by crossbar.
    """
    XBR_COIN_OID = uuid.UUID('74f53317-cbd6-4dc8-9214-195d0f9e98f9')

    @staticmethod
    def check_config(personality, extra: Optional[Dict]) -> Dict:
        """
        Check component extra configuration from ComponentConfig.extra.

        :param extra: Dictionary with component configuration.
        :type extra: dict

        :return: Normalized and auto-substituted configuration.
        :rtype: dict
        """
        if extra and 'blockchain' in extra:
            check_blockchain(personality, extra['blockchain'])
        else:
            raise checkconfig.InvalidConfigException(
                'missing mandatory attribute "blockchain" in XBR network backend configuration')
        return extra

    def __init__(self, config):
        from twisted.internet import reactor
        self._reactor = reactor

        self._status = 'starting'
        self.ident = '{}:{}:XBRNetwork@{}'.format(os.getpid(), threading.get_ident(), __version__)

        self.log.info('{klass}[{ident}].__init__()', klass=hl(self.__class__.__name__), ident=hlid(self.ident))

        self._dbpath = os.path.abspath(config.extra.get('dbpath', './.xbrnetwork'))
        self._db = zlmdb.Database(dbpath=self._dbpath, maxsize=2**30, readonly=False, sync=True)
        self._db.__enter__()
        self._meta = cfxdb.meta.Schema.attach(self._db)
        self._xbr = cfxdb.xbr.Schema.attach(self._db)
        self._xbrnetwork = cfxdb.xbrnetwork.Schema.attach(self._db)

        with self._db.begin() as txn:
            cnt_accounts = self._xbrnetwork.accounts.count(txn)
            cnt_idx_accounts_by_username = self._xbrnetwork.idx_accounts_by_username.count(txn)
            cnt_verified_actions = self._xbrnetwork.verified_actions.count(txn)

        self.log.info(
            'Database opened from {dbpath} (cnt_accounts={cnt_accounts}, cnt_idx_accounts_by_username={cnt_idx_accounts_by_username}, cnt_verified_actions={cnt_verified_actions})',
            dbpath=hlid(self._dbpath),
            cnt_accounts=hl(cnt_accounts),
            cnt_idx_accounts_by_username=hl(cnt_idx_accounts_by_username),
            cnt_verified_actions=hl(cnt_verified_actions))

        # External URL of web site. This is used for generating eg links in emails sent.
        #
        assert 'siteurl' in config.extra, 'external URL of web site required'
        website_url_from_env, website_url = maybe_from_env(config.extra['siteurl'])
        if website_url_from_env:
            self.log.info('External web site URL "{website_url}" configured from environment variable {envvar}',
                          website_url=hlval(website_url),
                          envvar=hlval(config.extra['siteurl']))
        else:
            self.log.info('External web site URL "{website_url}" from configuration', website_url=hlval(website_url))

        # Mailgun gateway configuration
        #
        if 'MAILGUN_KEY' in os.environ:
            mailgun_key = os.environ['MAILGUN_KEY']
        elif 'mailgun' in config.extra and 'key' in config.extra['mailgun']:
            mailgun_key = config.extra['mailgun']['key']
        else:
            raise RuntimeError('no mailgun key configured (neither from config, nor environment variable')

        if 'MAILGUN_URL' in os.environ:
            mailgun_url = os.environ['MAILGUN_URL']
        elif 'mailgun' in config.extra and 'url' in config.extra['mailgun']:
            mailgun_url = config.extra['mailgun']['url']
        else:
            raise RuntimeError('no mailgun url configured (neither from config, nor environment variable')

        if 'MAILGUN_FROM' in os.environ:
            mailgun_from = os.environ['MAILGUN_FROM']
        elif 'mailgun' in config.extra and 'from' in config.extra['mailgun']:
            mailgun_from = config.extra['mailgun']['from']
        else:
            mailgun_from = "The XBR project <no-reply@mailing.crossbar.io>"

        self._mailgw = MailGateway(mailgun_url, mailgun_key, mailgun_from, website_url)
        self._mailgun_from = mailgun_from

        # Market listing whitelist configuration
        self._markets_whitelist = []
        if 'markets_whitelist' in config.extra:
            assert type(config.extra['markets_whitelist']) == list, 'Must be a list of market UUIDs'
            for market in config.extra['markets_whitelist']:
                try:
                    market_uuid = uuid.UUID(market)
                    self._markets_whitelist.append(market_uuid)
                except ValueError:
                    assert False, f'Must be a list of market UUIDs, found invalid uuid {market} in list'

        # Blockchain gateway configuration
        #
        self._bc_gw_config = config.extra['blockchain']['gateway']
        self.log.info('Initializing Web3 from blockchain gateway configuration\n\n{gateway}\n',
                      gateway=pformat(self._bc_gw_config))
        self._w3 = make_w3(self._bc_gw_config)
        xbr.setProvider(self._w3)

        self._chain_id = config.extra['blockchain'].get('chain_id', 1)
        self.log.info('Using chain ID {chain_id}', chain_id=hlid(self._chain_id))

        # ipfs file caching config
        self._ipfs_files_directory = config.extra.get('ipfs_files_directory', './.ipfs_files')
        self._ipfs_files_path = os.path.join(config.extra.get("cbdir"), self._ipfs_files_directory)
        if not os.path.exists(self._ipfs_files_path):
            Path(self._ipfs_files_path).mkdir()

        # market maker private Ethereum key file
        keypath = os.path.abspath(config.extra['blockchain']['key'])
        if os.path.exists(keypath):
            with open(keypath, 'rb') as f:
                self._eth_privkey_raw = f.read()
                assert type(self._eth_privkey_raw) == bytes and len(self._eth_privkey_raw) == 32
                self.log.info('Existing XBR Network Backend Ethereum private key loaded from "{keypath}"',
                              keypath=hlid(keypath))
        else:
            self._eth_privkey_raw = os.urandom(32)
            with open(keypath, 'wb') as f:
                f.write(self._eth_privkey_raw)
                self.log.info('New XBR Network Backend Ethereum private key generated and stored as {keypath}',
                              keypath=hlid(keypath))

        # make sure the private key file has correct permissions
        if os.stat(keypath).st_mode & 511 != 384:  # 384 (decimal) == 0600 (octal)
            os.chmod(keypath, 384)
            self.log.info('File permissions on XBR Network Backend private Ethereum key fixed')

        # make a private key object from the raw private key bytes
        self._eth_privkey = eth_keys.keys.PrivateKey(self._eth_privkey_raw)
        self._eth_acct = Account.privateKeyToAccount(self._eth_privkey_raw)

        # get the canonical address of the account
        self._eth_adr_raw = self._eth_privkey.public_key.to_canonical_address()
        self._eth_adr = self._w3.toChecksumAddress(self._eth_adr_raw)

        # XBR Network backend
        #
        self._network = Backend(self, self._db, self._meta, self._xbr, self._xbrnetwork, self._chain_id,
                                self._eth_privkey_raw, self._w3, self._mailgw, config.extra['blockchain'],
                                self._ipfs_files_path)

        ApplicationSession.__init__(self, config)

    async def onJoin(self, details):
        self.log.info('{klass}[{ident}].onJoin(details={details})',
                      klass=self.__class__.__name__,
                      ident=self.ident,
                      details=details)

        await self.register(self, options=RegisterOptions(details=True))

        def get_balances(wallet_adr):
            eth_balance = self._w3.eth.getBalance(wallet_adr)
            xbr_balance = xbr.xbrtoken.functions.balanceOf(wallet_adr).call()
            return eth_balance, xbr_balance

        eth_balance, xbr_balance = await deferToThread(get_balances, self._eth_adr)

        qr = pyqrcode.create(self._eth_adr, error='L', mode='binary')
        self.log.info(
            '\n\n  {component}\n\n  Chain: {chain_id}\n  Address: {eth_adr}\n  ETH: {eth_balance}\n  XBR: {xbr_balance}\n{qrcode}',
            component=hl('XBR Network Backend (planet.xbr.network)'),
            chain_id=hlid(self._chain_id),
            eth_adr=hlid(self._eth_adr),
            eth_balance=hlval(eth_balance),
            xbr_balance=hlval(xbr_balance),
            qrcode=qr.terminal())

        self._status = 'ready'
        status = await self.get_status()
        await self.publish('xbr.network.on_status', status, options=PublishOptions(acknowledge=True))

    def onLeave(self, details):
        self.log.info('{klass}[{ident}].onLeave(details={details})',
                      klass=self.__class__.__name__,
                      ident=self.ident,
                      details=details)
        self._status = 'stopping'
        self._network.stop()
        # status = await self.get_status()
        # await self.publish('xbr.network.on_status', status, options=PublishOptions(acknowledge=True))
        # self.publish('xbr.network.on_status', status)
        ApplicationSession.onLeave(self, details)

    @wamp.register('xbr.network.echo')
    def echo(self, *args, **kwargs):
        """
        Test/Development test procedure: echo back any and all positional arguments
        and keywords arguments given.

        * **Procedure**: ``xbr.network.echo``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `test_api_echo.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api_echo.py/>`_

        :param args: Arbitrary positional call arguments - returned "as is".
        :type args: list

        :param kwargs: Arbitrary keyword call arguments - returned "as is".
        :type kwargs: dict

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: The positional and keyword arguments as provided to the call.
        :rtype: :class:`autobahn.wamp.types.CallResult`
        """
        details = kwargs.pop('details', None)
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        cnt_args = len(args)
        cnt_kwargs = len(kwargs)

        self.log.info('{klass}.echo(cnt_args={cnt_args}, cnt_kwargs={cnt_kwargs}, details={details})',
                      klass=self.__class__.__name__,
                      cnt_args=cnt_args,
                      cnt_kwargs=cnt_kwargs,
                      details=details)

        return CallResult(*args, **kwargs)

    @wamp.register('xbr.network.get_transaction_receipt', check_types=True)
    async def get_transaction_receipt(self, transaction: bytes, details: Optional[CallDetails] = None) -> dict:
        """

        :param transaction:
        :param details:
        :return:
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        r = await deferToThread(self._network._get_transaction_receipt, transaction)
        receipt = {}

        # copy over all information returned, all but two: "logs", "logsBloom"
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

    @wamp.register('xbr.network.get_gas_price', check_types=True)
    async def get_gas_price(self, details: Optional[CallDetails] = None) -> bytes:
        """

        :param details:
        :return:
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        gas_price = await deferToThread(self._network._get_gas_price)
        return gas_price

    @wamp.register('xbr.network.get_config', check_types=True)
    async def get_config(self, include_eula_text: bool = False, details: Optional[CallDetails] = None) -> dict:
        """
        Get backend configuration / settings.

        * **Procedure**: ``xbr.network.get_status``
        * **Errors**: ``wamp.error.*``

        .. note::

            All configuration settings here are security-insensitive ("harmless") and public.

        .. seealso:: Unit test `test_api_echo.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api_echo.py/>`_

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Current backend status information. For example:

            .. code-block:: python

                {
                    "now": 1573675753141788247,
                    "chain": 4,
                    "contracts": {
                        "xbrtoken": "0x78890bF748639B82D225FA804553FcDBe5819576",
                        "xbrnetwork": "0x96f2b95733066aD7982a7E8ce58FC91d12bfbB2c",
                    }
                    "eula": {
                        "hash": "QmV1eeDextSdUrRUQp9tUXF8SdvVeykaiwYLgrXHHVyULY",
                        "url": "https://raw.githubusercontent.com/crossbario/xbr-protocol/master/ipfs/xbr-eula/XBR-EULA.txt",
                        "text": "XBR End User License Agreement (EULA) ..."
                    }
                    "from": "The XBR project <no-reply@mailing.crossbar.io>"
                }

            * ``now``: Current time (number of nanoseconds since the Unix epoch).
            * ``chain``: Chain ID (blockchain network).
            * ``contracts``: Addresses of XBR smart contract instances (on-chain):

                * ``xbrtoken``: On-chain address of ``XBRToken`` contract.
                * ``xbrnetwork``: On-chain address of ``XBRNetwork`` contract.
            * ``eula``: Current XBR network EULA (IPFS Multihash):

                * ``url``: Web URL to download EULA text.
                * ``hash``: Hash of EULA text.
                * ``text``: Actual EULA text.
            * ``from``: Email sending address for system emails.
        """
        assert type(include_eula_text) == bool, 'include_eula_text must be bool, was {}'.format(
            type(include_eula_text))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        config = await deferToThread(self._network.get_config, include_eula_text=include_eula_text)
        config['from'] = self._mailgun_from
        return config

    @wamp.register('xbr.network.get_status', check_types=True)
    async def get_status(self, details: Optional[CallDetails] = None) -> dict:
        """
        Get backend status.

        * **Procedure**: ``xbr.network.get_status``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `test_api01_echo.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api01_echo.py/>`_

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Current backend status information. For example:

            .. code-block:: python

                {
                    "now": 1573675753141788247,
                    "status": "ready",
                    "chain": 4,
                    "block": {
                        "number": 5958028,
                        "hash": b"",
                        "gas_limit": 10000000,
                    }
                }

            * ``now``: Current time (number of nanoseconds since the Unix epoch).
            * ``status``: Current system status (one of ``["starting", "ready", "stopping"]``).
            * ``chain``: Chain ID (blockchain network).
            * ``block``: Current block information:

                * ``number``: Current block number
                * ``hash``: Current block hash
                * ``gas_limit``: Current block gas limit
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        status = await deferToThread(self._network.get_status)
        status['status'] = self._status
        return status

    @wamp.register('xbr.network.onboard_member', check_types=True)
    async def onboard_member(self,
                             member_username: str,
                             member_email: str,
                             client_pubkey: bytes,
                             wallet_type: str,
                             wallet_adr: bytes,
                             chain_id: int,
                             block_number: int,
                             contract_adr: bytes,
                             eula_hash: str,
                             profile_hash: Optional[str],
                             profile_data: Optional[bytes],
                             signature: bytes,
                             details: Optional[CallDetails] = None) -> dict:
        """
        On-board new member with the given information. If all is fine with the supplied information, the
        member will be sent a verification email to the email address specified.

        Once the Web link contained in the verification email is clicked, the :class:`xbrnetwork.Api.verify_onboard_member`
        procedure should be called with the (query) information contained in the verification link.

        * **Procedure**: ``xbr.network.onboard_member``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `test_api02_onboard.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api02_onboard.py/>`_

        :param member_username: New member username. A username must begin with a lower-case letter,
            continue with lower-case letters, digits or ``_`` and have a length from 4 to 14 characters.

        :param member_email: New member email address.

        :param client_pubkey: Client Ed25519 public key (32 bytes).

        :param wallet_type: Wallet type.

        :param wallet_adr: New member wallet address.

        :param chain_id: Blockchain ID.

        :param block_number: Current blockchain block number.

        :param contract_adr: Address of ``XBRNetwork`` smart contract.

        :param eula_hash: Multihash (sha256, base64 encoded) of XBR Network EULA signed (eg currently, the
            EULA multihash must be ``"QmV1eeDextSdUrRUQp9tUXF8SdvVeykaiwYLgrXHHVyULY"``).

        :param profile_hash: Multihash (SHA256 Base64-encoded, for example
            ``"QmcU74QYcPQJCPUVVRwguVfrSnt8ZJrnbXzYPhxfhey7Qb"``) computed from a CBOR-serialized profile object:

                .. code-block:: python

                    {
                        "member_username": member_username,
                        "member_email": member_email,
                        "client_pubkey": client_pubkey
                        "wallet_type": wallet_type
                    }

        :param profile_data: CBOR-serialized profile object (see above).

        :param signature: EIP712 signature (using wallet private key of member) over ``chain_id``, ``block_number``,
            ``contract_adr``, ``eula_hash`` and ``profile_hash``.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Verification submission, including verification action ID. For example:

            .. code-block:: python

                {
                    "timestamp": 1573675753141788247,
                    "action": "onboard-member",
                    "vaction_oid": b'\x9fUW\xd87\xf8D`\x8c\x90\xaaK\x97\xff\xa0\xbe'
                }

            * ``timestamp``: Timestamp of submission (number of nanoseconds since the Unix epoch).
            * ``action``: Type of action being verified, eg ``"onboard_member"``
            * ``vaction_oid``: ID of action verified (16 bytes UUID).
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)
        assert type(client_pubkey) == bytes, 'client_pubkey must be bytes, but was "{}"'.format(type(client_pubkey))
        assert len(client_pubkey) == 32, 'client_pubkey must be bytes[32], but was bytes[{}]'.format(
            len(client_pubkey))
        assert type(wallet_adr) == bytes, 'wallet_adr must be bytes, but was "{}"'.format(type(wallet_adr))
        assert len(wallet_adr) == 20, 'wallet_adr must be bytes[20], but was bytes[{}]'.format(len(wallet_adr))

        self.log.info(
            '{klass}.onboard_member(wallet_type={wallet_type}, eula_hash={eula_hash}, profile_hash={profile_hash}, wallet_adr={wallet_adr}, member_email={member_email}, member_username={member_username}, details={details})',
            klass=self.__class__.__name__,
            wallet_type=wallet_type,
            eula_hash=eula_hash,
            profile_hash=profile_hash,
            wallet_adr=wallet_adr,
            member_email=member_email,
            member_username=member_username,
            details=details)
        onboard_request_submitted = await self._network.onboard_member(member_username, member_email, client_pubkey,
                                                                       wallet_type, wallet_adr, chain_id, block_number,
                                                                       contract_adr, eula_hash, profile_hash,
                                                                       profile_data, signature)

        # FIXME: eligible_authid == authid of the user that is on-boarding
        eligible_authid = None
        await self.publish('xbr.network.on_onboard_member_vcode_sent',
                           onboard_request_submitted,
                           options=PublishOptions(acknowledge=True, eligible_authid=eligible_authid))

        return onboard_request_submitted

    @wamp.register('xbr.network.verify_onboard_member', check_types=True)
    async def verify_onboard_member(self,
                                    vaction_oid: bytes,
                                    vaction_code: str,
                                    details: Optional[CallDetails] = None) -> dict:
        """
        Verify on-boarding of a new member by submitting a verification code.

        Upon successful on-board, this procedure will also publish the same data that is returned
        to the following topic - but only for subscribers of same ``authid`` (clients of the user
        that was on-boarded):

        * **Procedure**: ``xbr.network.verify_onboard_member``
        * **Events**: ``xbr.network.on_new_member``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `test_api02_onboard.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api02_onboard.py/>`_

        :param vaction_oid: Verification action ID (16 bytes UUID).

        :param vaction_code: Verification code, for example ``"EK5H-JJ4H-CECK"``

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Member on-boarded information, including ID of new member. For example:

            .. code-block:: python

                {
                    'created': 1582146264584727254,
                    'member_oid': b'...',
                    'block_hash': b'...',
                    'block_number': b'...',
                    'transaction_hash': b'...',
                    'transaction_index': b'...'
                }

            * ``created``: Member creation timestamp (number of nanoseconds since the Unix epoch).
            * ``member_oid``: ID of newly on-boarded member (16 bytes UUID).
        """
        self.log.info(
            '{klass}.verify_onboard_member(vaction_oid={vaction_oid}, vaction_code={vaction_code}, details={details})',
            klass=self.__class__.__name__,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code,
            details=details)
        onboard_request_verified = await self._network.verify_onboard_member(vaction_oid, vaction_code)

        # FIXME: eligible_authid == authid of the user that was on-boarded
        eligible_authid = None
        await self.publish('xbr.network.on_onboard_member_vcode_verified',
                           onboard_request_verified,
                           options=PublishOptions(acknowledge=True, eligible_authid=eligible_authid))
        return onboard_request_verified

    @wamp.register('xbr.network.backup_wallet', check_types=True)
    def backup_wallet(self,
                      member_oid: bytes,
                      wallet_data: bytes,
                      signature: bytes,
                      details: Optional[CallDetails] = None) -> bytes:
        """
        If the account is using a hosted wallet (account ``wallet_type == "hosted"``), after creating a new client wallet
        private key, the client should upload the (encrypted) private key - encrypted with a password - by calling
        this procedure. A hosted wallet can be restored by calling ``xbr.network.recover_wallet``.

        :param member_oid: ID of the member to backup the hosted wallet for.

        :param wallet_data: Encrypted, serialized wallet data to backup. A maximum of 64kB can be stored.

        :param signature:

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: SHA256 hash computed over ``wallet_data``
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.recover_wallet', check_types=True)
    def recover_wallet(self,
                       member_email: str,
                       chain_id: int,
                       block_number: int,
                       contract_adr: bytes,
                       req_nonce: int,
                       wallet_adr: bytes,
                       signature: bytes,
                       details: Optional[CallDetails] = None) -> dict:
        """
        Recover a hosted wallet (account ``wallet_type == "hosted"``)

        :param member_email: Existing member (primary) email address.

        :param chain_id: Blockchain ID.

        :param block_number: Blockchain current block number.

        :param contract_adr: Address of ``XBRNetwork`` smart contract.

        :param req_nonce: Random request nonce (chosen by client).

        :param wallet_adr: Member wallet address used for signing.

        :param signature: EIP712 signature (using wallet private key of member) over ``member_email``,
            ``chain_id``, ``block_number``, ``contract_adr`` and ``req_nonce``.

        :return: Wallet recovery submission, including verification action ID and code. For example:

            .. code-block:: python

                {
                    "now": 1573675753141788247,
                    "valid_until": 1573675753971231455,
                    "vaction": "recover-wallet",
                    "vaction_oid": "9f5557d8-37f8-4460-8c90-aa4b97ffa0be",
                    "vaction_code": "PXFH-GF4Y-7ALJ"
                }
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.verify_recover_wallet', check_types=True)
    def verify_recover_wallet(self,
                              vaction_oid: bytes,
                              vaction_code: str,
                              details: Optional[CallDetails] = None) -> bytes:
        """
        Verify recovery of a (hosted) wallet the member by submitting a verification code.

        :param vaction_oid: Verification action ID.

        :param vaction_code: Verification code.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: The serialized wallet data (encrypted with a password).
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.get_member', check_types=True)
    async def get_member(self, member_oid: bytes, details: Optional[CallDetails] = None) -> dict:
        """
        Retrieve information for member given member ID (not wallet address).

        .. seealso:: Unit test `test_api04_member.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api04_member.py/>`_

        :param member_oid: ID of the member to retrieve information for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Member information. For example:

            .. code-block:: python

                {
                    'oid': b'\xaca\xc5\xbfm\xd1\xad\xbb\xcd[G\xcbM\xf7cE',
                    'created': 1582281124907755461,
                    'level': 1,
                    'address': b'\x81\xa6e\xa4\x1a!pxR\xc8\xe9CM\x1a\xdfN\x88\x9c\x84K',
                    'username': 'somebody'
                    'email': 'somebody@nodomain',
                    'eula': 'QmcU74QYcPQJCPUVVRwguVfrSnt8ZJrnbXzYPhxfhey7Qb',
                    'profile': 'QmV1eeDextSdUrRUQp9tUXF8SdvVeykaiwYLgrXHHVyULY',
                    'balance': {
                        'eth': b'',
                        'xbr': b''
                    },
                    'catalogs': 0,
                    'domains': 0,
                    'markets': 0,
                }

        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        # caller_authid=member-e939a1c8-8af0-4359-9415-acafc4a35ffa
        assert details and details.caller_authid and len(details.caller_authid) == 43

        # FIXME: do we want to enforce any record-level authorization here?
        #
        # WAMP authid on xbrnetwork follows this format: "member-"
        # member_oid_from_authid = uuid.UUID(details.caller_authid[7:])
        # member_oid_ = uuid.UUID(bytes=member_oid)
        # if member_oid_ != member_oid_from_authid:
        #     raise RuntimeError('only own information can be accessed!')

        member = await self._network.get_member(member_oid)

        return member

    @wamp.register('xbr.network.get_member_by_wallet', check_types=True)
    async def get_member_by_wallet(self, wallet_adr: bytes, details: Optional[CallDetails] = None) -> Optional[dict]:
        """
        Retrieve information for member given member wallet address (not member ID).

        .. seealso:: Unit test `test_api04_member.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api04_member.py/>`_

        :param wallet_adr: Member wallet address.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Member information.
        """
        assert type(wallet_adr) == bytes and len(wallet_adr) == 20, 'wallet_adr must be bytes[20], was {}'.format(
            type(wallet_adr))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        with self._db.begin() as txn:
            account_oid = self._xbrnetwork.idx_accounts_by_wallet[txn, wallet_adr]
            if not account_oid:
                return None

        result = await self.get_member(account_oid.bytes, details=details)
        return result

    @wamp.register('xbr.network.is_member', check_types=True)
    async def is_member(self, wallet_adr: bytes, details: Optional[CallDetails] = None) -> bool:
        """
        Check if the given Ethereum address is a member in the XBR network.

        .. note:: This procedure is public and can be called by anyone. However, membership information if
            public anyways, since membership is tracked on-chain.

        :param wallet_adr: Member wallet address.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Flag indicating whether the address is a member or not.
        """
        assert type(wallet_adr) == bytes and len(wallet_adr) == 20, 'wallet_adr must be bytes[20], was {}'.format(
            type(wallet_adr))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        # FIXME: we currently lack records in accounts for members that were created outside _our_ onboarding
        with self._db.begin() as txn:
            account_oid = self._xbrnetwork.idx_accounts_by_wallet[txn, wallet_adr]
            if account_oid:
                return True
            else:
                return False

    @wamp.register('xbr.network.login_member', check_types=True)
    async def login_member(self,
                           member_email: str,
                           client_pubkey: bytes,
                           chain_id: int,
                           block_number: int,
                           contract_adr: bytes,
                           timestamp: int,
                           wallet_adr: bytes,
                           signature: bytes,
                           details: Optional[CallDetails] = None) -> dict:
        """
        When a user is already member in the XBR network, a user client may call this procedure to login.

        Adds a (WAMP-cryptosign) client public key for the XBR member. The signature must be created using the
        private key of the members' wallet.

        For example, on a new browser instance, a user might install Metamask and provide the seedphrase
        of the users existing wallet. The client now creates a new Ed25519 private key (for WAMP-cryptosign).
        Then, by using Metamask for signing data and calling this procedure, the user will receive a verification
        email with a verification code. The client then needs to call :meth:`Api.verify_login_member`
        with the verification action ID and code received via email. This latter procedure will then
        add the user client key to the authentication database of the XBR Network backend.

        * **Procedure**: ``xbr.network.login_member``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `test_api03_login.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api03_login.py/>`_

        :param member_email: Existing member (primary) email address.

        :param client_pubkey: Client Ed25519 public key (32 bytes).

        :param chain_id: Blockchain ID.

        :param block_number: Blockchain current block number.

        :param contract_adr: Address of ``XBRNetwork`` smart contract.

        :param timestamp: Timestamp of submission (number of nanoseconds since the Unix epoch
            within the client).

        :param wallet_adr: Member wallet address used for signing.

        :param signature: EIP712 signature (using wallet private key of member) over ``member_email``,
            ``client_pubkey``, ``chain_id``, ``block_number``, ``contract_adr`` and ``timestamp``.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Verification submission, including verification action ID. For example:

            .. code-block:: python

                {
                    "timestamp": 1573675753141788247,
                    "action": "login-member",
                    "vaction_oid": b'\x9fUW\xd87\xf8D`\x8c\x90\xaaK\x97\xff\xa0\xbe'
                }

            * ``timestamp``: Timestamp of submission (number of nanoseconds since the Unix epoch).
            * ``action``: Type of action being verified, eg ``"login-member"``
            * ``vaction_oid``: ID of action verified (16 bytes UUID).
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)
        assert type(client_pubkey) == bytes, 'client_pubkey must be bytes, but was "{}"'.format(type(client_pubkey))
        assert len(client_pubkey) == 32, 'client_pubkey must be bytes[32], but was bytes[{}]'.format(
            len(client_pubkey))
        assert type(wallet_adr) == bytes, 'wallet_adr must be bytes, but was "{}"'.format(type(wallet_adr))
        assert len(wallet_adr) == 20, 'wallet_adr must be bytes[20], but was bytes[{}]'.format(len(wallet_adr))

        self.log.info(
            '{klass}.login_member(member_email={member_email}, client_pubkey={client_pubkey}, chain_id={chain_id}, block_number={block_number}, timestamp={timestamp}, wallet_adr={wallet_adr}, signature={signature}, details={details})',
            klass=self.__class__.__name__,
            member_email=member_email,
            client_pubkey=client_pubkey,
            chain_id=chain_id,
            block_number=block_number,
            timestamp=timestamp,
            wallet_adr=wallet_adr,
            signature=signature,
            details=details)
        login_request_submitted = await self._network.login_member(member_email, client_pubkey, chain_id, block_number,
                                                                   contract_adr, timestamp, wallet_adr, signature)
        return login_request_submitted

    @wamp.register('xbr.network.verify_login_member', check_types=True)
    async def verify_login_member(self,
                                  vaction_oid: bytes,
                                  vaction_code: str,
                                  details: Optional[CallDetails] = None) -> dict:
        """
        Verify login of member by submitting a verification code.

        Upon successful login, this procedure will also publish the same data that is returned
        to the following topic - but only for subscribers of same ``authid`` (clients of the user
        that was logged in):

        * **Procedure**: ``xbr.network.verify_login_member``
        * **Events**: ``xbr.network.on_member_login``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `test_api03_login.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api03_login.py/>`_

        :param vaction_oid: Verification action ID.

        :param vaction_code: Verification code.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Member login information, including ID of existing member. For example:

            .. code-block:: python

                {
                    "member_oid": None,
                    "client_pubkey": None,
                    "created": 1573675753141788247,
                }
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        self.log.info(
            '{klass}.verify_login_member(vaction_oid={vaction_oid}, vaction_code={vaction_code}, details={details})',
            klass=self.__class__.__name__,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code,
            details=details)
        login_request_verified = self._network.verify_login_member(vaction_oid, vaction_code)
        await self.publish('xbr.network.on_member_login',
                           login_request_verified,
                           options=PublishOptions(acknowledge=True))
        return login_request_verified

    @wamp.register('xbr.network.logout_member', check_types=True)
    async def logout_member(self, details: CallDetails):
        """
        Logout the currently authenticated authid and delete the (WAMP-cryptosign) client
        public key from the member.

        .. note::
            The procedure will return normally, but then immediately kill the client session
            pro-actively from the router-side.

        .. seealso:: Unit test `test_api03_logout.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api03_logout.py/>`_

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Client key removed information.
        """
        self.log.info('{klass}.logout_member(details={details})', klass=self.__class__.__name__, details=details)

        caller_session_id = details.caller
        member_oid = extract_member_oid(details)

        caller_pubkey = await self.call('xbr.network.authenticator.pubkey_by_session', caller_session_id)
        assert is_cs_pubkey(caller_pubkey)
        self.log.info('{klass}.logout_member with caller pubkey {caller_pubkey})',
                      klass=self.__class__.__name__,
                      caller_pubkey=hlid(b2a_hex(caller_pubkey).decode()))

        with self._db.begin() as txn:
            account = self._xbrnetwork.accounts[txn, member_oid]
            assert account
            userkey = self._xbrnetwork.user_keys[txn, caller_pubkey]
            assert userkey
            assert userkey.owner == member_oid

        with self._db.begin(write=True) as txn:
            del self._xbrnetwork.user_keys[txn, caller_pubkey]

        self.log.info('Ok, deleted client login for pubkey {caller_pubkey} of member {member_oid} ',
                      caller_pubkey=hlid(b2a_hex(caller_pubkey).decode()),
                      member_oid=hlid(member_oid))

        logout_info = {
            'logged_out': time_ns(),
            'from_session': caller_session_id,
            'member_oid': member_oid.bytes,
            'pubkey': caller_pubkey,
        }

        def kill():
            self.call('wamp.session.kill_by_authid', details.caller_authid)
            self.publish('xbr.network.on_logout',
                         logout_info,
                         options=PublishOptions(eligible_authid=[details.caller_authid]))
            self.log.info(
                'Ok, session {caller_session} logged out for client with pubkey {caller_pubkey} of member {member_oid} ',
                caller_session=hlid(caller_session_id),
                caller_pubkey=hlid(b2a_hex(caller_pubkey).decode()),
                member_oid=hlid(member_oid))

        # first return from this call, before killing its session ..
        self._reactor.callLater(0, kill)

        return logout_info

    @wamp.register('xbr.network.get_member_logins', check_types=True)
    def get_member_logins(self, member_oid: bytes, details: Optional[CallDetails] = None) -> list:
        """
        Get client keys currently associated with the member.

        .. seealso:: Unit test `test_api04_member.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api04_member.py/>`_

        :param member_oid: ID of the member of which to retrieve client keys for. This MUST be identical to the
            caller of this procedure - only the list of client keys for the currently authenticated member can
            be retrieved.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of client public keys currently associated with the member.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)
        assert type(member_oid) == bytes and len(member_oid) == 16

        # caller_authid=member-e939a1c8-8af0-4359-9415-acafc4a35ffa
        assert details and details.caller_authid and len(details.caller_authid) == 43

        # WAMP authid on xbrnetwork follows this format: "member-"
        member_oid_from_authid = uuid.UUID(details.caller_authid[7:])

        member_oid_ = uuid.UUID(bytes=member_oid)
        if member_oid_ != member_oid_from_authid:
            raise RuntimeError('only own information can be accessed!')

        t_zero = np.datetime64(0, 'ns')
        t_now = np.datetime64(time_ns(), 'ns')

        pubkeys = []
        with self._db.begin() as txn:
            for pubkey in self._xbrnetwork.idx_user_key_by_account.select(txn,
                                                                          from_key=(member_oid_, t_zero),
                                                                          to_key=(member_oid_, t_now),
                                                                          return_keys=False):
                pubkeys.append(pubkey)

        return pubkeys

    @wamp.register('xbr.network.get_member_login', check_types=True)
    def get_member_login(self, member_oid: bytes, client_pubkey: bytes, details: Optional[CallDetails] = None) -> dict:
        """
        Get client key details.

        .. seealso:: Unit test `test_api04_member.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api04_member.py/>`_

        :param member_oid: ID of the member of which to retrieve a client key for. This MUST be identical to the
            caller of this procedure - only client keys for the currently authenticated member can be retrieved.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Client key information.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)
        assert type(member_oid) == bytes and len(member_oid) == 16

        # caller_authid=member-e939a1c8-8af0-4359-9415-acafc4a35ffa
        assert details and details.caller_authid and len(details.caller_authid) == 43

        # WAMP authid on xbrnetwork follows this format: "member-"
        member_oid_from_authid = uuid.UUID(details.caller_authid[7:])

        member_oid_ = uuid.UUID(bytes=member_oid)
        if member_oid_ != member_oid_from_authid:
            raise RuntimeError('only own information can be accessed [1]')

        with self._db.begin() as txn:
            userkey = self._xbrnetwork.user_keys[txn, client_pubkey]
            if not userkey:
                raise RuntimeError('no such pubkey')
            if userkey.owner != member_oid_:
                raise RuntimeError('only own information can be accessed [2]')

        return userkey.marshal()

    @wamp.register('xbr.network.create_coin', check_types=True)
    async def create_coin(self,
                          member_oid: bytes,
                          coin_oid: bytes,
                          chain_id: int,
                          block_number: int,
                          contract_adr: bytes,
                          name: str,
                          symbol: str,
                          decimals: int,
                          initial_supply: bytes,
                          meta_hash: Optional[str],
                          meta_data: Optional[bytes],
                          signature: bytes,
                          attributes: Optional[dict],
                          details: Optional[CallDetails] = None) -> dict:
        """
        Create a new ERC20 coin for use in data markets as a means of payment.

        :param member_oid:
        :param coin_oid:
        :param chain_id: Blockchain ID.
        :param block_number: Blockchain current block number.
        :param contract_adr: Address of verifying contract.
        :param name:
        :param symbol:
        :param decimals:
        :param initial_supply:
        :param meta_hash:
        :param meta_data:
        :param attributes:
        :param signature: EIP712 signature for the coin creation.
        :param attributes: Coin attributes.
        :param details: Caller details.

        :return: Coin creation information.
        """
        assert type(member_oid) == bytes and len(member_oid) == 16
        assert type(coin_oid) == bytes and len(coin_oid) == 16
        assert type(chain_id) == int
        assert type(block_number) == int
        assert type(contract_adr) == bytes and len(contract_adr) == 20
        assert type(name) == str
        assert type(symbol) == str
        assert type(decimals) == int
        assert type(initial_supply) == bytes and len(initial_supply) == 32
        assert meta_hash is None or type(meta_hash) == str
        assert meta_data is None or type(meta_data) == bytes
        assert (meta_hash is None and meta_data is None) or (meta_hash is not None and meta_data is not None)
        assert attributes is None or type(attributes) == dict
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        member_oid_ = uuid.UUID(bytes=member_oid)
        coin_oid_ = uuid.UUID(bytes=coin_oid)

        request = await self._network.create_coin(member_oid_, coin_oid_, chain_id, block_number, contract_adr, name,
                                                  symbol, decimals, initial_supply, meta_hash, meta_data, signature,
                                                  attributes)
        return request

    @wamp.register('xbr.network.verify_create_coin', check_types=True)
    async def verify_create_coin(self,
                                 vaction_oid: bytes,
                                 vaction_code: str,
                                 details: Optional[CallDetails] = None) -> dict:
        """
        Verify creating a new ERC20 coin by submitting a verification code.

        Upon successful coin creation, this procedure will also publish the same data that is returned
        to the following topic:

        * **Procedure**: ``xbr.network.verify_create_coin``
        * **Events**: ``xbr.network.on_new_coin``
        * **Errors**: ``wamp.error.*``

        :param vaction_oid: Verification action ID (16 bytes UUID).

        :param vaction_code: Verification code, for example ``"EK5H-JJ4H-CECK"``

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Coin creation information, including ID of new coin. For example:

            .. code-block:: python

                {
                    'created': 1582146264584727254,
                    'market_oid': b'...',
                    'block_hash': b'...',
                    'block_number': b'...',
                    'transaction_hash': b'...',
                    'transaction_index': b'...'
                }

            * ``created``: Coin creation timestamp (number of nanoseconds since the Unix epoch).
            * ``market_oid``: ID of newly created coin (16 bytes UUID).
        """
        self.log.info(
            '{klass}.verify_create_coin(vaction_oid={vaction_oid}, vaction_code={vaction_code}, details={details})',
            klass=self.__class__.__name__,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code,
            details=details)
        request_verified = await self._network.verify_create_coin(vaction_oid, vaction_code)

        eligible_authrole = 'member'
        await self.publish('xbr.network.on_new_coin',
                           request_verified,
                           options=PublishOptions(acknowledge=True, eligible_authrole=eligible_authrole))
        return request_verified

    @wamp.register('xbr.network.get_coin', check_types=True)
    def get_coin(self,
                 coin_oid: bytes,
                 include_attributes: bool = False,
                 details: Optional[CallDetails] = None) -> Optional[dict]:
        """
        Retrieve basic information for the given ERC20 coin for markets.

        :param market_oid: OID of the XBR Data Market to retrieve information for.

        :param include_attributes: If set, include all attributes set on the market.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Market information.
        """
        assert type(coin_oid) == bytes, 'coin_oid must be bytes, was {}'.format(type(coin_oid))
        assert len(coin_oid) == 16, 'coin_oid must be bytes[16], was bytes[{}]'.format(len(coin_oid))
        assert type(include_attributes), 'include_attributes must be bool, was {}'.format(type(include_attributes))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        try:
            coin_oid_ = uuid.UUID(bytes=coin_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid market_oid: {}'.format(str(e)))

        # FIXME: the only coin currently defined is the XBR coin hard-coded here
        if coin_oid_ != self.XBR_COIN_OID:
            raise RuntimeError('no coin with oid {}'.format(coin_oid_))

        coin = {
            'oid': coin_oid_.bytes,
            'address': xbr.xbrtoken.address,
            'name': 'XBR',
            'decimals': 18,
            'initial_supply': pack_uint256(1000000000 * 10**18),
            'attributes': {
                'title': 'XBR Coin'
            }
        }
        return coin

    @wamp.register('xbr.network.get_coin_by_symbol', check_types=True)
    def get_coin_by_symbol(self, symbol: str, details: Optional[CallDetails] = None) -> Optional[bytes]:
        """
        Get coin by coin name.

        :param symbol: The symbol of the coin, eg. ``XBR``.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: If found, the OID of the coin.
        """
        assert type(symbol) == str, 'coin_name must be str, was {}'.format(type(symbol))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        if symbol == 'XBR':
            return self.XBR_COIN_OID.bytes
        else:
            return None

    @wamp.register('xbr.network.get_coin_balance', check_types=True)
    async def get_coin_balance(self,
                               member_oid: bytes,
                               coin_oid: bytes,
                               details: Optional[CallDetails] = None) -> bytes:
        """
        Get the current balance in the given coins, held by the given member.

        :param member_oid: Member to get coin balance for.
        :param coin_oid: Coin to get balance for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Current balance of given member and coin.
        """
        assert type(member_oid) == bytes, 'member_oid must be bytes, was {}'.format(type(member_oid))
        assert len(member_oid) == 16, 'member_oid must be bytes[16], was bytes[{}]'.format(len(member_oid))
        assert type(coin_oid) == bytes, 'coin_oid must be bytes, was {}'.format(type(coin_oid))
        assert len(coin_oid) == 16, 'coin_oid must be bytes[16], was bytes[{}]'.format(len(coin_oid))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        try:
            coin_oid_ = uuid.UUID(bytes=coin_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid coin_oid: {}'.format(str(e)))

        # FIXME: the only coin currently defined is the XBR coin hard-coded here
        if coin_oid_ != self.XBR_COIN_OID:
            raise RuntimeError('no coin with oid {}'.format(coin_oid_))

        try:
            member_oid_ = uuid.UUID(bytes=member_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid member_oid: {}'.format(str(e)))

        with self._db.begin() as txn:
            account = self._xbrnetwork.accounts[txn, member_oid_]
            if not account:
                return pack_uint256(0)

        def _get_coin_balance(account_adr):
            # FIXME: dynamically instantiate contract proxy for coin_adr given
            balance = xbr.xbrtoken.functions.balanceOf(account_adr).call()
            return pack_uint256(balance)

        # FIXME: get token contract address for coin from DB table
        balance = await deferToThread(_get_coin_balance, bytes(account.wallet_address))

        return balance

    @wamp.register('xbr.network.find_coins', check_types=False)
    async def find_coins(self,
                         created_from: Optional[int] = None,
                         limit: Optional[int] = None,
                         include_owners: Optional[List[bytes]] = None,
                         include_names: Optional[List[str]] = None,
                         details: Optional[CallDetails] = None) -> List[bytes]:
        """

        :param created_from:
        :param limit:
        :param include_owners:
        :param include_names:
        :param details:
        :return:
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        if (include_owners is not None or include_names is not None):
            raise NotImplementedError('filters are not yet implemented')

        if created_from is not None:
            raise NotImplementedError('created_from is not yet implemented')

        if limit is not None:
            raise NotImplementedError('limit is not yet implemented')

        # FIXME: the only coin currently defined is the XBR coin hard-coded here
        return [self.XBR_COIN_OID.bytes]

    @wamp.register('xbr.network.does_hash_exist', check_types=True)
    async def does_hash_exist(self, ipfs_hash: str, details: Optional[CallDetails] = None):
        # https://ethereum.stackexchange.com/a/70204
        if not re.match("^Qm[1-9A-HJ-NP-Za-km-z]{44}$", ipfs_hash):
            return False

        file_path = os.path.join(self._ipfs_files_path, ipfs_hash)
        if os.path.exists(file_path):
            return True

        try:
            response = await treq.get(f'https://ipfs.infura.io:5001/api/v0/cat?arg={ipfs_hash}', timeout=5)
            content = (await response.content()).decode()
            with open(file_path, 'w') as file:
                file.write(content)
            return True
        except ResponseNeverReceived:
            return False

    @wamp.register('xbr.network.create_market', check_types=True)
    async def create_market(self,
                            member_oid: bytes,
                            market_oid: bytes,
                            verifying_chain_id: int,
                            current_block_number: int,
                            verifying_contract_adr: bytes,
                            coin_adr: bytes,
                            terms_hash: Optional[str],
                            meta_hash: Optional[str],
                            meta_data: Optional[bytes],
                            market_maker_adr: bytes,
                            provider_security: bytes,
                            consumer_security: bytes,
                            market_fee: bytes,
                            signature: bytes,
                            attributes: Optional[dict],
                            details: Optional[CallDetails] = None) -> dict:
        """
        Create a new XBR Data Market.

        .. seealso:: Unit test `test_api05_market.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api05_market.py/>`_

        :param member_oid: Member who will own the market and act as a market operator. Usually the calling member.
        :param market_oid: New globally unique market OID (a 16-bytes UUID).
        :param verifying_chain_id: Blockchain ID (eg 1 for Ethereum mainnet, 4 for Rinkeby, etc).
        :param current_block_number: Current block number on blockchain.
        :param verifying_contract_adr: Address of verifying contract.
        :param coin_adr:
        :param terms_hash:
        :param meta_hash:
        :param meta_data:
        :param market_maker_adr:
        :param provider_security:
        :param consumer_security:
        :param market_fee:
        :param signature: EIP712 signature (computed over the fields ``chain_id``, ``block_number``,
            ``contract_adr``, ...) for the data market creation.
        :param attributes: Market attributes.
        :param details: Caller details.

        :return: Data market creation information.
        """
        assert type(verifying_chain_id) == int
        assert type(current_block_number) == int
        assert type(verifying_contract_adr) == bytes and len(verifying_contract_adr) == 20
        assert type(coin_adr) == bytes and len(coin_adr) == 20
        assert terms_hash is None or type(terms_hash) == str
        assert meta_hash is None or type(meta_hash) == str
        assert type(market_maker_adr) == bytes and len(market_maker_adr) == 20
        assert type(provider_security) == bytes and len(provider_security) == 32
        assert type(consumer_security) == bytes and len(consumer_security) == 32
        assert type(market_fee) == bytes and len(market_fee) == 32
        assert is_signature(signature)
        assert attributes is None or type(attributes) == dict
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        member_oid_ = uuid.UUID(bytes=member_oid)
        market_oid_ = uuid.UUID(bytes=market_oid)

        request_submitted = await self._network.create_market(member_oid_, market_oid_, verifying_chain_id,
                                                              current_block_number, verifying_contract_adr, coin_adr,
                                                              terms_hash, meta_hash, meta_data, market_maker_adr,
                                                              provider_security, consumer_security, market_fee,
                                                              signature, attributes)
        return request_submitted

    @wamp.register('xbr.network.verify_create_market', check_types=True)
    async def verify_create_market(self,
                                   vaction_oid: bytes,
                                   vaction_code: str,
                                   details: Optional[CallDetails] = None) -> dict:
        """
        Verify creating a new data market by submitting a verification code.

        Upon successful market creation, this procedure will also publish the same data that is returned
        to the following topic:

        * **Procedure**: ``xbr.network.verify_create_market``
        * **Events**: ``xbr.network.on_new_market``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `test_api05_market.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api05_market.py/>`_

        :param vaction_oid: Verification action ID (16 bytes UUID).

        :param vaction_code: Verification code, for example ``"EK5H-JJ4H-CECK"``

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Market creation information, including ID of new market. For example:

            .. code-block:: python

                {
                    'created': 1582146264584727254,
                    'market_oid': b'...',
                    'block_hash': b'...',
                    'block_number': b'...',
                    'transaction_hash': b'...',
                    'transaction_index': b'...'
                }

            * ``created``: Market creation timestamp (number of nanoseconds since the Unix epoch).
            * ``market_oid``: ID of newly created market (16 bytes UUID).
        """
        self.log.info(
            '{klass}.verify_create_market(vaction_oid={vaction_oid}, vaction_code={vaction_code}, details={details})',
            klass=self.__class__.__name__,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code,
            details=details)
        create_market_request_verified = await self._network.verify_create_market(vaction_oid, vaction_code)

        eligible_authrole = 'member'
        await self.publish('xbr.network.on_new_market',
                           create_market_request_verified,
                           options=PublishOptions(acknowledge=True, eligible_authrole=eligible_authrole))
        return create_market_request_verified

    @wamp.register('xbr.network.remove_market', check_types=True)
    def remove_market(self,
                      member_oid: bytes,
                      chain_id: int,
                      block_number: int,
                      contract_adr: bytes,
                      market_adr: bytes,
                      signature: bytes,
                      details: Optional[CallDetails] = None) -> dict:
        """
        Remove an existing XBR Data Market. The caller of this procedure must be the owner of the market, and
        all the market must be fully cleared first.

        :param member_oid: ID of the member to remove the data market under (must be owner).

        :param chain_id: Blockchain ID.

        :param block_number: Blockchain current block number.

        :param contract_adr: Address of ``XBRNetwork`` smart contract.

        :param market_adr: Address of market to remove (the address of the respective ``XBRMarket`` smart contract).

        :param signature: EIP712 signature (computed over the fields ``chain_id``, ``block_number``,
            ``contract_adr``, ...) for the data market removal.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Data market removal information.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.update_market', check_types=True)
    def update_market(self, market_oid: bytes, attributes: Optional[dict], details: Optional[CallDetails] = None):
        """
        Update off-chain information attached to market, such as attributes.

        :param market_oid: OID of the XBR Data Market to update information for.

        :param attributes: If provided, should be a mapping of names of attributes to update
            mapped to the new values (to set or modify) or to the value ``None`` to remove the attribute.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        assert type(market_oid) == bytes, 'market_oid must be bytes, was {}'.format(type(market_oid))
        assert len(market_oid) == 16, 'market_oid must be bytes[16], was bytes[{}]'.format(len(market_oid))
        assert attributes is None or type(attributes) == dict
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        try:
            _market_oid = uuid.UUID(bytes=market_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid market_oid: {}'.format(str(e)))

        self._network.update_market(_market_oid, attributes)

    @wamp.register('xbr.network.get_market', check_types=True)
    async def get_market(self,
                         market_oid: bytes,
                         include_attributes: Optional[bool] = False,
                         include_terms_text: Optional[bool] = False,
                         details: Optional[CallDetails] = None) -> dict:
        """
        Retrieve basic information for the given XBR Data Market.

        .. seealso:: Unit test `test_api05_market.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api05_market.py/>`_

        .. note::
            Given a ``market_adr``, this API here provides the same market information as the
            `Market-maker API <https://crossbario.com/docs/crossbar/xbr/api-reference.html#crossbar.edge.worker.xbr._marketmaker.MarketMaker.get_market>`__
            for the respective market. The difference is, the procedure is more general, in that
            it can return (basic) market information for any market, and in that the procedure is
            implemented in the `planet.xbr.network` backend rather than the XBR market maker running
            on the Crossbar.io edge node of the operator of the respective market.

        :param market_oid: OID of the XBR Data Market to retrieve information for.

        :param include_attributes: If set, include all attributes set on the market.

        :param include_terms_text: If set, download market terms text from Infura's IPFS
            gateway and include in the response.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Market information.
        """
        assert type(market_oid) == bytes, 'market_oid must be bytes, was {}'.format(type(market_oid))
        assert len(market_oid) == 16, 'market_oid must be bytes[16], was bytes[{}]'.format(len(market_oid))
        assert type(include_attributes), 'include_attributes must be bool, was {}'.format(type(include_attributes))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        try:
            _market_oid = uuid.UUID(bytes=market_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid market_oid: {}'.format(str(e)))

        market = await self._network.get_market(_market_oid, include_attributes, include_terms_text)
        return market

    @wamp.register('xbr.network.get_markets_by_owner', check_types=True)
    def get_markets_by_owner(self, owner_oid: bytes, details: Optional[CallDetails] = None) -> list:
        """
        Get list of XBR Data Markets owned by the given member.

        :param owner_oid: ID of the member to retrieve owned markets for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of markets owned by the given member.
        """
        assert type(owner_oid) == bytes, 'owner_oid must be bytes, was {}'.format(type(owner_oid))
        assert len(owner_oid) == 16, 'owner_oid must be bytes[16], was bytes[{}]'.format(len(owner_oid))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        member_oid_from_authid_ = extract_member_oid(details)
        owner_oid_ = uuid.UUID(bytes=owner_oid)
        if owner_oid_ != member_oid_from_authid_:
            raise RuntimeError('only own information can be accessed!')

        t_zero = np.datetime64(0, 'ns')
        t_now = np.datetime64(time_ns(), 'ns')

        markets = []
        with self._db.begin() as txn:
            owner = self._xbrnetwork.accounts[txn, owner_oid_]
            owner_adr = bytes(owner.wallet_address)
            for market_oid in self._xbr.idx_markets_by_owner.select(txn,
                                                                    from_key=(owner_adr, t_zero),
                                                                    to_key=(owner_adr, t_now),
                                                                    return_keys=False):
                markets.append(market_oid.bytes)

        return markets

    @wamp.register('xbr.network.get_actors_in_market', check_types=True)
    def get_actors_in_market(self, market_oid: bytes, details: Optional[CallDetails] = None) -> list:
        """
        Get list of market actors in a given market.

        :param market_oid: ID of the market to retrieve market actors for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of addresses of markets joined by the given actor.
        """
        assert type(market_oid) == bytes, 'market_oid must be bytes, was {}'.format(type(market_oid))
        assert len(market_oid) == 16, 'market_oid must be bytes[16], was bytes[{}]'.format(len(market_oid))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        market_oid_ = uuid.UUID(bytes=market_oid)

        actors_in_market = []
        with self._db.begin() as txn:
            from_key = (market_oid_, b'\0' * 20, 0)
            to_key = (market_oid_, b'\xff' * 20, 255)
            for _, actor_adr, actor_type in self._xbr.actors.select(txn,
                                                                    from_key=from_key,
                                                                    to_key=to_key,
                                                                    return_values=False):
                actors_in_market.append((actor_adr, actor_type))
        return actors_in_market

    @wamp.register('xbr.network.get_actor_in_market', check_types=True)
    def get_actor_in_market(self, market_oid: bytes, actor_adr: bytes, details: Optional[CallDetails] = None) -> list:
        """
        Get information on an actor in a market.

        :param market_oid: ID of the market the actor is joined to.
        :param actor_adr: Address the actor joined to the market.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Information on the actor in the market.
        """
        assert type(market_oid) == bytes, 'market_oid must be bytes, was {}'.format(type(market_oid))
        assert len(market_oid) == 16, 'market_oid must be bytes[16], was bytes[{}]'.format(len(market_oid))
        assert type(actor_adr) == bytes, 'actor_adr must be bytes, was {}'.format(type(actor_adr))
        assert len(actor_adr) == 20, 'actor_adr must be bytes[20], was bytes[{}]'.format(len(actor_adr))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        market_oid_ = uuid.UUID(bytes=market_oid)

        result = []
        with self._db.begin() as txn:
            from_key = (market_oid_, actor_adr, 0)
            to_key = (market_oid_, actor_adr, 255)
            for (market_id, _, actor_type), actor in self._xbr.actors.select(txn,
                                                                             from_key=from_key,
                                                                             to_key=to_key,
                                                                             return_keys=True,
                                                                             return_values=True):
                result.append(actor.marshal())

        self.log.info('{func}(market_oid={market_oid}, actor_adr={actor_adr}) ->\n{result}',
                      func=hltype(self.get_actor_in_market),
                      market_oid=hlid(market_oid_),
                      actor_adr=hlid('0x' + b2a_hex(actor_adr).decode()),
                      result=pformat(result))

        return result

    @wamp.register('xbr.network.get_markets_by_actor', check_types=True)
    def get_markets_by_actor(self, actor_oid: bytes, details: Optional[CallDetails] = None) -> list:
        """
        Get list of XBR Data Markets the actor is joined to.

        :param actor_oid: ID of the actor to retrieve joined markets for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of markets joined by the given actor.
        """
        assert type(actor_oid) == bytes, 'owner_oid must be bytes, was {}'.format(type(actor_oid))
        assert len(actor_oid) == 16, 'owner_oid must be bytes[16], was bytes[{}]'.format(len(actor_oid))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        actor_oid_ = uuid.UUID(bytes=actor_oid)

        # member_oid_from_authid_ = extract_member_oid(details)
        # if actor_oid_ != member_oid_from_authid_:
        #     raise RuntimeError('only own information can be accessed!')

        t_zero = np.datetime64(0, 'ns')
        t_now = np.datetime64(time_ns(), 'ns')

        markets = []
        with self._db.begin() as txn:
            account = self._xbrnetwork.accounts[txn, actor_oid_]
            if not account:
                raise RuntimeError('actor_oid: no member with oid {}'.format(actor_oid_))
            actor_adr = bytes(account.wallet_address)
            for market_oid in self._xbr.idx_markets_by_actor.select(txn,
                                                                    from_key=(actor_adr, t_zero),
                                                                    to_key=(actor_adr, t_now),
                                                                    return_keys=False):
                if self._markets_whitelist and market_oid not in self._markets_whitelist:
                    continue
                markets.append(market_oid.bytes)

        # deduplicate, since a given actor might be both buyer and seller
        markets = list(set(markets))

        return markets

    @wamp.register('xbr.network.get_markets_by_coin', check_types=True)
    def get_markets_by_coin(self, coin_oid: bytes, details: Optional[CallDetails] = None) -> list:
        """
        Get list of XBR Data Markets using a specific coin as a means of payment.

        :param coin_oid: OID of the coin to list markets for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of addresses of markets using the specified coin as a means of payment.
        """
        assert type(coin_oid) == bytes, 'coin_oid must be bytes, was {}'.format(type(coin_oid))
        assert len(coin_oid) == 16, 'coin_oid must be bytes[16], was bytes[{}]'.format(len(coin_oid))
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

        # member_oid_from_authid_ = extract_member_oid(details)
        # coin_oid = uuid.UUID(bytes=coin_oid)
        #
        # t_zero = np.datetime64(0, 'ns')
        # t_now = np.datetime64(time_ns(), 'ns')
        #
        # markets = []
        # with self._db.begin() as txn:
        #     for market in self._schema.idx_markets_by_coin.select(txn,
        #                                                           from_key=(coin_oid, t_zero),
        #                                                           to_key=(coin_oid, t_now),
        #                                                           return_keys=False):
        #         markets.append(market)
        #
        # return markets

    @wamp.register('xbr.network.find_markets', check_types=False)
    async def find_markets(self,
                           created_from: Optional[int] = None,
                           limit: Optional[int] = None,
                           include_owners: Optional[List[bytes]] = None,
                           include_actors: Optional[List[bytes]] = None,
                           include_titles: Optional[List[str]] = None,
                           include_descriptions: Optional[List[str]] = None,
                           include_tags: Optional[List[str]] = None,
                           include_apis: Optional[List[bytes]] = None,
                           details: Optional[CallDetails] = None) -> List[bytes]:
        """
        Search for XBR Data Markets by

        * owning member and joined actors
        * descriptive title, description and tags
        * APIs implemented by data services offered in markets

        as well as specify range and limit of the searched blockchain blocks and returned markets.

        .. seealso:: Unit test `test_api05_market.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api05_market.py/>`_

        .. note::
            When a specific filter is not provided, the filter remains un-applied and respective markets
            are *not* filtered in the results. Specifically, when called without any arguments, this procedure
            will return *all* existing markets. The pagination via ``created_from`` and ``limit`` still applies.

        :param created_from: Only return markets created within blocks not earlier than this block number.

        :param limit: Only return markets from this many blocks beginning with block ``created_from``.
            So ``limit`` is in number of blocks and must be a positive integer when provided.

            .. note::
                Since ``limit`` can not be smaller than one block, and since the number of
                markets created in blocks can vary per-block, the number of returned markets is only limited by the
                number of markets that could be technically created within one block given the block gas limit
                of the respective blockchain. *Currently*, the largest XBR contract is ``XBRNetwork`` which consumes
                5,278,476 gas out of a 10,000,000 maximum on Rinkeby. Which means, the number of markets returned
                per block is 0 or 1, and hence the number of markets returned is always ``<= limit``. But this
                should *not be assumed* as refactoring the XBR contracts might result in a smaller maximum
                contract size per created market.

        To search for markets, the following filters can be used:

        :param include_owners: If provided, only return markets owned by any of the owners specified.

        :param include_actors: If provided, only return markets joined by any of the actorss specified.

        :param include_titles: If provided, only return markets with a title that
            contains any of the specified titles.

        :param include_descriptions: If provided, only return markets with a description that
            contains any of the specified descriptions.

        :param include_tags: If provided, only return markets with a tag that contains any of the specified tags.

        :param include_apis: If provided, only return markets with services providing
            an API of any of the specified APIs.

        *FOR INTERNAL USE*

        :param details: DO NOT USE. Caller details internally provided by the router and cannot be used
            as an application level parameter.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of addresses of markets matching the search criteria.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        created_from = created_from or 0
        limit = limit or 10

        if (include_owners is not None or include_actors is not None or include_titles is not None
                or include_descriptions is not None or include_tags is not None or include_apis is not None):
            raise NotImplementedError('filters are not yet implemented')

        if created_from is not None and created_from < 0:
            raise ValueError('limit must be a non-negative integer')

        if limit is not None and limit < 1:
            raise ValueError('limit must be a strictly positive integer')

        if limit is not None and limit > 10:
            raise ValueError('limit exceeded system limit')

        def get_latest():
            block_info = self._w3.eth.getBlock('latest')
            return int(block_info['number'])

        latest = await deferToThread(get_latest)
        market_oids = []
        if created_from <= latest:
            with self._db.begin() as txn:
                for market_oid in self._xbr.markets.select(txn, return_keys=True, return_values=False):
                    if self._markets_whitelist and market_oid not in self._markets_whitelist:
                        continue
                    market_oids.append(market_oid.bytes)
                    if len(market_oids) >= limit:
                        break

        return market_oids

    @wamp.register('xbr.network.join_market', check_types=False)
    async def join_market(self,
                          member_id: bytes,
                          market_id: bytes,
                          chain_id: int,
                          block_number: int,
                          contract_adr: bytes,
                          actor_type: int,
                          meta_hash: Optional[bytes],
                          meta_data: Optional[bytes],
                          signature: bytes,
                          details: Optional[CallDetails] = None) -> dict:
        """
        Join an existing data market as a buyer (data consumer) and/or seller (data provider).

        If all is fine with the supplied information, the joining member will be sent a verification
        email to members primary email.

        Once the Web link contained in the verification email is clicked, the :class:`xbrnetwork.Api.verify_join_market`
        procedure should be called with the (query) information contained in the verification link.

        * **Procedure**: ``xbr.network.join_market``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `test_api06_market.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api06_market.py/>`_

        :param member_id: ID of the member that joins

        :param market_id: ID of the market to join.

        :param chain_id: Verifying blockchain ID.

        :param block_number: Current block number,

        :param contract_adr: Verifying contract address.

        :param actor_type: Type of actor to join under (``PROVIDER = 3``, ``CONSUMER = 4``).

        :param meta_hash: Multihash (SHA256 Base64-encoded, for example
            ``"QmcU74QYcPQJCPUVVRwguVfrSnt8ZJrnbXzYPhxfhey7Qb"``) computed from a CBOR-serialized metadata object:

                .. code-block:: python

                    {
                    }

        :param meta_data: CBOR-serialized metadata object (see above).

        :param signature: EIP712 signature (using private key of member) over ``chain_id``, ``block_number``,
            ``contract_adr``, ``market_id``, ``actor_type`` and ``meta_hash``.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return:
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        member_id_ = uuid.UUID(bytes=member_id)
        market_id_ = uuid.UUID(bytes=market_id)
        assert actor_type in [ActorType.PROVIDER, ActorType.CONSUMER,
                              ActorType.PROVIDER_CONSUMER], 'invalid actor_type {}'.format(actor_type)

        self.log.info(
            '{klass}.join_market(member_id={member_id}, market_id={market_id}, chain_id={chain_id}, block_number={block_number}, signature={signature}, details={details})',
            klass=self.__class__.__name__,
            member_id=member_id_,
            market_id=market_id_,
            chain_id=chain_id,
            block_number=block_number,
            signature=signature,
            details=details)

        submitted = await self._network.join_market(member_id_, market_id_, chain_id, block_number, contract_adr,
                                                    actor_type, meta_hash, meta_data, signature)
        return submitted

    @wamp.register('xbr.network.verify_join_market', check_types=True)
    async def verify_join_market(self,
                                 vaction_oid: bytes,
                                 vaction_code: str,
                                 details: Optional[CallDetails] = None) -> dict:
        """
        Verify joining a market by submitting a verification code.

        * **Procedure**: ``xbr.network.verify_join_market``
        * **Events**: ``xbr.network.on_market_join``
        * **Errors**: ``wamp.error.*``

        .. note::
            This procedure will also publish the same data that is returned to the above topic.

        .. seealso:: Unit test `test_api06_market.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/test_api06_market.py/>`_

        :param vaction_oid: Verification action ID.

        :param vaction_code: Verification code.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Market join information, including ID of existing market. For example:

            .. code-block:: python

                {
                    "member_oid": b'',
                    "market_oid": b'',
                    "roles": ["buyer", "seller"],
                    "joined": 1573675753141788247,
                }
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        self.log.info(
            '{klass}.verify_join_market(vaction_oid={vaction_oid}, vaction_code={vaction_code}, details={details})',
            klass=self.__class__.__name__,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code,
            details=details)
        join_market_request_verified = await self._network.verify_join_market(vaction_oid, vaction_code)
        await self.publish('xbr.network.on_market_join',
                           join_market_request_verified,
                           options=PublishOptions(acknowledge=True))
        return join_market_request_verified

    @wamp.register('xbr.network.create_catalog', check_types=True)
    async def create_catalog(self,
                             member_oid: bytes,
                             catalog_oid: bytes,
                             verifying_chain_id: int,
                             current_block_number: int,
                             verifying_contract_adr: bytes,
                             terms_hash: Optional[str],
                             meta_hash: Optional[str],
                             meta_data: Optional[bytes],
                             signature: bytes,
                             attributes: Optional[dict],
                             details: Optional[CallDetails] = None) -> dict:
        """
        Create a new XBR Data FbsRepository.

        :param member_oid: OID of the member to create the catalog under (the member will become catalog owner.).

        :param catalog_oid: OID of the new catalog.

        :param verifying_chain_id: Blockchain ID.

        :param current_block_number: Blockchain current block number.

        :param verifying_contract_adr: Address of ``XBRNetwork`` smart contract.

        :param terms_hash: Multihash for optional catalog terms that apply to the catalog
            and all APIs published to that catalog.

        :param meta_hash: Mutlihash for optional off-chain catalog meta-data.

        :param meta_data: Optional off-chain catalog meta-data.

        :param attributes: Object standard attributes like title, description and tags.

        :param signature: EIP712 signature for the catalog market creation.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Data catalog creation information.
        """
        assert is_bytes16(member_oid)
        assert is_bytes16(catalog_oid)
        assert is_chain_id(verifying_chain_id)
        assert is_block_number(current_block_number)
        assert is_address(verifying_contract_adr)
        assert terms_hash is None or type(terms_hash) == str
        assert meta_hash is None or type(meta_hash) == str
        assert meta_data is None or type(meta_data) == bytes
        assert is_signature(signature)
        assert attributes is None or type(attributes) == dict
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        try:
            _member_oid = uuid.UUID(bytes=member_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid member_oid: {}'.format(str(e)))

        member_oid_from_authid_ = extract_member_oid(details)
        if _member_oid != member_oid_from_authid_:
            raise RuntimeError('Can only create catalog for own self!')

        _catalog_oid = uuid.UUID(bytes=catalog_oid)

        submitted = await self._network.create_catalog(_member_oid, _catalog_oid, verifying_chain_id,
                                                       current_block_number, verifying_contract_adr, terms_hash,
                                                       meta_hash, meta_data, attributes, signature)

        return submitted

    @wamp.register('xbr.network.verify_create_catalog', check_types=True)
    async def verify_create_catalog(self,
                                    vaction_oid: bytes,
                                    vaction_code: str,
                                    details: Optional[CallDetails] = None) -> dict:
        """
        Verify creating a new data API catalog by submitting a verification code.

        Upon successful catalog creation, this procedure will also publish the same data that is returned
        to the following topic:

        * **Procedure**: ``xbr.network.verify_create_catalog``
        * **Events**: ``xbr.network.on_new_catalog``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `fixme.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/fixme.py/>`_

        :param vaction_oid: Verification action ID (16 bytes UUID).

        :param vaction_code: Verification code, for example ``"EK5H-JJ4H-CECK"``

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: FbsRepository creation information. For example:

            .. code-block:: python

                {
                    'created': 1582146264584727254,
                    'catalog_oid': b'...',
                    'block_hash': b'...',
                    'block_number': b'...',
                    'transaction_hash': b'...',
                    'transaction_index': b'...'
                }

            * ``created``: FbsRepository creation timestamp (number of nanoseconds since the Unix epoch).
            * ``catalog_oid``: ID of newly created catalog (16 bytes UUID).
        """
        self.log.info(
            '{klass}.verify_create_market(vaction_oid={vaction_oid}, vaction_code={vaction_code}, details={details})',
            klass=self.__class__.__name__,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code,
            details=details)

        created_catalog_request_verified = await self._network.verify_create_catalog(vaction_oid, vaction_code)
        await self.publish('xbr.network.on_catalog_created',
                           created_catalog_request_verified,
                           options=PublishOptions(acknowledge=True))
        return created_catalog_request_verified

    @wamp.register('xbr.network.remove_catalog', check_types=True)
    def remove_catalog(self,
                       member_oid: bytes,
                       chain_id: int,
                       block_number: int,
                       contract_adr: bytes,
                       signature: bytes,
                       details: Optional[CallDetails] = None):
        """
        Remove an existing XBR Data FbsRepository.

        :param member_oid: ID of the member to remove the data market under (must be owner).

        :param chain_id: Blockchain ID.

        :param block_number: Blockchain current block number.

        :param contract_adr: Address of ``XBRNetwork`` smart contract.

        :param signature: EIP712 signature (computed over the fields ``chain_id``, ``block_number``,
            ``contract_adr``, ...) for the data market removal.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Data catalog removal information.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.get_catalogs_by_owner', check_types=True)
    def get_catalogs_by_owner(self, member_oid: bytes, details: Optional[CallDetails] = None):
        """
        Get list of XBR Data Catalogs owned by the given member.

        :param member_oid: OID of the member to retrieve owned catalogs for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of OIDs of catalogs owned by the given member.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        member_oid_from_authid = extract_member_oid(details)
        member_oid_ = uuid.UUID(bytes=member_oid)
        if member_oid_ != member_oid_from_authid:
            raise RuntimeError('only own catalogs can be accessed!')

        t_zero = np.datetime64(0, 'ns')
        t_now = np.datetime64(time_ns(), 'ns')

        catalogs = []
        with self._db.begin() as txn:
            owner = self._xbrnetwork.accounts[txn, member_oid_from_authid]
            owner_adr = bytes(owner.wallet_address)
            for catalog_oid in self._xbr.idx_catalogs_by_owner.select(txn,
                                                                      from_key=(owner_adr, t_zero),
                                                                      to_key=(owner_adr, t_now),
                                                                      return_keys=False):
                catalogs.append(catalog_oid.bytes)

        return catalogs

    @wamp.register('xbr.network.get_catalog', check_types=True)
    def get_catalog(self,
                    catalog_oid: bytes,
                    include_attributes: bool = False,
                    details: Optional[CallDetails] = None) -> dict:
        """
        Retrieve basic information for the given XBR Data FbsRepository.

        :param catalog_oid: OID of the XBR Data FbsRepository to retrieve information for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: FbsRepository information.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        try:
            _catalog_oid = uuid.UUID(bytes=catalog_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid _catalog_oid: {}'.format(str(e)))

        catalog = self._network.get_catalog(_catalog_oid, include_attributes)
        return catalog.marshal()

    @wamp.register('xbr.network.find_catalogs', check_types=False)
    async def find_catalogs(self,
                            created_from: Optional[int] = None,
                            limit: Optional[int] = None,
                            include_owners: Optional[List[bytes]] = None,
                            include_apis: Optional[List[bytes]] = None,
                            include_titles: Optional[List[str]] = None,
                            include_descriptions: Optional[List[str]] = None,
                            include_tags: Optional[List[str]] = None,
                            details: Optional[CallDetails] = None) -> List[bytes]:
        """
        Search for XBR Data Catalogs by

        * owning member and joined actors
        * descriptive title, description and tags
        * APIs published to catalogs

        as well as specify range and limit of the searched blockchain blocks and returned catalogs.

        .. seealso:: Unit test `fixme.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/fixme.py/>`_

        .. note::
            When a specific filter is not provided, the filter remains un-applied and respective catalogs
            are *not* filtered in the results. Specifically, when called without any arguments, this procedure
            will return *all* existing catalogs. The pagination via ``created_from`` and ``limit`` still applies.

        :param created_from: Only return catalogs created within blocks not earlier than this block number.

        :param limit: Only return catalogs from this many blocks beginning with block ``created_from``.
            So ``limit`` is in number of blocks and must be a positive integer when provided.

        To search for catalogs, the following filters can be used:

        :param include_owners: If provided, only return catalogs owned by any of the owners specified.

        :param include_apis: If provided, only return catalogs containing any of the APIs specified.

        :param include_titles: If provided, only return catalogs with a title that
            contains any of the specified titles.

        :param include_descriptions: If provided, only return catalogs with a description that
            contains any of the specified descriptions.

        :param include_tags: If provided, only return catalogs with a tag that contains any of the specified tags.

        *FOR INTERNAL USE*

        :param details: DO NOT USE. Caller details internally provided by the router and cannot be used
            as an application level parameter.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of OIDs of catalogs matching the search criteria.
        """

        created_from = created_from or 0
        limit = limit or 10

        def get_latest():
            block_info = self._w3.eth.getBlock('latest')
            return int(block_info['number'])

        latest = await deferToThread(get_latest)
        catalog_oids = []
        if created_from <= latest:
            with self._db.begin() as txn:
                for catalog_oid in self._xbr.catalogs.select(txn, return_keys=True, return_values=False):
                    catalog_oids.append(catalog_oid.bytes)
                    if len(catalog_oids) >= limit:
                        break
        return catalog_oids

    @wamp.register('xbr.network.publish_api', check_types=True)
    def publish_api(self,
                    member_oid: bytes,
                    catalog_oid: bytes,
                    api_oid: bytes,
                    verifying_chain_id: int,
                    current_block_number: int,
                    verifying_contract_adr: bytes,
                    schema_hash: str,
                    schema_data: bytes,
                    meta_hash: Optional[str],
                    meta_data: Optional[bytes],
                    signature: bytes,
                    attributes: Optional[dict] = None,
                    details: Optional[CallDetails] = None) -> dict:
        """
        Publish an API to an existing XBR Data FbsRepository.

        :param member_oid: OID of the member to create the catalog under (the member will become catalog owner.).

        :param catalog_oid: OID of the (existing) catalog to publish the API to.

        :param api_oid: OID of the new API (as published in the catalog).

        :param verifying_chain_id: Blockchain ID.

        :param current_block_number: Blockchain current block number.

        :param verifying_contract_adr: Address of ``XBRNetwork`` smart contract.

        :param schema_hash: Multihash for XBR/WAMP Flatbuffers based API schema.

        :param schema_data: Serialized binary XBR/WAMP Flatbuffers API schema. This is the
            schema file contents (`.bfbs`) produced by the **flatc** compiler.

        :param meta_hash: Multihash for optional off-chain API meta-data.

        :param meta_data: Optional off-chain API meta-data.

        :param attributes: Object standard attributes like title, description and tags.

        :param signature: EIP712 signature for the catalog market creation.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: API creation information.
        """
        assert type(member_oid) == bytes and len(member_oid) == 16
        assert type(catalog_oid) == bytes and len(catalog_oid) == 16
        assert type(api_oid) == bytes and len(api_oid) == 16
        assert type(verifying_chain_id) == int
        assert type(current_block_number) == int
        assert type(verifying_contract_adr) == bytes and len(verifying_contract_adr) == 20
        assert schema_hash is None or type(schema_hash) == str
        assert schema_data is None or type(schema_data) == bytes
        assert (schema_hash is None and schema_data is None) or (schema_hash is not None and schema_data is not None)
        assert meta_hash is None or type(meta_hash) == str
        assert meta_data is None or type(meta_data) == bytes
        assert (meta_hash is None and meta_data is None) or (meta_hash is not None and meta_data is not None)
        assert is_signature(signature)
        assert attributes is None or type(attributes) == dict
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        member_oid_ = uuid.UUID(bytes=member_oid)
        catalog_oid_ = uuid.UUID(bytes=catalog_oid)
        api_oid_ = uuid.UUID(bytes=api_oid)

        result = self._network.publish_api(member_oid_, catalog_oid_, api_oid_, verifying_chain_id,
                                           current_block_number, verifying_contract_adr, schema_hash, schema_data,
                                           meta_hash, meta_data, signature, attributes)

        # member_oid_ = uuid.UUID(bytes=member_oid)
        # catalog_oid = uuid.UUID(bytes=catalog_oid)
        # api_oid = uuid.UUID(bytes=api_oid)

        return result

    @wamp.register('xbr.network.verify_publish_api', check_types=True)
    async def verify_publish_api(self,
                                 vaction_oid: bytes,
                                 vaction_code: str,
                                 details: Optional[CallDetails] = None) -> dict:
        """
        Verify publishing an API to an API catalog by submitting a verification code.

        Upon successful catalog creation, this procedure will also publish the same data that is returned
        to the following topic:

        * **Procedure**: ``xbr.network.verify_publish_api``
        * **Events**: ``xbr.network.on_api_published``
        * **Errors**: ``wamp.error.*``

        .. seealso:: Unit test `fixme.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/fixme.py/>`_

        :param vaction_oid: Verification action ID (16 bytes UUID).

        :param vaction_code: Verification code, for example ``"EK5H-JJ4H-CECK"``

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: API publication information. For example:

            .. code-block:: python

                {
                    'published': 1582146264584727254,
                    'member_oid': b'...',
                    'catalog_oid': b'...',
                    'api_oid': b'...',
                    'block_hash': b'...',
                    'block_number': b'...',
                    'transaction_hash': b'...',
                    'transaction_index': b'...'
                }

            * ``published``: API publication timestamp (number of nanoseconds since the Unix epoch).
            * ``api_oid``: OID of newly published API (16 bytes UUID).
        """
        self.log.info(
            '{klass}.verify_publish_api(vaction_oid={vaction_oid}, vaction_code={vaction_code}, details={details})',
            klass=self.__class__.__name__,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code,
            details=details)

        created_catalog_request_verified = self._network.verify_publish_api(vaction_oid, vaction_code)
        await self.publish('xbr.network.on_api_published',
                           created_catalog_request_verified,
                           options=PublishOptions(acknowledge=True))
        return created_catalog_request_verified

    @wamp.register('xbr.network.get_api', check_types=True)
    def get_api(self, api_oid: bytes, include_attributes: bool = False, details: Optional[CallDetails] = None) -> dict:
        """
        Retrieve basic information for the given XBR API.

        :param api_oid: OID of the XBR API (as published in a catalog) to retrieve information for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: API information.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        try:
            _api_oid = uuid.UUID(bytes=api_oid)
        except Exception as e:
            raise ApplicationError('wamp.error.invalid_argument', 'invalid api_oid: {}'.format(str(e)))

        api = self._network.get_api(_api_oid, include_attributes)
        return api.marshal()

    @wamp.register('xbr.network.find_apis', check_types=False)
    async def find_apis(self,
                        created_from: Optional[int] = None,
                        limit: Optional[int] = None,
                        include_owners: Optional[List[bytes]] = None,
                        include_catalogs: Optional[List[bytes]] = None,
                        include_titles: Optional[List[str]] = None,
                        include_descriptions: Optional[List[str]] = None,
                        include_tags: Optional[List[str]] = None,
                        details: Optional[CallDetails] = None) -> List[bytes]:
        """
        Search for XBR APIs by

        * owning member
        * catalog(s) the APIs are published in
        * descriptive title, description and tags

        as well as specify range and limit of the searched blockchain blocks and returned APIs.

        .. seealso:: Unit test `fixme.py <https://github.com/crossbario/xbr-www/blob/master/backend/test/fixme.py/>`_

        .. note::
            When a specific filter is not provided, the filter remains un-applied and respective APIs
            are *not* filtered in the results. Specifically, when called without any arguments, this procedure
            will return *all* existing APIs. The pagination via ``created_from`` and ``limit`` still applies.

        :param created_from: Only return APIs published within blocks not earlier than this block number.

        :param limit: Only return APIs from this many blocks beginning with block ``created_from``.
            So ``limit`` is in number of blocks and must be a positive integer when provided.

        To search for APIs, the following filters can be used:

        :param include_owners: If provided, only return APIs owned by any of the owners specified.

        :param include_catalogs: If provided, only return APIs published to a catalog in this list.

        :param include_titles: If provided, only return catalogs with a title that
            contains any of the specified titles.

        :param include_descriptions: If provided, only return catalogs with a description that
            contains any of the specified descriptions.

        :param include_tags: If provided, only return catalogs with a tag that contains any of the specified tags.

        *FOR INTERNAL USE*

        :param details: DO NOT USE. Caller details internally provided by the router and cannot be used
            as an application level parameter.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of OIDs of APIs matching the search criteria.
        """

        created_from = created_from or 0
        limit = limit or 10

        def get_latest():
            block_info = self._w3.eth.getBlock('latest')
            return int(block_info['number'])

        latest = await deferToThread(get_latest)
        api_oids = []
        if created_from <= latest:
            with self._db.begin() as txn:
                for api_oid in self._xbr.apis.select(txn, return_keys=True, return_values=False):
                    api_oids.append(api_oid.bytes)
                    if len(api_oids) >= limit:
                        break
        return api_oids

    @wamp.register('xbr.network.create_domain', check_types=True)
    def create_domain(self,
                      member_oid: bytes,
                      chain_id: int,
                      block_number: int,
                      contract_adr: bytes,
                      signature: bytes,
                      details: Optional[CallDetails] = None):
        """
        Create a new XBR Cloud Domain.

        :param member_oid: ID of the member to create the cloud domain under - the member will be owner.

        :param chain_id: Blockchain ID.

        :param block_number: Blockchain current block number.

        :param contract_adr: Address of ``XBRNetwork`` smart contract.

        :param signature: EIP712 signature (computed over the fields ``chain_id``, ``block_number``,
            ``contract_adr``, ...) for the data market creation.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Cloud domain creation information.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.remove_domain', check_types=True)
    def remove_domain(self,
                      member_oid: bytes,
                      chain_id: int,
                      block_number: int,
                      contract_adr: bytes,
                      signature: bytes,
                      details: Optional[CallDetails] = None):
        """
        Remove an existing XBR Cloud Domain.

        :param member_oid: ID of the member to remove the cloud domain under (must be owner).

        :param chain_id: Blockchain ID.

        :param block_number: Blockchain current block number.

        :param contract_adr: Address of ``XBRNetwork`` smart contract.

        :param signature: EIP712 signature (computed over the fields ``chain_id``, ``block_number``,
            ``contract_adr``, ...) for the cloud domain removal.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Cloud domain removal information.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.get_domains_by_owner', check_types=True)
    def get_domains_by_owner(self, member_oid: bytes, details: Optional[CallDetails] = None):
        """
        Get list of XBR Cloud Domains owned by the given member.

        :param member_oid: ID of the member to retrieve owned domains for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of addresses of domains owned by the given member.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.get_domain', check_types=True)
    def get_domain(self, domain_adr: bytes, details: Optional[CallDetails] = None):
        """
        Retrieve basic information for the given XBR Cloud Domain.

        :param domain_adr: Address of the XBR Cloud Domain to retrieve information for.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: Domain information.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()

    @wamp.register('xbr.network.find_domains', check_types=True)
    def find_domains(self,
                     include_owners: Optional[list] = None,
                     include_titles: Optional[list] = None,
                     include_descs: Optional[list] = None,
                     include_tags: Optional[list] = None,
                     details: Optional[CallDetails] = None):
        """
        Search for XBR Cloud Domains by owner, label, description, tags, etc.

        :param include_owners: If provided, only return cloud domains owned by any of the owners specified.

        :param include_titles: If provided, only return cloud domains with a title that contains any of the specified titles.

        :param include_descs: If provided, only return cloud domains with a description that contains any of the specified descriptions.

        :param include_tags: If provided, only return cloud domains with a tag that contains any of the specified tags.

        :param details: Caller details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :return: List of addresses of cloud domains matching the search criteria.
        """
        assert details is None or isinstance(
            details, CallDetails), 'details must be `autobahn.wamp.types.CallDetails`, but was `{}`'.format(details)

        raise NotImplementedError()
