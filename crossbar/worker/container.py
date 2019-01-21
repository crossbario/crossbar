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

from datetime import datetime

from twisted import internet
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.defer import returnValue
from twisted.python.failure import Failure

from autobahn.util import utcstr
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import ComponentConfig, PublishOptions
from autobahn import wamp

from crossbar.worker import _appsession_loader
from crossbar.worker.controller import WorkerController
from crossbar.router.protocol import WampWebSocketClientFactory, WampRawSocketClientFactory

from crossbar.common.twisted.endpoint import create_connecting_endpoint_from_config

__all__ = ('ContainerController',)


class ContainerComponent(object):
    """
    An application component running inside a container.

    This class is for _internal_ use within ContainerController.
    """

    def __init__(self, component_id, config, proto, session):
        """
        Ctor.

        :param component_id: The ID of the component within the container.
        :type component_id: int
        :param config: The component configuration the component was created from.
        :type config: dict
        :param proto: The transport protocol instance the component runs for talking
                      to the application router.
        :type proto: instance of CrossbarWampWebSocketClientProtocol or CrossbarWampRawSocketClientProtocol
        :param session: The application session of this component.
        :type session: Instance derived of ApplicationSession.
        """
        self.started = datetime.utcnow()
        self.id = component_id
        self.config = config
        self.proto = proto
        self.session = session

        # internal use; see e.g. restart_component
        self._stopped = Deferred()

    def marshal(self):
        """
        Marshal object information for use with WAMP calls/events.
        """
        now = datetime.utcnow()
        return {
            u'id': self.id,
            u'started': utcstr(self.started),
            u'uptime': (now - self.started).total_seconds(),
            u'config': self.config
        }


class ContainerController(WorkerController):
    """
    A container is a native worker process that hosts application components
    written in Python. A container connects to an application router (creating
    a WAMP transport) and attached to a given realm on the application router.
    """
    WORKER_TYPE = u'container'
    WORKER_TITLE = u'Container'

    SHUTDOWN_MANUAL = u'shutdown-manual'
    SHUTDOWN_ON_LAST_COMPONENT_STOPPED = u'shutdown-on-last-component-stopped'

    def __init__(self, config=None, reactor=None, personality=None):
        # base ctor
        WorkerController.__init__(self, config=config, reactor=reactor, personality=personality)

        # map: component ID -> ContainerComponent
        self.components = {}

        # when shall we exit?
        self._exit_mode = (config.extra.shutdown or self.SHUTDOWN_MANUAL)

        # "global" shared between all components
        self.components_shared = {
            u'reactor': reactor
        }

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        self.log.info('Container worker "{worker_id}" session {session_id} initializing ..', worker_id=self._worker_id, session_id=details.session)
        yield WorkerController.onJoin(self, details, publish_ready=False)

        self.log.info('Container worker "{worker_id}" session ready', worker_id=self._worker_id)

        # WorkerController.publish_ready()
        yield self.publish_ready()

    @wamp.register(None)
    def shutdown(self, details=None):
        """
        Stops the whole container gracefully by stopping all components
        currently running, and then stopping the container worker.

        Note: This behaves more gracefully than stopping the container
        from outside, using "stop_worker", and also returns the stopped
        components.

        :returns: List of IDs of the components stopped (if any) while shutting down.
        :rtype: list of str
        """
        stopped_component_ids = []
        dl = []
        for component in self.components.values():
            dl.append(self.stop_component(component.id, details=details))
            stopped_component_ids.append(component.id)
        self.disconnect()
        return stopped_component_ids

    @wamp.register(None)
    def start_component(self, component_id, config, reload_modules=False, details=None):
        """
        Starts a component in this container worker.

        :param component_id: The ID under which to start the component.
        :type component_id: str

        :param config: Component configuration.
        :type config: dict

        :param reload_modules: If `True`, enforce reloading of modules (user code)
           that were modified (see: TrackingModuleReloader).
        :type reload_modules: bool

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns: Component startup information.
        :rtype: dict
        """
        self.log.debug(u'{klass}.start_component({component_id}, {config})',
                       klass=self.__class__.__name__,
                       component_id=component_id,
                       config=config)

        # prohibit starting a component twice
        #
        if component_id in self.components:
            emsg = u'duplicate component "{}" - a component with this ID is already running (or starting)'.format(component_id)
            self.log.debug(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        # check component configuration
        #
        try:
            self.personality.check_container_component(self.personality, config)
        except Exception as e:
            emsg = u'invalid container component configuration: {}'.format(e)
            self.log.debug(emsg)
            raise ApplicationError(u'crossbar.error.invalid_configuration', emsg)
        else:
            self.log.debug(u'starting component "{component_id}" ..', component_id=component_id)

        # WAMP application component factory
        #
        realm = config.get(u'realm', None)
        assert type(realm) == str

        extra = config.get(u'extra', {})
        assert type(extra) == dict

        # forward crossbar node base directory
        extra['cbdir'] = self.config.extra.cbdir

        # allow access to controller session
        controller = self if self.config.extra.expose_controller else None

        # expose an object shared between components
        shared = self.components_shared if self.config.extra.expose_shared else None

        # this is the component configuration provided to the components ApplicationSession
        component_config = ComponentConfig(realm=realm,
                                           extra=extra,
                                           keyring=None,
                                           controller=controller,
                                           shared=shared)

        # define component ctor function
        try:
            create_component = _appsession_loader(config)
        except ApplicationError as e:
            # for convenience, also log failed component loading
            self.log.error(u'component loading failed', log_failure=Failure())
            if u'No module named' in str(e):
                self.log.error(u'  Python module search paths:')
                for path in e.kwargs['pythonpath']:
                    self.log.error(u'    {path}', path=path)
            raise

        # force reload of modules (user code)
        #
        if reload_modules:
            self._module_tracker.reload()

        # prepare some cleanup code this connection goes away
        def _closed(session, was_clean):
            """
            This is moderate hack around the fact that we don't have any way
            to "listen" for a close event on websocket or rawsocket
            objects. Also, the rawsocket implementation doesn't have
            "a" function we can wrap anyway (they are asyncio vs
            Twisted specific), so for both WebSocket and rawsocket
            cases, we actually listen on the WAMP session for
            transport close notifications.

            Ideally we'd listen for "close" on the transport but this
            works fine for cleaning up the components.
            """
            if component_id not in self.components:
                self.log.warn(
                    "Component '{id}' closed, but not in set.",
                    id=component_id,
                )
                return

            if was_clean:
                self.log.info(
                    "Closed connection to '{id}'",
                    id=component_id,
                )
            else:
                self.log.error(
                    "Lost connection to component '{id}' uncleanly",
                    id=component_id,
                )

            component = self.components[component_id]
            del self.components[component_id]
            self._publish_component_stop(component)
            component._stopped.callback(component.marshal())
            del component

            # figure out if we need to shut down the container itself or not
            if not self.components:
                if self._exit_mode == self.SHUTDOWN_ON_LAST_COMPONENT_STOPPED:
                    self.log.info(
                        "Container is hosting no more components: stopping container in exit mode <{exit_mode}> ...",
                        exit_mode=self._exit_mode,
                    )
                    self.shutdown()
                else:
                    self.log.info(
                        "Container is hosting no more components: continue running in exit mode <{exit_mode}>",
                        exit_mode=self._exit_mode,
                    )
            else:
                self.log.info(
                    "Container is still hosting {component_count} components: continue running in exit mode <{exit_mode}>",
                    exit_mode=self._exit_mode,
                    component_count=len(self.components),
                )

        # WAMP application session factory
        #
        def create_session():
            try:
                session = create_component(component_config)

                # any exception spilling out from user code in onXXX handlers is fatal!
                def panic(fail, msg):
                    self.log.error(
                        "Fatal error in component: {msg} - {log_failure.value}",
                        msg=msg, log_failure=fail,
                    )
                    session.disconnect()
                session._swallow_error = panic

                # see note above, for _closed -- we should be
                # listening for "the transport was closed", but
                # "session disconnect" is close enough (since there
                # are no "proper events" from websocket/rawsocket
                # implementations).
                session.on('disconnect', _closed)

                return session

            except Exception:
                self.log.failure(u'component instantiation failed: {log_failure.value}')
                raise

        # WAMP transport factory
        #
        transport_config = config[u'transport']

        if transport_config[u'type'] == u'websocket':

            # create a WAMP-over-WebSocket transport client factory
            transport_factory = WampWebSocketClientFactory(create_session, transport_config[u'url'])
            transport_factory.noisy = False

        elif transport_config[u'type'] == u'rawsocket':

            transport_factory = WampRawSocketClientFactory(create_session,
                                                           transport_config)
            transport_factory.noisy = False

        else:
            # should not arrive here, since we did check the config before
            raise Exception(u'logic error')

        # create and connect client endpoint
        #
        endpoint = create_connecting_endpoint_from_config(transport_config[u'endpoint'],
                                                          self.config.extra.cbdir,
                                                          self._reactor,
                                                          self.log)

        # now, actually connect the client
        #
        d = endpoint.connect(transport_factory)

        def on_connect_success(proto):
            component = ContainerComponent(component_id, config, proto, None)
            self.components[component_id] = component

            # publish event "on_component_start" to all but the caller
            #
            uri = self._uri_prefix + u'.on_component_started'

            component_started = {
                u'id': component_id,
                u'config': config
            }

            self.publish(uri, component_started, options=PublishOptions(exclude=details.caller))

            return component_started

        def on_connect_error(err):
            # https://twistedmatrix.com/documents/current/api/twisted.internet.error.ConnectError.html
            if isinstance(err.value, internet.error.ConnectError):
                emsg = u'could not connect container component to router - transport establishment failed ({})'.format(err.value)
                self.log.warn(emsg)
                raise ApplicationError(u'crossbar.error.cannot_connect', emsg)
            else:
                # should not arrive here (since all errors arriving here
                # should be subclasses of ConnectError)
                raise err

        d.addCallbacks(on_connect_success, on_connect_error)

        return d

    def _publish_component_stop(self, component):
        """
        Internal helper to publish details to on_component_stop
        """
        event = component.marshal()
        if self.is_connected():
            topic = self._uri_prefix + '.container.on_component_stop'
            # XXX just ignoring a Deferred here...
            self.publish(topic, event)
        return event

    @wamp.register(None)
    @inlineCallbacks
    def restart_component(self, component_id, reload_modules=False, details=None):
        """
        Restart a component currently running within this container using the
        same configuration that was used when first starting the component.

        :param component_id: The ID of the component to restart.
        :type component_id: str

        :param reload_modules: If `True`, enforce reloading of modules (user code)
                               that were modified (see: TrackingModuleReloader).
        :type reload_modules: bool

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns dict -- A dict with combined info from component stopping/starting.
        """
        if component_id not in self.components:
            raise ApplicationError(u'crossbar.error.no_such_object', 'no component with ID {} running in this container'.format(component_id))

        component = self.components[component_id]

        stopped = yield self.stop_container_component(component_id, details=details)
        started = yield self.start_component(component_id, component.config, reload_modules=reload_modules, details=details)

        del stopped[u'caller']
        del started[u'caller']

        restarted = {
            u'stopped': stopped,
            u'started': started,
            u'caller': {
                u'session': details.caller,
                u'authid': details.caller_authid,
                u'authrole': details.caller_authrole,
            }
        }

        self.publish(u'{}.on_component_restarted'.format(self._uri_prefix),
                     restarted,
                     options=PublishOptions(exclude=details.caller))

        returnValue(restarted)

    @wamp.register(None)
    @inlineCallbacks
    def stop_component(self, component_id, details=None):
        """
        Stop a component currently running within this container.

        :param component_id: The ID of the component to stop.
        :type component_id: int

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns: Stop information.
        :rtype: dict
        """
        self.log.debug('{klass}.stop_component({component_id}, {details})', klass=self.__class__.__name__, component_id=component_id, details=details)

        if component_id not in self.components:
            raise ApplicationError(u'crossbar.error.no_such_object', 'no component with ID {} running in this container'.format(component_id))

        component = self.components[component_id]

        try:
            component.proto.close()
        except:
            self.log.failure("failed to close protocol on component '{component_id}': {log_failure}", component_id=component_id)
            raise
        else:
            # essentially just waiting for "on_component_stop"
            yield component._stopped

        stopped = {
            u'component_id': component_id,
            u'uptime': (datetime.utcnow() - component.started).total_seconds(),
            u'caller': {
                u'session': details.caller if details else None,
                u'authid': details.caller_authid if details else None,
                u'authrole': details.caller_authrole if details else None,
            }
        }

        # the component.proto above normally already cleaned it up
        if component_id in self.components:
            del self.components[component_id]

        # FIXME: this is getting autobahn.wamp.exception.TransportLost
        if False:
            self.publish(u'{}.on_component_stopped'.format(self._uri_prefix),
                         stopped,
                         options=PublishOptions(exclude=details.caller))

        returnValue(stopped)

    @wamp.register(None)
    def get_component(self, component_id, details=None):
        """
        Get a component currently running within this container.

        :param component_id: The ID of the component to get.
        :type component_id: str

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns: Component detail information.
        :rtype: dict
        """
        self.log.debug('{klass}.get_component({component_id}, {details})', klass=self.__class__.__name__, component_id=component_id, details=details)

        if component_id not in self.components:
            raise ApplicationError(u'crossbar.error.no_such_object', 'no component with ID {} running in this container'.format(component_id))

        return self.components[component_id].marshal()

    @wamp.register(None)
    def get_components(self, details=None):
        """
        Get components currently running within this container.

        :param ids_only: If `True`, only return (sorted) list of component IDs.
        :type ids_only: bool

        :param details: Caller details.
        :type details: instance of :class:`autobahn.wamp.types.CallDetails`

        :returns: Plain (sorted) list of component IDs, or list of components
            sorted by component ID when `ids_only==True`.
        :rtype: list
        """
        self.log.debug('{klass}.list_components({details})', klass=self.__class__.__name__, details=details)
        return sorted(self.components.keys())
