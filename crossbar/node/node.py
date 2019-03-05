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

import twisted
from twisted.internet.defer import inlineCallbacks, Deferred, returnValue, gatherResults
from twisted.python.reflect import qual

from txaio import make_logger

from autobahn.wamp.types import CallOptions, ComponentConfig

from crossbar._util import hltype, hlid, hluserid, hl

from crossbar.router.router import RouterFactory
from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceAgent
from crossbar.worker.types import RouterRealm
from crossbar.common.checkconfig import NODE_SHUTDOWN_ON_WORKER_EXIT
from crossbar.common.key import _maybe_generate_key
from crossbar.node.controller import NodeController


class NodeOptions(object):

    def __init__(self, debug_lifecycle=False, debug_programflow=False, enable_vmprof=False):

        self.debug_lifecycle = debug_lifecycle
        self.debug_programflow = debug_programflow
        self.enable_vmprof = enable_vmprof


class Node(object):
    """
    Crossbar.io Standalone node personality.
    """
    NODE_CONTROLLER = NodeController

    ROUTER_SERVICE = RouterServiceAgent

    CONFIG_SOURCE_DEFAULT = 1
    CONFIG_SOURCE_EMPTY = 2
    CONFIG_SOURCE_LOCALFILE = 3
    CONFIG_SOURCE_XBRNETWORK = 4
    CONFIG_SOURCE_TO_STR = {
        1: 'default',
        2: 'empty',
        3: 'localfile',
        4: 'xbrnetwork',
    }

    # A Crossbar.io node is the running a controller process and one or multiple
    # worker processes.
    # A single Crossbar.io node runs exactly one instance of this class, hence
    # this class can be considered a system singleton.

    log = make_logger()

    def __init__(self, personality, cbdir=None, reactor=None, native_workers=None, options=None):
        """

        :param cbdir: The node directory to run from.
        :type cbdir: unicode
        :param reactor: Reactor to run on.
        :type reactor: :class:`twisted.internet.reactor` or None
        """
        self.personality = personality
        self.options = options or NodeOptions()

        self._native_workers = personality.native_workers

        # node directory
        self._cbdir = cbdir or u'.'

        # reactor we should run on
        if reactor is None:
            from twisted.internet import reactor
        self._reactor = reactor

        # allow overriding to add (or remove) native-worker types
        if native_workers is not None:
            self._native_workers = native_workers

        # local node management router
        self._router_factory = None

        # session factory for node management router
        self._router_session_factory = None

        # the node controller realm
        self._realm = u'crossbar'

        # config of this node.
        self._config = None

        # node private key :class:`autobahn.wamp.cryptosign.SigningKey`
        self._node_key = None

        # when running in managed mode, this will hold the session to CFC
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
        self._node_shutdown_triggers = [NODE_SHUTDOWN_ON_WORKER_EXIT]

        # will be filled with a Deferred in start(). the Deferred will fire when
        # the node has shut down, and the result signals if shutdown was clean
        self._shutdown_complete = None

        # for node elements started under specific IDs, and where
        # the node configuration does not specify an ID, use a generic
        # name numbered sequentially using the counters here
        self._worker_no = 1
        self._realm_no = 1
        self._role_no = 1
        self._connection_no = 1
        self._transport_no = 1
        self._webservice_no = 1
        self._component_no = 1

    @property
    def realm(self):
        return self._realm

    @property
    def key(self):
        """
        Returns the node (private signing) key pair.

        :return: The node key.
        :rtype: :class:`autobahn.wamp.cryptosign.SigningKey`
        """
        return self._node_key

    def load_keys(self, cbdir):
        """
        Load node public-private key pair from key files, possibly generating a new key pair if
        none exists.

        This is the _first_ function being called after the Node has been instantiated.

        IMPORTANT: this function is run _before_ start of Twisted reactor!
        """
        was_new, self._node_key = _maybe_generate_key(cbdir)
        return was_new

    def load_config(self, configfile=None, default=None):
        """
        Check and load the node configuration from:

        * from ``.crossbar/config.json`` or
        * from built-in (empty) default configuration

        This is the _second_ function being called after the Node has been instantiated.

        IMPORTANT: this function is run _before_ start of Twisted reactor!
        """
        if configfile:
            config_path = os.path.abspath(os.path.join(self._cbdir, configfile))

            # the following will read the config, check the config and replace
            # environment variable references in configuration values ("${MYVAR}") and
            # finally return the parsed configuration object
            self._config = self.personality.check_config_file(self.personality, config_path)
            config_source = Node.CONFIG_SOURCE_LOCALFILE
        else:
            config_path = None
            if default:
                self._config = default
                config_source = Node.CONFIG_SOURCE_DEFAULT
            else:
                self._config = {
                    u'version': 2,
                    u'controller': {},
                    u'workers': []
                }
                config_source = Node.CONFIG_SOURCE_EMPTY

            self.personality.check_config(self.personality, self._config)

        return config_source, config_path

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
            self._node_shutdown_triggers = [NODE_SHUTDOWN_ON_WORKER_EXIT]
            self.log.info("Using default node shutdown triggers {triggers}", triggers=self._node_shutdown_triggers)

    def stop(self):
        self._controller._shutdown_was_clean = True
        return self._controller.shutdown()

    @inlineCallbacks
    def start(self, node_id=None):
        """
        Starts this node. This will start a node controller and then spawn new worker
        processes as needed.

        The node keys (``load_keys``) and configuration (``load_config``) has to be loaded
        before starting the node.

        This is the _third_ function being called after the Node has been instantiated.
        """
        self.log.info('Starting {personality} node {method}',
                      personality=self.personality.NAME,
                      method=hltype(Node.start))

        # a configuration must have been loaded before
        if not self._config:
            raise Exception("No node configuration set")

        # a node can only be started once for now
        assert self._shutdown_complete is None
        assert self._node_id is None

        # get controller config/options
        controller_config = self._config.get('controller', {})
        controller_options = controller_config.get('options', {})

        # the node ID: CLI takes precedence over config over hostname
        if node_id:
            self._node_id = node_id
            _node_id_source = 'explicit run-time argument'
        elif 'id' in controller_config:
            self._node_id = controller_config['id']
            _node_id_source = 'explicit configuration'
        else:
            self._node_id = u'{}'.format(socket.gethostname()).lower()
            _node_id_source = 'hostname'
        self.log.info('Node ID {node_id} set from {node_id_source}',
                      node_id=hlid(self._node_id),
                      node_id_source=_node_id_source)

        # set controller process title
        try:
            import setproctitle
        except ImportError:
            self.log.warn("Warning, could not set process title (setproctitle not installed)")
        else:
            setproctitle.setproctitle(controller_options.get('title', 'crossbar-controller'))

        # add the node controller singleton component
        self._controller = self.NODE_CONTROLLER(self)

        # local node management router
        self._router_factory = RouterFactory(self._node_id, None)
        self._router_session_factory = RouterSessionFactory(self._router_factory)
        rlm_config = {
            'name': self._realm
        }
        rlm = RouterRealm(self._controller, None, rlm_config)
        router = self._router_factory.start_realm(rlm)

        # setup global static roles
        self._add_global_roles()

        # always add a realm service session
        cfg = ComponentConfig(self._realm)
        rlm.session = (self.ROUTER_SERVICE)(cfg, router)
        self._router_session_factory.add(rlm.session, authrole=u'trusted')
        self.log.debug('Router service session attached [{router_service}]', router_service=qual(self.ROUTER_SERVICE))

        self._router_session_factory.add(self._controller, authrole=u'trusted')
        self.log.debug('Node controller attached [{node_controller}]', node_controller=qual(self.NODE_CONTROLLER))

        # add extra node controller components
        self._add_extra_controller_components(controller_options)

        # setup Node shutdown triggers
        self._set_shutdown_triggers(controller_options)

        # setup node shutdown Deferred
        self._shutdown_complete = Deferred()

        # startup the node personality ..
        yield self.personality.Node.boot(self)

        # notify systemd that we are fully up and running
        try:
            import sdnotify
        except ImportError:
            # do nothing on non-systemd platforms
            pass
        else:
            sdnotify.SystemdNotifier().notify("READY=1")

        # return a shutdown deferred which we will fire to notify the code that
        # called start() - which is the main crossbar boot code
        res = {
            'shutdown_complete': self._shutdown_complete
        }
        returnValue(res)
#        returnValue(self._shutdown_complete)

    def boot(self):
        self.log.info('Booting node {method}', method=hltype(Node.boot))
        return self.boot_from_config(self._config)

    @inlineCallbacks
    def boot_from_config(self, config):
        """
        Startup elements in the node as specified in the provided node configuration.
        """
        # get controller configuration subpart
        controller = config.get('controller', {})
        parallel_worker_start = controller.get('options', {}).get('enable_parallel_worker_start', False)

        self.log.info('{bootmsg} {method}',
                      bootmsg=hl('Booting node from local configuration [parallel_worker_start={}] ..'.format(parallel_worker_start),
                                 color='green', bold=True),
                      method=hltype(Node.boot_from_config))

        # start Manhole in node controller
        if 'manhole' in controller:
            yield self._controller.call(u'crossbar.start_manhole', controller['manhole'], options=CallOptions())
            self.log.debug("controller: manhole started")

        # startup all workers
        workers = config.get('workers', [])
        if len(workers):
            self.log.info(hl('Will start {} worker{} ..'.format(len(workers), 's' if len(workers) > 1 else ''), color='green', bold=True))
        else:
            self.log.info(hl('No workers configured, nothing to do', color='green', bold=True))

        dl = []
        for worker in workers:

            # worker ID
            if 'id' in worker:
                worker_id = worker['id']
            else:
                worker_id = u'worker{:03d}'.format(self._worker_no)
                worker['id'] = worker_id
                self._worker_no += 1

            # worker type: either a native worker ('router', 'container', ..), or a guest worker ('guest')
            worker_type = worker['type']

            # native worker processes setup
            if worker_type in self._native_workers:

                # set logname depending on native worker type
                worker_logname = '{} {}'.format(self._native_workers[worker_type]['logname'], hlid(worker_id))

                # any worker specific options
                worker_options = worker.get('options', {})

                # start the (native) worker
                self.log.info(
                    "Order node to start {worker_logname}",
                    worker_logname=worker_logname,
                )

                d = self._controller.call(u'crossbar.start_worker', worker_id, worker_type, worker_options, options=CallOptions())

                @inlineCallbacks
                def configure_worker(res, worker_logname, worker_type, worker_id, worker):
                    self.log.info(
                        "Ok, node has started {worker_logname}",
                        worker_logname=worker_logname,
                    )

                    # now configure the worker
                    self.log.info(
                        "Configuring {worker_logname} ..",
                        worker_logname=worker_logname,
                    )
                    method_name = '_configure_native_worker_{}'.format(worker_type.replace('-', '_'))
                    try:
                        config_fn = getattr(self, method_name)
                    except AttributeError:
                        raise ValueError(
                            "A native worker of type '{}' is configured but "
                            "there is no method '{}' on {}".format(worker_type, method_name, type(self))
                        )
                    yield config_fn(worker_logname, worker_id, worker)
                    self.log.info(
                        "Ok, {worker_logname} configured",
                        worker_logname=worker_logname,
                    )

                d.addCallback(configure_worker, worker_logname, worker_type, worker_id, worker)

            # guest worker processes setup
            elif worker_type == u'guest':

                # now actually start the (guest) worker ..

                # FIXME: start_worker() takes the whole configuration item for guest workers, whereas native workers
                # only take the options (which is part of the whole config item for the worker)
                d = self._controller.call(u'crossbar.start_worker', worker_id, worker_type, worker, options=CallOptions())

            else:
                raise Exception('logic error: unexpected worker_type="{}"'.format(worker_type))

            if parallel_worker_start:
                dl.append(d)
            else:
                yield d

        yield gatherResults(dl)

        self.log.info(hl('Ok, local node configuration booted successfully!', color='green', bold=True))

    @inlineCallbacks
    def _configure_native_worker_common(self, worker_logname, worker_id, worker):
        # expanding PYTHONPATH of the newly started worker is now done
        # directly in NodeController._start_native_worker
        worker_options = worker.get('options', {})
        if False:
            if 'pythonpath' in worker_options:
                added_paths = yield self._controller.call(u'crossbar.worker.{}.add_pythonpath'.format(worker_id), worker_options['pythonpath'], options=CallOptions())
                self.log.warn("{worker}: PYTHONPATH extended for {paths}",
                              worker=worker_logname, paths=added_paths)

        # FIXME: as the CPU affinity is in the worker options, this _also_ (see above fix)
        # should be done directly in NodeController._start_native_worker
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
                realm_id = realm['id']
            else:
                realm_id = 'realm{:03d}'.format(self._realm_no)
                realm['id'] = realm_id
                self._realm_no += 1

            self.log.info(
                "Order {worker_logname} to start Realm {realm_id}",
                worker_logname=worker_logname,
                realm_id=hlid(realm_id),
            )

            yield self._controller.call(u'crossbar.worker.{}.start_router_realm'.format(worker_id), realm_id, realm, options=CallOptions())

            self.log.info(
                "Ok, {worker_logname} has started Realm {realm_id}",
                worker_logname=worker_logname,
                realm_id=hlid(realm_id),
            )

            # add roles to realm
            for role in realm.get('roles', []):
                if 'id' in role:
                    role_id = role['id']
                else:
                    role_id = 'role{:03d}'.format(self._role_no)
                    role['id'] = role_id
                    self._role_no += 1

                self.log.info(
                    "Order Realm {realm_id} to start Role {role_id}",
                    realm_id=hlid(realm_id),
                    role_id=hlid(role_id),
                )

                yield self._controller.call(u'crossbar.worker.{}.start_router_realm_role'.format(worker_id), realm_id, role_id, role, options=CallOptions())

                self.log.info(
                    "Ok, Realm {realm_id} has started Role {role_id}",
                    realm_id=hlid(realm_id),
                    role_id=hlid(role_id),
                )

        # start components to run embedded in the router
        for component in worker.get('components', []):

            if 'id' in component:
                component_id = component['id']
            else:
                component_id = 'component{:03d}'.format(self._component_no)
                component['id'] = component_id
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
                transport_id = transport['id']
            else:
                transport_id = 'transport{:03d}'.format(self._transport_no)
                transport['id'] = transport_id
                self._transport_no += 1

            add_paths_on_transport_create = False

            self.log.info(
                "Order {worker_logname} to start Transport {transport_id}",
                worker_logname=worker_logname,
                transport_id=hlid(transport_id),
            )

            yield self._controller.call(u'crossbar.worker.{}.start_router_transport'.format(worker_id),
                                        transport_id,
                                        transport,
                                        create_paths=add_paths_on_transport_create,
                                        options=CallOptions())
            self.log.info(
                "Ok, {worker_logname} has started Transport {transport_id}",
                worker_logname=worker_logname,
                transport_id=hlid(transport_id),
            )

            if not add_paths_on_transport_create:

                if transport['type'] == 'web':
                    paths = transport.get('paths', {})
                elif transport['type'] == 'universal':
                    paths = transport.get('web', {}).get('paths', {})
                else:
                    paths = None

                # Web service paths
                if paths:
                    for path in sorted(paths):
                        if path != '/':
                            webservice = paths[path]

                            if 'id' in webservice:
                                webservice_id = webservice['id']
                            else:
                                webservice_id = 'webservice{:03d}'.format(self._webservice_no)
                                webservice['id'] = webservice_id
                                self._webservice_no += 1

                            self.log.info(
                                "Order Transport {transport_id} to start Web Service {webservice_id}",
                                transport_id=hlid(transport_id),
                                webservice_id=hlid(webservice_id),
                                path=hluserid(path),
                            )

                            yield self._controller.call(u'crossbar.worker.{}.start_web_transport_service'.format(worker_id),
                                                        transport_id,
                                                        path,
                                                        webservice,
                                                        options=CallOptions())
                            self.log.info(
                                "Ok, Transport {transport_id} has started Web Service {webservice_id}",
                                transport_id=hlid(transport_id),
                                webservice_id=hlid(webservice_id),
                                path=hluserid(path),
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

        # start components to run embedded in the container
        #
        for component in worker.get('components', []):

            if 'id' in component:
                component_id = component['id']
            else:
                component_id = 'component{:03d}'.format(self._component_no)
                component['id'] = component_id
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

        transport_id = 'transport{:03d}'.format(self._transport_no)
        transport['id'] = transport_id
        self._transport_no = 1

        yield self._controller.call(u'crossbar.worker.{}.start_websocket_testee_transport'.format(worker_id), transport_id, transport, options=CallOptions())
        self.log.info(
            "{logname}: transport '{tid}' started",
            logname=worker_logname,
            tid=transport_id,
        )
