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

from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceSession
from crossbar.worker.router import RouterRealm
from crossbar.common import checkconfig
from crossbar.controller.process import NodeControllerSession
from crossbar.controller.management import NodeManagementBridgeSession
from crossbar.controller.management import NodeManagementSession


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

        # node private key autobahn.wamp.cryptosign.SigningKey
        self._node_key = None

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
                self.log.info("Node public key file {} not found - re-creating from node private key file {}".format(pubkey_path, privkey_path))
                pub_tags = OrderedDict([
                    (u'creator', priv_tags[u'creator']),
                    (u'created-at', priv_tags[u'created-at']),
                    (u'machine-id', priv_tags[u'machine-id']),
                    (u'public-key-ed25519', pubkey_hex),
                ])
                msg = u'Crossbar.io public key for node authentication\n\n'
                _write_node_key(pubkey_path, pub_tags, msg)

            self.log.debug("Node key already exists (public key: {})".format(pubkey_hex))

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
            msg = u'Crossbar.io public key for node authentication\n\n'
            _write_node_key(pubkey_path, tags, msg)

            # now, add the private key and write the private file
            tags[u'private-key-ed25519'] = privkey_hex
            msg = u'Crossbar.io private key for node authentication - KEEP THIS SAFE!\n\n'
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

        if cdc_mode:
            cdc_config = controller_config.get('cdc', {

                # CDC connecting transport
                u'transport': {
                    u'type': u'websocket',
                    u'url': u'wss://devops.crossbario.com/ws',
                    u'endpoint': {
                        u'type': u'tcp',
                        u'host': u'devops.crossbario.com',
                        u'port': 443,
                        u'timeout': 5,
                        u'tls': {
                            u'hostname': u'devops.crossbario.com'
                        }
                    }
                }
            })

            transport = cdc_config[u'transport']
            hostname = None
            if u'tls' in transport[u'endpoint']:
                transport[u'endpoint'][u'tls'][u'hostname']

            # extra info forwarded to CDC client session
            extra = {
                'node': self,
                'onready': Deferred(),
                'onexit': Deferred(),
                'node_key': self._node_key,
            }

            runner = ApplicationRunner(
                url=transport['url'],
                realm=None,
                extra=extra,
                ssl=optionsForClientTLS(hostname) if hostname else None,
            )

            try:
                self.log.info("Connecting to CDC at '{url}' ..", url=transport[u'url'])
                yield runner.run(NodeManagementSession, start_reactor=False, auto_reconnect=True)

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
