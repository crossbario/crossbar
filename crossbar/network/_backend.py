# coding=utf8

##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import inspect
import os
import re
import uuid
import time
import binascii
import hashlib
import threading
from typing import Dict

import zlmdb

import cfxdb.xbr.actor
import cfxdb.xbr.block
import cfxdb.xbr.market
import cfxdb.xbr.member
import cfxdb.xbr.token
import multihash
import cbor2
import numpy as np
from validate_email import validate_email

import cid

import web3
import eth_keys
import eth_account
import requests
from hexbytes import HexBytes

from txaio import make_logger, time_ns, sleep
from twisted.internet.threads import deferToThread

from autobahn.util import generate_activation_code, with_0x
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions
from autobahn.twisted.wamp import ApplicationSession
from autobahn import xbr
from autobahn.xbr import unpack_uint256, pack_uint256, make_w3

from crossbar._version import __version__

import cfxdb
from cfxdb.xbrnetwork import VerifiedAction, Account, UserKey
from cfxdb.xbr import Market, Actor, ActorType, Catalog, Api
from cfxdb.meta.attribute import Attribute

from autobahn.xbr import recover_eip712_member_register
from autobahn.xbr import recover_eip712_member_login
from autobahn.xbr import recover_eip712_market_create
from autobahn.xbr import recover_eip712_market_join
from autobahn.xbr import recover_eip712_catalog_create
from autobahn.xbr import recover_eip712_api_publish
from autobahn.xbr import is_address, is_block_number, is_chain_id, is_cs_pubkey

from ._mailgw import MailGateway

import treq

from ._util import hl, hlid, hlval, hlcontract, alternative_username
from ._error import UsernameAlreadyExists
from ._mailgw import _ONBOARD_MEMBER_LOG_VERIFICATION_CODE_START, _ONBOARD_MEMBER_LOG_VERIFICATION_CODE_END, \
    _LOGIN_MEMBER_LOG_VERIFICATION_CODE_START, _LOGIN_MEMBER_LOG_VERIFICATION_CODE_END, \
    _CREATE_MARKET_LOG_VERIFICATION_CODE_START, _CREATE_MARKET_LOG_VERIFICATION_CODE_END, \
    _JOIN_MARKET_LOG_VERIFICATION_CODE_START, _JOIN_MARKET_LOG_VERIFICATION_CODE_END, \
    _CREATE_CATALOG_LOG_VERIFICATION_CODE_START, _CREATE_CATALOG_LOG_VERIFICATION_CODE_END, \
    _PUBLISH_API_LOG_VERIFICATION_CODE_START, _PUBLISH_API_LOG_VERIFICATION_CODE_END

_USERNAME_PAT_STR = r'^[a-zA-Z][a-zA-Z0-9_]{3,14}$'
_USERNAME_PAT = re.compile(_USERNAME_PAT_STR)

_IPFS_API_GATEWAY = 'https://ipfs.infura.io:5001/api/v0'
_IPFS_PUT_DAG_ENDPOINT = f'{_IPFS_API_GATEWAY}/block/put'
_IPFS_ADD_FILE_ENDPOINT = f'{_IPFS_API_GATEWAY}/add'
_IPFS_CAT_FILE_ENDPOINT = f'{_IPFS_API_GATEWAY}/cat?arg={{file_hash}}'


def is_valid_username(username):
    return _USERNAME_PAT.match(username) is not None


def _verify_meta_data(meta_hash, meta_data, meta_obj_expected):
    if meta_hash is not None:
        if type(meta_hash) != str:
            raise RuntimeError('Invalid type {} for meta_hash'.format(type(meta_hash)))
        try:
            # Profile hash must be a valid IPFS CID
            meta_hash = str(cid.from_string(meta_hash))
        except Exception as e:
            raise RuntimeError('Invalid meta_hash "{}" - not a valid CID ({})'.format(meta_hash, e))
        if meta_data is None:
            raise RuntimeError('No profile_data, but meta_hash provided!')

    if meta_data is not None:
        if type(meta_data) != bytes:
            raise RuntimeError('Invalid type {} for meta_data'.format(type(meta_data)))
        if meta_hash is None:
            raise RuntimeError('No profile_hash, but meta_data provided!')

        h = hashlib.sha256()
        h.update(meta_data)

        # .. compute the sha256 multihash b58-encoded string from that ..
        _meta_hash = multihash.to_b58_string(multihash.encode(h.digest(), 'sha2-256'))

        if meta_hash != _meta_hash:
            raise RuntimeError('Invalid meta_hash "{}": hash does not match expected "{}"'.format(
                meta_hash, _meta_hash))

        # load the serialized profile data we received
        _meta_obj_received = cbor2.loads(meta_data)

        # check that actually signed profile data is what we expect (is equal to what the client provided
        # in member_username, member_email, .. parameters):
        if _meta_obj_received != meta_obj_expected:
            raise RuntimeError('Invalid meta_data {} does not match expected data {}'.format(
                _meta_obj_received, meta_obj_expected))


class Backend(object):
    """
    Backend implementation of (most of the) public API.
    """
    def __init__(self, session: ApplicationSession, db: zlmdb.Database, meta_schema: cfxdb.meta.Schema,
                 xbr_schema: cfxdb.xbr.Schema, xbrnetwork_schema: cfxdb.xbrnetwork.Schema, chain_id: int,
                 eth_privkey_raw: bytes, w3: web3.Web3, mailgw: MailGateway, bc_config: Dict, ipfs_cache_dir: str):
        """

        :param db:
        :param xbr_schema:
        :param xbrnetwork_schema:
        :param chain_id:
        :param eth_privkey_raw:
        :param w3:
        :param mailgw:
        :param bc_config:
        """
        self.log = make_logger()
        self._session = session
        self._db = db
        self._meta = meta_schema
        self._xbr = xbr_schema
        self._xbrnetwork = xbrnetwork_schema
        self._chain_id = chain_id
        self._eth_privkey_raw = eth_privkey_raw
        self._w3 = w3
        self._mailgw = mailgw
        self._bc_gw_config = bc_config['gateway']
        self._ipfs_cache_dir = ipfs_cache_dir

        # make a private key object from the raw private key bytes
        self._eth_privkey = eth_keys.keys.PrivateKey(self._eth_privkey_raw)
        self._eth_acct = eth_account.Account.privateKeyToAccount(self._eth_privkey_raw)

        # get the canonical address of the account
        self._eth_adr_raw = self._eth_privkey.public_key.to_canonical_address()
        self._eth_adr = web3.Web3.toChecksumAddress(self._eth_adr_raw)

        # the blockchain monitor is running on a background thread which exits once this gets False
        self._run_monitor = threading.Event()

        # initially begin scanning the blockchain with this block, and subsequently scan from the last
        # processed and locally persisted block record in the database
        scan_from_block = bc_config.get('from_block', 1)

        # FIXME: use the one provided by parent code
        from twisted.internet import reactor
        self._reactor = reactor

        # monitor/pull blockchain from a background thread
        self._monitor_blockchain_thread = self._reactor.callInThread(self._monitor_blockchain, self._bc_gw_config,
                                                                     scan_from_block)

        self.log.info('XBR Network backend initialized (version={version}, chain_id={chain_id}, eth_adr={eth_adr})',
                      version=__version__,
                      chain_id=self._chain_id,
                      eth_adr=self._eth_adr)

    def stop(self):
        """

        :return:
        """
        if not self._run_monitor.is_set():
            self._run_monitor.set()
            if self._monitor_blockchain_thread:
                self._monitor_blockchain_thread.join()

    def _save_verification_file(self, vaction_oid, vaction_type, verified_data):
        # in addition to writing the vaction to the embedded database, also write the
        # pending verification to a local file
        fd = '.verifications'
        if not os.path.isdir(fd):
            os.mkdir(fd)
        fn = '{}.{}'.format(vaction_type, vaction_oid)
        verification_file = os.path.abspath(os.path.join(fd, fn))
        with open(verification_file, 'wb') as f:
            f.write(cbor2.dumps(verified_data))
        self.log.info('New verification file "{verification_file}" written',
                      verification_file=hlval(verification_file))

    def _remove_verification_file(self, vaction_oid, vaction_type, rename_only=True):
        fd = '.verifications'
        if not os.path.isdir(fd):
            os.mkdir(fd)
        fn = '{}.{}'.format(vaction_type, vaction_oid)
        verification_file = os.path.abspath(os.path.join(fd, fn))
        if os.path.isfile(verification_file):
            if rename_only:
                fd = '.verifications/completed'
                if not os.path.isdir(fd):
                    os.mkdir(fd)
                new_verification_file = os.path.abspath(os.path.join(fd, fn))
                os.rename(verification_file, new_verification_file)
                self.log.info('Verification file renamed from "{verification_file}" to "{new_verification_file}"',
                              verification_file=hlval(verification_file),
                              new_verification_file=hlval(new_verification_file))
                return True
            else:
                os.remove(verification_file)
                self.log.info('Verification file removed "{verification_file}"',
                              verification_file=hlval(verification_file))
                return True
        else:
            return False

    def _download_and_cache(self, meta_hash):
        file_path = os.path.join(self._ipfs_cache_dir, meta_hash)
        if os.path.exists(file_path):
            return open(file_path, 'r').read()

        response = requests.get(_IPFS_CAT_FILE_ENDPOINT.format(file_hash=meta_hash), timeout=10)
        content = response.content.decode()
        with open(file_path, 'w') as file:
            file.write(content)

        return content

    async def _upload_to_infura(self, meta_hash, meta_data, upload=True):
        file_path = os.path.join(self._ipfs_cache_dir, meta_hash)
        if not os.path.exists(file_path):
            cbor2.dump(meta_data, open(file_path, 'bw'))
        if upload:
            response = await treq.post(_IPFS_PUT_DAG_ENDPOINT, files={'file': meta_data})
            if response.code == 200:
                return (await response.json())['Key']
            # FIXME: Push to "retry" database.
            return None
        return meta_hash

    async def _ensure_runtime(self, ts_started):
        # enforce run-time ~100ms (info leakage / timing attack / DoS protection)
        ts_ended = time_ns()
        duration_ms = int((ts_ended - ts_started) / 1000000.)
        if duration_ms < 100:
            delay_secs = (100. - duration_ms) / 1000.
            await sleep(delay_secs)
        else:
            self.log.warn('excessive run-time of {duration_ms} ms in {klass}.{caller}',
                          duration_ms=duration_ms,
                          klass=self.__class__.__name__,
                          caller=inspect.stack()[1].function)

    def _monitor_blockchain(self, gateway_config, scan_from_block, period=300):
        """

        :param gateway_config:
        :param scan_from_block:
        :param period:
        :return:
        """
        w3 = make_w3(gateway_config)
        initial_delay = 2

        self.log.info(
            'Start monitoring of blockchain ({blockchain_type}) on thread {thread_id} in {initial_delay} seconds, iterating every {period} seconds  ..',
            blockchain_type=str(self._bc_gw_config['type']),
            initial_delay=hlval(initial_delay),
            period=hlval(period),
            thread_id=hlval(int(threading.get_ident())))

        # using normal blocking call here, as we are running on a background thread!
        time.sleep(initial_delay)

        def _process_Token_Transfer(transactionHash, blockHash, args):
            # event Transfer(address indexed from, address indexed to, uint256 value);
            self.log.info(
                '{event}: processing event (tx_hash={tx_hash}, block_hash={block_hash}) - {value} XBR token transferred (on-chain) from {_from} to {_to})',
                event=hlcontract('XBRToken.Transfer'),
                tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()),
                block_hash=hlid('0x' + binascii.b2a_hex(blockHash).decode()),
                value=hlval(int(args.value / 10**18)),
                _from=hlval(args['from']),
                _to=hlval(args.to))

            stored = False
            with self._db.begin(write=True) as txn:

                transactionHash = bytes(transactionHash)

                token_transfer = self._xbr.token_transfers[txn, transactionHash]
                if token_transfer:
                    self.log.warn('{contract}(tx_hash={tx_hash}) record already stored in database.',
                                  contract=hlcontract('TokenTransfer'),
                                  tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()))
                else:
                    token_transfer = cfxdb.xbr.token.TokenTransfer()

                    token_transfer.tx_hash = transactionHash
                    token_transfer.block_hash = bytes(blockHash)
                    token_transfer.from_address = bytes(HexBytes(args['from']))
                    token_transfer.to_address = bytes(HexBytes(args.to))
                    token_transfer.value = args.value

                    self._xbr.token_transfers[txn, transactionHash] = token_transfer
                    stored = True

            if stored:
                self.log.info('new {contract}(tx_hash={tx_hash}) record stored database!',
                              contract=hlcontract('TokenTransfer'),
                              tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()))

        def _process_Token_Approval(transactionHash, blockHash, args):
            # event Approval(address indexed from, address indexed to, uint256 value);
            self.log.info(
                '{event}: processing event (tx_hash={tx_hash}, block_hash={block_hash}) - {value} XBR token approved (on-chain) from owner {owner} to spender {spender})',
                event=hlcontract('XBRToken.Approval'),
                tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()),
                block_hash=hlid('0x' + binascii.b2a_hex(blockHash).decode()),
                value=hlval(int(args.value / 10**18)),
                owner=hlval(args.owner),
                spender=hlval(args.spender))

            stored = False
            with self._db.begin(write=True) as txn:

                transactionHash = bytes(transactionHash)

                token_approval = self._xbr.token_approvals[txn, transactionHash]
                if token_approval:
                    self.log.warn('{contract}(tx_hash={tx_hash}) record already stored in database.',
                                  contract=hlcontract('TokenApproval'),
                                  tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()))
                else:
                    token_approval = cfxdb.xbr.token.TokenApproval()

                    token_approval.tx_hash = transactionHash
                    token_approval.block_hash = bytes(blockHash)
                    token_approval.owner_address = bytes(HexBytes(args.owner))
                    token_approval.spender_address = bytes(HexBytes(args.spender))
                    token_approval.value = args.value

                    self._xbr.token_approvals[txn, transactionHash] = token_approval
                    stored = True

            if stored:
                self.log.info('new {contract}(tx_hash={tx_hash}) record stored database!',
                              contract=hlcontract('TokenApproval'),
                              tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()))

        def _process_Network_MemberRegistered(transactionHash, blockHash, args):
            #     /// Event emitted when a new member joined the XBR Network.
            #     event MemberCreated (address indexed member, string eula, string profile, MemberLevel level);
            self.log.info(
                '{event}: processing event (tx_hash={tx_hash}, block_hash={block_hash}) - XBR member created at address {address})',
                event=hlcontract('XBRNetwork.MemberCreated'),
                tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()),
                block_hash=hlid('0x' + binascii.b2a_hex(blockHash).decode()),
                address=hlid(args.member))

            member_adr = bytes(HexBytes(args.member))

            if args.eula:
                h = multihash.decode(multihash.from_b58_string(args.eula))
                if h.name != 'sha2-256':
                    self.log.warn(
                        'WARNING: XBRNetwork.MemberCreated - eula "{eula}" is not an IPFS (sha2-256) b58-encoded multihash',
                        eula=hlval(args.eula))

            if args.profile:
                h = multihash.decode(multihash.from_b58_string(args.profile))
                if h.name != 'sha2-256':
                    self.log.warn(
                        'WARNING: XBRNetwork.MemberCreated - profile "{profile}" is not an IPFS (sha2-256) b58-encoded multihash',
                        eula=hlval(args.profile))

            stored = False
            with self._db.begin(write=True) as txn:

                member = self._xbr.members[txn, member_adr]
                if member:
                    self.log.warn('{contract}(tx_hash={tx_hash}) record already stored in database.',
                                  contract=hlcontract('TokenApproval'),
                                  tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()))
                else:
                    member = cfxdb.xbr.member.Member()
                    member.address = member_adr
                    member.timestamp = np.datetime64(time_ns(), 'ns')
                    member.registered = args.registered
                    member.eula = args.eula
                    member.profile = args.profile
                    member.level = args.level

                    self._xbr.members[txn, member_adr] = member
                    stored = True

            if stored:
                # FIXME: eligible_authid == authid of the user that was registered
                eligible_authid = None

                # FIXME: member information
                onboard_member_registered = {'fixme': True}
                self._reactor.callFromThread(self._session.publish,
                                             'xbr.network.on_onboard_member_complete',
                                             onboard_member_registered,
                                             options=PublishOptions(acknowledge=True, eligible_authid=eligible_authid))

                self.log.info('new {contract}(member_adr={member_adr}) record stored database!',
                              contract=hlcontract('MemberCreated'),
                              member_adr=hlid('0x' + binascii.b2a_hex(member_adr).decode()))

        def _process_Network_MemberRetired(transactionHash, blockHash, args):
            #     /// Event emitted when a member leaves the XBR Network.
            #     event MemberRetired (address member);
            self.log.warn('_process_Network_MemberRetired not implemented')

        def _process_Market_MarketCreated(transactionHash, blockHash, args):
            #     /// Event emitted when a new market was created.
            #     event MarketCreated (bytes16 indexed marketId, uint32 marketSeq, address owner, string terms, string meta,
            #         address maker, uint256 providerSecurity, uint256 consumerSecurity, uint256 marketFee);
            self.log.info(
                '{event}: processing event (tx_hash={tx_hash}, block_hash={block_hash}) - XBR market created with ID {market_id})',
                event=hlcontract('XBRMarket.MarketCreated'),
                tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()),
                block_hash=hlid('0x' + binascii.b2a_hex(blockHash).decode()),
                market_id=hlid(uuid.UUID(bytes=args.marketId)))

            market_id = uuid.UUID(bytes=args.marketId)

            if args.terms:
                h = multihash.decode(multihash.from_b58_string(args.terms))
                if h.name != 'sha2-256':
                    self.log.warn(
                        'WARNING: XBRMarket.MarketCreated - terms "{terms}" is not an IPFS (sha2-256) b58-encoded multihash',
                        terms=hlval(args.terms))

            if args.meta:
                h = multihash.decode(multihash.from_b58_string(args.meta))
                if h.name != 'sha2-256':
                    self.log.warn(
                        'WARNING: XBRMarket.MarketCreated - meta "{meta}" is not an IPFS (sha2-256) b58-encoded multihash',
                        meta=hlval(args.meta))

            stored = False
            with self._db.begin(write=True) as txn:

                market = self._xbr.markets[txn, market_id]
                if market:
                    self.log.warn('{contract}(tx_hash={tx_hash}) record already stored in database.',
                                  contract=hlcontract('MarketCreated'),
                                  tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()))
                else:
                    market = cfxdb.xbr.market.Market()
                    market.market = market_id
                    market.timestamp = np.datetime64(time_ns(), 'ns')

                    # FIXME
                    # market.created = args.created

                    market.seq = args.marketSeq
                    market.owner = bytes(HexBytes(args.owner))
                    market.terms = args.terms
                    market.meta = args.meta
                    market.maker = bytes(HexBytes(args.maker))
                    market.provider_security = args.providerSecurity
                    market.consumer_security = args.consumerSecurity
                    market.market_fee = args.marketFee

                    self._xbr.markets[txn, market_id] = market
                    stored = True

            if stored:
                self.log.info('new {contract}(market_id={market_id}) record stored database!',
                              contract=hlcontract('MarketCreated'),
                              market_id=hlid(market_id))

        def _process_Market_MarketUpdated(transactionHash, blockHash, args):
            #     /// Event emitted when a market was updated.
            #     event MarketUpdated (bytes16 indexed marketId, uint32 marketSeq, address owner, string terms, string meta,
            #         address maker, uint256 providerSecurity, uint256 consumerSecurity, uint256 marketFee);
            self.log.warn('_process_Market_MarketUpdated not implemented')

        def _process_Market_MarketClosed(transactionHash, blockHash, args):
            #     /// Event emitted when a market was closed.
            #     event MarketClosed (bytes16 indexed marketId);
            self.log.warn('_process_Market_MarketClosed not implemented')

        def _process_Market_ActorJoined(transactionHash, blockHash, args):
            # Event emitted when a new actor joined a market.
            # event ActorJoined (bytes16 indexed marketId, address actor, uint8 actorType, uint joined, uint256 security, string meta);
            self.log.info(
                '{event}: processing event (tx_hash={tx_hash}, block_hash={block_hash}) - XBR market actor {actor} joined market {market_id})',
                event=hlcontract('XBRMarket.ActorJoined'),
                tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()),
                block_hash=hlid('0x' + binascii.b2a_hex(blockHash).decode()),
                actor=hlid(args.actor),
                market_id=hlid(uuid.UUID(bytes=args.marketId)))

            market_id = uuid.UUID(bytes=args.marketId)
            actor_adr = bytes(HexBytes(args.actor))
            actor_type = int(args.actorType)

            if args.meta:
                h = multihash.decode(multihash.from_b58_string(args.meta))
                if h.name != 'sha2-256':
                    self.log.warn(
                        'WARNING: XBRMarket.MarketCreated - meta "{meta}" is not an IPFS (sha2-256) b58-encoded multihash',
                        terms=hlval(args.meta))

            stored = False
            with self._db.begin(write=True) as txn:

                actor = self._xbr.actors[txn, (market_id, actor_adr, actor_type)]
                if actor:
                    self.log.warn('{contract}(tx_hash={tx_hash}) record already stored in database.',
                                  contract=hlcontract('MarketCreated'),
                                  tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()))
                else:
                    actor = cfxdb.xbr.actor.Actor()
                    actor.timestamp = np.datetime64(time_ns(), 'ns')
                    actor.market = market_id
                    actor.actor = actor_adr
                    actor.actor_type = actor_type

                    actor.joined = args.joined
                    actor.security = args.security
                    actor.meta = args.meta

                    self._xbr.actors[txn, (market_id, actor_adr, actor_type)] = actor
                    stored = True

            if stored:
                self.log.info(
                    'new {contract}(market_id={market_id}, actor_adr={actor_adr}, actor_type={actor_type}) record stored database!',
                    contract=hlcontract('ActorJoined'),
                    market_id=hlid(market_id),
                    actor_adr=hlid('0x' + binascii.b2a_hex(actor_adr).decode()),
                    actor_type=hlid(actor_type))

        def _process_Market_ActorLeft(transactionHash, blockHash, args):
            #     /// Event emitted when an actor has left a market.
            #     event ActorLeft (bytes16 indexed marketId, address actor);
            self.log.warn('_process_Market_ActorLeft not implemented')

        Events = [
            (xbr.xbrtoken.events.Transfer, _process_Token_Transfer),
            (xbr.xbrtoken.events.Approval, _process_Token_Approval),
            (xbr.xbrnetwork.events.MemberRegistered, _process_Network_MemberRegistered),
            (xbr.xbrnetwork.events.MemberRetired, _process_Network_MemberRetired),
            (xbr.xbrmarket.events.MarketCreated, _process_Market_MarketCreated),
            (xbr.xbrmarket.events.MarketUpdated, _process_Market_MarketUpdated),
            (xbr.xbrmarket.events.MarketClosed, _process_Market_MarketClosed),
            (xbr.xbrmarket.events.ActorJoined, _process_Market_ActorJoined),
            (xbr.xbrmarket.events.ActorLeft, _process_Market_ActorLeft),
        ]

        # determine the block number, starting from which we scan the blockchain for XBR events
        current = w3.eth.getBlock('latest')
        last_processed = scan_from_block - 1
        with self._db.begin() as txn:
            for block_number in self._xbr.blocks.select(txn, return_values=False, reverse=True, limit=1):
                last_processed = unpack_uint256(block_number)
        if last_processed > current.number:
            raise ApplicationError(
                'wamp.error.invalid_argument',
                'last processed block number {} (or configured "scan_from" block number) is larger than then current block number {}'
                .format(last_processed, current.number))
        else:
            self.log.info(
                'Start scanning blockchain: current block is {current_block}, last processed is {last_processed} ..',
                current_block=hlval(current.number),
                last_processed=hlval(last_processed + 1))

        iteration = 1

        while not self._run_monitor.is_set():
            # current last block
            current = w3.eth.getBlock('latest')

            # track number of blocks processed
            cnt_blocks_success = 0
            cnt_blocks_error = 0
            cnt_xbr_events = 0

            # synchronize on-change changes locally by processing blockchain events
            if last_processed < current.number:
                while last_processed < current.number:
                    last_processed += 1
                    try:
                        self.log.info('Now processing blockchain block {last_processed} ..',
                                      last_processed=hlval(last_processed))
                        cnt_xbr_events += self._process_block(w3, last_processed, Events)
                    except:
                        self.log.failure()
                        cnt_blocks_error += 1
                    else:
                        cnt_blocks_success += 1

                self.log.info(
                    'Monitor blockchain iteration {iteration} completed: new block processed (last_processed={last_processed}, thread_id={thread_id}, period={period}, cnt_xbr_events={cnt_xbr_events}, cnt_blocks_success={cnt_blocks_success}, cnt_blocks_error={cnt_blocks_error})',
                    iteration=hlval(iteration),
                    last_processed=hlval(last_processed),
                    thread_id=hlval(int(threading.get_ident())),
                    period=hlval(period),
                    cnt_xbr_events=hlval(cnt_xbr_events, color='green') if cnt_xbr_events else hlval(cnt_xbr_events),
                    cnt_blocks_success=hlval(cnt_blocks_success, color='green')
                    if cnt_xbr_events else hlval(cnt_blocks_success),
                    cnt_blocks_error=hlval(cnt_blocks_error, color='red')
                    if cnt_blocks_error else hlval(cnt_blocks_error))
            else:
                self.log.info(
                    'Monitor blockchain iteration {iteration} completed: no new blocks found (last_processed={last_processed}, thread_id={thread_id}, period={period})',
                    iteration=hlval(iteration),
                    last_processed=hlval(last_processed),
                    thread_id=hlval(int(threading.get_ident())),
                    period=hlval(period))

            # sleep (using normal blocking call here, as we are running on a background thread!)
            self._run_monitor.wait(period)

            iteration += 1

    def _process_block(self, w3, block_number, Events):
        """

        :param w3:
        :param block_number:
        :param Events:
        :return:
        """
        cnt = 0
        # FIXME: we filter by block, and XBRToken/XBRNetwork contract addresses, but
        # there are also dynamically created XBRChannel instances (which fire close events)
        filter_params = {
            'address': [xbr.xbrtoken.address, xbr.xbrnetwork.address],
            'fromBlock': block_number,
            'toBlock': block_number,
        }
        result = w3.eth.getLogs(filter_params)
        if result:
            for evt in result:
                receipt = w3.eth.getTransactionReceipt(evt['transactionHash'])
                for Event, handler in Events:
                    # FIXME: MismatchedABI pops up .. we silence this with errors=web3.logs.DISCARD
                    if hasattr(web3, 'logs') and web3.logs:
                        all_res = Event().processReceipt(receipt, errors=web3.logs.DISCARD)
                    else:
                        all_res = Event().processReceipt(receipt)
                    for res in all_res:
                        self.log.info('{handler} processing block {block_number} / txn {txn} with args {args}',
                                      handler=hl(handler.__name__),
                                      block_number=hlid(block_number),
                                      txn=hlid('0x' + binascii.b2a_hex(evt['transactionHash']).decode()),
                                      args=hlval(res.args))
                        handler(res.transactionHash, res.blockHash, res.args)
                        cnt += 1

        with self._db.begin(write=True) as txn:
            block = cfxdb.xbr.block.Block()
            block.timestamp = np.datetime64(time_ns(), 'ns')
            block.block_number = block_number
            # FIXME
            # block.block_hash = bytes()
            block.cnt_events = cnt
            self._xbr.blocks[txn, pack_uint256(block_number)] = block

        if cnt:
            self.log.info('Processed blockchain block {block_number}: processed {cnt} XBR events.',
                          block_number=hlid(block_number),
                          cnt=hlid(cnt))
        else:
            self.log.info('Processed blockchain block {block_number}: no XBR events found!',
                          block_number=hlid(block_number))

        return cnt

    def _get_transaction_receipt(self, transaction: bytes):
        """

        :param transaction:
        :return:
        """
        # get the full transaction receipt given the transaction hash
        receipt = self._w3.eth.getTransactionReceipt(transaction)
        return receipt

    def _get_gas_price(self):
        """

        :return:
        """
        # FIXME: read from eth gas station
        return self._w3.toWei('10', 'gwei')

    def _get_balances(self, wallet_adr):
        """

        :param wallet_adr:
        :return:
        """
        eth_balance = self._w3.eth.getBalance(wallet_adr)
        xbr_balance = xbr.xbrtoken.functions.balanceOf(wallet_adr).call()
        return eth_balance, xbr_balance

    def _send_for(self, function, *args):
        # FIXME: estimate gas required for call
        gas = 1300000

        # each submitted transaction must contain a nonce, which is obtained by the on-chain transaction number
        # for this account, including pending transactions (I think ..;) ..
        nonce = self._w3.eth.getTransactionCount(self._eth_acct.address, block_identifier='pending')
        self.log.info('{klass}._send_for ({func}) [1/4] - Ethereum transaction nonce: nonce={nonce}',
                      klass=hl(self.__class__.__name__),
                      func=function.fn_name,
                      nonce=nonce)

        # serialize transaction raw data from contract call and transaction settings
        raw_transaction = function(*args).buildTransaction({
            'from': self._eth_acct.address,
            'gas': gas,
            'gasPrice': self._get_gas_price(),
            'chainId': self._chain_id,  # https://stackoverflow.com/a/57901206/884770
            'nonce': nonce,
        })
        self.log.info(
            '{klass}._send_for ({func}) [2/4] - Ethereum transaction created: raw_transaction=\n{raw_transaction}\n',
            klass=hl(self.__class__.__name__),
            func=function.fn_name,
            raw_transaction=raw_transaction)

        # compute signed transaction from above serialized raw transaction
        signed_txn = self._w3.eth.account.sign_transaction(raw_transaction, private_key=self._eth_privkey_raw)
        self.log.info('{klass}._send_for ({func}) [3/4] - Ethereum transaction signed: signed_txn=\n{signed_txn}\n',
                      klass=hl(self.__class__.__name__),
                      func=function.fn_name,
                      signed_txn=hlval(binascii.b2a_hex(signed_txn.rawTransaction).decode()))

        # now send the pre-signed transaction to the blockchain via the gateway ..
        # https://web3py.readthedocs.io/en/stable/web3.eth.html  # web3.eth.Eth.sendRawTransaction
        txn_hash = self._w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        txn_hash = bytes(txn_hash)
        self.log.info('{klass}._send_for ({func}) [4/4] - Ethereum transaction submitted: txn_hash=0x{txn_hash}',
                      klass=hl(self.__class__.__name__),
                      func=function.fn_name,
                      txn_hash=hlval(binascii.b2a_hex(txn_hash).decode()))

        return txn_hash

    def _send_registerFor(self, member, registered, eula, profile, signature):
        """
        Send transaction to XBRNetwork.registerFor on-chain contract. This method is run
        on a background thread, as web3 is blocking.

        :param member:
        :param registered:
        :param eula:
        :param profile:
        :param signature:
        :return:
        """
        return self._send_for(xbr.xbrnetwork.functions.registerMemberFor, member, registered, eula, profile, signature)

    def _send_createMarketFor(self, member, created, marketId, coin, terms, meta, maker, providerSecurity,
                              consumerSecurity, marketFee, signature):
        """
        Send transaction to XBRNetwork.registerFor on-chain contract. This method is run
        on a background thread, as web3 is blocking.

        :param member:
        :param registered:
        :param eula:
        :param profile:
        :param signature:
        :return:
        """
        return self._send_for(xbr.xbrmarket.functions.createMarketFor, member, created, marketId, coin, terms, meta,
                              maker, providerSecurity, consumerSecurity, marketFee, signature)

    def _send_joinMarketFor(self, member, joined, marketId, actorType, meta, signature):
        """
        Send transaction to XBRMarket.joinMarketFor on-chain contract. This method is run
        on a background thread, as web3 is blocking.

        :param member:
        :param joined:
        :param marketId:
        :param actorType:
        :param meta:
        :param signature:
        :return:
        """
        return self._send_for(xbr.xbrmarket.functions.joinMarketFor, member, joined, marketId, actorType, meta,
                              signature)

    def _send_createCatalogFor(self, member, created, catalog_id, terms, meta, signature):
        return self._send_for(xbr.xbrcatalog.functions.createCatalogFor, member, created, catalog_id, terms, meta,
                              signature)

    def get_config(self, include_eula_text=False):
        """
        Assemble and return configuration.

        :param include_eula_text: If set, fetch and include latest EULA text.

        .. note::
            This procedure is blocking, hence run on a background thread.

        :return:
        """
        now = time_ns()
        chain_id = int(self._w3.net.version)

        # on-chain calls
        verifying_chain_id = int(xbr.xbrnetwork.functions.verifyingChain().call())
        verifying_contract_adr = str(xbr.xbrnetwork.functions.verifyingContract().call())
        xbr_network_eula_hash = str(xbr.xbrnetwork.functions.eula().call())
        xbr_network_eula_url = _IPFS_CAT_FILE_ENDPOINT.format(file_hash=xbr_network_eula_hash)
        planet_eula_hash = 'QmVSAj3Wp3U9wo43NBUMrsFNa4MYUvA65vtj9zY7kAxSF8'
        planet_eula_url = _IPFS_CAT_FILE_ENDPOINT.format(file_hash=planet_eula_hash)
        if include_eula_text:
            xbr_network_eula_text = self._download_and_cache(xbr_network_eula_hash)
            planet_eula_text = self._download_and_cache(planet_eula_hash)
        else:
            xbr_network_eula_text = None
            planet_eula_text = None

        result = {
            'now': now,
            'chain': chain_id,
            'verifying_chain_id': verifying_chain_id,
            'verifying_contract_adr': verifying_contract_adr,
            'contracts': {
                'xbrtoken': str(xbr.xbrtoken.address),
                'xbrnetwork': str(xbr.xbrnetwork.address),
            },
            'eula': {
                'url': xbr_network_eula_url,
                'hash': xbr_network_eula_hash,
                'text': xbr_network_eula_text,
            },
            'planet_xbr_eula': {
                'url': planet_eula_url,
                'hash': planet_eula_hash,
                'text': planet_eula_text,
            }
        }
        return result

    def get_status(self):
        """
        Assemble and return current status.

        .. note::
            This procedure is blocking, hence run on a background thread.

        :return:
        """

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

    async def onboard_member(self, member_username, member_email, client_pubkey, wallet_type, wallet_adr, chain_id,
                             block_number, contract_adr, eula_hash, profile_hash, profile_data, signature):
        ts_started = time_ns()

        if type(member_username) != str or not is_valid_username(member_username):
            raise RuntimeError('Invalid username "{}" - must be a string matching the regular expression {}'.format(
                member_username, _USERNAME_PAT_STR))

        if type(member_email) != str or not validate_email(member_email, check_mx=False, verify=False):
            raise RuntimeError('Invalid email address "{}"'.format(member_email))

        if not is_cs_pubkey(client_pubkey):
            raise RuntimeError('Invalid client public key "{}"'.format(client_pubkey))

        if type(wallet_type) != str or wallet_type not in Account.WALLET_TYPE_FROM_STRING:
            raise RuntimeError('Invalid wallet type "{}"'.format(wallet_type))

        if not is_address(wallet_adr):
            raise RuntimeError('Invalid wallet address "{}"'.format(wallet_adr))

        if not is_chain_id(chain_id):
            raise RuntimeError('Invalid chain_id "{}"'.format(chain_id))

        if not is_block_number(block_number):
            raise RuntimeError('Invalid block_number "{}"'.format(block_number))

        if not is_address(contract_adr):
            raise RuntimeError('Invalid contract_adr "{}"'.format(contract_adr))

        network_eula_hash = await deferToThread(lambda: str(xbr.xbrnetwork.functions.eula().call()))
        if type(eula_hash) != str or eula_hash != network_eula_hash:
            raise RuntimeError('EULA must be accepted')

        if profile_hash is not None:
            if type(profile_hash) != str:
                raise RuntimeError('Invalid type {} for profile_hash'.format(type(profile_hash)))
            try:
                # Profile hash must be a valid IPFS CID
                profile_hash_ = cid.from_string(profile_hash)
                profile_hash = str(profile_hash_)
            except Exception as e:
                raise RuntimeError('Invalid profile_hash "{}" - not a valid CID ({})'.format(profile_hash, e))
            if profile_data is None:
                raise RuntimeError('No profile_data, but profile_hash provided!')

        if profile_data is not None:
            if type(profile_data) != bytes:
                raise RuntimeError('Invalid type {} for profile_data'.format(type(profile_data)))
            if profile_hash is None:
                raise RuntimeError('No profile_hash, but profile_data provided!')

            h = hashlib.sha256()
            h.update(profile_data)

            # .. compute the sha256 multihash b58-encoded string from that ..
            _profile_hash = multihash.to_b58_string(multihash.encode(h.digest(), 'sha2-256'))

            if profile_hash != _profile_hash:
                raise RuntimeError('Invalid profile_hash "{}": hash does not match expected "{}"'.format(
                    profile_hash, _profile_hash))

            # re-create an aux-data object with info only stored off-chain (in our xbrbackend DB) ..
            _profile_obj_expected = {
                'member_username': member_username,
                'member_email': member_email,
                'client_pubkey': client_pubkey,
                'wallet_type': wallet_type,
            }

            # load the serialized profile data we received
            _profile_obj_received = cbor2.loads(profile_data)

            # check that actually signed profile data is what we expect (is equal to what the client provided
            # in member_username, member_email, .. parameters):
            if _profile_obj_received != _profile_obj_expected:
                raise RuntimeError('Invalid profile_data {} does not match expected data {}'.format(
                    _profile_obj_received, _profile_obj_expected))

        if type(signature) != bytes:
            raise RuntimeError('Invalid type {} for signature'.format(type(signature)))
        if len(signature) != (32 + 32 + 1):
            raise RuntimeError('Invalid signature length {} - must be 65'.format(len(signature)))

        try:
            signer_address = recover_eip712_member_register(chain_id, contract_adr, wallet_adr, block_number,
                                                            eula_hash, profile_hash, signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed (wallet_adr={wallet_adr}): {err}',
                          wallet_adr=wallet_adr,
                          err=str(e))
            raise ApplicationError('xbr.network.error.invalid_signature',
                                   'EIP712 signature recovery failed ({})'.format(e))

        if signer_address != wallet_adr:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, wallet_adr={wallet_adr}',
                          signer_address=signer_address,
                          wallet_adr=wallet_adr)
            raise ApplicationError('xbr.network.error.invalid_signature', 'EIP712 signature invalid')

        with self._db.begin() as txn:
            # Check if the wallet is already used to create an account, if so
            # then send a login email to the user instead.
            account_oid = self._xbrnetwork.idx_accounts_by_wallet[txn, wallet_adr]
            if account_oid:
                member = self._xbrnetwork.accounts[txn, account_oid]
                timestamp = time_ns()
                return await self._really_login(account_oid,
                                                member.email,
                                                client_pubkey,
                                                timestamp,
                                                wallet_adr,
                                                ts_started,
                                                was_signup=True)

            # Check if the user already exists for that email
            account_oid = self._xbrnetwork.idx_accounts_by_email[txn, member_email]
            if account_oid:
                member = self._xbrnetwork.accounts[txn, account_oid]
                # If wallet matches, then just send a login email
                if member.wallet_address == wallet_adr:
                    timestamp = time_ns()
                    return await self._really_login(account_oid,
                                                    member.email,
                                                    client_pubkey,
                                                    timestamp,
                                                    wallet_adr,
                                                    ts_started,
                                                    was_signup=True)
                else:
                    # If wallet address is different, send email to user
                    # and tell them to use the correct wallet to login instead.
                    address_hex = binascii.b2a_hex(bytes(member.wallet_address)).decode()
                    self._mailgw.send_wrong_wallet_email(member_email, with_0x(address_hex),
                                                         with_0x(binascii.b2a_hex(wallet_adr).decode()))
                    return await self._ensure_runtime(ts_started)

            # check if a member with desired username already exists
            account_oid = self._xbrnetwork.idx_accounts_by_username[txn, member_username]
            if account_oid:
                # if the desired username is already taken, iterate to find an alternative
                alt_username = member_username
                while account_oid:
                    alt_username = alternative_username(alt_username)
                    account_oid = self._xbrnetwork.idx_accounts_by_username[txn, alt_username]
                await self._ensure_runtime(ts_started)
                raise UsernameAlreadyExists(member_username, alt_username=alt_username)

        # create new verification action ID and code
        vaction_oid = uuid.uuid4()

        # generate a new verification code: this must only be sent via a 2nd channel!
        vaction_code = generate_activation_code()

        # member onboarding time
        onboarded = time_ns()

        # send email with verification link, containing the verification code (email is the 2nd channel here)
        if not member_email.endswith('@nodomain'):  # filter CI/test scripts data and skip sending emails!
            self._mailgw.send_onboard_verification(member_email, vaction_oid, vaction_code)
        else:
            self.log.warn('Sending of email to "{member_email}" skipped - domain is filtered',
                          member_email=member_email)

        # data that is verified
        verified_data = {
            'onboarded': onboarded,
            'onboard_account_oid': uuid.uuid4().bytes,
            'onboard_vcode': vaction_code,
            'onboard_client_pubkey': client_pubkey,
            'onboard_member_name': member_username,
            'onboard_member_email': member_email,
            'onboard_wallet_address': wallet_adr,
            'onboard_wallet_type': Account.WALLET_TYPE_FROM_STRING[wallet_type],
            'onboard_registered': block_number,
            'onboard_eula': eula_hash,
            'onboard_profile': profile_hash,
            'onboard_signature': signature,
        }

        # store verification data in database ..
        with self._db.begin(write=True) as txn:
            # FIXME: can this happen? what should we do?
            # double check (again) for username collision, as the mailgun email submit happens async in above after
            # we initially checked for collision
            account_oid = self._xbrnetwork.idx_accounts_by_username[txn, member_username]
            if account_oid:
                raise RuntimeError('Username "{}" already exists'.format(member_username))

            vaction = VerifiedAction()
            vaction.oid = vaction_oid
            vaction.created = np.datetime64(onboarded, 'ns')
            vaction.vtype = VerifiedAction.VERIFICATION_TYPE_ONBOARD_MEMBER
            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_PENDING
            vaction.vcode = vaction_code
            # vaction.verified_oid = None
            vaction.verified_data = verified_data

            self._xbrnetwork.verified_actions[txn, vaction.oid] = vaction

        # in addition to writing the vaction to the embedded database, also write the
        # pending verification to a local file
        self._save_verification_file(vaction.oid, 'onboard-member-email-verification', vaction.verified_data)

        # print "magic opening bracket" to log for automated testing (do not change the string!)
        self.log.info(_ONBOARD_MEMBER_LOG_VERIFICATION_CODE_START)

        # print all information provided in verification email sent
        self.log.info(
            '>>>>> "onboarded": {onboarded}, "vaction_oid": "{vaction_oid}", "member_email": "{member_email}", "vaction_code": "{vaction_code}" <<<<<',
            onboarded=onboarded,
            member_email=member_email,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code)

        # print "magic closing bracket" to log for automated testing (do not change the string!)
        self.log.info(_ONBOARD_MEMBER_LOG_VERIFICATION_CODE_END)

        # on-board member submission information
        onboard_request_submitted = {
            'timestamp': onboarded,
            'action': 'onboard_member',
            'vaction_oid': vaction_oid.bytes,
        }

        await self._ensure_runtime(ts_started)

        return onboard_request_submitted

    async def verify_onboard_member(self, vaction_oid, vaction_code):
        """

        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        try:
            vaction_oid = uuid.UUID(bytes=vaction_oid)
        except ValueError:
            raise RuntimeError('invalid verification oid "{}"'.format(vaction_oid))

        with self._db.begin(write=True) as txn:
            vaction = self._xbrnetwork.verified_actions[txn, vaction_oid]
            if not vaction:
                raise RuntimeError('no verification action {}'.format(vaction_oid))

            if vaction.vstatus != VerifiedAction.VERIFICATION_STATUS_PENDING:
                raise RuntimeError('verification action in state {}'.format(vaction.vstatus))

            if vaction.vcode != vaction_code:
                raise RuntimeError('invalid verification code "{}"'.format(vaction_code))

            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_VERIFIED

            if vaction.vtype == VerifiedAction.VERIFICATION_TYPE_ONBOARD_MEMBER:

                self._xbrnetwork.verified_actions[txn, vaction_oid] = vaction

                onboard_member_name = vaction.verified_data['onboard_member_name']
                account_oid = self._xbrnetwork.idx_accounts_by_username[txn, onboard_member_name]
                if account_oid:
                    vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_FAILED
                    raise RuntimeError('username "{}" already exists'.format(onboard_member_name))
                else:
                    account = Account()
                    account.oid = uuid.UUID(bytes=vaction.verified_data['onboard_account_oid'])
                    account.created = np.datetime64(time_ns(), 'ns')
                    account.username = onboard_member_name
                    account.email = vaction.verified_data['onboard_member_email']
                    account.wallet_type = vaction.verified_data['onboard_wallet_type']
                    account.wallet_address = vaction.verified_data['onboard_wallet_address']

                    userkey = UserKey()
                    userkey.pubkey = vaction.verified_data['onboard_client_pubkey']

                    # for the very first client key provided by the client during onboarding,
                    # we set creation data identical to that of the whole account
                    userkey.created = account.created
                    userkey.owner = account.oid

                    # store account and user key records
                    self._xbrnetwork.accounts[txn, account.oid] = account
                    self._xbrnetwork.user_keys[txn, userkey.pubkey] = userkey
            else:
                raise RuntimeError('unknown verification type {}'.format(vaction.vtype))

        self.log.info('ok, new account member_oid={member_oid} successfully created for user username="{username}"!',
                      member_oid=account.oid,
                      username=account.username)

        try:
            self._remove_verification_file(vaction_oid, 'onboard-member-email-verification')
        except Exception as err:
            self.log.warn('error while removing verification file: {err}', err=err)

        try:
            txn_hash = await deferToThread(self._send_registerFor, vaction.verified_data['onboard_wallet_address'],
                                           vaction.verified_data['onboard_registered'],
                                           vaction.verified_data['onboard_eula'],
                                           vaction.verified_data['onboard_profile'],
                                           vaction.verified_data['onboard_signature'])
        except Exception as e:
            self.log.failure()
            if isinstance(e, ValueError) and e.args[0]['message'].endswith("MEMBER_ALREADY_REGISTERED"):
                raise ApplicationError("xbr.network.error.member_already_registered", "Member is already registered")
            # FIXME: we have to retry, but not in-line before returning from this call
            raise e
        else:
            # return on-board member verification information
            onboard_request_verified = {
                'created': int(account.created),
                'member_oid': account.oid.bytes,
                'transaction': txn_hash,
                'verified_data': vaction.verified_data,
            }

            return onboard_request_verified

    async def login_member(self, member_email, client_pubkey, chain_id, block_number, contract_adr, timestamp,
                           wallet_adr, signature):
        """

        :param member_email:
        :param client_pubkey:
        :param chain_id:
        :param block_number:
        :param contract_adr:
        :param timestamp:
        :param wallet_adr:
        :param signature:
        :return:
        """
        ts_started = time_ns()

        if type(member_email) != str or not validate_email(member_email, check_mx=False, verify=False):
            raise RuntimeError('Invalid member_email "{}"'.format(member_email))

        if type(client_pubkey) != bytes or len(client_pubkey) != 32:
            raise RuntimeError('Invalid client_pubkey "{}"'.format(client_pubkey))

        if type(chain_id) != int:
            raise RuntimeError('Invalid chain_id "{}"'.format(chain_id))

        if type(block_number) != int:
            raise RuntimeError('Invalid block_number "{}"'.format(block_number))

        if type(contract_adr) != bytes or len(contract_adr) != 20:
            raise RuntimeError('Invalid contract_adr "{}"'.format(contract_adr))

        if type(timestamp) != int:
            raise RuntimeError('Invalid timestamp "{}"'.format(timestamp))

        if type(wallet_adr) != bytes or len(wallet_adr) != 20:
            raise RuntimeError('Invalid wallet_adr "{}"'.format(wallet_adr))

        if type(signature) != bytes:
            raise RuntimeError('Invalid type {} for signature'.format(type(signature)))
        if len(signature) != (32 + 32 + 1):
            raise RuntimeError('Invalid signature length {} - must be 65'.format(len(signature)))

        try:
            signer_address = recover_eip712_member_login(chain_id, contract_adr, wallet_adr, block_number, timestamp,
                                                         member_email, client_pubkey, signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed (wallet_adr={wallet_adr}): {err}',
                          wallet_adr=wallet_adr,
                          err=str(e))
            raise ApplicationError('xbr.network.error.invalid_signature',
                                   'EIP712 signature recovery failed ({})'.format(e))

        if signer_address != wallet_adr:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, wallet_adr={wallet_adr}',
                          signer_address=signer_address,
                          wallet_adr=wallet_adr)
            raise ApplicationError('xbr.network.error.invalid_signature', 'EIP712 signature invalid')

        with self._db.begin() as txn:
            account_oid = self._xbrnetwork.idx_accounts_by_wallet[txn, wallet_adr]
            if account_oid:
                member = self._xbrnetwork.accounts[txn, account_oid]
                if member.email != member_email:
                    raise ApplicationError('xbr.network.error.invalid_email',
                                           "Provided email not associated to the member")

            account_oid = self._xbrnetwork.idx_accounts_by_email[txn, member_email]
            if not account_oid:
                self.log.warn(
                    '{klass}.login_member: silently ignore request for email address "{email}" which is not a known member!',
                    email=member_email,
                    klass=self.__class__.__name__)

                # silently (to the caller!) ignore email addresses which aren't for active members,
                # so that we don't leak information about what emails are members

                # enforce run-time ~100ms (info leakage / timing attack / DoS protection)
                await self._ensure_runtime(ts_started)

                # Return a "fake" object here, so the caller
                # can't distinguish if the user exists or not
                fake_submit = {
                    'timestamp': timestamp,
                    'action': 'login_member',
                    'vaction_oid': uuid.uuid4().bytes,
                }
                return fake_submit

            member_address = self._xbrnetwork.accounts[txn, account_oid].wallet_address
            if member_address != wallet_adr:
                self.log.warn("Signer address ({signer_address}) does not match member's address ({member_address})",
                              signer_address=wallet_adr,
                              member_address=bytes(member_address))
                raise ApplicationError('xbr.network.error.invalid_wallet',
                                       "Signer address does not match member's address")

        return await self._really_login(account_oid, member_email, client_pubkey, timestamp, wallet_adr, ts_started)

    async def _really_login(self,
                            account_oid,
                            member_email,
                            client_pubkey,
                            timestamp,
                            wallet_adr,
                            ts_started,
                            was_signup=False):
        # create new verification action ID and code
        vaction_oid = uuid.uuid4()

        # generate a new verification code: this must only be sent via a 2nd channel!
        vaction_code = generate_activation_code()

        # send email with verification link, containing the verification code (email is the 2nd channel here)
        if not member_email.endswith('@nodomain'):  # filter CI/test scripts data and skip sending emails!
            self._mailgw.send_login_verification(member_email,
                                                 vaction_oid,
                                                 vaction_code,
                                                 binascii.b2a_hex(wallet_adr).decode(),
                                                 was_signup_request=was_signup)
        else:
            self.log.warn('Sending of email to "{member_email}" skipped - domain is filtered',
                          member_email=member_email)

        # data that is verified
        verified_data = {
            'login_time': timestamp,
            'login_vcode': vaction_code,
            'login_client_pubkey': client_pubkey,
            'login_account_oid': account_oid,
            'login_wallet_address': wallet_adr,
        }

        # store verification data in database ..
        with self._db.begin(write=True) as txn:
            vaction = VerifiedAction()
            vaction.oid = vaction_oid
            vaction.created = np.datetime64(timestamp, 'ns')
            vaction.vtype = VerifiedAction.VERIFICATION_TYPE_LOGIN_MEMBER
            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_PENDING
            vaction.vcode = vaction_code
            vaction.verified_oid = account_oid
            vaction.verified_data = verified_data

            self._xbrnetwork.verified_actions[txn, vaction.oid] = vaction

        # in addition to writing the vaction to the embedded database, also write the
        # pending verification to a local file
        self._save_verification_file(vaction.oid, 'login-member-email-verification', vaction.verified_data)

        # print "magic opening bracket" to log for automated testing (do not change the string!)
        self.log.info(_LOGIN_MEMBER_LOG_VERIFICATION_CODE_START)

        # print all information provided in verification email sent
        self.log.info(
            '>>>>> "timestamp": {timestamp}, "vaction_oid": "{vaction_oid}", "member_email": "{member_email}", "vaction_code": "{vaction_code}" <<<<<',
            timestamp=timestamp,
            member_email=member_email,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code)

        # print "magic closing bracket" to log for automated testing (do not change the string!)
        self.log.info(_LOGIN_MEMBER_LOG_VERIFICATION_CODE_END)

        # on-board member submission information
        login_request_submitted = {
            'timestamp': timestamp,
            'action': 'login_member',
            'vaction_oid': vaction_oid.bytes,
        }

        # enforce run-time ~100ms (info leakage / timing attack / DoS protection)
        await self._ensure_runtime(ts_started)

        return login_request_submitted

    def verify_login_member(self, vaction_oid, vaction_code):
        """

        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        try:
            vaction_oid = uuid.UUID(bytes=vaction_oid)
        except ValueError:
            raise RuntimeError('Invalid vaction_oid "{}"'.format(vaction_oid))

        if type(vaction_code) != str:
            raise RuntimeError('Invalid vaction_code "{}"'.format(vaction_code))

        with self._db.begin(write=True) as txn:
            vaction = self._xbrnetwork.verified_actions[txn, vaction_oid]
            if not vaction:
                raise RuntimeError('no verification action {}'.format(vaction_oid))

            if vaction.vstatus != VerifiedAction.VERIFICATION_STATUS_PENDING:
                raise RuntimeError('verification action in state {}'.format(vaction.vstatus))

            if vaction.vcode != vaction_code:
                self.log.warn(
                    '{klass}.verify_login_member: invalid verification code "{vaction_code}" received in client login - expected "{vaction_code_expected}"',
                    klass=self.__class__.__name__,
                    vaction_code_expected=vaction.vcode,
                    vaction_code=vaction_code)
                raise RuntimeError('invalid verification code "{}"'.format(vaction_code))

            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_VERIFIED

            if vaction.vtype == VerifiedAction.VERIFICATION_TYPE_LOGIN_MEMBER:

                self._xbrnetwork.verified_actions[txn, vaction_oid] = vaction

                account_oid = vaction.verified_oid
                account = self._xbrnetwork.accounts[txn, account_oid]

                userkey = UserKey()
                userkey.pubkey = vaction.verified_data['login_client_pubkey']
                userkey.created = np.datetime64(time_ns(), 'ns')
                userkey.owner = account.oid

                # store (additional) user key record (associated with user account)
                self._xbrnetwork.user_keys[txn, userkey.pubkey] = userkey
            else:
                raise RuntimeError('invalid verification type {}'.format(vaction.vtype))

        try:
            self._remove_verification_file(vaction_oid, 'login-member-email-verification')
        except Exception as err:
            self.log.warn('error while removing verification file: {err}', err=err)

        # on-board member verification information
        login_request_verified = {
            'member_oid': userkey.owner.bytes,
            'client_pubkey': userkey.pubkey,
            'created': int(userkey.created),
            'verified_data': vaction.verified_data,
        }
        return login_request_verified

    async def get_member(self, member_oid):

        assert type(member_oid) == bytes and len(member_oid) == 16
        member_oid = uuid.UUID(bytes=member_oid)

        with self._db.begin() as txn:
            account = self._xbrnetwork.accounts[txn, member_oid]
            if not account:
                raise RuntimeError('no member with oid {}'.format(member_oid))

        wallet_adr = bytes(account.wallet_address)

        self.log.info('{klass}.get_member(member_oid={member_oid}, wallet_adr={wallet_adr}) [xbrtoken={xbrtoken}]',
                      klass=self.__class__.__name__,
                      xbrtoken=str(xbr.xbrtoken.address),
                      member_oid=member_oid,
                      wallet_adr=wallet_adr)

        def do_get_member(wallet_adr):
            # check latest on-chain ETH/XBR balance on member wallet
            member_eth_balance = self._w3.eth.getBalance(wallet_adr)
            member_xbr_balance = xbr.xbrtoken.functions.balanceOf(wallet_adr).call()

            # convert for wire transfer
            member_eth_balance = pack_uint256(member_eth_balance)
            member_xbr_balance = pack_uint256(member_xbr_balance)

            member_registered, member_profile, member_eula, member_level, member_signature = xbr.xbrnetwork.functions.members(
                wallet_adr).call()

            # count markets owned by member
            cnt_markets = xbr.xbrmarket.functions.countMarketsByOwner(wallet_adr).call()

            # FIXME
            cnt_catalogs = 0
            cnt_domains = 0

            data = {
                'oid': member_oid.bytes,
                'address': wallet_adr,
                'level': member_level,
                'profile': member_profile,
                'eula': member_eula,
                'balance': {
                    'xbr': member_xbr_balance,
                    'eth': member_eth_balance,
                },
                'email': account.email,
                'username': account.username,
                'created': int(account.created),
                'markets': cnt_markets,
                'catalogs': cnt_catalogs,
                'domains': cnt_domains,
            }
            return data

        result = await deferToThread(do_get_member, wallet_adr)
        return result

    def get_block(self, block_no):
        """

        :param block_no:
        :return:
        """
        assert type(block_no) == bytes and len(block_no) == 32, 'block_no must be bytes[32], was "{}"'.format(block_no)

        with self._db.begin() as txn:
            block = self._xbr.blocks[txn, block_no]
            if not block:
                raise ApplicationError('crossbar.error.no_such_object', 'no block {}'.format(block_no.decode()))

        return block.marshal()

    def update_market(self, market_oid, attributes):
        """

        :param market_oid:
        :return:
        """
        assert isinstance(market_oid, uuid.UUID), 'market_oid must be bytes[16], was "{}"'.format(market_oid)
        assert attributes is None or type(attributes) == dict

        with self._db.begin(write=True) as txn:

            # FIXME: table of object on which to attach attributes: "schema.markets" !
            table_oid = uuid.UUID('861b0942-0c3f-4d41-bc35-d8c86af0b2c9')
            for attribute_name in attributes:
                attribute_key = (table_oid, market_oid, attribute_name)

                attribute = self._meta.attributes[txn, attribute_key]

                if not attribute:
                    attribute = Attribute()
                    attribute.table_oid = table_oid
                    attribute.object_oid = market_oid
                    attribute.attribute = attribute_name

                new_value = attributes[attribute_name]
                if new_value is None:
                    del self._meta.attributes[txn, (table_oid, market_oid, attribute_name)]
                else:
                    attribute.modified = np.datetime64(time_ns(), 'ns')
                    attribute.value = attributes[attribute_name]
                    self._meta.attributes[txn, (table_oid, market_oid, attribute_name)] = attribute

    async def create_coin(self, member_oid, coin_oid, chain_id, block_number, contract_adr, name, symbol, decimals,
                          initial_supply, meta_hash, meta_data, signature, attributes):
        raise NotImplementedError()

    async def verify_create_coin(self, vaction_oid, vaction_code):
        raise NotImplementedError()

    async def get_market(self, market_oid, include_attributes, include_terms_text):
        """

        :param market_oid:
        :return:
        """
        assert isinstance(market_oid, uuid.UUID), 'market_oid must be bytes[16], was "{}"'.format(market_oid)
        assert type(include_attributes), 'include_attributes must be bool, was {}'.format(type(include_attributes))

        with self._db.begin() as txn:
            market = self._xbr.markets[txn, market_oid]
            if not market:
                raise ApplicationError('crossbar.error.no_such_object', 'no market {}'.format(market_oid))

            result = market.marshal()
            if include_attributes:
                attributes = {}

                # FIXME: table of object on which to attach attributes: "schema.markets" !
                table_oid = uuid.UUID('861b0942-0c3f-4d41-bc35-d8c86af0b2c9')

                # Note: uuid.UUID(int=market_oid.int + 1) is a trick to get a correct upper search key here
                from_key = (table_oid, market_oid, '')
                to_key = (table_oid, uuid.UUID(int=market_oid.int + 1), '')
                for attribute in self._meta.attributes.select(txn, return_keys=False, from_key=from_key,
                                                              to_key=to_key):
                    attributes[attribute.attribute] = attribute.value

                result['attributes'] = attributes

        terms_text = ''
        if include_terms_text:
            terms_text = await deferToThread(self._download_and_cache, result['terms'])

        result['terms_text'] = terms_text
        return result

    async def create_market(self, member_id, market_id, chain_id, block_number, contract_adr, coin_adr, terms_hash,
                            meta_hash, meta_data, maker, provider_security, consumer_security, market_fee, signature,
                            attributes):
        ts_started = time_ns()

        with self._db.begin() as txn:
            account = self._xbrnetwork.accounts[txn, member_id]
            if not account:
                raise RuntimeError('no member with oid {}'.format(member_id))

        member_adr = bytes(account.wallet_address)
        member_email = account.email

        providerSecurity_ = unpack_uint256(provider_security)
        consumerSecurity_ = unpack_uint256(consumer_security)
        marketFee_ = unpack_uint256(market_fee)

        meta_obj_expected = {
            'chain_id': chain_id,
            'block_number': block_number,
            'contract_adr': contract_adr,
            'member_adr': member_adr,
            'member_oid': member_id.bytes,
            'market_oid': market_id.bytes,
        }

        _verify_meta_data(meta_hash, meta_data, meta_obj_expected)

        if type(signature) != bytes:
            raise RuntimeError('Invalid type {} for signature'.format(type(signature)))
        if len(signature) != (32 + 32 + 1):
            raise RuntimeError('Invalid signature length {} - must be 65'.format(len(signature)))

        try:
            signer_address = recover_eip712_market_create(chain_id, contract_adr, member_adr, block_number,
                                                          market_id.bytes, coin_adr, terms_hash, meta_hash, maker,
                                                          providerSecurity_, consumerSecurity_, marketFee_, signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed (member_adr={member_adr}): {err}',
                          member_adr=member_adr,
                          err=str(e))
            raise ApplicationError('xbr.network.error.invalid_signature',
                                   'EIP712 signature recovery failed ({})'.format(e))

        if signer_address != member_adr:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, member_adr={member_adr}',
                          signer_address=signer_address,
                          member_adr=member_adr)
            raise ApplicationError('xbr.network.error.invalid_signature', 'EIP712 signature invalid')

        with self._db.begin() as txn:
            market_oid = self._xbr.idx_markets_by_maker[txn, maker]
            if market_oid:
                raise ApplicationError("xbr.network.error.maker_already_working_for_other_market",
                                       "The market maker is already working for another market")

        # create new verification action ID and code
        vaction_oid = uuid.uuid4()

        # generate a new verification code: this must only be sent via a 2nd channel!
        vaction_code = generate_activation_code()

        # send email with verification link, containing the verification code (email is the 2nd channel here)
        if not member_email.endswith('@nodomain'):  # filter CI/test scripts data and skip sending emails!
            self._mailgw.send_create_market_verification(member_email, vaction_oid, vaction_code)
        else:
            self.log.warn('Sending of email to "{member_email}" skipped - domain is filtered',
                          member_email=member_email)

        should_upload = not member_email.endswith('@nodomain')
        result_hash = await self._upload_to_infura(meta_hash, meta_data, should_upload)
        assert result_hash == meta_hash

        # data that is verified
        verified_data = {
            'created': block_number,
            'vcode': vaction_code,
            'member_adr': bytes(member_adr),
            'member_oid': member_id.bytes,
            'market_oid': market_id.bytes,
            'coin_adr': bytes(coin_adr),
            'chain_id': chain_id,
            'block_number': block_number,
            'contract_adr': contract_adr,
            'terms_hash': terms_hash,
            'meta_hash': meta_hash,
            'meta_data': bytes(meta_data),
            'maker': bytes(maker),
            'providerSecurity': provider_security,
            'consumerSecurity': consumer_security,
            'marketFee': market_fee,
            'signature': bytes(signature),
            'attributes': attributes,
        }
        # FIXME: cbor2.types.CBOREncodeTypeError: cannot serialize type memoryview
        for k in verified_data:
            v = verified_data[k]
            if type(v) == type(memoryview):
                verified_data[k] = bytes(v)
                self.log.warn('Monkey-patched (memoryview => bytes) dict "verified_data" for key "{key_name}"',
                              key_name=k)

        # db creation time
        created = np.datetime64(time_ns(), 'ns')

        # store verification data in database ..
        with self._db.begin(write=True) as txn:
            vaction = VerifiedAction()
            vaction.oid = vaction_oid
            vaction.created = created
            vaction.vtype = VerifiedAction.VERIFICATION_TYPE_CREATE_MARKET
            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_PENDING
            vaction.vcode = vaction_code
            # FIXME: cannot serialize type memoryview
            # vaction.verified_oid = market_id
            vaction.verified_data = verified_data

            self._xbrnetwork.verified_actions[txn, vaction.oid] = vaction

        # in addition to writing the vaction to the embedded database, also write the
        # pending verification to a local file
        self._save_verification_file(vaction.oid, 'create-market-email-verification', vaction.verified_data)

        # print "magic opening bracket" to log for automated testing (do not change the string!)
        self.log.info(_CREATE_MARKET_LOG_VERIFICATION_CODE_START)

        # print all information provided in verification email sent
        self.log.info(
            '>>>>> "created": {created}, "vaction_oid": "{vaction_oid}", "market_id": "{market_id}", "vaction_code": "{vaction_code}" <<<<<',
            created=created,
            market_id=market_id.bytes,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code)

        # print "magic closing bracket" to log for automated testing (do not change the string!)
        self.log.info(_CREATE_MARKET_LOG_VERIFICATION_CODE_END)

        # on-board member submission information
        createmarket_request_submitted = {
            'timestamp': int(created),
            'action': 'create_market',
            'vaction_oid': vaction_oid.bytes,
        }

        # enforce run-time ~100ms (info leakage / timing attack / DoS protection)
        await self._ensure_runtime(ts_started)

        return createmarket_request_submitted

    async def verify_create_market(self, vaction_oid, vaction_code):
        """

        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        try:
            vaction_oid = uuid.UUID(bytes=vaction_oid)
        except ValueError:
            raise RuntimeError('invalid verification oid "{}"'.format(vaction_oid))

        with self._db.begin(write=True) as txn:
            vaction = self._xbrnetwork.verified_actions[txn, vaction_oid]
            if not vaction:
                raise RuntimeError('no verification action {}'.format(vaction_oid))

            if vaction.vstatus != VerifiedAction.VERIFICATION_STATUS_PENDING:
                raise RuntimeError('verification action in state {}'.format(vaction.vstatus))

            if vaction.vcode != vaction_code:
                raise RuntimeError('invalid verification code "{}"'.format(vaction_code))

            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_VERIFIED

            if vaction.vtype == VerifiedAction.VERIFICATION_TYPE_CREATE_MARKET:
                self._xbrnetwork.verified_actions[txn, vaction_oid] = vaction

                market = Market()
                market.market = uuid.UUID(bytes=vaction.verified_data['market_oid'])

                # FIXME? which timestamp to use?
                market.timestamp = np.datetime64(time_ns(), 'ns')
                # market.timestamp = vaction.verified_data['timestamp']

                # sequence is only determined by the on-chain contract once submitted
                # market.seq = None

                # FIXME? database relation is actually via vaction.verified_data['member_oid']
                market.owner = vaction.verified_data['member_adr']
                market.coin = vaction.verified_data['coin_adr']
                market.terms = vaction.verified_data['terms_hash']
                market.meta = vaction.verified_data['meta_hash']
                market.maker = vaction.verified_data['maker']

                # FIXME? unnecessary pack/unpack?
                market.provider_security = unpack_uint256(vaction.verified_data['providerSecurity'])
                market.consumer_security = unpack_uint256(vaction.verified_data['consumerSecurity'])
                market.market_fee = unpack_uint256(vaction.verified_data['marketFee'])

                self._xbr.markets[txn, market.market] = market

                if vaction.verified_data['attributes']:
                    # FIXME: table of object on which to attach attributes: "schema.markets" !
                    table_oid = uuid.UUID('861b0942-0c3f-4d41-bc35-d8c86af0b2c9')

                    # object on which to attach attributes
                    object_oid = market.market

                    for attribute_name, attribute_value in vaction.verified_data['attributes'].items():
                        attribute = Attribute()
                        attribute.table_oid = table_oid
                        attribute.object_oid = object_oid
                        attribute.attribute = attribute_name
                        attribute.modified = np.datetime64(time_ns(), 'ns')
                        attribute.value = attribute_value

                        self._meta.attributes[txn, (table_oid, object_oid, attribute_name)] = attribute
            else:
                raise RuntimeError('unknown verification type {}'.format(vaction.vtype))

        self.log.info('ok, new market market_oid={market_oid} successfully created!', market_oid=market.market)

        try:
            self._remove_verification_file(vaction_oid, 'create-market-email-verification')
        except Exception as err:
            self.log.warn('error while removing verification file: {err}', err=err)

        try:
            member = vaction.verified_data['member_adr']
            created = vaction.verified_data['created']
            coin = vaction.verified_data['coin_adr']
            marketId = vaction.verified_data['market_oid']
            terms = vaction.verified_data['terms_hash']
            meta = vaction.verified_data['meta_hash']
            maker = vaction.verified_data['maker']

            # FIXME? unnecessary pack/unpack?
            providerSecurity = unpack_uint256(vaction.verified_data['providerSecurity'])
            consumerSecurity = unpack_uint256(vaction.verified_data['consumerSecurity'])
            marketFee = unpack_uint256(vaction.verified_data['marketFee'])

            signature = vaction.verified_data['signature']

            txn_hash = await deferToThread(self._send_createMarketFor, member, created, marketId, coin, terms, meta,
                                           maker, providerSecurity, consumerSecurity, marketFee, signature)
        except Exception as e:
            if isinstance(e, ValueError) and e.args[0]['message'].endswith("MAKER_ALREADY_WORKING_FOR_OTHER_MARKET"):
                raise ApplicationError("xbr.network.error.maker_already_working_for_other_market",
                                       "The market maker is already working for another market")
            # FIXME:...
            raise e
        else:
            # return market creation verification information
            create_market_request_verified = {
                'created': int(market.timestamp),
                'market_oid': market.market.bytes,
                'transaction': txn_hash,
            }

            return create_market_request_verified

    async def join_market(self, member_id, market_id, chain_id, block_number, contract_adr, actor_type, meta_hash,
                          meta_data, signature):
        """

        :param member_id:
        :param market_id:
        :param chain_id:
        :param block_number:
        :param contract_adr:
        :param actor_type:
        :param meta_hash:
        :param meta_data:
        :param signature:
        :return:
        """
        ts_started = time_ns()

        if not isinstance(member_id, uuid.UUID):
            raise RuntimeError('member_id must be UUID, was {}'.format(type(member_id)))

        if not isinstance(market_id, uuid.UUID):
            raise RuntimeError('market_id must be UUID, was {}'.format(type(market_id)))

        if type(chain_id) != int:
            raise RuntimeError('Invalid chain_id "{}"'.format(chain_id))

        if type(contract_adr) != bytes or len(contract_adr) != 20:
            raise RuntimeError('Invalid contract_adr "{}"'.format(contract_adr))

        if type(block_number) != int:
            raise RuntimeError('Invalid block_number "{}"'.format(block_number))

        if type(contract_adr) != bytes or len(contract_adr) != 20:
            raise RuntimeError('Invalid contract_adr "{}"'.format(contract_adr))  # type: ignore

        if type(actor_type) != int:
            raise RuntimeError('Invalid actor_type {}'.format(type(actor_type)))

        if actor_type not in [ActorType.PROVIDER, ActorType.CONSUMER, ActorType.PROVIDER_CONSUMER]:
            raise RuntimeError('Invalid actor_type {}'.format(actor_type))

        _meta_object_expected = {}
        _verify_meta_data(meta_hash, meta_data, _meta_object_expected)

        if type(signature) != bytes:
            raise RuntimeError('Invalid type {} for signature'.format(type(signature)))

        if len(signature) != (32 + 32 + 1):
            raise RuntimeError('Invalid signature length {} - must be 65'.format(len(signature)))

        with self._db.begin() as txn:
            account = self._xbrnetwork.accounts[txn, member_id]
            member_adr = bytes(account.wallet_address)
            member_email = account.email

        try:
            signer_address = recover_eip712_market_join(chain_id, contract_adr, member_adr, block_number,
                                                        market_id.bytes, actor_type, meta_hash, signature)
        except Exception as e:
            self.log.failure()
            self.log.warn('EIP712 signature recovery failed (member_adr={member_adr}): {err}',
                          member_adr=member_adr,
                          err=str(e))
            raise ApplicationError('xbr.network.error.invalid_signature',
                                   'EIP712 signature recovery failed ({})'.format(e))

        if signer_address != member_adr:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, member_adr={member_adr}',
                          signer_address=signer_address,
                          member_adr=member_adr)
            raise ApplicationError('xbr.network.error.invalid_signature', 'EIP712 signature invalid')

        with self._db.begin() as txn:
            market = self._xbr.markets[txn, market_id]
            if market and market.owner == member_adr:
                raise ApplicationError("xbr.network.error.send_is_owner", 'Cannot join own market')

        # create new verification action ID and code
        vaction_oid = uuid.uuid4()
        created = time_ns()

        # generate a new verification code: this must only be sent via a 2nd channel!
        vaction_code = generate_activation_code()

        # send email with verification link, containing the verification code (email is the 2nd channel here)
        if not member_email.endswith('@nodomain'):  # filter CI/test scripts data and skip sending emails!
            self._mailgw.send_join_market_verification(member_email, vaction_oid, vaction_code)
        else:
            self.log.warn('Sending of email to "{member_email}" skipped - domain is filtered',
                          member_email=member_email)

        # data that is verified
        verified_data = {
            'created': created,
            'vcode': vaction_code,
            'member_adr': bytes(member_adr),
            'member_oid': member_id.bytes,
            'market_oid': market_id.bytes,
            'chain_id': chain_id,
            'joined': block_number,
            'contract_adr': contract_adr,
            'actor_type': actor_type,
            'meta_hash': meta_hash,
            'meta_data': bytes(meta_data),
            'signature': bytes(signature),
        }

        # store verification data in database ..
        with self._db.begin(write=True) as txn:
            vaction = VerifiedAction()
            vaction.oid = vaction_oid
            vaction.created = np.datetime64(created, 'ns')
            vaction.vtype = VerifiedAction.VERIFICATION_TYPE_JOIN_MARKET
            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_PENDING
            vaction.vcode = vaction_code
            vaction.verified_oid = member_id
            vaction.verified_data = verified_data

            self._xbrnetwork.verified_actions[txn, vaction.oid] = vaction

        # in addition to writing the vaction to the embedded database, also write the
        # pending verification to a local file
        self._save_verification_file(vaction.oid, 'join-market-email-verification', vaction.verified_data)

        # print "magic opening bracket" to log for automated testing (do not change the string!)
        self.log.info(_JOIN_MARKET_LOG_VERIFICATION_CODE_START)

        # print all information provided in verification email sent
        self.log.info(
            '>>>>> "created": {created}, "vaction_oid": "{vaction_oid}", "member_email": "{member_email}", "vaction_code": "{vaction_code}" <<<<<',
            created=created,
            member_email=member_email,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code)

        # print "magic closing bracket" to log for automated testing (do not change the string!)
        self.log.info(_JOIN_MARKET_LOG_VERIFICATION_CODE_END)

        # on-board member submission information
        request_submitted = {
            'created': created,
            'action': 'join_market',
            'vaction_oid': vaction_oid.bytes,
        }

        # enforce run-time ~100ms (info leakage / timing attack / DoS protection)
        await self._ensure_runtime(ts_started)

        return request_submitted

    async def verify_join_market(self, vaction_oid, vaction_code):
        """

        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        try:
            vaction_oid = uuid.UUID(bytes=vaction_oid)
        except ValueError:
            raise RuntimeError('Invalid vaction_oid "{}"'.format(vaction_oid))

        if type(vaction_code) != str:
            raise RuntimeError('Invalid vaction_code "{}"'.format(vaction_code))

        with self._db.begin(write=True) as txn:
            vaction = self._xbrnetwork.verified_actions[txn, vaction_oid]
            if not vaction:
                raise RuntimeError('no verification action {}'.format(vaction_oid))

            if vaction.vstatus != VerifiedAction.VERIFICATION_STATUS_PENDING:
                raise RuntimeError('verification action in state {}'.format(vaction.vstatus))

            if vaction.vcode != vaction_code:
                self.log.warn(
                    '{klass}.verify_login_member: invalid verification code "{vaction_code}" received in client login - expected "{vaction_code_expected}"',
                    klass=self.__class__.__name__,
                    vaction_code_expected=vaction.vcode,
                    vaction_code=vaction_code)
                raise RuntimeError('invalid verification code "{}"'.format(vaction_code))

            # ok, verification is valid! now apply the action being verified (here, "join market")
            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_VERIFIED

            if vaction.vtype == VerifiedAction.VERIFICATION_TYPE_JOIN_MARKET:
                self._xbrnetwork.verified_actions[txn, vaction_oid] = vaction
            else:
                raise RuntimeError('invalid verification type {}'.format(vaction.vtype))

            created = np.datetime64(vaction.verified_data['created'], 'ns')
            member_adr = vaction.verified_data['member_adr']
            member_oid = uuid.UUID(bytes=vaction.verified_data['member_oid'])
            market_oid = uuid.UUID(bytes=vaction.verified_data['market_oid'])

            actor = Actor()
            actor.timestamp = created
            actor.market = market_oid
            actor.actor = member_adr
            actor.actor_type = vaction.verified_data['actor_type']
            actor.joined = vaction.verified_data['joined']
            actor.meta_hash = vaction.verified_data['meta_hash']
            actor.meta_data = vaction.verified_data['meta_data']
            actor.signature = vaction.verified_data['signature']
            actor_key = (actor.market, actor.actor, actor.actor_type)

            self._xbr.actors[txn, actor_key] = actor
            self._xbr.idx_markets_by_actor[txn, (member_adr, created)] = market_oid

        # remove verification file
        try:
            self._remove_verification_file(vaction_oid, 'join-market-email-verification')
        except Exception as err:
            self.log.warn('error while removing verification file: {err}', err=err)

        # submit market join transaction to the blockchain
        try:
            member = vaction.verified_data['member_adr']
            joined = vaction.verified_data['joined']
            marketId = vaction.verified_data['market_oid']
            actorType = vaction.verified_data['actor_type']
            meta = vaction.verified_data['meta_hash']

            signature = vaction.verified_data['signature']
            txn_hash = await deferToThread(self._send_joinMarketFor, member, joined, marketId, actorType, meta,
                                           signature)
        except Exception as e:
            self.log.warn('Failed to submit _send_joinMarketFor: {err}', err=e)
            if isinstance(e, ValueError) and e.args[0]['message'].endswith("SENDER_IS_OWNER"):
                raise ApplicationError("xbr.network.error.sender_is_owner", "Cannot join own market")
            raise e
        else:
            # join-market verification information
            request_verified = {
                'created': int(created),
                'member_oid': member_oid.bytes,
                'market_oid': market_oid.bytes,
                'actor_type': actorType,
                'transaction': txn_hash,
            }
            return request_verified

    async def create_catalog(self, member_oid: uuid.UUID, catalog_oid: uuid.UUID, verifying_chain_id: int,
                             current_block_number: int, verifying_contract_adr: bytes, terms_hash: str, meta_hash: str,
                             meta_data: bytes, attributes: dict, signature: bytes):

        if not isinstance(member_oid, uuid.UUID):
            raise RuntimeError('member_oid must be UUID, was {}'.format(type(member_oid)))

        if not isinstance(catalog_oid, uuid.UUID):
            raise RuntimeError('catalog_oid must be UUID, was {}'.format(type(catalog_oid)))

        if type(verifying_chain_id) != int:
            raise RuntimeError('verifying_chain_id must be int, was "{}"'.format(type(verifying_chain_id)))

        if type(current_block_number) != int:
            raise RuntimeError('current_block_number must be int, was "{}"'.format(type(current_block_number)))

        if type(verifying_contract_adr) != bytes and len(verifying_contract_adr) != 20:
            raise RuntimeError('Invalid verifying_contract_adr "{!r}"'.format(verifying_contract_adr))

        if terms_hash and type(terms_hash) != str:
            raise RuntimeError('terms_hash must be str, was "{}"'.format(type(terms_hash)))

        if meta_hash and meta_data:
            _meta_object_expected = {}  # type: ignore
            _verify_meta_data(meta_hash, meta_data, _meta_object_expected)

        if attributes and type(attributes) != dict:
            raise RuntimeError('attributes must be dict, was "{}"'.format(type(attributes)))

        if type(signature) != bytes:
            raise RuntimeError('Invalid type {} for signature'.format(type(signature)))

        if len(signature) != (32 + 32 + 1):
            raise RuntimeError('Invalid signature length {} - must be 65'.format(len(signature)))

        with self._db.begin() as txn:
            account = self._xbrnetwork.accounts[txn, member_oid]
            member_adr = bytes(account.wallet_address)
            member_email = account.email

        try:
            signer_address = recover_eip712_catalog_create(verifying_chain_id, verifying_contract_adr, member_adr,
                                                           current_block_number, catalog_oid.bytes, terms_hash,
                                                           meta_hash, signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed (member_adr={}): {}', member_adr, str(e))
            raise ApplicationError('xbr.network.error.invalid_signature', f'EIP712 signature recovery failed ({e})')

        if member_adr != signer_address:
            self.log.warn('EIP712 signature invalid: signer_address={}, member_adr={}', signer_address, member_adr)
            raise ApplicationError('xbr.network.error.invalid_signature', 'EIP712 signature invalid')

        # create new verification action ID and code
        vaction_oid = uuid.uuid4()
        created = time_ns()

        # generate a new verification code: this must only be sent via a 2nd channel!
        vaction_code = generate_activation_code()

        # send email with verification link, containing the verification code (email is the 2nd channel here)
        if not member_email.endswith('@nodomain'):  # filter CI/test scripts data and skip sending emails!
            self._mailgw.send_join_market_verification(member_email, vaction_oid, vaction_code)
        else:
            self.log.warn('Sending of email to "{member_email}" skipped - domain is filtered',
                          member_email=member_email)

        should_upload = not member_email.endswith('@nodomain')
        result_hash = await self._upload_to_infura(meta_hash, meta_data, should_upload)
        assert result_hash == meta_hash

        # data that is verified
        verified_data = {
            'created': created,
            'vcode': vaction_code,
            'member_adr': bytes(member_adr),
            'member_oid': member_oid.bytes,
            'catalog_oid': catalog_oid.bytes,
            'chain_id': verifying_chain_id,
            'block_number': current_block_number,
            'contract_adr': verifying_contract_adr,
            'terms_hash': terms_hash,
            'meta_hash': meta_hash,
            'meta_data': meta_data,
            'signature': bytes(signature),
        }

        # store verification data in database ..
        with self._db.begin(write=True) as txn:
            vaction = VerifiedAction()
            vaction.oid = vaction_oid
            vaction.created = np.datetime64(created, 'ns')
            vaction.vtype = VerifiedAction.VERIFICATION_TYPE_CREATE_CATALOG
            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_PENDING
            vaction.vcode = vaction_code
            vaction.verified_oid = member_oid
            vaction.verified_data = verified_data

            self._xbrnetwork.verified_actions[txn, vaction.oid] = vaction

        # in addition to writing the vaction to the embedded database, also write the
        # pending verification to a local file
        self._save_verification_file(vaction.oid, 'create-catalog-email-verification', vaction.verified_data)

        # print "magic opening bracket" to log for automated testing (do not change the string!)
        self.log.info(_CREATE_CATALOG_LOG_VERIFICATION_CODE_START)

        # print all information provided in verification email sent
        self.log.info(
            '>>>>> "created": {created}, "vaction_oid": "{vaction_oid}", "member_email": "{member_email}", "vaction_code": "{vaction_code}" <<<<<',
            created=created,
            member_email=member_email,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code)

        # print "magic closing bracket" to log for automated testing (do not change the string!)
        self.log.info(_CREATE_CATALOG_LOG_VERIFICATION_CODE_END)

        # on-board member submission information
        request_submitted = {
            'created': created,
            'action': 'create_catalog',
            'vaction_oid': vaction_oid.bytes,
        }

        return request_submitted

    async def verify_create_catalog(self, vaction_oid, vaction_code):
        """

        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        try:
            vaction_oid = uuid.UUID(bytes=vaction_oid)
        except ValueError:
            raise RuntimeError('Invalid vaction_oid "{}"'.format(vaction_oid))

        if type(vaction_code) != str:
            raise RuntimeError('Invalid vaction_code "{}"'.format(vaction_code))

        with self._db.begin(write=True) as txn:
            vaction = self._xbrnetwork.verified_actions[txn, vaction_oid]
            if not vaction:
                raise RuntimeError('no verification action {}'.format(vaction_oid))

            if vaction.vstatus != VerifiedAction.VERIFICATION_STATUS_PENDING:
                raise RuntimeError('verification action in state {}'.format(vaction.vstatus))

            if vaction.vcode != vaction_code:
                self.log.warn(
                    '{klass}.verify_create_catalog: invalid verification code "{vaction_code}" received in catalog creation - expected "{vaction_code_expected}"',
                    klass=self.__class__.__name__,
                    vaction_code_expected=vaction.vcode,
                    vaction_code=vaction_code)
                raise RuntimeError('invalid verification code "{}"'.format(vaction_code))

            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_VERIFIED

            if vaction.vtype == VerifiedAction.VERIFICATION_TYPE_CREATE_CATALOG:
                self._xbrnetwork.verified_actions[txn, vaction_oid] = vaction
            else:
                raise RuntimeError('invalid verification type {}'.format(vaction.vtype))

        created = np.datetime64(vaction.verified_data['created'], 'ns')
        member_adr = vaction.verified_data['member_adr']
        member_oid = uuid.UUID(bytes=vaction.verified_data['member_oid'])
        catalog_oid = uuid.UUID(bytes=vaction.verified_data['catalog_oid'])

        catalog = Catalog()
        catalog.oid = catalog_oid
        catalog.timestamp = created
        catalog.owner = member_adr
        catalog.seq = vaction.verified_data['block_number']

        with self._db.begin(write=True) as txn:
            self._xbr.catalogs[txn, catalog.oid] = catalog
            self._xbr.idx_catalogs_by_owner[txn, (member_adr, created)] = member_oid

        try:
            self._remove_verification_file(vaction_oid, 'create-catalog-email-verification')
        except Exception as err:
            self.log.warn(f'error while removing verification file: {err}')

        # submit market join transaction to the blockchain
        try:
            member = vaction.verified_data['member_adr']
            created = vaction.verified_data['block_number']
            catalog_oid = vaction.verified_data['catalog_oid']
            terms_hash = vaction.verified_data['terms_hash']
            meta = vaction.verified_data['meta_hash']
            signature = vaction.verified_data['signature']

            txn_hash = await deferToThread(self._send_createCatalogFor, member, created, catalog_oid, terms_hash, meta,
                                           signature)
        except Exception as e:
            self.log.warn('Failed to submit _send_createCatalogFor: {err}', err=e)
            raise e

        # on-board member verification information
        request_verified = {
            'created': int(created),
            'member_oid': member_oid.bytes,
            'catalog_oid': catalog_oid,
            'transaction': txn_hash
        }
        return request_verified

    def get_catalog(self, catalog_oid, include_attributes):
        assert isinstance(catalog_oid, uuid.UUID), 'catalog_oid must be bytes[16], was "{}"'.format(catalog_oid)
        assert type(include_attributes), 'include_attributes must be bool, was {}'.format(type(include_attributes))

        with self._db.begin() as txn:
            catalog = self._xbr.catalogs[txn, catalog_oid]
            if not catalog:
                raise ApplicationError('crossbar.error.no_such_object', 'no catalog {}'.format(catalog_oid))

            return catalog

    def publish_api(self, member_oid, catalog_oid, api_oid, verifying_chain_id, current_block_number,
                    verifying_contract_adr, schema_hash, schema_data, meta_hash, meta_data, signature, attributes):

        if not isinstance(member_oid, uuid.UUID):
            raise RuntimeError('member_oid must be UUID, was {}'.format(type(member_oid)))

        if not isinstance(catalog_oid, uuid.UUID):
            raise RuntimeError('catalog_oid must be UUID, was {}'.format(type(catalog_oid)))

        if not isinstance(api_oid, uuid.UUID):
            raise RuntimeError('api_oid must be UUID, was {}'.format(type(api_oid)))

        if type(verifying_chain_id) != int:
            raise RuntimeError('verifying_chain_id must be int, was "{}"'.format(type(verifying_chain_id)))

        if type(current_block_number) != int:
            raise RuntimeError('current_block_number must be int, was "{}"'.format(type(current_block_number)))

        if type(verifying_contract_adr) != bytes and len(verifying_contract_adr) != 20:
            raise RuntimeError('Invalid verifying_contract_adr "{!r}"'.format(verifying_contract_adr))

        if schema_hash and type(schema_hash) != str:
            raise RuntimeError('schema_hash must be str, was "{}"'.format(type(schema_hash)))

        if meta_hash and type(meta_hash) != str:
            raise RuntimeError('meta_hash must be str, was "{}"'.format(type(meta_hash)))

        _meta_object_expected = {}  # type: ignore
        _verify_meta_data(schema_hash, schema_data, _meta_object_expected)

        _verify_meta_data(meta_hash, meta_data, _meta_object_expected)

        if attributes and type(attributes) != dict:
            raise RuntimeError('attributes must be dict, was "{}"'.format(type(attributes)))

        if type(signature) != bytes:
            raise RuntimeError('Invalid type {} for signature'.format(type(signature)))

        if len(signature) != (32 + 32 + 1):
            raise RuntimeError('Invalid signature length {} - must be 65'.format(len(signature)))

        with self._db.begin() as txn:
            account = self._xbrnetwork.accounts[txn, member_oid]
            member_adr = bytes(account.wallet_address)
            member_email = account.email

        try:
            signer_address = recover_eip712_api_publish(verifying_chain_id, verifying_contract_adr, member_adr,
                                                        current_block_number, catalog_oid.bytes, api_oid.bytes,
                                                        schema_hash, meta_hash, signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed (member_adr={}): {}', member_adr, str(e))
            raise ApplicationError('xbr.network.error.invalid_signature', f'EIP712 signature recovery failed ({e})')

        if member_adr != signer_address:
            self.log.warn('EIP712 signature invalid: signer_address={}, member_adr={}', signer_address, member_adr)
            raise ApplicationError('xbr.network.error.invalid_signature', 'EIP712 signature invalid')

        # create new verification action ID and code
        vaction_oid = uuid.uuid4()
        created = time_ns()

        # generate a new verification code: this must only be sent via a 2nd channel!
        vaction_code = generate_activation_code()

        # data that is verified
        verified_data = {
            'created': created,
            'vcode': vaction_code,
            'member_adr': bytes(member_adr),
            'member_oid': member_oid.bytes,
            'catalog_oid': catalog_oid.bytes,
            'api_oid': api_oid.bytes,
            'chain_id': verifying_chain_id,
            'block_number': current_block_number,
            'contract_adr': verifying_contract_adr,
            'schema_hash': schema_hash,
            'schema_data': bytes(schema_data),
            'meta_hash': meta_hash,
            'meta_data': bytes(meta_data),
            'signature': bytes(signature),
        }
        #
        # # store verification data in database ..
        with self._db.begin(write=True) as txn:
            vaction = VerifiedAction()
            vaction.oid = vaction_oid
            vaction.created = np.datetime64(created, 'ns')
            vaction.vtype = VerifiedAction.VERIFICATION_TYPE_CREATE_CATALOG
            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_PENDING
            vaction.vcode = vaction_code
            vaction.verified_oid = member_oid
            vaction.verified_data = verified_data

            self._xbrnetwork.verified_actions[txn, vaction.oid] = vaction

        # in addition to writing the vaction to the embedded database, also write the
        # pending verification to a local file
        self._save_verification_file(vaction.oid, 'publish-api-email-verification', vaction.verified_data)
        #
        # print "magic opening bracket" to log for automated testing (do not change the string!)
        self.log.info(_PUBLISH_API_LOG_VERIFICATION_CODE_START)

        # print all information provided in verification email sent
        self.log.info(
            '>>>>> "created": {created}, "vaction_oid": "{vaction_oid}", "member_email": "{member_email}", "vaction_code": "{vaction_code}" <<<<<',
            created=created,
            member_email=member_email,
            vaction_oid=vaction_oid,
            vaction_code=vaction_code)

        # print "magic closing bracket" to log for automated testing (do not change the string!)
        self.log.info(_PUBLISH_API_LOG_VERIFICATION_CODE_END)

        # on-board member submission information
        request_submitted = {
            'created': created,
            'action': 'publish_api',
            'vaction_oid': vaction_oid.bytes,
        }

        return request_submitted

    def verify_publish_api(self, vaction_oid, vaction_code):
        """

        :param vaction_oid:
        :param vaction_code:
        :return:
        """
        try:
            vaction_oid = uuid.UUID(bytes=vaction_oid)
        except ValueError:
            raise RuntimeError('Invalid vaction_oid "{}"'.format(vaction_oid))

        if type(vaction_code) != str:
            raise RuntimeError('Invalid vaction_code "{}"'.format(vaction_code))

        with self._db.begin(write=True) as txn:
            vaction = self._xbrnetwork.verified_actions[txn, vaction_oid]
            if not vaction:
                raise RuntimeError('no verification action {}'.format(vaction_oid))

            if vaction.vstatus != VerifiedAction.VERIFICATION_STATUS_PENDING:
                raise RuntimeError('verification action in state {}'.format(vaction.vstatus))

            if vaction.vcode != vaction_code:
                self.log.warn(
                    '{klass}.verify_publish_api: invalid verification code "{vaction_code}" received in api publishing - expected "{vaction_code_expected}"',
                    klass=self.__class__.__name__,
                    vaction_code_expected=vaction.vcode,
                    vaction_code=vaction_code)
                raise RuntimeError('invalid verification code "{}"'.format(vaction_code))

            vaction.vstatus = VerifiedAction.VERIFICATION_STATUS_VERIFIED

            if vaction.vtype == VerifiedAction.VERIFICATION_TYPE_PUBLISH_API:
                self._xbrnetwork.verified_actions[txn, vaction_oid] = vaction
            else:
                raise RuntimeError('invalid verification type {}'.format(vaction.vtype))

        created = np.datetime64(vaction.verified_data['created'], 'ns')
        member_adr = vaction.verified_data['member_adr']
        member_oid = uuid.UUID(bytes=vaction.verified_data['member_oid'])
        catalog_oid = uuid.UUID(bytes=vaction.verified_data['catalog_oid'])
        api_oid = uuid.UUID(bytes=vaction.verified_data['api_oid'])

        api = Api()
        api.oid = api_oid
        api.catalog_oid = catalog_oid
        api.owner = member_adr
        api.published = vaction.verified_data['block_number']
        api.timestamp = np.datetime64(time_ns(), 'ns')

        with self._db.begin(write=True) as txn:
            self._xbr.apis[txn, api_oid] = api
            self._xbr.idx_apis_by_catalog[txn, (catalog_oid.bytes, created)] = api_oid

        try:
            self._remove_verification_file(vaction_oid, 'publish-api-email-verification')
        except Exception as err:
            self.log.warn(f'error while removing verification file: {err}')

        # on-board member verification information
        request_verified = {
            'created': int(created),
            'member_oid': member_oid.bytes,
            'catalog_oid': catalog_oid.bytes,
            'api_oid': api_oid.bytes,
        }
        return request_verified

    def get_api(self, api_oid, include_attributes):
        assert isinstance(api_oid, uuid.UUID), 'api_oid must be UUID, was "{}"'.format(api_oid)
        assert type(include_attributes), 'include_attributes must be bool, was {}'.format(type(include_attributes))

        with self._db.begin() as txn:
            api = self._xbr.apis[txn, api_oid]
            if not api:
                raise ApplicationError('crossbar.error.no_such_object', 'no api {}'.format(api_oid))

            return api
