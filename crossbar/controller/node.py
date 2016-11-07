#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
#
#  Should you enter into a separate license agreement after having received a copy of
#  this software, then the terms of such license agreement replace the terms below at
#  the time at which such license agreement becomes effective.
#
#  In case a separate license agreement ends, and such agreement ends without being
#  replaced by another separate license agreement, the license terms below apply
#  from the time at which said agreement ends.
#
#  LICENSE TERMS
#
#  This program is free software: you can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License, version 3, as published by the
#  Free Software Foundation. This program is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  See the GNU Affero General Public License Version 3 for more details.
#
#  You should have received a copy of the GNU Affero General Public license along
#  with this program. If not, see <http://www.gnu.org/licenses/agpl-3.0.en.html>.
#
#####################################################################################

from __future__ import absolute_import

import os
import traceback
import socket
import getpass
import pkg_resources
import binascii
from collections import OrderedDict

import pyqrcode

from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

import twisted
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.ssl import optionsForClientTLS

from txaio import make_logger

from autobahn.util import utcnow
from autobahn.wamp import cryptosign
from autobahn.wamp.types import CallDetails, CallOptions, ComponentConfig
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationRunner
from autobahn.wamp.cryptosign import _read_signify_ed25519_pubkey, _qrcode_from_signify_ed25519_pubkey

import crossbar
from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceSession
from crossbar.worker.router import RouterRealm
from crossbar.common import checkconfig
from crossbar.controller.process import NodeControllerSession
from crossbar.controller.management import NodeManagementBridgeSession
from crossbar.controller.management import NodeManagementSession


__all__ = ('Node',)


def _read_release_pubkey():
    release_pubkey_file = 'crossbar-{}.pub'.format('-'.join(crossbar.__version__.split('.')[0:2]))
    release_pubkey_path = os.path.join(pkg_resources.resource_filename('crossbar', 'keys'), release_pubkey_file)

    release_pubkey_hex = binascii.b2a_hex(_read_signify_ed25519_pubkey(release_pubkey_path)).decode('ascii')

    with open(release_pubkey_path) as f:
        release_pubkey_base64 = f.read().splitlines()[1]

    release_pubkey_qrcode = _qrcode_from_signify_ed25519_pubkey(release_pubkey_path)

    release_pubkey = {
        u'base64': release_pubkey_base64,
        u'hex': release_pubkey_hex,
        u'qrcode': release_pubkey_qrcode
    }

    return release_pubkey


def _parse_keyfile(key_path, private=True):
    """
    Internal helper. This parses a node.pub or node.priv file and
    returns a dict mapping tags -> values.
    """
    if os.path.exists(key_path) and not os.path.isfile(key_path):
        raise Exception("Key file '{}' exists, but isn't a file".format(key_path))

    allowed_tags = [u'public-key-ed25519', u'machine-id', u'created-at',
                    u'creator']
    if private:
        allowed_tags.append(u'private-key-ed25519')

    tags = OrderedDict()
    with open(key_path, 'r') as key_file:
        got_blankline = False
        for line in key_file.readlines():
            if line.strip() == '':
                got_blankline = True
            elif got_blankline:
                tag, value = line.split(':', 1)
                tag = tag.strip().lower()
                value = value.strip()
                if tag not in allowed_tags:
                    raise Exception("Invalid tag '{}' in key file {}".format(tag, key_path))
                if tag in tags:
                    raise Exception("Duplicate tag '{}' in key file {}".format(tag, key_path))
                tags[tag] = value
    return tags


def _read_node_pubkey(cbdir, privkey_path=u'key.priv', pubkey_path=u'key.pub'):

    node_pubkey_path = os.path.join(cbdir, pubkey_path)

    if not os.path.exists(node_pubkey_path):
        raise Exception('no node public key found at {}'.format(node_pubkey_path))

    node_pubkey_tags = _parse_keyfile(node_pubkey_path)

    node_pubkey_hex = node_pubkey_tags[u'public-key-ed25519']

    qr = pyqrcode.create(node_pubkey_hex, error='L', mode='binary')

    mode = 'text'

    if mode == 'text':
        node_pubkey_qr = qr.terminal()

    elif mode == 'svg':
        import io
        data_buffer = io.BytesIO()

        qr.svg(data_buffer, omithw=True)

        node_pubkey_qr = data_buffer.getvalue()

    else:
        raise Exception('logic error')

    node_pubkey = {
        u'hex': node_pubkey_hex,
        u'qrcode': node_pubkey_qr
    }

    return node_pubkey


def _machine_id():
    """
    for informational purposes, try to get a machine unique id thing
    """
    try:
        # why this? see: http://0pointer.de/blog/projects/ids.html
        with open('/var/lib/dbus/machine-id', 'r') as f:
            return f.read().strip()
    except:
        # OS X? Something else? Get a hostname, at least.
        return socket.gethostname()


def _creator():
    """
    for informational purposes, try to identify the creator (user@hostname)
    """
    try:
        return u'{}@{}'.format(getpass.getuser(), socket.gethostname())
    except:
        return None


def _write_node_key(filepath, tags, msg):
    """
    Internal helper.
    Write the given tags to the given file
    """
    with open(filepath, 'w') as f:
        f.write(msg)
        for (tag, value) in tags.items():
            if value:
                f.write(u'{}: {}\n'.format(tag, value))


class Node(object):
    """
    A Crossbar.io node is the running a controller process and one or multiple
    worker processes.

    A single Crossbar.io node runs exactly one instance of this class, hence
    this class can be considered a system singleton.
    """

    log = make_logger()

    def __init__(self, cbdir=None, reactor=None):
        """

        :param cbdir: The node directory to run from.
        :type cbdir: unicode
        :param reactor: Reactor to run on.
        :type reactor: obj or None
        """
        # node directory
        self._cbdir = cbdir or u'.'

        # reactor we should run on
        if reactor is None:
            from twisted.internet import reactor
        self._reactor = reactor

        # the node's management realm when running in managed mode (this comes from CDC!)
        self._management_realm = None

        # the node's ID when running in managed mode (this comes from CDC!)
        self._node_id = None

        # node extra when running in managed mode (this comes from CDC!)
        self._node_extra = None

        # the node controller realm
        self._realm = u'crossbar'

        # config of this node.
        self._config = None

        # node private key autobahn.wamp.cryptosign.SigningKey
        self._node_key = None

        # node controller session (a singleton ApplicationSession embedded
        # in the local node router)
        self._controller = None

        # when running in managed mode, this will hold the bridge session
        # attached to the local management router
        self._bridge_session = None

        # when running in managed mode, this will hold the uplink session to CDC
        self._manager = None

        # node shutdown triggers, one or more of checkconfig.NODE_SHUTDOWN_MODES
        self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT]

        # map from router worker IDs to
        self._realm_templates = {}

        # for node elements started under specific IDs, and where
        # the node configuration does not specify an ID, use a generic
        # name numbered sequentially using the counters here
        self._worker_no = 1
        self._realm_no = 1
        self._role_no = 1
        self._connection_no = 1
        self._transport_no = 1
        self._component_no = 1

    def maybe_generate_key(self, cbdir, privkey_path=u'key.priv', pubkey_path=u'key.pub'):

        privkey_path = os.path.join(cbdir, privkey_path)
        pubkey_path = os.path.join(cbdir, pubkey_path)

        if os.path.exists(privkey_path):

            # node private key seems to exist already .. check!

            priv_tags = _parse_keyfile(privkey_path, private=True)
            for tag in [u'creator', u'created-at', u'machine-id', u'public-key-ed25519', u'private-key-ed25519']:
                if tag not in priv_tags:
                    raise Exception("Corrupt node private key file {} - {} tag not found".format(privkey_path, tag))

            privkey_hex = priv_tags[u'private-key-ed25519']
            privkey = SigningKey(privkey_hex, encoder=HexEncoder)
            pubkey = privkey.verify_key
            pubkey_hex = pubkey.encode(encoder=HexEncoder).decode('ascii')

            if priv_tags[u'public-key-ed25519'] != pubkey_hex:
                raise Exception(
                    ("Inconsistent node private key file {} - public-key-ed25519 doesn't"
                     " correspond to private-key-ed25519").format(pubkey_path)
                )

            if os.path.exists(pubkey_path):
                pub_tags = _parse_keyfile(pubkey_path, private=False)
                for tag in [u'creator', u'created-at', u'machine-id', u'public-key-ed25519']:
                    if tag not in pub_tags:
                        raise Exception("Corrupt node public key file {} - {} tag not found".format(pubkey_path, tag))

                if pub_tags[u'public-key-ed25519'] != pubkey_hex:
                    raise Exception(
                        ("Inconsistent node public key file {} - public-key-ed25519 doesn't"
                         " correspond to private-key-ed25519").format(pubkey_path)
                    )
            else:
                self.log.info(
                    "Node public key file {pub_path} not found - re-creating from node private key file {priv_path}",
                    pub_path=pubkey_path,
                    priv_path=privkey_path,
                )
                pub_tags = OrderedDict([
                    (u'creator', priv_tags[u'creator']),
                    (u'created-at', priv_tags[u'created-at']),
                    (u'machine-id', priv_tags[u'machine-id']),
                    (u'public-key-ed25519', pubkey_hex),
                ])
                msg = u'Crossbar.io node public key\n\n'
                _write_node_key(pubkey_path, pub_tags, msg)

            self.log.debug("Node key already exists (public key: {hex})", hex=pubkey_hex)

        else:
            # node private key does not yet exist: generate one

            privkey = SigningKey.generate()
            privkey_hex = privkey.encode(encoder=HexEncoder).decode('ascii')
            pubkey = privkey.verify_key
            pubkey_hex = pubkey.encode(encoder=HexEncoder).decode('ascii')

            # first, write the public file
            tags = OrderedDict([
                (u'creator', _creator()),
                (u'created-at', utcnow()),
                (u'machine-id', _machine_id()),
                (u'public-key-ed25519', pubkey_hex),
            ])
            msg = u'Crossbar.io node public key\n\n'
            _write_node_key(pubkey_path, tags, msg)

            # now, add the private key and write the private file
            tags[u'private-key-ed25519'] = privkey_hex
            msg = u'Crossbar.io node private key - KEEP THIS SAFE!\n\n'
            _write_node_key(privkey_path, tags, msg)

            self.log.info("New node key pair generated!")

        # fix file permissions on node public/private key files
        # note: we use decimals instead of octals as octal literals have changed between Py2/3
        #
        if os.stat(pubkey_path).st_mode & 511 != 420:  # 420 (decimal) == 0644 (octal)
            os.chmod(pubkey_path, 420)
            self.log.info("File permissions on node public key fixed!")

        if os.stat(privkey_path).st_mode & 511 != 384:  # 384 (decimal) == 0600 (octal)
            os.chmod(privkey_path, 384)
            self.log.info("File permissions on node private key fixed!")

        self._node_key = cryptosign.SigningKey(privkey)

        return pubkey_hex

    def load(self, configfile=None):
        """
        Check and load the node configuration (usually, from ".crossbar/config.json")
        or load built-in CDC default config.
        """
        if configfile:
            configpath = os.path.join(self._cbdir, configfile)

            self.log.debug("Loading node configuration from '{configpath}' ..",
                           configpath=configpath)

            # the following will read the config, check the config and replace
            # environment variable references in configuration values ("${MYVAR}") and
            # finally return the parsed configuration object
            self._config = checkconfig.check_config_file(configpath)

            self.log.info("Node configuration loaded from '{configfile}'",
                          configfile=configfile)
        else:
            self._config = {
                u'version': 2,
                u'controller': {},
                u'workers': []
            }
            checkconfig.check_config(self._config)
            self.log.info("Node configuration loaded from built-in config.")

    @inlineCallbacks
    def start(self, cdc_mode=False):
        """
        Starts this node. This will start a node controller and then spawn new worker
        processes as needed.
        """
        if not self._config:
            raise Exception("No node configuration loaded")

        # get controller config/options
        #
        controller_config = self._config.get('controller', {})
        controller_options = controller_config.get('options', {})

        # set controller process title
        #
        try:
            import setproctitle
        except ImportError:
            self.log.warn("Warning, could not set process title (setproctitle not installed)")
        else:
            setproctitle.setproctitle(controller_options.get('title', 'crossbar-controller'))

        # router and factory that creates router sessions
        #
        self._router_factory = RouterFactory()
        self._router_session_factory = RouterSessionFactory(self._router_factory)

        # create a new router for the realm
        #
        rlm_config = {
            'name': self._realm
        }
        rlm = RouterRealm(None, rlm_config)
        router = self._router_factory.start_realm(rlm)

        # always add a realm service session
        #
        cfg = ComponentConfig(self._realm)
        rlm.session = RouterServiceSession(cfg, router)
        self._router_session_factory.add(rlm.session, authrole=u'trusted')

        # add a router bridge session when running in managed mode
        #
        if cdc_mode:
            self._bridge_session = NodeManagementBridgeSession(cfg)
            self._router_session_factory.add(self._bridge_session, authrole=u'trusted')
        else:
            self._bridge_session = None

        # Node shutdown mode
        #
        if cdc_mode:
            # in managed mode, a node - by default - only shuts down when explicitly asked to,
            # or upon a fatal error in the node controller
            self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_SHUTDOWN_REQUESTED]
        else:
            # in standalone mode, a node - by default - is immediately shutting down whenever
            # a worker exits (successfully or with error)
            self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT]

        # allow to override node shutdown triggers
        #
        if 'shutdown' in controller_options:
            self.log.info("Overriding default node shutdown triggers with {triggers} from node config", triggers=controller_options['shutdown'])
            self._node_shutdown_triggers = controller_options['shutdown']
        else:
            self.log.info("Using default node shutdown triggers {triggers}", triggers=self._node_shutdown_triggers)

        # add the node controller singleton session
        #
        self._controller = NodeControllerSession(self)
        self._router_session_factory.add(self._controller, authrole=u'trusted')

        # detect WAMPlets (FIXME: remove this!)
        #
        wamplets = self._controller._get_wamplets()
        if len(wamplets) > 0:
            self.log.info("Detected {wamplets} WAMPlets in environment:",
                          wamplets=len(wamplets))
            for wpl in wamplets:
                self.log.info("WAMPlet {dist}.{name}",
                              dist=wpl['dist'], name=wpl['name'])
        else:
            self.log.debug("No WAMPlets detected in enviroment.")

        panic = False
        try:
            # startup the node from local node configuration
            #
            yield self._startup(self._config)

            # connect to CDC when running in managed mode
            #
            if cdc_mode:
                cdc_config = controller_config.get('cdc', {

                    # CDC connecting transport
                    u'transport': {
                        u'type': u'websocket',
                        u'url': u'wss://cdc.crossbario.com/ws',
                        u'endpoint': {
                            u'type': u'tcp',
                            u'host': u'cdc.crossbario.com',
                            u'port': 443,
                            u'timeout': 5,
                            u'tls': {
                                u'hostname': u'cdc.crossbario.com'
                            }
                        }
                    }
                })

                transport = cdc_config[u'transport']
                hostname = None
                if u'tls' in transport[u'endpoint']:
                    transport[u'endpoint'][u'tls'][u'hostname']

                runner = ApplicationRunner(
                    url=transport['url'],
                    realm=None,
                    extra=None,
                    ssl=optionsForClientTLS(hostname) if hostname else None,
                )

                def make(config):
                    # extra info forwarded to CDC client session
                    extra = {
                        'node': self,
                        'on_ready': Deferred(),
                        'on_exit': Deferred(),
                        'node_key': self._node_key,
                    }

                    @inlineCallbacks
                    def on_ready(res):
                        self._manager, self._management_realm, self._node_id, self._node_extra = res

                        if self._bridge_session:
                            try:
                                yield self._bridge_session.attach_manager(self._manager, self._management_realm, self._node_id)
                                status = yield self._manager.call(u'cdc.remote.status@1')
                            except:
                                self.log.failure()
                            else:
                                self.log.info('Connected to CDC for management realm "{realm}" (current time is {now})', realm=self._management_realm, now=status[u'now'])
                        else:
                            self.log.warn('Uplink CDC session established, but no bridge session setup!')

                    @inlineCallbacks
                    def on_exit(res):
                        if self._bridge_session:
                            try:
                                yield self._bridge_session.detach_manager()
                            except:
                                self.log.failure()
                            else:
                                self.log.info('Disconnected from CDC for management realm "{realm}"', realm=self._management_realm)
                        else:
                            self.log.warn('Uplink CDC session lost, but no bridge session setup!')

                        self._manager, self._management_realm, self._node_id, self._node_extra = None, None, None, None

                    extra['on_ready'].addCallback(on_ready)
                    extra['on_exit'].addCallback(on_exit)

                    config = ComponentConfig(extra=extra)
                    session = NodeManagementSession(config)

                    return session

                self.log.info("Connecting to CDC at '{url}' ..", url=transport[u'url'])
                yield runner.run(make, start_reactor=False, auto_reconnect=True)

            # Notify systemd that crossbar is fully up and running
            # (this has no effect on non-systemd platforms)
            try:
                import sdnotify
                sdnotify.SystemdNotifier().notify("READY=1")
            except:
                pass

        except ApplicationError as e:
            panic = True
            self.log.error("{msg}", msg=e.error_message())

        except Exception:
            panic = True
            traceback.print_exc()

        if panic:
            try:
                self._reactor.stop()
            except twisted.internet.error.ReactorNotRunning:
                pass

    @inlineCallbacks
    def _startup(self, config):
        """
        Startup elements in the node as specified in the provided node configuration.
        """
        self.log.info('Configuring node from local configuration ...')

        # call options we use to call into the local node management API
        call_options = CallOptions()

        # fake call details we use to call into the local node management API
        call_details = CallDetails(caller=0)

        # get contoller configuration subpart
        controller = config.get('controller', {})

        # start Manhole in node controller
        if 'manhole' in controller:
            yield self._controller.start_manhole(controller['manhole'], details=call_details)

        # startup all workers
        workers = config.get('workers', [])
        if len(workers):
            self.log.info('Starting {nworkers} workers ...', nworkers=len(workers))
        else:
            self.log.info('No workers configured!')
        for worker in workers:

            # worker ID
            if 'id' in worker:
                worker_id = worker.pop('id')
            else:
                worker_id = 'worker-{:03d}'.format(self._worker_no)
                self._worker_no += 1

            # worker type - a type of working process from the following fixed list
            worker_type = worker['type']
            assert(worker_type in ['router', 'container', 'guest', 'websocket-testee'])

            # set logname depending on worker type
            if worker_type == 'router':
                worker_logname = "Router '{}'".format(worker_id)
            elif worker_type == 'container':
                worker_logname = "Container '{}'".format(worker_id)
            elif worker_type == 'websocket-testee':
                worker_logname = "WebSocketTestee '{}'".format(worker_id)
            elif worker_type == 'guest':
                worker_logname = "Guest '{}'".format(worker_id)
            else:
                raise Exception("logic error")

            # any worker specific options
            worker_options = worker.get('options', {})

            # native worker processes: router, container, websocket-testee
            if worker_type in ['router', 'container', 'websocket-testee']:

                # start a new native worker process ..
                if worker_type == 'router':
                    yield self._controller.start_router(worker_id, worker_options, details=call_details)

                elif worker_type == 'container':
                    yield self._controller.start_container(worker_id, worker_options, details=call_details)

                elif worker_type == 'websocket-testee':
                    yield self._controller.start_websocket_testee(worker_id, worker_options, details=call_details)

                else:
                    raise Exception("logic error")

                # setup native worker generic stuff
                if 'pythonpath' in worker_options:
                    added_paths = yield self._controller.call('crossbar.worker.{}.add_pythonpath'.format(worker_id), worker_options['pythonpath'], options=call_options)
                    self.log.debug("{worker}: PYTHONPATH extended for {paths}",
                                   worker=worker_logname, paths=added_paths)

                if 'cpu_affinity' in worker_options:
                    new_affinity = yield self._controller.call('crossbar.worker.{}.set_cpu_affinity'.format(worker_id), worker_options['cpu_affinity'], options=call_options)
                    self.log.debug("{worker}: CPU affinity set to {affinity}",
                                   worker=worker_logname, affinity=new_affinity)

                if 'manhole' in worker:
                    yield self._controller.call('crossbar.worker.{}.start_manhole'.format(worker_id), worker['manhole'], options=call_options)
                    self.log.debug("{worker}: manhole started",
                                   worker=worker_logname)

                # setup router worker
                if worker_type == 'router':

                    # start realms on router
                    for realm in worker.get('realms', []):

                        # start realm
                        if 'id' in realm:
                            realm_id = realm.pop('id')
                        else:
                            realm_id = 'realm-{:03d}'.format(self._realm_no)
                            self._realm_no += 1

                        yield self._controller.call('crossbar.worker.{}.start_router_realm'.format(worker_id), realm_id, realm, options=call_options)
                        self.log.info("{worker}: realm '{realm_id}' (named '{realm_name}') started",
                                      worker=worker_logname, realm_id=realm_id, realm_name=realm['name'])

                        # add roles to realm
                        for role in realm.get('roles', []):
                            if 'id' in role:
                                role_id = role.pop('id')
                            else:
                                role_id = 'role-{:03d}'.format(self._role_no)
                                self._role_no += 1

                            yield self._controller.call('crossbar.worker.{}.start_router_realm_role'.format(worker_id), realm_id, role_id, role, options=call_options)
                            self.log.info(
                                "{logname}: role '{role}' (named '{role_name}') started on realm '{realm}'",
                                logname=worker_logname,
                                role=role_id,
                                role_name=role['name'],
                                realm=realm_id,
                            )

                        # start uplinks for realm
                        for uplink in realm.get('uplinks', []):
                            if 'id' in uplink:
                                uplink_id = uplink.pop('id')
                            else:
                                uplink_id = 'uplink-{:03d}'.format(self._uplink_no)
                                self._uplink_no += 1

                            yield self._controller.call('crossbar.worker.{}.start_router_realm_uplink'.format(worker_id), realm_id, uplink_id, uplink, options=call_options)
                            self.log.info(
                                "{logname}: uplink '{uplink}' started on realm '{realm}'",
                                logname=worker_logname,
                                uplink=uplink_id,
                                realm=realm_id,
                            )

                    # start connections (such as PostgreSQL database connection pools)
                    # to run embedded in the router
                    for connection in worker.get('connections', []):

                        if 'id' in connection:
                            connection_id = connection.pop('id')
                        else:
                            connection_id = 'connection-{:03d}'.format(self._connection_no)
                            self._connection_no += 1

                        yield self._controller.call('crossbar.worker.{}.start_connection'.format(worker_id), connection_id, connection, options=call_options)
                        self.log.info(
                            "{logname}: connection '{connection}' started",
                            logname=worker_logname,
                            connection=connection_id,
                        )

                    # start components to run embedded in the router
                    for component in worker.get('components', []):

                        if 'id' in component:
                            component_id = component.pop('id')
                        else:
                            component_id = 'component-{:03d}'.format(self._component_no)
                            self._component_no += 1

                        yield self._controller.call('crossbar.worker.{}.start_router_component'.format(worker_id), component_id, component, options=call_options)
                        self.log.info(
                            "{logname}: component '{component}' started",
                            logname=worker_logname,
                            component=component_id,
                        )

                    # start transports on router
                    for transport in worker['transports']:

                        if 'id' in transport:
                            transport_id = transport.pop('id')
                        else:
                            transport_id = 'transport-{:03d}'.format(self._transport_no)
                            self._transport_no += 1

                        yield self._controller.call('crossbar.worker.{}.start_router_transport'.format(worker_id), transport_id, transport, options=call_options)
                        self.log.info(
                            "{logname}: transport '{tid}' started",
                            logname=worker_logname,
                            tid=transport_id,
                        )

                # setup container worker
                elif worker_type == 'container':

                    # if components exit "very soon after" we try to
                    # start them, we consider that a failure and shut
                    # our node down. We remove this subscription 2
                    # seconds after we're done starting everything
                    # (see below). This is necessary as
                    # start_container_component returns as soon as
                    # we've established a connection to the component
                    def component_exited(info):
                        component_id = info.get("id")
                        self.log.critical("Component '{component_id}' failed to start; shutting down node.", component_id=component_id)
                        try:
                            self._reactor.stop()
                        except twisted.internet.error.ReactorNotRunning:
                            pass
                    topic = 'crossbar.worker.{}.container.on_component_stop'.format(worker_id)
                    component_stop_sub = yield self._controller.subscribe(component_exited, topic)

                    # start connections (such as PostgreSQL database connection pools)
                    # to run embedded in the container
                    #
                    for connection in worker.get('connections', []):

                        if 'id' in connection:
                            connection_id = connection.pop('id')
                        else:
                            connection_id = 'connection-{:03d}'.format(self._connection_no)
                            self._connection_no += 1

                        yield self._controller.call('crossbar.worker.{}.start_connection'.format(worker_id), connection_id, connection, options=call_options)
                        self.log.info(
                            "{logname}: connection '{connection}' started",
                            logname=worker_logname,
                            connection=connection_id,
                        )

                    # start components to run embedded in the container
                    #
                    for component in worker.get('components', []):

                        if 'id' in component:
                            component_id = component.pop('id')
                        else:
                            component_id = 'component-{:03d}'.format(self._component_no)
                            self._component_no += 1

                        yield self._controller.call('crossbar.worker.{}.start_container_component'.format(worker_id), component_id, component, options=call_options)
                        self.log.info("{worker}: component '{component_id}' started",
                                      worker=worker_logname, component_id=component_id)

                    # after 2 seconds, consider all the application components running
                    self._reactor.callLater(2, component_stop_sub.unsubscribe)

                # setup websocket-testee worker
                elif worker_type == 'websocket-testee':

                    # start transport on websocket-testee
                    transport = worker['transport']
                    transport_id = 'transport-{:03d}'.format(self._transport_no)
                    self._transport_no = 1

                    yield self._controller.call('crossbar.worker.{}.start_websocket_testee_transport'.format(worker_id), transport_id, transport, options=call_options)
                    self.log.info(
                        "{logname}: transport '{tid}' started",
                        logname=worker_logname,
                        tid=transport_id,
                    )

                else:
                    raise Exception("logic error")

            elif worker_type == 'guest':

                # start guest worker
                #
                yield self._controller.start_guest(worker_id, worker, details=call_details)
                self.log.info("{worker}: started", worker=worker_logname)

            else:
                raise Exception("logic error")

        self.log.info('Local node configuration applied.')
