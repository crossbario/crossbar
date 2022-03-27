##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import os
import uuid
import time
import binascii
import threading
from collections.abc import Mapping
from pprint import pformat
from pathlib import Path

import requests
import numpy as np
import web3
import multihash
from hexbytes import HexBytes
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads import deferToThread

from txaio import make_logger, time_ns

import zlmdb
import cfxdb

from autobahn import wamp
from autobahn.wamp.exception import ApplicationError

from autobahn import xbr
from autobahn.xbr import unpack_uint256, pack_uint256, make_w3

from crossbar.node.worker import NativeWorkerProcess
from crossbar.worker.controller import WorkerController

from crossbar._util import hl, hlid, hlval, hlcontract
from crossbar.edge.worker.xbr import MarketMaker

__all__ = ('MarketplaceController', 'MarketplaceControllerProcess')


class MarketplaceControllerProcess(NativeWorkerProcess):

    TYPE = 'marketplace'
    LOGNAME = 'Marketplace'


class MarketplaceController(WorkerController):

    WORKER_TYPE = u'marketplace'
    WORKER_TITLE = u'Marketplace'

    STATUS_STARTING = 'starting'
    STATUS_RUNNING = 'running'
    STATUS_STOPPING = 'stopping'

    log = make_logger()

    def __init__(self, config=None, reactor=None, personality=None):
        # WorkerController derives of NativeProcess, which will set self._reactor
        WorkerController.__init__(self, config=config, reactor=reactor, personality=personality)

        worker_options_extra = dict(config.extra.extra)
        self._database_config = worker_options_extra['database']
        self._blockchain_config = worker_options_extra['blockchain']
        self._ipfs_files_directory = worker_options_extra.get('ipfs_files_directory', './.ipfs_files')

        # xbrmm worker status
        self._status = None

        # map of market makers by ID
        self._makers = {}
        self._maker_adr2id = {}

        # open xbrmm worker database, containing a replicate of xbr on-chain data (other than
        # channels, which are market specific and stored in the market maker database of the maker of that market)
        self._dbpath = os.path.abspath(
            self._database_config.get('dbpath', './.xbrmm-{}-db'.format(config.extra.worker)))
        self._db = zlmdb.Database(dbpath=self._dbpath,
                                  maxsize=self._database_config.get('maxsize', 2**30),
                                  readonly=False,
                                  sync=True)
        self._db.__enter__()

        # generic database object metadata
        self._meta = cfxdb.meta.Schema.attach(self._db)

        # xbr database schema
        self._xbr = cfxdb.xbr.Schema.attach(self._db)

        # xbr market maker schema
        self._xbrmm = cfxdb.xbrmm.Schema.attach(self._db)

        # event object too coordinate exit of blockchain monitor background check
        self._run_monitor = None

        # blockchain gateway configuration
        self._bc_gw_config = self._blockchain_config['gateway']
        self.log.info('Initializing Web3 from blockchain gateway configuration\n\n{gateway}\n',
                      gateway=pformat(self._bc_gw_config))
        self._w3 = make_w3(self._bc_gw_config)
        xbr.setProvider(self._w3)

        self._chain_id = self._blockchain_config.get('chain_id', 1)
        self.log.info('Using chain ID {chain_id}', chain_id=hlid(self._chain_id))

        # To be initiated once cbdir variable gets available
        self._ipfs_files_dir = os.path.join(config.extra.cbdir, self._ipfs_files_directory)

    @inlineCallbacks
    def onJoin(self, details, publish_ready=True):
        self.log.info(
            'XBR Markets Worker starting (realm={realm}, prefix="{prefix}", session={session}, authid={authid}, authrole={authrole})',
            realm=hlid(details.realm),
            prefix=hlid(self._uri_prefix),
            session=hlid(details.session),
            authid=hlid(details.authid),
            authrole=hlid(details.authrole))
        self.log.info('XBR Markets Worker configuration:\n\n{config}', config=pformat(self.config.extra))

        self._status = self.STATUS_STARTING

        yield WorkerController.onJoin(self, details, publish_ready=False)

        # any special session setup for the market maker goes here ..

        # start blockchain monitor is running on a background thread which exits once this gets False
        self._run_monitor = threading.Event()
        self._stop_monitor = False

        # FIXME: check self.xbr.blocks for latest block already processed
        # initially begin scanning the blockchain with this block, and subsequently scan from the last
        # processed and locally persisted block record in the database
        if 'from_block' in self._blockchain_config:
            scan_from_block = self._blockchain_config['from_block']
            self.log.info('Initial scanning of blockchain beginning with block {scan_from_block} from configuration',
                          scan_from_block=scan_from_block)
        else:
            scan_from_block = 1
            self.log.info('Initial scanning of blockchain from block 1 (!)')

        # monitor/pull blockchain from a background thread
        self._monitor_blockchain_thread = self._reactor.callInThread(self._monitor_blockchain, self._bc_gw_config,
                                                                     scan_from_block)
        self._status = self.STATUS_RUNNING

        yield self.publish_ready()

        self.log.info('XBR Markets Worker ready!')

    @inlineCallbacks
    def onLeave(self, details):
        """

        :param details:
        :return:
        """
        self.log.info('XBR Markets Worker shutting down ({market_cnt} markets to shutdown) ..',
                      market_cnt=len(self._makers))

        self._status = self.STATUS_STOPPING

        # shutdown each market ..
        makers = list(self._makers.values())
        for maker in makers:
            yield maker.stop()
            self.log.info('Market Maker "{maker_id}" stopped.', maker_id=hlid(maker._id))

        self._stop_monitor = True

        # stop blockchain monitoring background thread, possibly waking up
        # the thread from some blocking activity (like sleeping in a syscall)
        if not self._run_monitor.is_set():
            self._run_monitor.set()

        # make sure to join the background thread, so this main thread running
        # in the process exits - and thus the whole process
        if self._monitor_blockchain_thread:
            self._monitor_blockchain_thread.join()

        # disconnect from router
        self.disconnect()

        self._status = None

        self.log.info('XBR Markets Worker shutdown complete!')

    def _trigger_monitor_blockchain(self):
        self.log.info('Trigger (explicitly) the background blockchain monitor ..')
        self._run_monitor.set()
        self._run_monitor.clear()

    def _download_ipfs_file(self, file_hash):
        if not os.path.exists(self._ipfs_files_dir):
            Path(self._ipfs_files_dir).mkdir()

        file_path = os.path.join(self._ipfs_files_dir, file_hash)
        if os.path.exists(file_path):
            # If file exists in storage but not in db, then just add
            # a db entry.
            with self._db.begin(write=True) as txn:
                ipfs_file = self._xbrmm.ipfs_files[txn, file_hash]
                if not ipfs_file:
                    ipfs_file = cfxdb.xbrmm.IPFSFile()
                    ipfs_file.file_hash = file_hash
                    self._xbrmm.ipfs_files[txn, file_hash] = ipfs_file
        else:
            ipfs_file = cfxdb.xbrmm.IPFSFile()
            ipfs_file.file_hash = file_hash
            path = 'https://ipfs.infura.io:5001/api/v0/cat?arg={}'.format(file_hash)
            response = requests.get(path)
            if response.status_code == 200:
                with open(file_path, 'w') as file:
                    file.write(response.text)
                with self._db.begin(write=True) as txn:
                    self._xbrmm.ipfs_files[txn, file_hash] = ipfs_file
            else:
                ipfs_file.retries = ipfs_file.retries + 1
                ipfs_file.errored_at = np.datetime64(time_ns(), 'ns')
                with self._db.begin(write=True) as txn:
                    self._xbrmm.ipfs_files[txn, file_hash] = ipfs_file

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
            self.log.warn('_process_Market_ActorLeft not implemented')

        def _process_Market_ConsentSet(transactionHash, blockHash, args):
            # Event emitted when a consent is set
            # emit ConsentSet(member, updated, marketId, delegate, delegateType,
            #                 apiCatalog, consent, servicePrefix);
            self.log.info('{event}: processing event (tx_hash={tx_hash}, block_hash={block_hash}) ..',
                          event=hlcontract('XBRMarket.ConsentSet'),
                          tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()),
                          block_hash=hlid('0x' + binascii.b2a_hex(blockHash).decode()))

            catalog_oid = uuid.UUID(bytes=args.apiCatalog)
            member = uuid.UUID(bytes=args.member)
            delegate = args.delegate
            delegate_type = args.delegateType
            market_oid = uuid.UUID(bytes=args.marketId)
            with self._db.begin(write=True) as txn:
                consent = self._xbr.consents[txn, (catalog_oid, member, delegate, delegate_type, market_oid)]
                consent.synced = True

        def _process_Catalog_CatalogCreated(transactionHash, blockHash, args):
            # Event emitted when a new API catalog is created
            # emit CatalogCreated(catalogId, created, catalogSeq, owner, terms, meta);
            self.log.info('{event}: processing event (tx_hash={tx_hash}, block_hash={block_hash}) ..',
                          event=hlcontract('XBRCatalog.CatalogCreated'),
                          tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()),
                          block_hash=hlid('0x' + binascii.b2a_hex(blockHash).decode()))

            catalog_oid = uuid.UUID(bytes=args.catalogId)
            owner = bytes(HexBytes(args.owner))
            created = np.datetime64(time_ns(), 'ns')
            with self._db.begin(write=True) as txn:
                catalog = cfxdb.xbr.catalog.Catalog()
                catalog.oid = catalog_oid
                catalog.timestamp = created
                catalog.seq = args.catalogSeq
                catalog.owner = owner
                catalog.terms = args.terms
                catalog.meta = args.meta
                self._xbr.catalogs[txn, catalog_oid] = catalog

            deferToThread(self._download_ipfs_file, args.meta)

        def _process_Catalog_ApiPublished(transactionHash, blockHash, args):
            self.log.warn('_process_Catalog_ApiPublished not implemented')

        def _process_Channel_Opened(transactionHash, blockHash, args):
            # Event emitted when a new XBR data market has opened.
            # event Opened(XBRTypes.ChannelType ctype, bytes16 indexed marketId, bytes16 indexed channelId,
            #              address actor, address delegate, address marketmaker, address recipient,
            #              uint256 amount, bytes signature);
            self.log.info('{event}: processing event (tx_hash={tx_hash}, block_hash={block_hash}) ..',
                          event=hlcontract('XBRChannel.Opened'),
                          tx_hash=hlid('0x' + binascii.b2a_hex(transactionHash).decode()),
                          block_hash=hlid('0x' + binascii.b2a_hex(blockHash).decode()))

            channel_oid = uuid.UUID(bytes=args.channelId)
            marketmaker_adr = bytes(HexBytes(args.marketmaker))
            marketmaker_adr_str = web3.Web3.toChecksumAddress(marketmaker_adr)

            # we only persist data for xbr markets operated by one of the market makers we run in this worker
            if marketmaker_adr_str not in self._maker_adr2id or self._maker_adr2id[
                    marketmaker_adr_str] not in self._makers:
                self.log.info(
                    '{event}: skipping channel (channel {channel_oid} in market with market maker address {marketmaker_adr} is in for any market in this markets worker)',
                    event=hlcontract('XBRChannel.Opened'),
                    channel_oid=hlid(channel_oid),
                    marketmaker_adr=hlid(marketmaker_adr_str))
                return

            # prepare new channel data
            channel_type = int(args.ctype)
            market_oid = uuid.UUID(bytes=args.marketId)
            actor_adr = bytes(HexBytes(args.actor))
            delegate_adr = bytes(HexBytes(args.delegate))
            recipient_adr = bytes(HexBytes(args.recipient))
            amount = int(args.amount)
            # FIXME
            # signature = bytes(HexBytes(args.signature))
            # FIXME
            # member_oid = uuid.UUID()

            # get the market maker by address
            maker = self._makers[self._maker_adr2id[marketmaker_adr_str]]

            # the market maker specific embedded database and schema
            db = maker.db
            xbrmm = maker.schema

            # depending on channel type, different database schema classes and tables are used
            if channel_type == cfxdb.xbrmm.ChannelType.PAYMENT:
                channel = cfxdb.xbrmm.PaymentChannel()
                channels = xbrmm.payment_channels
                channels_by_delegate = xbrmm.idx_payment_channel_by_delegate
                balance = cfxdb.xbrmm.PaymentChannelBalance()
                balances = xbrmm.payment_balances
            elif channel_type == cfxdb.xbrmm.ChannelType.PAYING:
                channel = cfxdb.xbrmm.PayingChannel()
                channels = xbrmm.paying_channels
                channels_by_delegate = xbrmm.idx_paying_channel_by_delegate
                balance = cfxdb.xbrmm.PayingChannelBalance()
                balances = xbrmm.paying_balances
            else:
                assert False, 'should not arrive here'

            # fill in information for newly replicated channel
            channel.market_oid = market_oid
            # FIXME
            # channel.member_oid = member_oid
            channel.channel_oid = channel_oid
            channel.timestamp = np.datetime64(time_ns(), 'ns')
            # channel.open_at = None

            # FIXME: should read that from even args after deployment of
            # https://github.com/crossbario/xbr-protocol/pull/138
            channel.seq = 1
            channel.channel_type = channel_type
            channel.marketmaker = marketmaker_adr
            channel.actor = actor_adr
            channel.delegate = delegate_adr
            channel.recipient = recipient_adr
            channel.amount = amount

            # FIXME
            channel.timeout = 0
            channel.state = cfxdb.xbrmm.ChannelState.OPEN
            # FIXME
            # channel.open_sig = signature

            # create an off-chain balance record for the channel with remaining == initial amount
            balance.remaining = channel.amount
            # FIXME: should read that from even args after deployment of
            # https://github.com/crossbario/xbr-protocol/pull/138
            balance.seq = 1

            # now store the new channel and balance in the database
            stored = False
            cnt_channels_before = 0
            cnt_channels_by_delegate_before = 0
            cnt_channels_after = 0
            cnt_channels_by_delegate_after = 0
            with db.begin(write=True) as txn:
                if channels[txn, channel_oid]:
                    self.log.warn('{event}: channel already stored in database [channel_oid={channel_oid}]',
                                  event=hlcontract('XBRChannel.Opened'),
                                  channel_oid=hlid(channel_oid))
                else:
                    cnt_channels_before = channels.count(txn)
                    cnt_channels_by_delegate_before = channels_by_delegate.count(txn)

                    # store the channel along with the off-chain balance
                    channels[txn, channel_oid] = channel
                    balances[txn, channel_oid] = balance
                    stored = True

                    cnt_channels_after = channels.count(txn)
                    cnt_channels_by_delegate_after = channels_by_delegate.count(txn)

            self.log.info(
                '{event} DB result: stored={stored}, cnt_channels_before={cnt_channels_before}, cnt_channels_by_delegate_before={cnt_channels_by_delegate_before}, cnt_channels_after={cnt_channels_after}, cnt_channels_by_delegate_after={cnt_channels_by_delegate_after}',
                event=hlcontract('XBRChannel.Opened'),
                stored=hlval(stored),
                cnt_channels_before=hlval(cnt_channels_before),
                cnt_channels_by_delegate_before=hlval(cnt_channels_by_delegate_before),
                cnt_channels_after=hlval(cnt_channels_after),
                cnt_channels_by_delegate_after=hlval(cnt_channels_by_delegate_after))
            if stored:
                # FIXME: publish WAMP event
                self.log.info(
                    '{event}: new channel stored in database [actor_adr={actor_adr}, channel_type={channel_type}, market_oid={market_oid}, member_oid={member_oid}, channel_oid={channel_oid}]',
                    event=hlcontract('XBRChannel.Opened'),
                    market_oid=hlid(market_oid),
                    # FIXME
                    member_oid=hlid(None),
                    channel_oid=hlid(channel_oid),
                    actor_adr=hlid('0x' + binascii.b2a_hex(actor_adr).decode()),
                    channel_type=hlid(channel_type))

        def _process_Channel_Closing(transactionHash, blockHash, args):
            self.log.warn('_process_Channel_Closing not implemented')

        def _process_Channel_Closed(transactionHash, blockHash, args):
            self.log.warn('_process_Channel_Closed not implemented')

        # map XBR contract log event to event processing function
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
            (xbr.xbrmarket.events.ConsentSet, _process_Market_ConsentSet),
            (xbr.xbrcatalog.events.CatalogCreated, _process_Catalog_CatalogCreated),
            (xbr.xbrcatalog.events.ApiPublished, _process_Catalog_ApiPublished),
            (xbr.xbrchannel.events.Opened, _process_Channel_Opened),
            (xbr.xbrchannel.events.Closing, _process_Channel_Closing),
            (xbr.xbrchannel.events.Closed, _process_Channel_Closed),
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

        while not self._stop_monitor and not self._run_monitor.is_set():
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
        # filter by block, and XBR contract addresses
        # FIXME: potentially add filters for global data or market specific data for the markets started in this worker
        filter_params = {
            'address': [
                xbr.xbrtoken.address, xbr.xbrnetwork.address, xbr.xbrcatalog.address, xbr.xbrmarket.address,
                xbr.xbrchannel.address
            ],
            'fromBlock':
            block_number,
            'toBlock':
            block_number,
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

    @inlineCallbacks
    @wamp.register(None)
    def start_market_maker(self, maker_id, config, details=None):
        """
        Starts a XBR Market Maker providing services in a specific XBR market.
        """
        if type(maker_id) != str:
            emsg = 'maker_id has invalid type {}'.format(type(maker_id))
            raise ApplicationError('wamp.error.invalid_argument', emsg)

        if not isinstance(config, Mapping):
            emsg = 'maker_id has invalid type {}'.format(type(config))
            raise ApplicationError('wamp.error.invalid_argument', emsg)

        if maker_id in self._makers:
            emsg = 'could not start market maker: a market maker with ID "{}" is already running (or starting)'.format(
                maker_id)
            raise ApplicationError('crossbar.error.already_running', emsg)

        self.personality.check_market_maker(self.personality, config)

        self.log.info('XBR Market Maker "{maker_id}" starting with config:\n{config}',
                      maker_id=hlid(maker_id),
                      config=pformat(config))

        maker = MarketMaker(self, maker_id, config, self._db, self._ipfs_files_dir)
        self._makers[maker_id] = maker
        self._maker_adr2id[maker.address] = maker_id

        yield maker.start()

        status = yield maker.status()
        self.log.info('{msg}: {accounts} local accounts, current block number is {current_block_no}',
                      msg=hl('Blockchain status', color='green', bold=True),
                      current_block_no=hlid(status['current_block_no']),
                      accounts=hlid(len(status['accounts'])))

        started = {
            'id': maker_id,
            'address': maker.address,
        }
        self.publish(u'{}.on_maker_started'.format(self._uri_prefix), started)

        self.log.info(
            'XBR Market Maker "{maker_id}" (address {maker_adr}) started. Now running {maker_cnt} market makers in total in this worker component.',
            maker_id=maker_id,
            maker_adr=maker.address,
            maker_cnt=len(self._makers))

        returnValue(started)

    @inlineCallbacks
    @wamp.register(None)
    def stop_market_maker(self, maker_id, details=None):
        if type(maker_id) != str:
            emsg = 'maker_id has invalid type {}'.format(type(maker_id))
            raise ApplicationError('wamp.error.invalid_argument', emsg)

        if maker_id not in self._makers:
            emsg = 'could not stop market maker: no market maker with ID "{}" is currently running'.format(maker_id)
            raise ApplicationError('crossbar.error.already_running', emsg)

        yield self._makers[maker_id].stop()
        del self._makers[maker_id]
        self.log.info(
            'XBR Market Maker "{maker_id}" stopped. Now running {maker_cnt} market makers in total in this worker component.',
            maker_id=maker_id,
            maker_cnt=len(self._makers))

        stopped = {
            'id': maker_id,
        }
        self.publish(u'{}.on_maker_stopped'.format(self._uri_prefix), stopped)

        returnValue(stopped)
