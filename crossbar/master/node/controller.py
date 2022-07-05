###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import re
import os
import iso8601
import humanize
import uuid
import threading
import pprint
from datetime import datetime
from collections import OrderedDict
from pathlib import Path

import cbor2
import numpy as np

from autobahn import wamp, util
from autobahn.twisted.wamp import ApplicationSession
from autobahn.util import utcnow
from autobahn.wamp.types import RegisterOptions, CallDetails, PublishOptions
from autobahn.wamp.request import Registration

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread

import txaio
import treq
import zlmdb
from txaio import time_ns

from crossbar._util import hlid, hl, hlval, hltype
from crossbar.node.main import _get_versions
from crossbar.common import checkconfig
from crossbar.common.key import _read_release_key, _write_node_key, _parse_node_key

from cfxdb.globalschema import GlobalSchema
from cfxdb.mrealmschema import MrealmSchema
from crossbar.master.mrealm.mrealm import MrealmManager, ManagementRealm, Node
from crossbar.master.node.user import UserManager
from cfxdb.user import User, UserRole, UserMrealmRole
from cfxdb.usage import MasterNodeUsage
from cfxdb.log import MWorkerLog

_CFC_DOMAIN = 'crossbarfabriccenter.domain.'
_CFC_MREALM = 'crossbarfabriccenter.mrealm.'
_CFC_USER = 'crossbarfabriccenter.user.'


class DomainManager(object):
    """
    Global domain backend.
    """
    def __init__(self, session, db, schema):
        self.log = session.log
        self._db = db
        self._schema = schema

        self._session = session

    def register(self, session, prefix, options):
        return session.register(self, prefix=prefix, options=options)

    @wamp.register(None)
    def get_status(self, details=None):
        """
        Get global (domain) realm status.

        :procedure: ``crossbarfabriccenter.domain.get_status``

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallOptions`

        :returns: Global system status information.
        :rtype: dict
        """
        assert isinstance(details, CallDetails)

        self.log.debug('{klass}.get_status(details={details})', klass=self.__class__.__name__, details=details)

        now = utcnow()
        uptime_secs = (iso8601.parse_date(now) - iso8601.parse_date(self._session._started)).total_seconds()
        uptime_secs_str = humanize.naturaldelta(uptime_secs)
        res = {
            'type': 'domain',
            'realm': self._session._realm,
            'now': utcnow(),
            'started': self._session._started,
            'uptime': uptime_secs_str,
            'tick': self._session._tick
        }
        return res

    @wamp.register(None)
    def get_version(self, details=None):
        """
        Returns CFC software stack version information.

        :procedure: ``crossbarfabriccenter.domain.get_version``

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallOptions`

        :return: Information on software stack versions.
        :rtype: dict
        """
        assert isinstance(details, CallDetails)

        self.log.debug('{klass}.get_version(details={details})', klass=self.__class__.__name__, details=details)

        # FIXME
        from twisted.internet import reactor
        versions = _get_versions(reactor)

        return versions.marshal()

    @wamp.register(None)
    def get_license(self, details=None):
        """
        Returns CFC software stack license information.

        :procedure: ``crossbarfabriccenter.domain.get_license``

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallOptions`

        :return: License information, including enabled features and limits.
        :rtype: dict
        """
        assert isinstance(details, CallDetails)

        self.log.debug('{klass}.get_license(details={details})', klass=self.__class__.__name__, details=details)

        # FIXME: check blockchain for license information
        license = {
            'product': 'crossbar-free-tier',
            'description': 'crossbar free usage tier including 5 managed nodes.',
            'terms': 'https://crossbario.com/license',
            'features': {
                'xbr': False
            },
            'limits': {
                'concurrent-nodes': 5
            }
        }
        return license


class DomainController(ApplicationSession):
    """
    Main CFC backend for a domain (instance of CFC, all CFC nodes connected to one controller node / database).

    There is exactly one instance running per master node of a domain.
    """
    log = txaio.make_logger()

    def _initialize(self):
        # self.config.controller
        # self.config.shared

        # comes from "crossbar/master/node/config.json"
        assert self.config.extra
        cbdir = self.config.extra['cbdir']

        # Release (public) key
        self._release_pubkey_hex = _read_release_key()['hex']

        # FIXME: Node key
        self._node_key = None
        # self._node_key = nacl.signing.SigningKey(self._node_key_hex, encoder=nacl.encoding.HexEncoder)
        # self.config.controller.secmod[1]
        # self.config.controller.call()

        # Metering knobs - FIXME: read and honor all knobs
        meterurl = self.config.extra.get('metering', {}).get('submit', {}).get('url', '${CROSSBAR_METERING_URL}')
        self._meterurl = checkconfig.maybe_from_env('metering.submit.url', meterurl)

        # auto-create default management realm, auto-pair nodes to default mrealm from watching directories
        # for new node public keys. configuration example:
        #
        #       "auto_default_mrealm": {
        #           "enabled": true,
        #           "watch_to_pair": [],
        #           "write_pairing_file": true
        #        }
        #
        self._auto_default_mrealm = self.config.extra.get('auto_default_mrealm', False)

        # create database and attach tables to database slots
        #
        config = self.config.extra.get('database', {})

        dbpath = config.get('path', '.db-controller')
        assert type(dbpath) == str
        dbpath = os.path.join(cbdir, dbpath)

        maxsize = config.get('maxsize', 128 * 2**20)
        assert type(maxsize) == int
        # allow maxsize 128kiB to 128GiB
        assert maxsize >= 128 * 1024 and maxsize <= 128 * 2**30

        # setup global database and schema
        # self.db = zlmdb.Database(dbpath=dbpath, maxsize=maxsize, readonly=False, sync=True, context=self)
        self.db = zlmdb.Database.open(dbpath=dbpath, maxsize=maxsize, readonly=False, sync=True, context=self)
        self.db.__enter__()
        self.schema = GlobalSchema.attach(self.db)
        self.log.info('{func} {action} [dbpath={dbpath}, maxsize={maxsize}]',
                      func=hltype(self._initialize),
                      action=hlval('global database newly opened', color='green'),
                      dbpath=hlid(dbpath),
                      maxsize=hlid(maxsize))

    async def onJoin(self, details):

        self._initialize()

        # check if magic special builtin "superuser" exists
        #
        with self.db.begin(write=True) as txn:
            self._superuser_authid = 'superuser'
            self._superuser_oid = self.schema.idx_users_by_email[txn, self._superuser_authid]
            if not self._superuser_oid:
                self._superuser_oid = uuid.uuid4()
                user = User()
                user.oid = self._superuser_oid
                user.email = self._superuser_authid
                user.pubkey = None
                user.registered = datetime.utcnow()
                self.schema.users[txn, user.oid] = user
                self.log.info(
                    hl('SUPERUSER created and stored in database (oid={}, email={})'.format(user.oid, user.email),
                       color='green',
                       bold=True))
            else:
                self.log.info(
                    hl('SUPERUSER already exists in database (oid={})'.format(self._superuser_oid),
                       color='green',
                       bold=True))

        # check if default management realm exists
        #
        self._watch_and_pair_lc = None
        self._watch_and_pair_count = None
        self._default_mrealm_oid = None
        self._default_mrealm_enabled = self._auto_default_mrealm.get('enabled', False)
        if self._default_mrealm_enabled:
            self.log.info('{action}', action=hl('Default management realm enabled', color='green', bold=True))
        else:
            self.log.info('{action}', action=hl('Default management realm disabled', color='red', bold=True))
        if self._default_mrealm_enabled:
            # the default management realm (if exists) has always the name "default"!
            mrealm_name = 'default'

            with self.db.begin(write=True) as txn:
                self._default_mrealm_oid = self.schema.idx_mrealms_by_name[txn, mrealm_name]
                if self._default_mrealm_oid:
                    self.log.debug('ok, default management realm already exists ({oid})',
                                   oid=hlid(self._default_mrealm_oid))

                    # This should not happen - but better verify that the owner of the default management realm
                    # is the current superuser.
                    # FIXME: merely logging a warning is likely not enough to address this!
                    #
                    mrealm = self.schema.mrealms[txn, self._default_mrealm_oid]
                    if mrealm.owner != self._superuser_oid:
                        self.log.warn(
                            '\n\nWARNING: default management realm not owned by SUPERUSER! [owner={owner}, superuser={superuser}]\n\n',
                            superuser=hlid(self._superuser_oid),
                            owner=hlid(mrealm.owner))
                else:
                    # the OID of a newly created default management realm varies locally
                    self._default_mrealm_oid = uuid.uuid4()

                    new_mrealm = ManagementRealm()
                    new_mrealm.oid = self._default_mrealm_oid
                    new_mrealm.label = 'default mrealm'
                    new_mrealm.description = 'Default management realm (automatically pre-created)'
                    new_mrealm.tags = []
                    new_mrealm.name = mrealm_name
                    new_mrealm.created = datetime.utcnow()
                    new_mrealm.owner = self._superuser_oid
                    new_mrealm.cf_router = 'cfrouter1'
                    new_mrealm.cf_container = 'cfcontainer1'

                    # store new management realm
                    self.schema.mrealms[txn, new_mrealm.oid] = new_mrealm

                    # store roles for user that created the management realm
                    roles = UserMrealmRole([UserRole.OWNER, UserRole.ADMIN, UserRole.USER, UserRole.GUEST])
                    self.schema.users_mrealm_roles[txn, (self._superuser_oid, new_mrealm.oid)] = roles

                    self.log.info('{action} [oid={oid}]',
                                  action=hl('Default management realm created', color='red', bold=True),
                                  oid=hlid(new_mrealm.oid))

            self._watch_to_pair = self._auto_default_mrealm.get('watch_to_pair', None)
            if self._watch_to_pair:
                self.log.info('{action}', action=hl('Watch-to-pair enabled', color='green', bold=True))
            else:
                self.log.info('{action}', action=hl('Watch-to-pair disabled', color='red', bold=True))
            if self._watch_to_pair:
                self._watch_to_pair = checkconfig.maybe_from_env('auto_default_mrealm.watch_to_pair',
                                                                 self._watch_to_pair,
                                                                 hide_value=False)
                if self._watch_to_pair:
                    self._watch_to_pair = Path(self._watch_to_pair)
                if self._watch_to_pair and self._watch_to_pair.is_dir():
                    node_dir_pat = self._auto_default_mrealm.get('watch_to_pair_pattern', None)
                    if node_dir_pat:
                        node_dir_pat = re.compile(node_dir_pat)

                    # FIXME: read from config
                    follow_symlinks = True

                    @inlineCallbacks
                    def watch_and_pair():
                        self.log.debug('{klass}::watch_and_pair[counter={cnt}, watch_to_pair="{watch_to_pair}"]',
                                       cnt=hlval(self._watch_and_pair_count),
                                       watch_to_pair=self._watch_to_pair,
                                       klass=self.__class__.__name__)
                        try:
                            self._watch_and_pair_count += 1

                            if node_dir_pat:
                                node_dirs = [
                                    x.name for x in os.scandir(self._watch_to_pair)
                                    if x.is_dir(follow_symlinks=follow_symlinks) and node_dir_pat.match(x.name)
                                ]
                            else:
                                node_dirs = [
                                    x.name for x in os.scandir(self._watch_to_pair)
                                    if x.is_dir(follow_symlinks=follow_symlinks)
                                ]

                            pubkeys = []
                            for node_dir in node_dirs:
                                # r = root, d = directories, f = files
                                for r, d, f in os.walk(os.path.join(self._watch_to_pair, node_dir)):
                                    for file in f:
                                        if file == 'key.pub':
                                            node_key_file = os.path.join(r, file)
                                            if os.path.isfile(node_key_file):
                                                node_key_tags = _parse_node_key(node_key_file)
                                                node_key_hex = node_key_tags['public-key-ed25519']
                                                node_id = node_key_tags.get('node-authid', None)
                                                cluster_ip = node_key_tags.get('node-cluster-ip', None)
                                                pubkeys.append((r, node_key_hex, node_id, cluster_ip))

                            self.log.debug(
                                '{klass}::watch_and_pair: found {cnt} directories (matching), with {cntk} node keys scanned ..',
                                cnt=hl(len(node_dirs)),
                                cntk=hl(len(pubkeys)),
                                klass=self.__class__.__name__)

                            if pubkeys:
                                # determine actually new pubkeys
                                new_pubkeys = []
                                with self.db.begin() as txn:
                                    for cbdir, pubkey, node_id, cluster_ip in pubkeys:
                                        node_oid = self.schema.idx_nodes_by_pubkey[txn, pubkey]
                                        if not node_oid:
                                            new_pubkeys.append((cbdir, pubkey, node_id, cluster_ip))
                                        else:
                                            node = self.schema.nodes[txn, node_oid]
                                            self.log.debug(
                                                '{klass}::watch_and_pair: node with pubkey {pubkey} already paired as node {node} to mrealm {mrealm}',
                                                klass=self.__class__.__name__,
                                                pubkey=hlid(pubkey),
                                                node=hlid(node.oid),
                                                mrealm=hlid(node.mrealm_oid))

                                self.log.debug(
                                    '{klass}::watch_and_pair: scanned ({count}) directory "{watch_to_pair}" for node auto-pairing, found {cnt_new_keys} new (in {cnt_keys} total) keys',
                                    count=hlval(self._watch_and_pair_count),
                                    watch_to_pair=hlid(self._watch_to_pair),
                                    cnt_keys=hlval(len(pubkeys)),
                                    cnt_new_keys=hlval(len(new_pubkeys)),
                                    klass=self.__class__.__name__)

                                # store all new pubkeys
                                for cbdir, pubkey, node_id, cluster_ip in new_pubkeys:
                                    node = Node()
                                    node.oid = uuid.uuid4()
                                    node.pubkey = pubkey
                                    node.cluster_ip = cluster_ip

                                    # auto-pair newly discovered node to the default management realm, and owned by superuser
                                    node.owner_oid = self._superuser_oid
                                    node.mrealm_oid = self._default_mrealm_oid
                                    if node_id:
                                        node.authid = node_id
                                    else:
                                        node.authid = 'node-{}'.format(str(node.oid)[:8])
                                    node.authextra = {
                                        'node_oid': str(node.oid),
                                        'cluster_ip': cluster_ip,
                                        'mrealm_oid': str(node.mrealm_oid),
                                    }

                                    # store paired node in database
                                    with self.db.begin(write=True) as txn:
                                        self.schema.nodes[txn, node.oid] = node

                                    if self._auto_default_mrealm.get('write_pairing_file', False):
                                        management_url = self._auto_default_mrealm.get('management_url', None)
                                        if management_url:
                                            management_url = checkconfig.maybe_from_env(
                                                'auto_default_mrealm.management_url', management_url, hide_value=False)

                                        activation_code = None
                                        if self._auto_default_mrealm.get('include_activation_code', False):
                                            activation_code = util.generate_activation_code()
                                            # FIXME: store activation & check later

                                        activation_file = os.path.join(cbdir, 'key.activate')
                                        if not os.path.exists(activation_file):
                                            file_tags = OrderedDict([
                                                ('created-at', utcnow()),
                                                ('management-url', management_url or 'wss://master.xbr.network/ws'),
                                                ('management-realm', 'default'),
                                                ('management-realm-oid', str(node.mrealm_oid)),
                                                ('node-oid', str(node.oid)),
                                                ('node-cluster-ip', node.cluster_ip),
                                                ('node-authid', str(node.authid)),
                                                ('activation-code', activation_code),
                                                ('public-key-ed25519', pubkey),
                                            ])
                                            file_msg = 'Crossbar.io node activation\n\n'
                                            try:
                                                _write_node_key(activation_file, file_tags, file_msg)
                                            except OSError as e:
                                                self.log.warn(
                                                    '{klass}::watch_and_pair: failed to write {action} to {activation_file} ({err})',
                                                    klass=self.__class__.__name__,
                                                    action=hl('Node activation file', color='red', bold=True),
                                                    activation_file=hlval(activation_file),
                                                    err=str(e))
                                            else:
                                                self.log.info(
                                                    '{klass}::watch_and_pair: {action} written to {activation_file}',
                                                    klass=self.__class__.__name__,
                                                    action=hl('Node activation file', color='red', bold=True),
                                                    activation_file=hlval(activation_file))
                                        else:
                                            self.log.warn(
                                                '{klass}::watch_and_pair: skipped writing {action} to {activation_file} (path already exists)',
                                                klass=self.__class__.__name__,
                                                action=hl('Node activation file', color='red', bold=True),
                                                activation_file=hlval(activation_file))

                                    topic = 'crossbarfabriccenter.mrealm.on_node_paired'
                                    payload = node.marshal()
                                    yield self.publish(topic, payload, options=PublishOptions(acknowledge=True))

                                    self.log.info(
                                        '{klass}::watch_and_pair: {action} with pubkey={pubkey}, oid={node_oid}, authid={authid} to default management realm {mrealm}!',
                                        klass=self.__class__.__name__,
                                        action=hl('Auto-paired node', color='red', bold=True),
                                        node_oid=hlid(node.oid),
                                        authid=hlid(node.authid),
                                        pubkey=hlval(node.pubkey),
                                        mrealm=hlid(node.mrealm_oid))
                            else:
                                self.log.debug(
                                    '{klass}::watch_and_pair: scanned ({count}) directory "{watch_to_pair}" for node auto-pairing: no nodes found',
                                    klass=self.__class__.__name__,
                                    count=hlval(self._watch_and_pair_count),
                                    watch_to_pair=hlid(self._watch_to_pair))
                        except:
                            self.log.failure()

                    self._watch_and_pair_lc = LoopingCall(watch_and_pair)
                    self._watch_and_pair_count = 0
                    self._watch_and_pair_lc.start(10)
                else:
                    if self._watch_to_pair:
                        self.log.warn('skipping to watch "{watch_to_pair}" for node auto-pairing - not a directory!',
                                      watch_to_pair=self._watch_to_pair.absolute())
                    else:
                        self.log.warn('skipping to watch for node auto-pairing - no directory configured!')

        # initialize management backends
        #
        self._domain_mgr = DomainManager(self, self.db, self.schema)
        self._user_mgr = UserManager(self, self.db, self.schema)
        self._mrealm_mgr = MrealmManager(self, self.db, self.schema)

        domains = (
            (_CFC_DOMAIN, self._domain_mgr.register),
            (_CFC_USER, self._user_mgr.register),
            (_CFC_MREALM, self._mrealm_mgr.register),
        )  # yapf: disable
        for topic, procedure in domains:
            results = await procedure(self, prefix=topic, options=RegisterOptions(details_arg='details'))
            for reg in results:
                if type(reg) == Registration:
                    self.log.debug('Registered CFC API <{proc}>', proc=reg.procedure)
                else:
                    self.log.error('Error: <{}>'.format(reg.value.args[0]))

        # start master heartbeat loop ..
        #
        self._tick = 1

        @inlineCallbacks
        def tick():
            # process regular master activities
            started = time_ns()

            # watch master database fill grade
            dbstats = self.db.stats()
            free = dbstats['free']
            used = dbstats['current_size']
            if free < 0.01:
                self.log.error('Global master database full! Initiating EMERGENCY SHUTDOWN .. [{free}% free]',
                               free=round(free * 100., 2))

                # if we don't have at least 1% free space, immediately shutdown the whole node so we don't
                # run into "db full" later possibly half way through the body of a management procedure
                yield self.config.controller.call('crossbar.shutdown')
            elif free < 0.1:
                self.log.warn('Global master database almost full: only {free}% free space left!',
                              free=round(free * 100., 2))

            # >>> BEGIN of master heartbeat loop tasks

            # FIXME: tried to open same dbpath "/home/oberstet/scm/typedefint/crossbar-cluster/.recordevolution/master/.crossbar/.db-mrealm-659f476d-c320-48c7-825b-d27efdfde8e8" twice within same process: cannot open database for <zlmdb._database.Database object at 0x7ffa474cf8b0> (PID 98672, Context <crossbar.master.node.controller.DomainController object at 0x7ffa47511f70>), already opened in <zlmdb._database.Database object at 0x7ffa474b6af0> (PID 98672, Context <crossbar.master.node.controller.DomainController object at 0x7ffa47511f70>)
            if False:
                # 1) aggregate and store usage metering records
                cnt_new = None
                if True:
                    try:
                        cnt_new = yield self._do_metering(started)
                    except:
                        self.log.failure()

                # 2) submit usage metering records to metering service
                if self._meterurl:
                    if cnt_new:
                        try:
                            yield self._submit_metering(started)
                        except:
                            self.log.failure()
                else:
                    self.log.warn('Skipping to submit metering records - no metering URL set!')

            # >>> END of master heartbeat loop tasks

            # publish master heartbeat
            ticked = {'now': utcnow(), 'tick': self._tick}
            yield self.publish('{}on_tick'.format(_CFC_DOMAIN), ticked, options=PublishOptions(acknowledge=True))

            # master heartbeat loop finished!
            duration = int(round((time_ns() - started) / 1000000.))
            if duration > 500:
                self.log.warn('Master heartbeat loop iteration {tick} finished: excessive run-time of {duration} ms!',
                              tick=self._tick,
                              duration=duration)
            self.log.debug(
                'Master heartbeat loop iteration {tick} finished in {duration} ms (database {used} used, {free}% free)',
                tick=self._tick,
                free=round(free * 100., 2),
                used=humanize.naturalsize(used),
                duration=duration)

            # set next master heartbeat loop iteration sequence number
            self._tick += 1

        # FIXME: make this configurable from master node config
        master_tick_period = 300
        c = LoopingCall(tick)
        c.start(master_tick_period)
        self.log.debug('Master heartbeat loop started .. [period={period} secs]', period=master_tick_period)

        # note status started
        #
        self._started = utcnow()
        self.log.debug('Domain controller ready (realm="{realm}")!', realm=hlid(self._realm))

    def _first_metering(self, mrealm_id):
        """
        Determine timestamp of first node heartbeat from any node of a given management realm.

        :param mrealm_id:
        :return:
        """
        dbpath = os.path.join(self.config.extra['cbdir'], '.db-mrealm-{}'.format(mrealm_id))
        # db = zlmdb.Database(dbpath=dbpath, readonly=False, context=self)
        db = zlmdb.Database.open(dbpath=dbpath, readonly=False, context=self)
        schema = MrealmSchema.attach(db)

        with self.db.begin() as txn:
            with db.begin() as txn2:
                for (ts, node_id) in schema.mnode_logs.select(txn2, reverse=False, return_values=False):
                    node = self.schema.nodes[txn, node_id]
                    if node and node.mrealm_oid == mrealm_id:
                        return ts

    def _agg_metering_mnode_logs(self, from_ts, until_ts, mrealm_id, by_node=False):
        """
        Aggregate raw managed node and worker logs and store usage metering records.

        Note: This is run on a background thread!

        :param from_ts:
        :param until_ts:
        :param mrealm_id:
        :param by_node:
        :return:
        """

        dbpath = os.path.join(self.config.extra['cbdir'], '.db-mrealm-{}'.format(mrealm_id))
        # db = zlmdb.Database(dbpath=dbpath, readonly=False, context=self)
        db = zlmdb.Database.open(dbpath=dbpath, readonly=False, context=self)
        schema = MrealmSchema.attach(db)

        if by_node:
            # compute aggregate sum grouped by node_id
            res = {}
            with db.begin() as txn:
                for (ts, node_id) in schema.mnode_logs.select(txn,
                                                              from_key=(from_ts, uuid.UUID(bytes=b'\x00' * 16)),
                                                              to_key=(until_ts, uuid.UUID(bytes=b'\xff' * 16)),
                                                              return_values=False,
                                                              reverse=False):

                    rec = schema.mnode_logs[txn, (ts, node_id)]

                    if node_id not in res:
                        res[node_id] = {
                            'count': 0,
                            'nodes': 0,
                            'routers': 0,
                            'containers': 0,
                            'guests': 0,
                            'proxies': 0,
                            'marketmakers': 0,
                            'hostmonitors': 0,
                            'controllers': 0,
                        }

                    res[node_id]['count'] += 1
                    res[node_id]['nodes'] += rec.period
                    res[node_id]['routers'] += rec.routers * rec.period
                    res[node_id]['containers'] += rec.containers * rec.period
                    res[node_id]['guests'] += rec.guests * rec.period
                    res[node_id]['proxies'] += rec.proxies * rec.period
                    res[node_id]['marketmakers'] += rec.marketmakers * rec.period
                    res[node_id]['hostmonitors'] += rec.hostmonitors * rec.period
                    res[node_id]['controllers'] += rec.controllers * rec.period

        else:
            # compute aggregate sum
            res = {
                'count': 0,
                'nodes': 0,
                'routers': 0,
                'containers': 0,
                'guests': 0,
                'proxies': 0,
                'marketmakers': 0,
                'hostmonitors': 0,
                'controllers': 0,
            }
            nodes = set()
            with db.begin() as txn:
                for (ts, node_id) in schema.mnode_logs.select(txn,
                                                              from_key=(from_ts, uuid.UUID(bytes=b'\x00' * 16)),
                                                              to_key=(until_ts, uuid.UUID(bytes=b'\xff' * 16)),
                                                              return_values=False,
                                                              reverse=False):

                    rec = schema.mnode_logs[txn, (ts, node_id)]

                    if node_id not in nodes:
                        nodes.add(node_id)

                    res['count'] += 1
                    res['nodes'] += rec.period
                    res['routers'] += rec.routers * rec.period
                    res['containers'] += rec.containers * rec.period
                    res['guests'] += rec.guests * rec.period
                    res['proxies'] += rec.proxies * rec.period
                    res['marketmakers'] += rec.marketmakers * rec.period
                    res['hostmonitors'] += rec.hostmonitors * rec.period
                    res['controllers'] += rec.controllers * rec.period

        self.log.debug(
            '  Metering: aggregated node logs metering records on thread {thread_id} [mrealm_id={mrealm_id}, from_ts={from_ts}, until_ts={until_ts}]:\n{res}',
            mrealm_id=mrealm_id,
            from_ts=from_ts,
            until_ts=until_ts,
            thread_id=threading.get_ident(),
            res=pprint.pformat(res))

        return res

    def _agg_metering_mworker_logs(self, from_ts, until_ts, mrealm_id):
        """
        Aggregate raw managed node and worker logs and store usage metering records.

        Note: This is run on a background thread!

        :param from_ts:
        :param until_ts:
        :param mrealm_id:
        :param by_node:
        :return:
        """

        dbpath = os.path.join(self.config.extra['cbdir'], '.db-mrealm-{}'.format(mrealm_id))
        # db = zlmdb.Database(dbpath=dbpath, readonly=False, context=self)
        db = zlmdb.Database.open(dbpath=dbpath, readonly=False, context=self)
        schema = MrealmSchema.attach(db)

        # compute aggregate sum
        res = {
            'count': 0,
            'total': 0,
            'controllers': 0,
            'hostmonitors': 0,
            'routers': 0,
            'containers': 0,
            'guests': 0,
            'proxies': 0,
            'marketmakers': 0,
            'sessions': 0,
            'msgs_call': 0,
            'msgs_yield': 0,
            'msgs_invocation': 0,
            'msgs_result': 0,
            'msgs_error': 0,
            'msgs_publish': 0,
            'msgs_published': 0,
            'msgs_event': 0,
            'msgs_register': 0,
            'msgs_registered': 0,
            'msgs_subscribe': 0,
            'msgs_subscribed': 0,
        }
        wres = {}
        nodes = set()
        with db.begin() as txn:
            # go over all worker heartbeat records in given time interval ..
            for (ts, node_id,
                 worker_id) in schema.mworker_logs.select(txn,
                                                          from_key=(from_ts, uuid.UUID(bytes=b'\x00' * 16), ''),
                                                          to_key=(until_ts, uuid.UUID(bytes=b'\xff' * 16), ''),
                                                          return_values=False,
                                                          reverse=False):

                rec = schema.mworker_logs[txn, (ts, node_id, worker_id)]

                assert rec.period

                # set of nodes we encountered in heartbeats in the time interval
                if node_id not in nodes:
                    nodes.add(node_id)

                # type name (str) of the worker
                worker_type = MWorkerLog.WORKER_TYPENAMES[rec.type]

                # increment used "worker seconds"
                # FIXME: cleanup this hack ..
                if worker_type.endswith('y'):
                    # proxy -> proxies
                    res['{}ies'.format(worker_type[:-1])] += rec.period
                else:
                    res['{}s'.format(worker_type)] += rec.period

                # increment processed records
                res['count'] += 1

                # for workers of type "router", we compute additional statistics:
                if worker_type == 'router':
                    wkey = (node_id, worker_id)
                    if wkey not in wres:
                        wres[wkey] = {
                            # session seconds
                            'sessions': 0,

                            # minimum number of WAMP messages per type
                            'msgs_call_min': 0,
                            'msgs_yield_min': 0,
                            'msgs_invocation_min': 0,
                            'msgs_result_min': 0,
                            'msgs_error_min': 0,
                            'msgs_publish_min': 0,
                            'msgs_published_min': 0,
                            'msgs_event_min': 0,
                            'msgs_register_min': 0,
                            'msgs_registered_min': 0,
                            'msgs_subscribe_min': 0,
                            'msgs_subscribed_min': 0,

                            # maximum number of WAMP messages per type
                            'msgs_call_max': 0,
                            'msgs_yield_max': 0,
                            'msgs_invocation_max': 0,
                            'msgs_result_max': 0,
                            'msgs_error_max': 0,
                            'msgs_publish_max': 0,
                            'msgs_published_max': 0,
                            'msgs_event_max': 0,
                            'msgs_register_max': 0,
                            'msgs_registered_max': 0,
                            'msgs_subscribe_max': 0,
                            'msgs_subscribed_max': 0,
                        }

                    # increment used "session seconds" (seconds of connected clients)
                    wres[wkey]['sessions'] += rec.router_sessions * rec.period

                    if rec.recv_call > wres[wkey]['msgs_call_max']:
                        wres[wkey]['msgs_call_max'] = rec.recv_call
                    if not wres[wkey]['msgs_call_min'] or rec.recv_call < wres[wkey]['msgs_call_min']:
                        wres[wkey]['msgs_call_min'] = rec.recv_call

                    if rec.recv_yield > wres[wkey]['msgs_yield_max']:
                        wres[wkey]['msgs_yield_max'] = rec.recv_yield
                    if not wres[wkey]['msgs_yield_min'] or rec.recv_yield < wres[wkey]['msgs_yield_min']:
                        wres[wkey]['msgs_yield_min'] = rec.recv_yield

                    if rec.sent_invocation > wres[wkey]['msgs_invocation_max']:
                        wres[wkey]['msgs_invocation_max'] = rec.sent_invocation
                    if not wres[wkey]['msgs_invocation_min'] or rec.sent_invocation < wres[wkey]['msgs_invocation_min']:
                        wres[wkey]['msgs_invocation_min'] = rec.sent_invocation

                    # FIXME
                    # if rec.sent_error > res[wkey]['msgs_error_max']:
                    #     res[wkey]['msgs_error_max'] = rec.sent_error
                    # if not res[wkey]['msgs_error_min'] or rec.sent_error < res[wkey]['msgs_error_min']:
                    #     res[wkey]['msgs_error_min'] = rec.sent_error

                    if rec.sent_result > wres[wkey]['msgs_result_max']:
                        wres[wkey]['msgs_result_max'] = rec.sent_result
                    if not wres[wkey]['msgs_result_min'] or rec.sent_result < wres[wkey]['msgs_result_min']:
                        wres[wkey]['msgs_result_min'] = rec.sent_result

                    if rec.recv_publish > wres[wkey]['msgs_publish_max']:
                        wres[wkey]['msgs_publish_max'] = rec.recv_publish
                    if not wres[wkey]['msgs_publish_min'] or rec.recv_publish < wres[wkey]['msgs_publish_min']:
                        wres[wkey]['msgs_publish_min'] = rec.recv_publish

                    if rec.sent_published > wres[wkey]['msgs_published_max']:
                        wres[wkey]['msgs_published_max'] = rec.sent_published
                    if not wres[wkey]['msgs_published_min'] or rec.sent_published < wres[wkey]['msgs_published_min']:
                        wres[wkey]['msgs_published_min'] = rec.sent_published

                    if rec.sent_event > wres[wkey]['msgs_event_max']:
                        wres[wkey]['msgs_event_max'] = rec.sent_event
                    if not wres[wkey]['msgs_event_min'] or rec.sent_event < wres[wkey]['msgs_event_min']:
                        wres[wkey]['msgs_event_min'] = rec.sent_event

                    if rec.recv_register > wres[wkey]['msgs_register_max']:
                        wres[wkey]['msgs_register_max'] = rec.recv_register
                    if not wres[wkey]['msgs_register_min'] or rec.recv_register < wres[wkey]['msgs_register_min']:
                        wres[wkey]['msgs_register_min'] = rec.recv_register

                    if rec.sent_registered > wres[wkey]['msgs_registered_max']:
                        wres[wkey]['msgs_registered_max'] = rec.sent_registered
                    if not wres[wkey]['msgs_registered_min'] or rec.sent_registered < wres[wkey]['msgs_registered_min']:
                        wres[wkey]['msgs_registered_min'] = rec.sent_registered

                    if rec.recv_subscribe > wres[wkey]['msgs_subscribe_max']:
                        wres[wkey]['msgs_subscribe_max'] = rec.recv_subscribe
                    if not wres[wkey]['msgs_subscribe_min'] or rec.recv_subscribe < wres[wkey]['msgs_subscribe_min']:
                        wres[wkey]['msgs_subscribe_min'] = rec.recv_subscribe

                    if rec.sent_subscribed > wres[wkey]['msgs_subscribed_max']:
                        wres[wkey]['msgs_subscribed_max'] = rec.sent_subscribed
                    if not wres[wkey]['msgs_subscribed_min'] or rec.sent_subscribed < wres[wkey]['msgs_subscribed_min']:
                        wres[wkey]['msgs_subscribed_min'] = rec.sent_subscribed

        res['nodes'] = len(nodes)

        for wkey in wres:
            res['sessions'] += wres[wkey]['sessions']
            res['msgs_call'] += wres[wkey]['msgs_call_max'] - wres[wkey]['msgs_call_min']
            res['msgs_yield'] += wres[wkey]['msgs_yield_max'] - wres[wkey]['msgs_yield_min']
            res['msgs_invocation'] += wres[wkey]['msgs_invocation_max'] - wres[wkey]['msgs_invocation_min']
            res['msgs_result'] += wres[wkey]['msgs_result_max'] - wres[wkey]['msgs_result_min']
            res['msgs_error'] += wres[wkey]['msgs_error_max'] - wres[wkey]['msgs_error_min']
            res['msgs_publish'] += wres[wkey]['msgs_publish_max'] - wres[wkey]['msgs_publish_min']
            res['msgs_published'] += wres[wkey]['msgs_published_max'] - wres[wkey]['msgs_published_min']
            res['msgs_event'] += wres[wkey]['msgs_event_max'] - wres[wkey]['msgs_event_min']
            res['msgs_register'] += wres[wkey]['msgs_register_max'] - wres[wkey]['msgs_register_min']
            res['msgs_registered'] += wres[wkey]['msgs_registered_max'] - wres[wkey]['msgs_registered_min']
            res['msgs_subscribe'] += wres[wkey]['msgs_subscribe_max'] - wres[wkey]['msgs_subscribe_min']
            res['msgs_subscribed'] += wres[wkey]['msgs_subscribed_max'] - wres[wkey]['msgs_subscribed_min']

        self.log.debug(
            '  Metering: aggregated {cnt_records} records from mworker_logs: {cnt_nodes} nodes, {cnt} metering records, thread {thread_id} [mrealm_id={mrealm_id}, from_ts={from_ts}, until_ts={until_ts}]',
            cnt=len(res),
            cnt_nodes=res['nodes'],
            cnt_records=res['count'],
            mrealm_id=mrealm_id,
            from_ts=from_ts,
            until_ts=until_ts,
            thread_id=threading.get_ident())

        return res

    @inlineCallbacks
    def _do_metering(self, started):
        self.log.debug('Usage metering: aggregating heartbeat records .. [started="{started}", thread_id={thread_id}]',
                       started=np.datetime64(started, 'ns'),
                       thread_id=threading.get_ident())

        # FIXME: make this tunable from the master node config
        agg_mins = 5

        # determine intervals of (from_ts, until_ts) for which to compute usage data from aggregate raw heartbeat data
        intervals = []
        mrealm_ids = []
        with self.db.begin() as txn:
            mrealm_ids.extend(self.schema.mrealms.select(txn, return_values=False))

            last_ts = None
            for (ts, _) in self.schema.usage.select(txn, reverse=True, limit=1, return_values=False):
                last_ts = ts

            if not last_ts:
                for mrealm_id in mrealm_ids:
                    ts = self._first_metering(mrealm_id)
                    if not last_ts or ts < last_ts:
                        last_ts = ts
                if not last_ts:
                    last_ts = np.datetime64(np.datetime64(time_ns(), 'ns') - np.timedelta64(agg_mins, 'm'), 'ns')

                last_ts = np.datetime64(last_ts.astype('datetime64[m]'), 'ns')
                self.log.debug('Usage metering: first metering timestamp set to "{last_ts}"', last_ts=last_ts)
            else:
                self.log.debug('Usage metering: last metering timestamp stored is "{last_ts}"', last_ts=last_ts)

            until_ts = np.datetime64(last_ts + np.timedelta64(agg_mins, 'm'), 'ns')

            while until_ts < np.datetime64(time_ns(), 'ns'):
                intervals.append((last_ts, until_ts))
                self.log.debug('Usage metering: aggregation interval ("{last_ts}", "{until_ts}") appended',
                               last_ts=last_ts,
                               until_ts=until_ts)

                last_ts = until_ts
                until_ts = np.datetime64(last_ts + np.timedelta64(agg_mins, 'm'), 'ns')

        cnt_new = 0

        # iterate over intervals to be aggregated ..
        if intervals:
            self.log.debug(
                'Usage metering: {cnt_intervals} intervals collected - now aggregating on background threads ..',
                cnt_intervals=len(intervals))

            # iterate over intervals ..
            for from_ts, until_ts in intervals:

                # .. and all management realms ..
                # FIXME: aggregate all mrealms for a given interval in one go
                for mrealm_id in mrealm_ids:
                    try:
                        # aggregate all _worker_ heartbeat data for interval (from_ts, until_ts) and mrealm_id
                        mrealm_res = yield deferToThread(self._agg_metering_mworker_logs, from_ts, until_ts, mrealm_id)

                        self.log.debug('Usage metering: worker aggregate result\n{mrealm_node_res}',
                                       mrealm_node_res=pprint.pformat(mrealm_res))

                        # aggregate all _node_ heartbeat data for interval (from_ts, until_ts) and mrealm_id
                        mrealm_node_res = yield deferToThread(self._agg_metering_mnode_logs, from_ts, until_ts,
                                                              mrealm_id)

                        self.log.debug('Usage metering: node aggregate result\n{mrealm_node_res}',
                                       mrealm_node_res=pprint.pformat(mrealm_node_res))
                    except:
                        self.log.failure()
                    else:
                        # overwrite "nodes" with what the node-based aggregate says (which is correct):
                        mrealm_res['nodes'] = mrealm_node_res['nodes']

                        for key in ['routers', 'guests', 'containers', 'proxies', 'marketmakers', 'controllers']:
                            if mrealm_res[key] != mrealm_node_res[key]:
                                self.log.warn(
                                    'Usage metering: node/worker aggregate for worker type "{key}" differ on worker seconds: {worker_res} != {node_res} (worker-based / node-based aggregate)',
                                    key=key,
                                    worker_res=mrealm_res[key],
                                    node_res=mrealm_node_res[key])

                        mrealm_res['timestamp'] = int(until_ts)
                        mrealm_res['timestamp_from'] = int(from_ts)
                        mrealm_res['mrealm_id'] = str(mrealm_id)
                        mrealm_res['seq'] = self._tick

                        # FIXME: set master (!) node public key
                        # mrealm_res['pubkey'] = self._node_key.verify_key.encode(encoder=nacl.encoding.RawEncoder)

                        # usage records start in status "RECEIVED"
                        mrealm_res['status'] = 1
                        mrealm_res['processed'] = time_ns()

                        # not used here
                        # mrealm_res['sent'] = None
                        # mrealm_res['status_message'] = None

                        # parse the raw dict into object
                        usage = MasterNodeUsage.parse(mrealm_res)

                        # finally, store new usage record in database
                        with self.db.begin(write=True) as txn:
                            self.schema.usage[txn, (until_ts, mrealm_id)] = usage

                        # publish usage metering event
                        topic = '{}on_meter_usage'.format(_CFC_DOMAIN)
                        yield self.publish(topic,
                                           str(mrealm_id),
                                           str(from_ts),
                                           str(until_ts),
                                           usage.marshal(),
                                           options=PublishOptions(acknowledge=True))

                        self.log.debug(
                            'Usage metering: aggregated and stored period from {from_ts} to {until_ts} ({duration}) usage metering data for mrealm "{mrealm_id}"',
                            mrealm_id=mrealm_id,
                            duration=str(np.timedelta64(until_ts - from_ts, 's')),
                            from_ts=from_ts,
                            until_ts=until_ts)
                        self.log.debug('Usage metering data:\n{usage}', usage=pprint.pformat(usage.marshal()))

                        cnt_new += 1
        else:
            self.log.debug('Usage metering: no new intervals to aggregate.')

        self.log.debug('Usage metering: finished aggregating [{cnt_new} intervals stored]', cnt_new=cnt_new)

        return cnt_new

    @inlineCallbacks
    def _submit_metering(self, started, filter_status=[1], limit=None):
        self.log.debug('Usage metering: submitting metering records .. [started="{started}"]',
                       started=np.datetime64(started, 'ns'))

        # collects keys in table "schema.usage" for metering records to be submitted
        keys = []

        # we only submit meterings up to 24h old
        from_ts = np.datetime64(np.datetime64(time_ns(), 'ns') - np.timedelta64(24, 'h'), 'ns')
        from_key = (from_ts, uuid.UUID(bytes=b'\x00' * 16))

        with self.db.begin() as txn:
            for rec in self.schema.usage.select(txn, reverse=False, return_keys=False, from_key=from_key, limit=limit):
                if rec.status in filter_status:
                    keys.append((rec.timestamp, rec.mrealm_id))

        tried = 0
        success = 0
        failed = 0

        # submit each metering record (here, sequentially)
        for key in keys:
            # fetch the record we want to submit
            with self.db.begin() as txn:
                rec = self.schema.usage[txn, key]

            self.log.debug('Usage metering: submitting metering record to "{url}"\n{rec}',
                           rec=pprint.pformat(rec.marshal()),
                           url=self._meterurl)

            # serialize metering data
            data = cbor2.dumps(rec.marshal())

            # FIXME: the master node public key
            # verify_key = self._node_key.verify_key.encode(encoder=nacl.encoding.RawEncoder)
            #
            # # sign metering data with master node (private) key
            #
            # # POST message body is concatenation of verify key and signed message:
            # data = verify_key + signed_msg
            #
            # self.log.debug('HTTP/POST: verify_key={lvk} data={ld} raw_data={lrd} signed_msg={lsm}',
            #                lvk=len(verify_key),
            #                ld=len(data),
            #                lrd=len(raw_data),
            #                lsm=len(signed_msg))

            tried += 1
            metering_id = None

            try:
                # issue the actual (outgoing) HTTP/POST request (with a 5s timeout) ..
                response = yield treq.post(self._meterurl, data=data, timeout=5)

                # .. and receive response body
                rdata = yield treq.content(response)

                if response.code != 200:
                    raise Exception('metering denied by metering service: HTTP response {}, "{}")'.format(
                        response.code, rdata))

            except Exception as e:
                # eg "twisted.internet.error.ConnectionRefusedError"
                # self.log.failure()
                rec.status = 3
                rec.status_message = 'failed to submit metering record: {}'.format(e)
                rec.processed = np.datetime64(time_ns(), 'ns')
                failed += 1
                self.log.warn('Usage metering: failed to submit metering record for "{timestamp}" - "{errmsg}"',
                              timestamp=rec.timestamp,
                              errmsg=str(e))
            else:
                try:
                    metering_id = uuid.UUID(bytes=rdata)
                except Exception as e:
                    rec.status = 3
                    rec.status_message = 'invalid response from metering service: {}'.format(e)
                    rec.processed = np.datetime64(time_ns(), 'ns')
                    failed += 1
                    self.log.log_failure()
                else:
                    rec.status = 2
                    rec.processed = np.datetime64(time_ns(), 'ns')
                    rec.metering_id = metering_id
                    success += 1
                    self.log.debug(
                        'Usage metering: metering record for "{timestamp}" successfully submitted [meterurl="{meterurl}", metering_id="{metering_id}"]',
                        meterurl=self._meterurl,
                        timestamp=rec.timestamp,
                        metering_id=metering_id,
                        response_length=len(rdata))

            with self.db.begin(write=True) as txn:
                self.schema.usage[txn, key] = rec

            self.log.debug(
                'Usage metering: metering record for "{timestamp}" processed with new status {status} [metering_id="{metering_id}"].',
                timestamp=rec.timestamp,
                metering_id=metering_id,
                status=rec.status)

        self.log.debug(
            'Usage metering: finished submitting metering records [tried={tried}, success={success}, failed={failed}]',
            tried=tried,
            success=success,
            failed=failed)
