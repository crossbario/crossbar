##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import sys
import os
import json
import pkg_resources
from collections import OrderedDict

import click
import psutil

import txaio
from txaio import make_logger

from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.ssl import optionsForClientTLS
from twisted.internet.task import LoopingCall

from autobahn import wamp
from autobahn.twisted.util import sleep
from autobahn.twisted.wamp import ApplicationRunner
from autobahn.wamp.types import ComponentConfig, CallOptions
from autobahn.wamp.exception import ApplicationError
from autobahn.websocket.util import parse_url

from crossbar._util import hl, hltype, hlid
from crossbar.common import checkconfig
from crossbar.node import node, controller

from crossbar.edge.node.management import NodeManagementBridgeSession, NodeManagementSession

try:
    from crossbar.edge.node.docker import DockerClient
    _HAS_DOCKER = True
except ImportError:
    _HAS_DOCKER = False

_ALLOWED_ACTIVATION_TAGS = [
    'created-at', 'management-url', 'management-realm', 'management-realm-oid', 'node-oid', 'node-authid',
    'node-cluster-ip', 'activation-code', 'public-key-ed25519'
]


def _parse_activation_file(path):
    """
    Internal helper. This parses a ``key.activation`` file and returns a dict mapping tags -> values.

    .. code-block::console

        Crossbar.io node activation

        created-at: 2020-07-05T11:49:59.125Z
        management-url: ws://localhost:9000/ws
        management-realm: default
        management-realm-oid: 6e8117fb-5bd8-4e83-860c-decefa1e95ac
        node-oid: 664e99a6-6a65-4f64-a95e-46ac9c28c80e
        node-authid: node-664e99
        activation-code: P33W-GS4H-5L4Q
        public-key-ed25519: 22c6e16005dfb0824466e35ae4b4f71746230628c2dec233f3b8cba22c4acce8
    """
    if not os.path.exists(path):
        raise Exception('activation file path "{}" does not exist'.format(path))

    if not os.path.isfile(path):
        raise Exception('activation file path "{}" exists, but is not a file'.format(path))

    tags = OrderedDict()
    with open(path, 'r') as key_file:
        got_blankline = False
        for line in key_file.readlines():
            if line.strip() == '':
                got_blankline = True
            elif got_blankline:
                tag, value = line.split(':', 1)
                tag = tag.strip().lower()
                value = value.strip()
                if tag not in _ALLOWED_ACTIVATION_TAGS:
                    raise Exception('invalid tag "{}" in activation file "{}"'.format(tag, path))
                if tag in tags:
                    raise Exception('duplicate tag "{}" in activation file "{}"'.format(tag, path))
                tags[tag] = value
    return tags


class FabricNodeControllerSession(controller.NodeController):
    """
    This is the central node controller for CF nodes.

    It derives of the node controller base class in CB and adds
    the following functionality exposed to CFC:

    - can manage a host Docker daemon
    """
    # yapf: disable
    log = make_logger()

    def onUserError(self, fail, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.ISession.onUserError`
        """
        if isinstance(fail.value, ApplicationError):
            self.log.debug('{klass}.onUserError(): "{msg}"',
                           klass=self.__class__.__name__,
                           msg=fail.value.error_message())
        else:
            self.log.error(
                '{klass}.onUserError(): "{msg}"\n{traceback}',
                klass=self.__class__.__name__,
                msg=msg,
                traceback=txaio.failure_format_traceback(fail),
            )

    def __init__(self, node):
        controller.NodeController.__init__(self, node)

        # Docker client used for exposing the host Docker
        # daemon via the node management API.
        self._docker_client = None

    def onConnect(self):
        # attach to host docker daemon
        if _HAS_DOCKER:
            if self._node._enable_docker:
                if os.path.exists('/run/docker.sock'):
                    self._docker_client = DockerClient(self._node._reactor, self)
                    self._docker_client.startup()
                else:
                    self.log.warn('Docker daemon integration enabled, but Docker Unix domain socket path cannot be accessed!')
            else:
                self.log.info('Docker daemon integration disabled!')
        else:
            self.log.info('Docker unavailable or unsupported!')

        controller.NodeController.onConnect(self)

    @inlineCallbacks
    def _shutdown(self, restart=False, mode=None):
        # override base class method (without calling the base method) ..

        self.log.info('{klass}._shutdown(restart={restart}, mode={mode})',
                      klass=self.__class__.__name__, restart=restart, mode=mode)

        if self._node._manager_runner:
            self.log.warn('Stopping management uplink ..')
            yield self._node._manager_runner.stop()
            self._node._manager = None
            self._node._manager_runner = None

        if self._docker_client:
            yield self._docker_client.shutdown()
            self._docker_client = None

    @wamp.register(None)
    def get_status(self, details=None):
        """
        Return basic information about this node.

        :returns: Information on the Crossbar.io node.
        :rtype: dict
        """
        status = super(FabricNodeControllerSession, self).get_status(details=details)
        status.update({
            # the following come from CFC (and are only filled
            # when the node personality is FABRIC!)
            'management_realm':
            self._node._management_realm,
            'management_node_id':
            self._node._node_id,
            'management_session_id':
            self._node._manager._session_id if self._node._manager else None,
            'management_node_extra':
            self._node._node_extra,

            # True if remote Docker management is available
            'has_docker':
            self._docker_client is not None
        })
        return status

    #
    # Docker support
    # https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#docker-control
    #
    def _ensure_docker(self):
        if not self._docker_client:
            raise ApplicationError("crossbar.error.feature_unavailable",
                                   "Docker not available or Docker daemon integration not enabled")

    @wamp.register(None)
    @inlineCallbacks
    def get_docker_info(self, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerget_info
        """
        self._ensure_docker()
        return (yield self._docker_client.get_info())

    @wamp.register(None)
    @inlineCallbacks
    def get_docker_ping(self, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerget_ping
        """
        self._ensure_docker()
        return (yield self._docker_client.ping())

    @wamp.register(None)
    @inlineCallbacks
    def get_docker_version(self, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerget_version
        """
        self._ensure_docker()
        return (yield self._docker_client.version())

    @wamp.register(None)
    @inlineCallbacks
    def get_docker_df(self, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerget_df
        """
        self._ensure_docker()
        return (yield self._docker_client.df())

    @wamp.register(None)
    @inlineCallbacks
    def get_docker_containers(self, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerget_containers
        """
        self._ensure_docker()
        return (yield self._docker_client.get_containers())

    @wamp.register(None)
    @inlineCallbacks
    def get_docker_container(self, container_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerget_container
        """
        self._ensure_docker()
        return (yield self._docker_client.get_container(container_id))

    @wamp.register(None)
    @inlineCallbacks
    def start_docker_container(self, container_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerstart_container
        """
        self._ensure_docker()
        return (yield self._docker_client.start(container_id))

    @wamp.register(None)
    @inlineCallbacks
    def create_docker_container(self, image, config={}, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockercreate_container
        """
        self._ensure_docker()
        return (yield self._docker_client.create(image, config))

    @wamp.register(None)
    @inlineCallbacks
    def stop_docker_container(self, container_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerstop_container
        """
        self._ensure_docker()
        return (yield self._docker_client.container(container_id, 'stop'))

    @wamp.register(None)
    @inlineCallbacks
    def restart_docker_container(self, container_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerrestart_container
        """
        self._ensure_docker()
        return (yield self._docker_client.restart(container_id))

    @wamp.register(None)
    @inlineCallbacks
    def destroy_docker_container(self, container_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerremove_container
        """
        self._ensure_docker()
        return (yield self._docker_client.container(container_id, 'remove'))

    @wamp.register(None)
    @inlineCallbacks
    def pause_docker_container(self, container_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerpause_container
        """
        self._ensure_docker()
        return (yield self._docker_client.container(container_id, 'pause'))

    @wamp.register(None)
    @inlineCallbacks
    def unpause_docker_container(self, container_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerunpause_container
        """
        self._ensure_docker()
        return (yield self._docker_client.container(container_id, 'unpause'))

    @wamp.register(None)
    def request_docker_tty(self, id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerrequest_tty`
        """
        self._ensure_docker()
        return self._docker_client.request_tty(id)

    @wamp.register(None)
    @inlineCallbacks
    def watch_docker_container(self, container_id, tty_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerwatch_container
        """
        self._ensure_docker()
        return (yield self._docker_client.watch(container_id, tty_id))

    @wamp.register(None)
    @inlineCallbacks
    def shell_docker_container(self, container_id, tty_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockershell_container
        """
        self._ensure_docker()
        return (yield self._docker_client.shell(container_id, tty_id))

    @wamp.register(None)
    @inlineCallbacks
    def backlog_docker_container(self, container_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerbacklog_container
        """
        self._ensure_docker()
        return (yield self._docker_client.backlog(container_id))

    @wamp.register(None)
    @inlineCallbacks
    def keystroke_docker_container(self, container_id, data, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerkeystroke_container
        """
        self._ensure_docker()
        return (yield self._docker_client.keystroke(container_id, data))

    @wamp.register(None)
    @inlineCallbacks
    def get_docker_images(self, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerget_images
        """
        self._ensure_docker()
        return (yield self._docker_client.get_images())

    @wamp.register(None)
    @inlineCallbacks
    def delete_docker_image(self, image_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerdelete_image
        """
        self._ensure_docker()
        return (yield self._docker_client.delete_image(image_id))

    @wamp.register(None)
    @inlineCallbacks
    def get_docker_image(self, image_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerget_image
        """
        self._ensure_docker()
        return (yield self._docker_client.get_image(image_id))

    @wamp.register(None)
    @inlineCallbacks
    def remove_docker_image(self, image_id, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerremove_image
        """
        self._ensure_docker()
        return (yield self._docker_client.image(image_id, 'remove'))

    @wamp.register(None)
    @inlineCallbacks
    def prune_docker_images(self, filter, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerprune_image
        """
        self._ensure_docker()
        return (yield self._docker_client.prune(filter))

    @wamp.register(None)
    @inlineCallbacks
    def fs_docker_open(self, id, path, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerfsopen
        """
        self._ensure_docker()
        return (yield self._docker_client.fs_open(id, path))

    @wamp.register(None)
    @inlineCallbacks
    def fs_docker_get(self, id, path, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerfsget
        """
        self._ensure_docker()
        return (yield self._docker_client.fs_get(id, path))

    @wamp.register(None)
    @inlineCallbacks
    def fs_docker_put(self, id, path, data, details=None):
        """
        https://github.com/crossbario/crossbar-fabric-public/blob/master/docs/api/Management-API.md#crossbarfabriccenterremotedockerfsput
        """
        self._ensure_docker()
        return (yield self._docker_client.fs_put(id, path, data))


def compute_mgmt_uplink_config(log, cbdir, config, fn_reboot=None, use_activation_file=True, use_default_fabric=False):
    """
    Determine the transport configuration of the management uplink for this node
    in the following order (using the first one that succeeds):

    * node activation file
    * management URL environment variable
    * node configuration file
    * built-in default ("master.xbr.network")

    :param cbdir:
    :param config:
    :param fn_reboot:
    :param use_activation_file:
    :param use_default_fabric:
    :return:
    """
    fabric_transport_config = None

    # [1] pick up auto-activation files dropped by a master node (`${CBDIR}/key.activate`)
    if not fabric_transport_config and use_activation_file:
        def do_check_for_activation_file(activation_file, reboot_on_discover):
            if os.path.isfile(activation_file):
                tags = _parse_activation_file(activation_file)
                is_secure, hostname, port, _, _, _ = parse_url(tags['management-url'])
                config = {
                    'type': 'websocket',
                    'url': tags['management-url'],
                    'endpoint': {
                        'type': 'tcp',
                        'host': hostname,
                        'port': port,
                        'timeout': 5
                    }
                }
                if is_secure:
                    config['endpoint']['tls'] = {
                        'hostname': hostname
                    }
                _msg = 'Found auto-activation file "{}", using management URL "{}" - [1]'.format(activation_file,
                                                                                                 config['url'])
                log.info(click.style(_msg, fg='red', bold=True))

                if reboot_on_discover and fn_reboot:
                    # stop the node and enforce complete reboot - which will then pick up the new configuration
                    fn_reboot()

                # return the management uplink transport configuration, as derived from the activation file
                return config

        # an activation file must be placed next to the node key pair (key.pub, key.priv)
        activation_file = os.path.join(cbdir, 'key.activate')

        # check and maybe load config from activation file
        fabric_transport_config = do_check_for_activation_file(activation_file, reboot_on_discover=False)

        # if there wasn't an activation file, periodically check for ..
        if not fabric_transport_config:
            lc = LoopingCall(do_check_for_activation_file, activation_file, reboot_on_discover=True)
            lc.start(1)
            log.info('Looping call to check for node activation file started! - [1]')

    # [2] management uplink configured via env var
    if not fabric_transport_config:
        url = os.environ['CROSSBAR_FABRIC_URL'].strip() if 'CROSSBAR_FABRIC_URL' in os.environ else ''
        if url != '':
            secure, host, tcp_port, _, _, _ = parse_url(url)
            fabric_transport_config = {
                'type': 'websocket',
                'url': url,
                'endpoint': {
                    'type': 'tcp',
                    'host': host,
                    'port': tcp_port,
                    'timeout': 5
                }
            }
            if secure:
                fabric_transport_config['endpoint']['tls'] = {
                    'hostname': host
                }
            log.info(
                click.style('Using management uplink at "{}" (from envvar) - [2]'.format(url),
                            fg='red', bold=True))

    # [3] user has configured a custom management uplink in the node configuration
    if not fabric_transport_config:
        if 'controller' in config and 'fabric' in config['controller'] and config['controller']['fabric']:

            fabric_config = config['controller']['fabric']

            # allow to deactivate the management uplink connecting transport by setting "transport" to null
            fabric_transport_config = fabric_config.get('transport', None)

            if fabric_transport_config:
                url = fabric_transport_config.get('url', None)
                log.info(
                    click.style('Using management uplink at "{}" (from node configuration) - [3]'.format(url),
                                fg='red', bold=True))
            else:
                log.info(
                    click.style('Management uplink deactivated - [3]',
                                fg='red', bold=True))

    # [4] use hard-coded default management uplink
    if not fabric_transport_config and use_default_fabric:
        # default CFC (= our cloud hosted CFC service)
        fabric_transport_config = {
            'type': 'websocket',
            'url': 'wss://master.xbr.network/ws',
            'endpoint': {
                'type': 'tcp',
                'host': 'master.xbr.network',
                'port': 443,
                'timeout': 5,
                'tls': {
                    'hostname': 'master.xbr.network'
                }
            }
        }
        log.info(
            click.style(
                'Using default fabric controller at URL "{}" (from envvar) - [4]'.format(fabric_transport_config['url']),
                fg='red', bold=True))

    return fabric_transport_config


class FabricNode(node.Node):
    """
    Crossbar.io node personality.
    """
    DEFAULT_CONFIG_PATH = 'edge/node/config/bare.json'
    NODE_CONTROLLER = FabricNodeControllerSession

    def __init__(self, personality, cbdir=None, reactor=None, native_workers=None, options=None):
        node.Node.__init__(self, personality, cbdir, reactor, native_workers, options)

        # looping call that runs the node controller watchdog
        self._watchdog_looper = None

        # the node controller realm (where eg worker controller live). we explicitly use the
        # same realm as Crossbar.io OSS
        self._realm = 'crossbar'

        # enable docker daemon integration
        self._enable_docker = None

        # when running in managed mode, this will hold the bridge session
        # attached to the local management router
        self._bridge_session = None

        # if this node has a proper management uplink configured to connect to
        self._has_management_config = False

        # if this node was connected to its configured management uplink successfully at least once
        # during run-time (since last reboot) of this node
        self._was_management_connected = False

        # when we periodically check for a node activation file, the looping call for doing
        # the check - and automatically shutdown when an activation file was found (after boot)
        self._check_for_activation_file = None

        # when self._was_management_connected, the URL we've been connected to
        self._management_url = None

        # when running in managed mode, this will hold the management uplink session to
        # the crossbar master node
        self._manager = None
        self._manager_runner = None

        # the node's management realm when running in managed mode (this comes from CFC!)
        self._management_realm = None

        # the node's ID when running in managed mode (this comes from CFC!)
        self._node_id = None

        # node extra when running in managed mode (this comes from CFC!)
        self._node_extra = None

        # when the node starts up, it will connect to CFC, and then apply the
        # local node configuration, and this flag will be set. when the CFC connection
        # is lost, and then reestablished, the local node configuration should NOT
        # be applied a second time though - hence this flag
        self._local_config_applied = False

        # We really only need to see this once (?)
        self._displayed_pairing_message = False

        # for automatic ID assignment of "makers" within workers of type "xbrmm"
        self._maker_no = 1

    def load_config(self, configfile=None):
        """
        Check and load the node configuration from:

        * from ``.crossbar/config.json`` or
        * from built-in (empty) default configuration

        This is the _second_ function being called after the Node has been instantiated.

        IMPORTANT: this function is run _before_ start of Twisted reactor!
        """
        config_source = None
        config_path = None

        # if the node hasn't been configured from XBR network, fallback to loading config from local config file
        if not self._config:
            default_filename = pkg_resources.resource_filename('crossbar', self.DEFAULT_CONFIG_PATH)
            with open(default_filename) as f:
                default_config = json.load(f)
            config_source, config_path = node.Node.load_config(self, configfile, default_config)
            self.log.info('Node configuration loaded from {config_source} ({config_path})',
                          config_source=hlid(config_source),
                          config_path=hlid(config_path))

        # Docker host integration
        if _HAS_DOCKER and self._config and 'controller' in self._config:
            self._enable_docker = self._config['controller'].get('enable_docker', False)

        return config_source, config_path

    def _watchdog(self):
        # on Linux, check that we start with sufficient system entropy
        entropy_avail = None
        if sys.platform.startswith('linux'):
            try:
                with open('/proc/sys/kernel/random/entropy_avail', 'r') as ent:
                    entropy_avail = int(ent.read())
                    # FIXME: my machine never has more than ~ 300 units available, 1000 seems a little optomistic!
                    if entropy_avail < 64:
                        self.log.warn('WARNING: insufficient entropy ({} bytes) available - try installing rng-tools'.format(entropy_avail))
            except PermissionError:
                # this happens when packaged as a snap: the code prevented from reading a location
                # # that is not allowed to a confined snap package
                entropy_avail = -1

        # check for at least 100MB free memory
        mem_avail = psutil.virtual_memory().available // 2 ** 20
        if mem_avail < 100:
            self.log.warn('WARNING: available memory dropped to {mem_avail} MB', mem_avail=mem_avail)

        self.log.trace('WATCHDOG: entropy_avail {entropy_avail} bytes, mem_avail {mem_avail} MB',
                       entropy_avail=entropy_avail, mem_avail=mem_avail)

    @inlineCallbacks
    def start(self, node_id=None):
        self.log.info('{note} [{method}]',
                      note=hl('Starting node (initialize edge-node personality) ..', color='green', bold=True),
                      method=hltype(FabricNode.start))

        # run watchdog at 5Hz
        self._watchdog_looper = LoopingCall(self._watchdog)
        self._watchdog_looper.start(.2)

        res = yield node.Node.start(self, node_id or self._node_id)
        return res

    @inlineCallbacks
    def boot(self, use_activation_file=True, use_default_fabric=False):
        self.log.info('Booting node {method}', method=hltype(FabricNode.boot))

        def reboot():
            self.stop(restart=True)

        # determine the transport configuration of the management uplink for this node
        fabric_transport_config = compute_mgmt_uplink_config(self.log, self._cbdir, self._config, reboot,
                                                             use_activation_file=use_activation_file,
                                                             use_default_fabric=use_default_fabric)

        # now finally, if we do have a transport configuration for the management uplink at this point,
        # then start the management uplink ..
        if fabric_transport_config:

            self._has_management_config = True

            url = fabric_transport_config['url']
            hostname = None
            if 'tls' in fabric_transport_config.get('endpoint', {}):
                hostname = fabric_transport_config['endpoint']['tls']['hostname']

            self._manager_runner = ApplicationRunner(
                url=url,
                realm=None,
                extra=None,
                ssl=optionsForClientTLS(hostname) if hostname else None,
            )

            def make(config):
                # extra info forwarded to CFC client session
                extra = {
                    'node': self,
                    'on_ready': Deferred(),
                    'on_exit': Deferred(),
                }

                @inlineCallbacks
                def on_ready_success(res):
                    try:
                        self._manager, self._management_realm, self._management_session_id, self._node_id, self._node_extra = res
                        if self._bridge_session:
                            try:
                                yield self._bridge_session.attach_manager(
                                    self._manager, self._management_realm, self._node_id)
                            except:
                                self.log.failure()
                            else:
                                while True:
                                    try:
                                        # we actually test the management uplink by calling a procedure on the master
                                        yield self._manager.call('crossbarfabriccenter.mrealm.get_status')
                                    except ApplicationError as e:
                                        if e.error == 'wamp.error.no_such_procedure':
                                            self.log.info('Could not get master status ("wamp.error.no_such_procedure") - retrying in 5 secs ..')
                                        else:
                                            self.log.failure()
                                        yield sleep(5)
                                    except:
                                        self.log.failure()
                                        self.log.info('Could not get master status - retrying in 5 secs ..')
                                        yield sleep(5)
                                    else:
                                        self.log.info(
                                            click.style(
                                                'Connected to Crossbar.io Master at management realm "{realm}", set node ID "{node_id}" (extra={node_extra}, session_id={session_id})',
                                                fg='green',
                                                bold=True),
                                            realm=self._management_realm,
                                            node_id=self._node_id,
                                            node_extra=self._node_extra,
                                            session_id=self._manager._session_id)

                                        # if the management uplink was successfully established and tested once, mark it so
                                        if not self._was_management_connected:
                                            self._was_management_connected = True
                                            self._management_url = url

                                        try:
                                            worker_ids = yield self._bridge_session.call(
                                                'crossbar.get_workers')
                                            for worker_id in worker_ids:
                                                yield self._bridge_session.call(
                                                    'crossbar.worker.{}.set_node_id'.format(worker_id),
                                                    self._node_id)
                                        except:
                                            self.log.warn(
                                                'INTERNAL ERROR: could not set node_id "{node_id}" after CFC connection was established',
                                                node_id=self._node_id)
                                            self.log.failure()

                                        break
                        else:
                            self.log.warn(
                                'Uplink Crossbar.io Master session established, but no bridge session setup!'
                            )
                    except Exception as e:
                        self.log.warn('error in on_ready: {}'.format(e))

                    # ok, we are connected to CFC and normally will be configurated programmatically from there.
                    # however, it is still possible to apply any local node configuration by setting
                    #
                    # node_extra:
                    # {
                    #    "on_start_apply_config", true
                    # }
                    #
                    # node_extra comes from CFC and has to be configured there (when the node is paired)
                    #
                    if self._node_extra:

                        # by default, apply local config (from a node configuration file, if there is one)
                        on_start_apply_config = self._node_extra.get('on_start_apply_config', True)

                        if on_start_apply_config:
                            if not self._local_config_applied:
                                self.log.info('Applying local node configuration (on_start_apply_config is enabled)')
                                yield self.boot_from_config(self._config)
                                self._local_config_applied = True
                            else:
                                self.log.info('Local node configuration was already applied - skipping')
                    else:
                        self.log.info('Skipping any local node configuration (no local config or on_start_apply_config is "off")')

                def on_ready_error(err):
                    if isinstance(
                            err.value,
                            ApplicationError) and err.value.error in ['fabric.auth-failed.node-unpaired', 'fabric.auth-failed.node-already-connected']:

                        if not self._displayed_pairing_message:
                            self._displayed_pairing_message = True
                            self.log.error(
                                click.style(err.value.error_message().upper(), fg='red', bold=True))

                        self.stop()
                    else:
                        self.log.error(click.style(
                            'Could not connect to CFC: {error}', fg='red', bold=True), error=err.value
                        )

                @inlineCallbacks
                def on_exit_success(reason):
                    if self._bridge_session:
                        try:
                            yield self._bridge_session.detach_manager()
                        except:
                            self.log.failure()
                        else:
                            self.log.debug(
                                'Disconnected from Crossbar.io Master for management realm "{realm}"',
                                realm=self._management_realm)
                    else:
                        self.log.warn(
                            'Uplink Crossbar.io Master session lost, but no bridge session setup!')

                    self._manager, self._management_realm, self._management_session_id, self._node_id, self._node_extra = None, None, None, None, None

                def on_exit_error(err):
                    print(err)

                extra['on_ready'].addCallbacks(on_ready_success, on_ready_error)
                extra['on_exit'].addCallbacks(on_exit_success, on_exit_error)

                config = ComponentConfig(extra=extra)
                session = NodeManagementSession(self._manager_runner, config)
                return session

            self.log.info('Connecting to Crossbar.io Master at {url} ..', url=url)

            yield self._manager_runner.run(make, start_reactor=False, auto_reconnect=True)

        else:
            # here, we don't have a management uplink :(
            self.log.info(
                hl('No management uplink configured (running unmanaged/single-node)',
                   color='red',
                   bold=True))
            self._has_management_config = False

            # nevertheless, now boot from local node config!
            yield self.boot_from_config(self._config)
            self._local_config_applied = True

    def _add_extra_controller_components(self, controller_config):
        extra = {
            'node': self,
            'controller_config': controller_config,
        }
        cfg = ComponentConfig(self._realm, extra=extra)
        self._bridge_session = NodeManagementBridgeSession(cfg)
        router = self._router_factory.get(self._realm)
        self._router_session_factory.add(self._bridge_session, router, authrole='trusted')

    def _set_shutdown_triggers(self, controller_options):
        if 'shutdown' in controller_options:
            self._node_shutdown_triggers = controller_options['shutdown']
            self.log.info("Using node shutdown triggers {triggers} from configuration", triggers=self._node_shutdown_triggers)
        else:
            # NODE_SHUTDOWN_ON_SHUTDOWN_REQUESTED
            # NODE_SHUTDOWN_ON_WORKER_EXIT
            # NODE_SHUTDOWN_ON_WORKER_EXIT_WITH_ERROR
            # NODE_SHUTDOWN_ON_LAST_WORKER_EXIT

            # in managed mode, a node - by default - only shuts down when explicitly asked to,
            # or upon a fatal error in the node controller
            self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_SHUTDOWN_REQUESTED]

            self.log.info("Using default node shutdown triggers {triggers}", triggers=self._node_shutdown_triggers)

    def _add_worker_role(self, worker_auth_role, options):
        worker_role_config = {
            # each (native) worker is authenticated under a worker-specific authrole
            "name":
            worker_auth_role,
            "permissions": [
                # the worker requires these permissions to work:
                {
                    # management API provided by the worker. note that the worker management API is provided under
                    # the URI prefix "crossbar.worker.<worker_id>". note that the worker is also authenticated
                    # under authrole <worker_auth_role> on realm "crossbar"
                    "uri": worker_auth_role,
                    "match": "prefix",
                    "allow": {
                        "call": True,
                        "register": True,
                        "publish": True,
                        "subscribe": True
                    },
                    "disclose": {
                        "caller": True,
                        "publisher": True
                    },
                    "cache": True
                },
                {
                    # controller procedure called by the worker (to check for controller status)
                    "uri": "crossbar.get_status",
                    "match": "exact",
                    "allow": {
                        "call": True,
                        "register": False,
                        "publish": False,
                        "subscribe": False
                    },
                    "disclose": {
                        "caller": True,
                        "publisher": True
                    },
                    "cache": True
                }
            ]
        }
        # if configured to expose the controller connection within the worker (to make it available
        # in user code such as dynamic authenticators and router/container components), also add
        # permissions to actually use the (local) node management API
        if options.get('expose_controller', True):
            vendor_permissions = {
                "uri": "crossbar.",
                "match": "prefix",
                "allow": {
                    "call": True,
                    "register": False,
                    "publish": False,
                    "subscribe": True
                },
                "disclose": {
                    "caller": True,
                    "publisher": True
                },
                "cache": True
            }
            worker_role_config["permissions"].append(vendor_permissions)
            vendor_permissions = {
                "uri": "crossbarfabriccenter.",
                "match": "prefix",
                "allow": {
                    "call": True,
                    "register": True,
                    "publish": True,
                    "subscribe": True
                },
                "disclose": {
                    "caller": True,
                    "publisher": True
                },
                "cache": True
            }
            worker_role_config["permissions"].append(vendor_permissions)

        self._router_factory.add_role(self._realm, worker_role_config)

        self.log.info(
            'worker-specific role "{authrole}" added on node management router realm "{realm}" {func}',
            func=hltype(self._add_worker_role),
            authrole=hlid(worker_role_config['name']),
            realm=hlid(self._realm))

    def _extend_worker_args(self, args, options):
        if 'expose_shared' in options and options['expose_shared']:
            args.extend(['--expose_shared=true'])
        if 'expose_controller' in options and options['expose_controller']:
            args.extend(['--expose_controller=true'])

    @inlineCallbacks
    def _configure_native_worker_connections(self, worker_logname, worker_id, worker):
        # start connections (such as PostgreSQL database connection pools)
        # to run embedded in the router
        for connection in worker.get('connections', []):

            if 'id' in connection:
                connection_id = connection.pop('id')
            else:
                connection_id = 'connection{:03d}'.format(self._connection_no)
                self._connection_no += 1

            yield self._controller.call('crossbar.worker.{}.start_connection'.format(worker_id), connection_id, connection, options=CallOptions())
            self.log.info(
                "{logname}: connection '{connection}' started",
                logname=worker_logname,
                connection=connection_id,
            )

    @inlineCallbacks
    def _configure_native_worker_router(self, worker_logname, worker_id, worker):
        # setup db connection pool
        yield self._configure_native_worker_connections(worker_logname, worker_id, worker)

        # in this case, call the base class method _after_ above - because we want db connections
        # to be available when router/container components might start ..
        yield node.Node._configure_native_worker_router(self, worker_logname, worker_id, worker)

    @inlineCallbacks
    def _configure_native_worker_container(self, worker_logname, worker_id, worker):
        # setup db connection pool
        yield self._configure_native_worker_connections(worker_logname, worker_id, worker)

        # in this case, call the base class method _after_ above - because we want db connections
        # to be available when router/container components might start ..
        yield node.Node._configure_native_worker_container(self, worker_logname, worker_id, worker)

    @inlineCallbacks
    def _configure_native_worker_hostmonitor(self, worker_logname, worker_id, worker):
        # after the native worker has started, and the HostMonitor controller session
        # has attached to the local node router, we need to do the following, if we
        # want it to work _also_ from a local node config.json. driving from CFC
        # at run-time always works (also without the bits here)

        # 1. the native workers' common options are configured by calling into the worker
        yield self._configure_native_worker_common(worker_logname, worker_id, worker)

        # 2. the host monitor specific actions need to be done, namely, starting the monitoring
        monitoring_config = worker.get('monitor', None)
        yield self._controller.call('crossbar.worker.{}.start_monitoring'.format(worker_id), monitoring_config, options=CallOptions())

    @inlineCallbacks
    def _configure_native_worker_xbrmm(self, worker_logname, worker_id, worker):
        # 1. configure native workers' common options
        yield self._configure_native_worker_common(worker_logname, worker_id, worker)

        # 2. configure market makers (defined within the xbrmm worker)
        for maker in worker.get('makers', []):
            if 'id' in maker:
                maker_id = maker.pop('id')
            else:
                maker_id = 'maker{:03d}'.format(self._maker_no)
                self._maker_no += 1
            maker['id'] = maker_id
            yield self._controller.call('crossbar.worker.{}.start_market_maker'.format(worker_id), maker_id, maker, options=CallOptions())
