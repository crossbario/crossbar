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
import socket
import getpass
import pkg_resources
import binascii
import six
import subprocess
from collections import OrderedDict

import pyqrcode

from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

import twisted
from twisted.internet.defer import inlineCallbacks
from twisted.python.runtime import platform
from twisted.python.reflect import qual

from txaio import make_logger

from autobahn.util import utcnow
from autobahn.wamp import cryptosign
from autobahn.wamp.types import CallOptions, ComponentConfig
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.cryptosign import _read_signify_ed25519_pubkey, _qrcode_from_signify_ed25519_pubkey

import crossbar
from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceSession
from crossbar.worker.router import RouterRealm
from crossbar.worker.router import RouterWorkerSession
from crossbar.common import checkconfig
from crossbar.controller.process import NodeControllerSession
from crossbar.controller.processtypes import RouterWorkerProcess
from crossbar.controller.processtypes import ContainerWorkerProcess
from crossbar.controller.processtypes import WebSocketTesteeWorkerProcess
from crossbar.worker.container import ContainerWorkerSession
from crossbar.worker.testee import WebSocketTesteeWorkerSession


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
    if platform.isLinux():
        try:
            # why this? see: http://0pointer.de/blog/projects/ids.html
            with open('/var/lib/dbus/machine-id', 'r') as f:
                return f.read().strip()
        except:
            # Non-dbus using Linux, get a hostname
            return socket.gethostname()

    elif platform.isMacOSX():
        # Get the serial number of the platform
        import plistlib
        plist_data = subprocess.check_output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice", "-a"])

        if six.PY2:
            # Only API on 2.7
            return plistlib.readPlistFromString(plist_data)[0]["IOPlatformSerialNumber"]
        else:
            # New, non-deprecated 3.4+ API
            return plistlib.loads(plist_data)[0]["IOPlatformSerialNumber"]

    else:
        # Something else, just get a hostname
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
            if value is None:
                value = 'unknown'
            f.write(u'{}: {}\n'.format(tag, value))


def default_native_workers():
    factory = dict()
    factory['router'] = {
        'class': RouterWorkerProcess,
        'worker_class': RouterWorkerSession,

        # check a whole router worker configuration item (including realms, transports, ..)
        'checkconfig_item': checkconfig.check_router,

        # only check router worker options
        'checkconfig_options': checkconfig.check_router_options,

        'logname': 'Router',
        'topics': {
            'starting': u'crossbar.node.on_router_starting',
            'started': u'crossbar.node.on_router_started',
        }
    }
    factory['container'] = {
        'class': ContainerWorkerProcess,
        'worker_class': ContainerWorkerSession,

        # check a whole container worker configuration item (including components, ..)
        'checkconfig_item': checkconfig.check_container,

        # only check container worker options
        'checkconfig_options': checkconfig.check_container_options,

        'logname': 'Container',
        'topics': {
            'starting': u'crossbar.node.on_container_starting',
            'started': u'crossbar.node.on_container_started',
        }
    }
    factory['websocket-testee'] = {
        'class': WebSocketTesteeWorkerProcess,
        'worker_class': WebSocketTesteeWorkerSession,

        # check a whole websocket testee worker configuration item
        'checkconfig_item': checkconfig.check_websocket_testee_options,

        # only check websocket testee worker worker options
        'checkconfig_options': checkconfig.check_websocket_testee_options,

        'logname': 'WebSocketTestee',
        'topics': {
            'starting': u'crossbar.node.on_websocket_testee_starting',
            'started': u'crossbar.node.on_websocket_testee_started',
        }
    }
    return factory


class Node(object):
    """
    Crossbar.io Community node personality.
    """

    # http://patorjk.com/software/taag/#p=display&h=1&f=Stick%20Letters&t=Crossbar.io
    BANNER = r"""     __  __  __  __  __  __      __     __
    /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
    \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/

"""
    PERSONALITY = "Crossbar.io COMMUNITY"

    NODE_CONTROLLER = NodeControllerSession

    ROUTER_SERVICE = RouterServiceSession

    _native_workers = default_native_workers()

    # A Crossbar.io node is the running a controller process and one or multiple
    # worker processes.
    # A single Crossbar.io node runs exactly one instance of this class, hence
    # this class can be considered a system singleton.

    log = make_logger()

    def __init__(self, cbdir=None, reactor=None, native_workers=None):
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

        # allow overriding to add (or remove) native-worker types
        if native_workers is not None:
            self._native_workers = native_workers

        # the node controller realm
        self._realm = u'crossbar'

        # config of this node.
        self._config = None

        # node private key autobahn.wamp.cryptosign.SigningKey
        self._node_key = None

        # when running in managed mode, this will hold the uplink session to CFC
        self._manager = None

        # the node's management realm when running in managed mode (this comes from CFC!)
        self._management_realm = None

        # the node's ID when running in managed mode (this comes from CFC!)
        self._node_id = None

        # node extra when running in managed mode (this comes from CFC!)
        self._node_extra = None

        # node controller session (a singleton ApplicationSession embedded
        # in the local node router)
        self._controller = None

        # node shutdown triggers, one or more of checkconfig.NODE_SHUTDOWN_MODES
        self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT]

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
        or load built-in empty config.
        """
        if configfile:
            configpath = os.path.abspath(os.path.join(self._cbdir, configfile))

            self.log.debug('Loading node configuration from "{configpath}" ..',
                           configpath=configpath)

            # the following will read the config, check the config and replace
            # environment variable references in configuration values ("${MYVAR}") and
            # finally return the parsed configuration object
            self._config = checkconfig.check_config_file(configpath, self._native_workers)

            self.log.info('Node configuration loaded from "{configpath}"',
                          configpath=configpath)
        else:
            self._config = {
                u'version': 2,
                u'controller': {},
                u'workers': []
            }
            checkconfig.check_config(self._config, self._native_workers)
            self.log.info('Node configuration loaded from built-in config.')

    def _add_global_roles(self):
        self.log.info('No extra node router roles')

    def _add_worker_role(self, worker_auth_role, options):
        worker_role_config = {
            u"name": worker_auth_role,
            u"permissions": [
                # the worker requires these permissions to work:
                {
                    # worker_auth_role: "crossbar.worker.worker-001"
                    u"uri": worker_auth_role,
                    u"match": u"prefix",
                    u"allow": {
                        u"call": False,
                        u"register": True,
                        u"publish": True,
                        u"subscribe": False
                    },
                    u"disclose": {
                        u"caller": False,
                        u"publisher": False
                    },
                    u"cache": True
                },
                {
                    u"uri": u"crossbar.get_status",
                    u"match": u"exact",
                    u"allow": {
                        u"call": True,
                        u"register": False,
                        u"publish": False,
                        u"subscribe": False
                    },
                    u"disclose": {
                        u"caller": False,
                        u"publisher": False
                    },
                    u"cache": True
                }
            ]
        }
        self._router_factory.add_role(self._realm, worker_role_config)

    def _drop_worker_role(self, worker_auth_role):
        self._router_factory.drop_role(self._realm, worker_auth_role)

    def _extend_worker_args(self, args, options):
        pass

    def _add_extra_controller_components(self, controller_options):
        pass

    def _set_shutdown_triggers(self, controller_options):
        # allow to override node shutdown triggers
        #
        if 'shutdown' in controller_options:
            self._node_shutdown_triggers = controller_options['shutdown']
            self.log.info("Using node shutdown triggers {triggers} from configuration", triggers=self._node_shutdown_triggers)
        else:
            self._node_shutdown_triggers = [checkconfig.NODE_SHUTDOWN_ON_WORKER_EXIT]
            self.log.info("Using default node shutdown triggers {triggers}", triggers=self._node_shutdown_triggers)

    @inlineCallbacks
    def start(self):
        """
        Starts this node. This will start a node controller and then spawn new worker
        processes as needed.
        """
        if not self._config:
            raise Exception("No node configuration set")

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

        # local node management router
        #
        self._router_factory = RouterFactory(self._node_id, None)
        self._router_session_factory = RouterSessionFactory(self._router_factory)
        rlm_config = {
            'name': self._realm
        }
        rlm = RouterRealm(None, rlm_config)
        router = self._router_factory.start_realm(rlm)

        # setup global static roles
        #
        self._add_global_roles()

        # always add a realm service session
        #
        cfg = ComponentConfig(self._realm)
        rlm.session = (self.ROUTER_SERVICE)(cfg, router)
        self._router_session_factory.add(rlm.session, authrole=u'trusted')
        self.log.debug('Router service session attached [{router_service}]', router_service=qual(self.ROUTER_SERVICE))

        # add the node controller singleton component
        #
        self._controller = self.NODE_CONTROLLER(self)

        self._router_session_factory.add(self._controller, authrole=u'trusted')
        self.log.debug('Node controller attached [{node_controller}]', node_controller=qual(self.NODE_CONTROLLER))

        # add extra node controller components
        #
        self._add_extra_controller_components(controller_options)

        # setup Node shutdown triggers
        #
        self._set_shutdown_triggers(controller_options)

        panic = False
        try:
            # startup the node personality ..
            yield self._startup()

            # .. and notify systemd that we are fully up and running
            try:
                import sdnotify
                sdnotify.SystemdNotifier().notify("READY=1")
            except:
                # do nothing on non-systemd platforms
                pass

        except ApplicationError as e:
            panic = True
            self.log.error("{msg}", msg=e.error_message())

        except Exception:
            panic = True
            self.log.failure()
            self.log.error('fatal: could not startup node')

        if panic:
            try:
                self._reactor.stop()
            except twisted.internet.error.ReactorNotRunning:
                pass

    def _startup(self):
        return self._configure_node_from_config(self._config)

    @inlineCallbacks
    def _configure_node_from_config(self, config):
        """
        Startup elements in the node as specified in the provided node configuration.
        """
        self.log.info('Configuring node from local configuration ...')

        # get contoller configuration subpart
        controller = config.get('controller', {})

        # start Manhole in node controller
        if 'manhole' in controller:
            yield self._controller.call(u'crossbar.start_manhole', controller['manhole'], options=CallOptions())
            self.log.debug("controller: manhole started")

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
                worker_id = u'worker-{:03d}'.format(self._worker_no)
                self._worker_no += 1

            # worker type: either a native worker ('router', 'container', ..), or a guest worker ('guest')
            worker_type = worker['type']

            # native worker processes setup
            if worker_type in self._native_workers:

                # set logname depending on native worker type
                worker_logname = '{} "{}"'.format(self._native_workers[worker_type]['logname'], worker_id)

                # any worker specific options
                worker_options = worker.get('options', {})

                # now actually start the (native) worker ..
                yield self._controller.call(u'crossbar.start_worker', worker_id, worker_type, worker_options, options=CallOptions())

                # setup native worker generic stuff
                method_name = '_configure_native_worker_{}'.format(worker_type.replace('-', '_'))
                try:
                    config_fn = getattr(self, method_name)
                except AttributeError:
                    raise ValueError(
                        "A native worker of type '{}' is configured but "
                        "there is no method '{}' on {}".format(worker_type, method_name, type(self))
                    )
                yield config_fn(worker_logname, worker_id, worker)

            # guest worker processes setup
            elif worker_type == u'guest':

                # now actually start the (guest) worker ..

                # FIXME: start_worker() takes the whole configuration item for guest workers, whereas native workers
                # only take the options (which is part of the whole config item for the worker)
                yield self._controller.call(u'crossbar.start_worker', worker_id, worker_type, worker, options=CallOptions())

            else:
                raise Exception('logic error: unexpected worker_type="{}"'.format(worker_type))

        self.log.info('Local node configuration applied successfully!')

    @inlineCallbacks
    def _configure_native_worker_common(self, worker_logname, worker_id, worker):
        # expanding PYTHONPATH of the newly started worker is now done
        # directly in NodeControllerSession._start_native_worker
        worker_options = worker.get('options', {})
        if False:
            if 'pythonpath' in worker_options:
                added_paths = yield self._controller.call(u'crossbar.worker.{}.add_pythonpath'.format(worker_id), worker_options['pythonpath'], options=CallOptions())
                self.log.warn("{worker}: PYTHONPATH extended for {paths}",
                              worker=worker_logname, paths=added_paths)

        # FIXME: as the CPU affinity is in the worker options, this _also_ (see above fix)
        # should be done directly in NodeControllerSession._start_native_worker
        if True:
            if 'cpu_affinity' in worker_options:
                new_affinity = yield self._controller.call(u'crossbar.worker.{}.set_cpu_affinity'.format(worker_id), worker_options['cpu_affinity'], options=CallOptions())
                self.log.debug("{worker}: CPU affinity set to {affinity}",
                               worker=worker_logname, affinity=new_affinity)

        # this is fine to start after the worker has been started, as manhole is
        # CB developer/support feature anyways (like a vendor diagnostics port)
        if 'manhole' in worker:
            yield self._controller.call(u'crossbar.worker.{}.start_manhole'.format(worker_id), worker['manhole'], options=CallOptions())
            self.log.debug("{worker}: manhole started",
                           worker=worker_logname)

    @inlineCallbacks
    def _configure_native_worker_router(self, worker_logname, worker_id, worker):
        yield self._configure_native_worker_common(worker_logname, worker_id, worker)

        # start realms on router
        for realm in worker.get('realms', []):

            # start realm
            if 'id' in realm:
                realm_id = realm.pop('id')
            else:
                realm_id = 'realm-{:03d}'.format(self._realm_no)
                self._realm_no += 1

            yield self._controller.call(u'crossbar.worker.{}.start_router_realm'.format(worker_id), realm_id, realm, options=CallOptions())
            self.log.info("{worker}: realm '{realm_id}' (named '{realm_name}') started",
                          worker=worker_logname, realm_id=realm_id, realm_name=realm['name'])

            # add roles to realm
            for role in realm.get('roles', []):
                if 'id' in role:
                    role_id = role.pop('id')
                else:
                    role_id = 'role-{:03d}'.format(self._role_no)
                    self._role_no += 1

                yield self._controller.call(u'crossbar.worker.{}.start_router_realm_role'.format(worker_id), realm_id, role_id, role, options=CallOptions())
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

                yield self._controller.call(u'crossbar.worker.{}.start_router_realm_uplink'.format(worker_id), realm_id, uplink_id, uplink, options=CallOptions())
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

            yield self._controller.call(u'crossbar.worker.{}.start_connection'.format(worker_id), connection_id, connection, options=CallOptions())
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

            yield self._controller.call(u'crossbar.worker.{}.start_router_component'.format(worker_id), component_id, component, options=CallOptions())
            self.log.info(
                "{logname}: component '{component}' started",
                logname=worker_logname,
                component=component_id,
            )

        # start transports on router
        for transport in worker.get('transports', []):

            if 'id' in transport:
                transport_id = transport.pop('id')
            else:
                transport_id = 'transport-{:03d}'.format(self._transport_no)
                self._transport_no += 1

            add_paths_on_transport_create = False

            yield self._controller.call(u'crossbar.worker.{}.start_router_transport'.format(worker_id),
                                        transport_id,
                                        transport,
                                        add_paths=add_paths_on_transport_create,
                                        options=CallOptions())
            self.log.info(
                "{logname}: transport '{tid}' started",
                logname=worker_logname,
                tid=transport_id,
            )

            if not add_paths_on_transport_create:

                if transport['type'] == 'web':
                    paths = transport.get('paths', {})
                elif transport['type'] == 'universal':
                    paths = transport.get('web', {}).get('paths', {})
                else:
                    paths = None

                if paths:
                    for path in sorted(paths):
                        if path != '/':
                            config = paths[path]
                            yield self._controller.call(u'crossbar.worker.{}.start_web_transport_service'.format(worker_id),
                                                        transport_id,
                                                        path,
                                                        config,
                                                        options=CallOptions())
                            self.log.info(
                                "{logname}: web service '{path_type}' started on path '{path}' on transport '{tid}'",
                                logname=worker_logname,
                                path_type=config['type'],
                                path=path,
                                tid=transport_id,
                            )

    @inlineCallbacks
    def _configure_native_worker_container(self, worker_logname, worker_id, worker):
        yield self._configure_native_worker_common(worker_logname, worker_id, worker)

        # if components exit "very soon after" we try to start them,
        # we consider that a failure and shut our node down. We remove
        # this subscription 2 seconds after we're done starting
        # everything (see below). This is necessary as start_component
        # returns as soon as we've established a connection to the
        # component
        def component_exited(info):
            component_id = info.get("id")
            self.log.critical("Component '{component_id}' failed to start; shutting down node.", component_id=component_id)
            try:
                self._reactor.stop()
            except twisted.internet.error.ReactorNotRunning:
                pass
        topic = u'crossbar.worker.{}.container.on_component_stop'.format(worker_id)
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

            yield self._controller.call(u'crossbar.worker.{}.start_connection'.format(worker_id), connection_id, connection, options=CallOptions())
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

            yield self._controller.call(u'crossbar.worker.{}.start_component'.format(worker_id), component_id, component, options=CallOptions())
            self.log.info("{worker}: component '{component_id}' started",
                          worker=worker_logname, component_id=component_id)

        # after 2 seconds, consider all the application components running
        self._reactor.callLater(2, component_stop_sub.unsubscribe)

    @inlineCallbacks
    def _configure_native_worker_websocket_testee(self, worker_logname, worker_id, worker):
        yield self._configure_native_worker_common(worker_logname, worker_id, worker)
        # start transport on websocket-testee
        transport = worker['transport']
        transport_id = 'transport-{:03d}'.format(self._transport_no)
        self._transport_no = 1

        yield self._controller.call(u'crossbar.worker.{}.start_websocket_testee_transport'.format(worker_id), transport_id, transport, options=CallOptions())
        self.log.info(
            "{logname}: transport '{tid}' started",
            logname=worker_logname,
            tid=transport_id,
        )
