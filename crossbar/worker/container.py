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

import sys
import importlib
import pkg_resources
import traceback
from functools import partial
from datetime import datetime

from twisted.internet import reactor
from twisted import internet
from twisted.python import log
from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks, returnValue

from autobahn.util import utcstr
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import ComponentConfig, \
    PublishOptions, \
    RegisterOptions

from crossbar.common import checkconfig
from crossbar.worker.worker import NativeWorkerSession
from crossbar.router.protocol import WampWebSocketClientFactory, \
    WampRawSocketClientFactory

from crossbar.twisted.endpoint import create_connecting_endpoint_from_config

__all__ = ('ContainerWorkerSession',)


class ContainerComponent:

    """
    An application component running inside a container.

    This class is for _internal_ use within ContainerWorkerSession.
    """

    def __init__(self, id, config, proto, session):
        """
        Ctor.

        :param id: The ID of the component within the container.
        :type id: int
        :param config: The component configuration the component was created from.
        :type config: dict
        :param proto: The transport protocol instance the component runs for talking
                      to the application router.
        :type proto: instance of CrossbarWampWebSocketClientProtocol or CrossbarWampRawSocketClientProtocol
        :param session: The application session of this component.
        :type session: Instance derived of ApplicationSession.
        """
        self.started = datetime.utcnow()
        self.id = id
        self.config = config
        self.proto = proto
        self.session = session

        # internal use; see e.g. restart_container_component
        self._stopped = Deferred()

    def marshal(self):
        """
        Marshal object information for use with WAMP calls/events.
        """
        now = datetime.utcnow()
        return {
            'id': self.id,
            'started': utcstr(self.started),
            'uptime': (now - self.started).total_seconds(),
            'config': self.config
        }


class ContainerWorkerSession(NativeWorkerSession):
    """
    A container is a native worker process that hosts application components
    written in Python. A container connects to an application router (creating
    a WAMP transport) and attached to a given realm on the application router.
    """
    WORKER_TYPE = 'container'

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        yield NativeWorkerSession.onJoin(self, details, publish_ready=False)

        # map: component ID -> ContainerComponent
        self.components = {}

        # the procedures registered
        procs = [
            'get_container_components',
            'start_container_component',
            'stop_container_component',
            'restart_container_component'
        ]

        dl = []
        for proc in procs:
            uri = '{}.{}'.format(self._uri_prefix, proc)
            if self.debug:
                log.msg("Registering procedure '{}'".format(uri))
            dl.append(self.register(getattr(self, proc), uri, options=RegisterOptions(details_arg='details')))

        regs = yield DeferredList(dl)

        if self.debug:
            log.msg("ContainerWorker registered {} procedures".format(len(regs)))

        # NativeWorkerSession.publish_ready()
        yield self.publish_ready()

    def start_container_component(self, id, config, reload_modules=False, details=None):
        """
        Starts a Class or WAMPlet in this component container.

        :param config: Component configuration.
        :type config: dict
        :param reload_modules: If `True`, enforce reloading of modules (user code)
                               that were modified (see: TrackingModuleReloader).
        :type reload_modules: bool
        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns dict -- A dict with combined info from component starting.
        """
        if self.debug:
            log.msg("{}.start_container_component".format(self.__class__.__name__), id, config)

        # prohibit starting a component twice
        #
        if id in self.components:
            emsg = "ERROR: could not start component - a component with ID '{}'' is already running (or starting)".format(id)
            log.msg(emsg)
            raise ApplicationError('crossbar.error.already_running', emsg)

        # check configuration
        #
        try:
            checkconfig.check_container_component(config)
        except Exception as e:
            emsg = "ERROR: invalid container component configuration ({})".format(e)
            log.msg(emsg)
            raise ApplicationError("crossbar.error.invalid_configuration", emsg)
        else:
            if self.debug:
                log.msg("Starting {}-component in container.".format(config['type']))

        realm = config['realm']
        componentcfg = ComponentConfig(realm=realm, extra=config.get('extra', None))

        # 1) create WAMP application component factory
        #
        if config['type'] == 'wamplet':

            package = config['package']
            entrypoint = config['entrypoint']

            try:
                # create_component() is supposed to make instances of ApplicationSession later
                #
                create_component = pkg_resources.load_entry_point(package, 'autobahn.twisted.wamplet', entrypoint)

            except Exception as e:
                tb = traceback.format_exc()
                emsg = 'ERROR: failed to import WAMPlet {}.{} ("{}")'.format(package, entrypoint, e)
                log.msg(emsg)
                raise ApplicationError("crossbar.error.cannot_import", emsg, tb)

            else:
                if self.debug:
                    log.msg("Creating component from WAMPlet {}.{}".format(package, entrypoint))

        elif config['type'] == 'class':

            qualified_classname = config['classname']

            try:
                c = qualified_classname.split('.')
                module_name, class_name = '.'.join(c[:-1]), c[-1]
                module = importlib.import_module(module_name)

                # create_component() is supposed to make instances of ApplicationSession later
                #
                create_component = getattr(module, class_name)

            except Exception as e:
                emsg = "Failed to import class '{}' - {}".format(qualified_classname, e)
                log.msg(emsg)
                log.msg("PYTHONPATH: {}".format(sys.path))
                raise ApplicationError("crossbar.error.class_import_failed", emsg)

            else:
                if self.debug:
                    log.msg("Creating component from class {}".format(qualified_classname))

        else:
            # should not arrive here, since we did `check_container_component()`
            raise Exception("logic error")

        # force reload of modules (user code)
        #
        if reload_modules:
            self._module_tracker.reload()

        # WAMP application session factory
        # ultimately, this gets called once the connection is
        # establised, from onOpen in autobahn/wamp/websocket.py:59
        def create_session():
            try:
                return create_component(componentcfg)
            except Exception:
                log.err(_why="Instantiating component failed")
                raise

        # 2) create WAMP transport factory
        #
        transport_config = config['transport']
        transport_debug = transport_config.get('debug', False)
        transport_debug_wamp = transport_config.get('debug_wamp', False)

        # WAMP-over-WebSocket transport
        #
        if transport_config['type'] == 'websocket':

            # create a WAMP-over-WebSocket transport client factory
            #
            transport_factory = WampWebSocketClientFactory(create_session,
                                                           transport_config['url'],
                                                           debug=transport_debug,
                                                           debug_wamp=transport_debug_wamp)
            transport_factory.noisy = False

        # WAMP-over-RawSocket transport
        #
        elif transport_config['type'] == 'rawsocket':

            transport_factory = WampRawSocketClientFactory(create_session,
                                                           transport_config)
            transport_factory.noisy = False

        else:
            # should not arrive here, since we did `check_container_component()`
            raise Exception("logic error")

        # 3) create and connect client endpoint
        #
        endpoint = create_connecting_endpoint_from_config(transport_config['endpoint'],
                                                          self.config.extra.cbdir,
                                                          reactor)

        # now connect the client
        #
        d = endpoint.connect(transport_factory)

        def success(proto):
            component = ContainerComponent(id, config, proto, None)
            self.components[id] = component

            def close_wrapper(orig, was_clean, code, reason):
                """
                Wrap our protocol's onClose so we can tell when the component
                exits.
                """
                r = orig(was_clean, code, reason)
                if component.id not in self.components:
                    log.msg("Component '{}' closed, but not in set.".format(component.id))
                    return r

                if was_clean:
                    log.msg("Closed connection to '{}' with code '{}'".format(component.id, code))
                else:
                    msg = "Lost connection to component '{}' with code '{}'."
                    log.msg(msg.format(component.id, code))

                if reason:
                    log.msg(str(reason))
                del self.components[component.id]
                self._publish_component_stop(component)
                component._stopped.callback(component.marshal())
                return r
            proto.onClose = partial(close_wrapper, proto.onClose)

            # publish event "on_component_start" to all but the caller
            #
            topic = self._uri_prefix + '.container.on_component_start'
            event = {'id': id}
            self.publish(topic, event, options=PublishOptions(exclude=[details.caller]))
            return event

        def error(err):
            # https://twistedmatrix.com/documents/current/api/twisted.internet.error.ConnectError.html
            if isinstance(err.value, internet.error.ConnectError):
                emsg = "ERROR: could not connect container component to router - transport establishment failed ({})".format(err.value)
                log.msg(emsg)
                raise ApplicationError('crossbar.error.cannot_connect', emsg)
            else:
                # should not arrive here (since all errors arriving here should be subclasses of ConnectError)
                raise err

        d.addCallbacks(success, error)

        return d

    def _publish_component_stop(self, component):
        """
        Internal helper to publish details to on_component_stop
        """
        event = component.marshal()
        topic = self._uri_prefix + '.container.on_component_stop'
        # XXX just ignoring a Deferred here...
        self.publish(topic, event)
        return event

    @inlineCallbacks
    def restart_container_component(self, id, reload_modules=False, details=None):
        """
        Restart a component currently running within this container using the
        same configuration that was used when first starting the component.

        :param id: The ID of the component to restart.
        :type id: int
        :param reload_modules: If `True`, enforce reloading of modules (user code)
                               that were modified (see: TrackingModuleReloader).
        :type reload_modules: bool
        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns dict -- A dict with combined info from component stopping/starting.
        """
        if id not in self.components:
            raise ApplicationError('crossbar.error.no_such_object', 'no component with ID {} running in this container'.format(id))

        component = self.components[id]

        stopped = yield self.stop_container_component(id, details=details)
        started = yield self.start_container_component(
            id, component.config, reload_modules=reload_modules, details=details)

        returnValue({'stopped': stopped, 'started': started})

    @inlineCallbacks
    def stop_container_component(self, id, details=None):
        """
        Stop a component currently running within this container.

        :param id: The ID of the component to stop.
        :type id: int
        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns dict -- A dict with component start information.
        """
        if id not in self.components:
            raise ApplicationError('crossbar.error.no_such_object', 'no component with ID {} running in this container'.format(id))

        component = self.components[id]
        try:
            component.proto.close()
        except:
            log.err(_why="Failed to close component '{}':".format(id))
            raise

        # essentially just waiting for "on_component_stop"
        yield component._stopped
        returnValue(component.marshal())

    def get_container_components(self, details=None):
        """
        Get components currently running within this container.

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns list -- List of components.
        """
        res = []
        for c in self.components.values():
            res.append(c.marshal())
        return res
