#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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
from collections import OrderedDict

import twisted
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.ssl import optionsForClientTLS

from autobahn.util import utcnow
from autobahn.wamp.types import CallDetails, CallOptions, ComponentConfig
from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationRunner

from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceSession
from crossbar.worker.router import RouterRealm
from crossbar.common import checkconfig
from crossbar.controller.process import NodeControllerSession
from crossbar.controller.management import NodeManagementBridgeSession
from crossbar.controller.management import NodeManagementSession

from txaio import make_logger

try:
    import nacl  # noqa
    HAS_NACL = True
except ImportError:
    HAS_NACL = False


__all__ = ('Node',)


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


def _machine_id():
    """
    for informational purposes, try to get a machine unique id thing
    """
    try:
        # why this? see: http://0pointer.de/blog/projects/ids.html
        with open('/var/lib/dbus/machine-id', 'r') as f:
            return f.read().strip()
    except:
        return None


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

    # set file mode to read only for owner
    # 384 (decimal) == 0600 (octal) - we use that for Py2/3 reasons
    os.chmod(filepath, 384)


def maybe_generate_key(log, cbdir, privkey_path=u'key.priv', pubkey_path=u'key.pub'):
    if not HAS_NACL:
        log.warn("Skipping node key generation - NaCl package not installed!")
        return

    from nacl.signing import SigningKey
    from nacl.encoding import HexEncoder

    privkey = None
    pubkey = None
    privkey_path = os.path.join(cbdir, privkey_path)
    pubkey_path = os.path.join(cbdir, pubkey_path)

    if os.path.exists(privkey_path):
        # node private key seems to exist already .. check!
        tags = _parse_keyfile(privkey_path, private=True)
        if u'private-key-ed25519' not in tags:
            raise Exception("Node private key file lacks a 'private-key-ed25519' tag!")

        privkey = tags[u'private-key-ed25519']
        # recreate a signing key from the base64 encoding
        privkey_obj = SigningKey(privkey, encoder=HexEncoder)
        pubkey = privkey_obj.verify_key.encode(encoder=HexEncoder).decode('ascii')

        # confirm we have the public key in the file, and that it is
        # correct
        if u'public-key-ed25519' in tags:
            if tags[u'public-key-ed25519'] != pubkey:
                raise Exception(
                    ("Inconsistent key file '{}': 'public-key-ed25519' doesn't"
                     " correspond to private-key-ed25519").format(privkey_path)
                )
        log.debug("Node key already exists (public key: {})".format(pubkey))

        if os.path.exists(pubkey_path):
            pubtags = _parse_keyfile(pubkey_path, private=False)
            if u'public-key-ed25519' not in pubtags:
                raise Exception(
                    ("Pubkey file '{}' exists but lacks 'public-key-ed25519'"
                     " tag").format(pubkey_path)
                )
            if pubtags[u'public-key-ed25519'] != pubkey:
                raise Exception(
                    ("Inconsistent key file '{}': 'public-key-ed25519' doesn't"
                     " correspond to private-key-ed25519").format(pubkey_path)
                )
        else:
            log.info("'{}' not found; re-creating from '{}'".format(pubkey_path, privkey_path))
            tags = OrderedDict([
                (u'creator', _creator()),
                (u'created-at', utcnow()),
                (u'machine-id', _machine_id()),
                (u'public-key-ed25519', pubkey),
            ])
            msg = u'Crossbar.io public key for node authentication\n\n'
            _write_node_key(pubkey_path, tags, msg)

    else:
        # node private key does NOT yet exist: generate one
        privkey_obj = SigningKey.generate()
        privkey = privkey_obj.encode(encoder=HexEncoder).decode('ascii')
        pubkey = privkey_obj.verify_key.encode(encoder=HexEncoder).decode('ascii')

        # first, write the public file
        tags = OrderedDict([
            (u'creator', _creator()),
            (u'created-at', utcnow()),
            (u'machine-id', _machine_id()),
            (u'public-key-ed25519', pubkey),
        ])
        msg = u'Crossbar.io public key for node authentication\n\n'
        _write_node_key(pubkey_path, tags, msg)

        # now, add the private key and write the private file
        tags[u'private-key-ed25519'] = privkey
        msg = u'Crossbar.io private key for node authentication - KEEP THIS SAFE!\n\n'
        _write_node_key(privkey_path, tags, msg)

        log.info("New node key generated!")

    return pubkey


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

        # the node's name (must be unique within the management realm)
        self._node_id = None

        # the node's management realm
        self._realm = None

        # config of this node.
        self._config = None

        # node controller session (a singleton ApplicationSession embedded
        # in the local node router)
        self._controller = None

        # when run in "managed mode", this will hold the uplink WAMP session
        # from the node controller to the mananagement application
        self._manager = None

        # node shutdown triggers, one or more of checkconfig.NODE_SHUTDOWN_MODES
        self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT]

        # map fro router worker IDs to
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
                u"controller": {
                    u"cdc": {
                        u"enabled": True
                    }
                }
            }
            checkconfig.check_config(self._config)
            self.log.info("Node configuration loaded from built-in CDC config.")

    def _prepare_node_keys(self):
        from nacl.signing import SigningKey
        from nacl.encoding import HexEncoder

        # make sure CBDIR/.cdc exists
        #
        cdc_dir = os.path.join(self._cbdir, '.cdc')
        if os.path.isdir(cdc_dir):
            pass
        elif os.path.exists(cdc_dir):
            raise Exception(".cdc exists, but isn't a directory")
        else:
            os.mkdir(cdc_dir)
            self.log.info("CDC directory created")

        # load node ID, either from .cdc/node.id or from CDC_NODE_ID
        #
        def split_nid(nid_s):
            nid_c = nid_s.strip().split('@')
            if len(nid_c) != 2:
                raise Exception("illegal node principal '{}' - must follow the form <node id>@<management realm>".format(nid_s))
            node_id, realm = nid_c
            # FIXME: regex check node_id and realm
            return node_id, realm

        nid_file = os.path.join(cdc_dir, 'node.id')
        node_id, realm = None, None
        if os.path.isfile(nid_file):
            with open(nid_file, 'r') as f:
                node_id, realm = split_nid(f.read())
        elif os.path.exists(nid_file):
            raise Exception("{} exists, but isn't a file".format(nid_file))
        else:
            if 'CDC_NODE_ID' in os.environ:
                node_id, realm = split_nid(os.environ['CDC_NODE_ID'])
            else:
                raise Exception("Neither node ID file {} exists nor CDC_NODE_ID environment variable set".format(nid_file))

        # Load the node key, either from .cdc/node.key or from CDC_NODE_KEY.
        # The node key is a Ed25519 key in either raw format (32 bytes) or in
        # hex-encoded form (64 characters).
        #
        # Actually, what's loaded is not the secret Ed25519 key, but the _seed_
        # for that key. Private keys are derived from this 32-byte (256-bit)
        # random seed value. It is thus the seed value which is sensitive and
        # must be protected.
        #
        skey_file = os.path.join(cdc_dir, 'node.key')
        skey = None
        if os.path.isfile(skey_file):
            # FIXME: check file permissions are 0600!

            # This value is read in here.
            skey_len = os.path.getsize(skey_file)
            if skey_len in (32, 64):
                with open(skey_file, 'r') as f:
                    skey_seed = f.read()
                    encoder = None
                    if skey_len == 64:
                        encoder = HexEncoder
                    skey = SigningKey(skey_seed, encoder=encoder)
                self.log.info("Existing CDC node key loaded from {skey_file}.", skey_file=skey_file)
            else:
                raise Exception("invalid node key length {} (key must either be 32 raw bytes or hex encoded 32 bytes, hence 64 byte char length)")
        elif os.path.exists(skey_file):
            raise Exception("{} exists, but isn't a file".format(skey_file))
        else:
            skey = SigningKey.generate()
            skey_seed = skey.encode(encoder=HexEncoder)
            with open(skey_file, 'w') as f:
                f.write(skey_seed)

            # set file mode to read only for owner
            # 384 (decimal) == 0600 (octal) - we use that for Py2/3 reasons
            os.chmod(skey_file, 384)
            self.log.info("New CDC node key {skey_file} generated.", skey_file=skey_file)

        return realm, node_id, skey

    @inlineCallbacks
    def start(self, cdc_mode=False):
        """
        Starts this node. This will start a node controller and then spawn new worker
        processes as needed.
        """
        if not self._config:
            raise Exception("No node configuration loaded")

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

        # the node controller realm
        #
        self._realm = controller_config.get(u'realm', u'crossbar')

        # the node's name (must be unique within the management realm when running
        # in "managed mode")
        #
        if 'id' in controller_config:
            self._node_id = controller_config['id']
            self.log.info("Node ID '{node_id}' set from config", node_id=self._node_id)
        elif 'CDC_ID' in os.environ:
            self._node_id = u'{}'.format(os.environ['CDC_ID'])
            self.log.info("Node ID '{node_id}' set from environment variable CDC_ID", node_id=self._node_id)
        else:
            self._node_id = u'{}'.format(socket.gethostname())
            self.log.info("Node ID '{node_id}' set from hostname", node_id=self._node_id)

        # standalone vs managed mode
        #
        if 'cdc' in controller_config and controller_config['cdc'].get('enabled', False):

            self._prepare_node_keys()

            cdc_config = controller_config['cdc']

            # CDC connecting transport
            #
            if 'transport' in cdc_config:
                transport = cdc_config['transport']
                if 'tls' in transport['endpoint']:
                    if 'hostname' in transport['endpoint']:
                        hostname = transport['endpoint']['tls']['hostname']
                    else:
                        raise Exception("TLS activated on CDC connection, but 'hostname' not provided")
                else:
                    hostname = None
                self.log.warn("CDC transport configuration overridden from node config!")
            else:
                transport = {
                    "type": u"websocket",
                    "url": u"wss://devops.crossbario.com/ws",
                    "endpoint": {
                        "type": u"tcp",
                        "host": u"devops.crossbario.com",
                        "port": 443,
                        "timeout": 5,
                        "tls": {
                            "hostname": u"devops.crossbario.com"
                        }
                    }
                }
                hostname = u'devops.crossbario.com'

            # CDC management realm
            #
            if 'realm' in cdc_config:
                realm = cdc_config['realm']
                self.log.info("CDC management realm '{realm}' set from config", realm=realm)
            elif 'CDC_REALM' in os.environ:
                realm = u"{}".format(os.environ['CDC_REALM']).strip()
                self.log.info("CDC management realm '{realm}' set from enviroment variable CDC_REALM", realm=realm)
            else:
                raise Exception("CDC management realm not set - either 'realm' must be set in node configuration, or in CDC_REALM enviroment variable")

            # CDC authentication credentials (for WAMP-CRA)
            #
            authid = self._node_id
            if 'secret' in cdc_config:
                authkey = cdc_config['secret']
                self.log.info("CDC authentication secret loaded from config")
            elif 'CDC_SECRET' in os.environ:
                authkey = u"{}".format(os.environ['CDC_SECRET']).strip()
                self.log.info("CDC authentication secret loaded from environment variable CDC_SECRET")
            else:
                raise Exception("CDC authentication secret not set - either 'secret' must be set in node configuration, or in CDC_SECRET enviroment variable")

            # extra info forwarded to CDC client session
            #
            extra = {
                'node': self,
                'onready': Deferred(),
                'onexit': Deferred(),
                'authid': authid,
                'authkey': authkey
            }

            runner = ApplicationRunner(
                url=transport['url'], realm=realm, extra=extra,
                ssl=optionsForClientTLS(hostname) if hostname else None,
            )

            try:
                self.log.info("Connecting to CDC at '{url}' ..", url=transport['url'])
                yield runner.run(NodeManagementSession, start_reactor=False)

                # wait until we have attached to the uplink CDC
                self._manager = yield extra['onready']
            except Exception as e:
                raise Exception("Could not connect to CDC - {}".format(e))

            # in managed mode, a node - by default - only shuts down when explicitly asked to,
            # or upon a fatal error in the node controller
            self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_SHUTDOWN_REQUESTED]

            self.log.info("Connected to Crossbar.io DevOps Center (CDC)! Your node runs in managed mode.")
        else:
            self._manager = None

            # in standalone mode, a node - by default - is immediately shutting down whenever
            # a worker exits (successfully or with error)
            self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT]

        # allow to override node shutdown triggers
        #
        if 'shutdown' in controller_options:
            self.log.info("Overriding default node shutdown triggers with {} from node config".format(controller_options['shutdown']))
            self._node_shutdown_triggers = controller_options['shutdown']
        else:
            self.log.info("Using default node shutdown triggers {}".format(self._node_shutdown_triggers))

        # router and factory that creates router sessions
        #
        self._router_factory = RouterFactory(self._node_id)
        self._router_session_factory = RouterSessionFactory(self._router_factory)

        rlm_config = {
            'name': self._realm
        }
        rlm = RouterRealm(None, rlm_config)

        # create a new router for the realm
        router = self._router_factory.start_realm(rlm)

        # add a router/realm service session
        cfg = ComponentConfig(self._realm)

        rlm.session = RouterServiceSession(cfg, router)
        self._router_session_factory.add(rlm.session, authrole=u'trusted')

        if self._manager:
            self._bridge_session = NodeManagementBridgeSession(cfg, self, self._manager)
            self._router_session_factory.add(self._bridge_session, authrole=u'trusted')
        else:
            self._bridge_session = None

        # the node controller singleton WAMP application session
        #
        self._controller = NodeControllerSession(self)

        # add the node controller singleton session to the router
        #
        self._router_session_factory.add(self._controller, authrole=u'trusted')

        # Detect WAMPlets
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
            yield self._startup(self._config)

            # Notify systemd that crossbar is fully up and running
            # This has no effect on non-systemd platforms
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
        for worker in config.get('workers', []):

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
                    added_paths = yield self._controller.call('crossbar.node.{}.worker.{}.add_pythonpath'.format(self._node_id, worker_id), worker_options['pythonpath'], options=call_options)
                    self.log.debug("{worker}: PYTHONPATH extended for {paths}",
                                   worker=worker_logname, paths=added_paths)

                if 'cpu_affinity' in worker_options:
                    new_affinity = yield self._controller.call('crossbar.node.{}.worker.{}.set_cpu_affinity'.format(self._node_id, worker_id), worker_options['cpu_affinity'], options=call_options)
                    self.log.debug("{worker}: CPU affinity set to {affinity}",
                                   worker=worker_logname, affinity=new_affinity)

                if 'manhole' in worker:
                    yield self._controller.call('crossbar.node.{}.worker.{}.start_manhole'.format(self._node_id, worker_id), worker['manhole'], options=call_options)
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

                        yield self._controller.call('crossbar.node.{}.worker.{}.start_router_realm'.format(self._node_id, worker_id), realm_id, realm, options=call_options)
                        self.log.info("{worker}: realm '{realm_id}' (named '{realm_name}') started",
                                      worker=worker_logname, realm_id=realm_id, realm_name=realm['name'])

                        # add roles to realm
                        for role in realm.get('roles', []):
                            if 'id' in role:
                                role_id = role.pop('id')
                            else:
                                role_id = 'role-{:03d}'.format(self._role_no)
                                self._role_no += 1

                            yield self._controller.call('crossbar.node.{}.worker.{}.start_router_realm_role'.format(self._node_id, worker_id), realm_id, role_id, role, options=call_options)
                            self.log.info("{}: role '{}' (named '{}') started on realm '{}'".format(worker_logname, role_id, role['name'], realm_id))

                        # start uplinks for realm
                        for uplink in realm.get('uplinks', []):
                            if 'id' in uplink:
                                uplink_id = uplink.pop('id')
                            else:
                                uplink_id = 'uplink-{:03d}'.format(self._uplink_no)
                                self._uplink_no += 1

                            yield self._controller.call('crossbar.node.{}.worker.{}.start_router_realm_uplink'.format(self._node_id, worker_id), realm_id, uplink_id, uplink, options=call_options)
                            self.log.info("{}: uplink '{}' started on realm '{}'".format(worker_logname, uplink_id, realm_id))

                    # start connections (such as PostgreSQL database connection pools)
                    # to run embedded in the router
                    for connection in worker.get('connections', []):

                        if 'id' in connection:
                            connection_id = connection.pop('id')
                        else:
                            connection_id = 'connection-{:03d}'.format(self._connection_no)
                            self._connection_no += 1

                        yield self._controller.call('crossbar.node.{}.worker.{}.start_connection'.format(self._node_id, worker_id), connection_id, connection, options=call_options)
                        self.log.info("{}: connection '{}' started".format(worker_logname, connection_id))

                    # start components to run embedded in the router
                    for component in worker.get('components', []):

                        if 'id' in component:
                            component_id = component.pop('id')
                        else:
                            component_id = 'component-{:03d}'.format(self._component_no)
                            self._component_no += 1

                        yield self._controller.call('crossbar.node.{}.worker.{}.start_router_component'.format(self._node_id, worker_id), component_id, component, options=call_options)
                        self.log.info("{}: component '{}' started".format(worker_logname, component_id))

                    # start transports on router
                    for transport in worker['transports']:

                        if 'id' in transport:
                            transport_id = transport.pop('id')
                        else:
                            transport_id = 'transport-{:03d}'.format(self._transport_no)
                            self._transport_no += 1

                        yield self._controller.call('crossbar.node.{}.worker.{}.start_router_transport'.format(self._node_id, worker_id), transport_id, transport, options=call_options)
                        self.log.info("{}: transport '{}' started".format(worker_logname, transport_id))

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
                    topic = 'crossbar.node.{}.worker.{}.container.on_component_stop'.format(self._node_id, worker_id)
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

                        yield self._controller.call('crossbar.node.{}.worker.{}.start_connection'.format(self._node_id, worker_id), connection_id, connection, options=call_options)
                        self.log.info("{}: connection '{}' started".format(worker_logname, connection_id))

                    # start components to run embedded in the container
                    #
                    for component in worker.get('components', []):

                        if 'id' in component:
                            component_id = component.pop('id')
                        else:
                            component_id = 'component-{:03d}'.format(self._component_no)
                            self._component_no += 1

                        yield self._controller.call('crossbar.node.{}.worker.{}.start_container_component'.format(self._node_id, worker_id), component_id, component, options=call_options)
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

                    yield self._controller.call('crossbar.node.{}.worker.{}.start_websocket_testee_transport'.format(self._node_id, worker_id), transport_id, transport, options=call_options)
                    self.log.info("{}: transport '{}' started".format(worker_logname, transport_id))

                else:
                    raise Exception("logic error")

            elif worker_type == 'guest':

                # start guest worker
                #
                yield self._controller.start_guest(worker_id, worker, details=call_details)
                self.log.info("{worker}: started", worker=worker_logname)

            else:
                raise Exception("logic error")
