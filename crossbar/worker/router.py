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

import six

from crossbar.worker.types import RouterComponent, RouterRealm, RouterRealmRole, RouterRealmUplink
from twisted.internet.defer import Deferred, DeferredList, maybeDeferred
from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure

from autobahn import wamp
from autobahn.util import utcstr
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, ComponentConfig

from crossbar._util import class_name

from crossbar.router import uplink
from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceSession
from crossbar.router.router import RouterFactory

from crossbar.worker import _appsession_loader
from crossbar.worker.worker import NativeWorkerSession
from crossbar.common import checkconfig


__all__ = ('RouterWorkerSession',)


class RouterWorkerSession(NativeWorkerSession):
    """
    A native Crossbar.io worker that runs a WAMP router which can manage
    multiple realms, run multiple transports and links, as well as host
    multiple (embedded) application components.
    """
    WORKER_TYPE = u'router'
    WORKER_TITLE = u'Router'
    router_realm_class = RouterRealm
    router_factory_class = RouterFactory

    def __init__(self, config=None, reactor=None, personality=None):
        # base ctor
        NativeWorkerSession.__init__(self, config=config, reactor=reactor, personality=personality)

        # factory for producing (per-realm) routers
        self._router_factory = self.router_factory_class(None, self)

        # factory for producing router sessions
        self._router_session_factory = RouterSessionFactory(self._router_factory)

        # map: realm ID -> RouterRealm
        self.realms = {}

        # map: realm URI -> realm ID
        self.realm_to_id = {}

        # map: component ID -> RouterComponent
        self.components = {}

        # "global" shared between all components
        self.components_shared = {
            u'reactor': reactor
        }

        # map: transport ID -> RouterTransport
        self.transports = {}

    def onWelcome(self, msg):
        # this is a hook for authentication methods to deny the
        # session after the Welcome message -- do we need to do
        # anything in this impl?
        pass

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        self.log.info('Router worker "{worker_id}" session {session_id} initializing ..', worker_id=self._worker_id, session_id=details.session)

        yield NativeWorkerSession.onJoin(self, details, publish_ready=False)

        self.log.info('Router worker "{worker_id}" session ready', worker_id=self._worker_id)

        # NativeWorkerSession.publish_ready()
        yield self.publish_ready()

    def onLeave(self, details):
        # when this router is shutting down, we disconnect all our
        # components so that they have a chance to shutdown properly
        # -- e.g. on a ctrl-C of the router.
        leaves = []
        if self.components:
            for component in self.components.values():
                if component.session.is_connected():
                    d = maybeDeferred(component.session.leave)

                    def done(_):
                        self.log.info(
                            "component '{id}' disconnected",
                            id=component.id,
                        )
                        component.session.disconnect()
                    d.addCallback(done)
                    leaves.append(d)
        dl = DeferredList(leaves, consumeErrors=True)
        # we want our default behavior, which disconnects this
        # router-worker, effectively shutting it down .. but only
        # *after* the components got a chance to shutdown.
        dl.addBoth(lambda _: super(RouterWorkerSession, self).onLeave(details))

    @wamp.register(None)
    def get_router_realms(self, details=None):
        """
        Get realms currently running on this router worker.

        :returns: List of realms currently running.
        :rtype: list of str
        """
        self.log.debug("{name}.get_router_realms", name=self.__class__.__name__)

        return sorted(self.realms.keys())

    @wamp.register(None)
    def get_router_realm(self, realm_id, details=None):
        """
        Return realm detail information.

        :returns: realm information object
        :rtype: dict
        """
        self.log.debug("{name}.get_router_realm(realm_id={realm_id})", name=self.__class__.__name__, realm_id=realm_id)

        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        return self.realms[realm_id].marshal()

    @wamp.register(None)
    @inlineCallbacks
    def start_router_realm(self, realm_id, realm_config, details=None):
        """
        Starts a realm on this router worker.

        :param realm_id: The ID of the realm to start.
        :type realm_id: str

        :param realm_config: The realm configuration.
        :type realm_config: dict
        """
        self.log.debug("{name}.start_router_realm", name=self.__class__.__name__)

        # prohibit starting a realm twice
        #
        if realm_id in self.realms:
            emsg = "Could not start realm: a realm with ID '{}' is already running (or starting)".format(realm_id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        # check configuration
        #
        try:
            checkconfig.check_router_realm(realm_config)
        except Exception as e:
            emsg = "Invalid router realm configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # URI of the realm to start
        realm = realm_config['name']

        # router/realm wide options
        options = realm_config.get('options', {})

        enable_meta_api = options.get('enable_meta_api', True)

        # expose router/realm service API additionally on local node management router
        bridge_meta_api = options.get('bridge_meta_api', False)
        if bridge_meta_api:
            # FIXME
            bridge_meta_api_prefix = u'crossbar.worker.{worker_id}.realm.{realm_id}.root.'.format(worker_id=self._worker_id, realm_id=realm_id)
        else:
            bridge_meta_api_prefix = None

        # track realm
        rlm = self.router_realm_class(realm_id, realm_config)
        self.realms[realm_id] = rlm
        self.realm_to_id[realm] = realm_id

        # create a new router for the realm
        router = self._router_factory.start_realm(rlm)

        # add a router/realm service session
        extra = {
            # the RouterServiceSession will fire this when it is ready
            'onready': Deferred(),

            # if True, forward the WAMP meta API (implemented by RouterServiceSession)
            # that is normally only exposed on the app router/realm _additionally_
            # to the local node management router.
            'enable_meta_api': enable_meta_api,
            'bridge_meta_api': bridge_meta_api,
            'bridge_meta_api_prefix': bridge_meta_api_prefix,

            # the management session on the local node management router to which
            # the WAMP meta API is exposed to additionally, when the bridge_meta_api option is set
            'management_session': self,
        }
        cfg = ComponentConfig(realm, extra)
        rlm.session = RouterServiceSession(cfg, router)
        self._router_session_factory.add(rlm.session, authrole=u'trusted')

        yield extra['onready']

        self.log.info("Realm '{realm}' started", realm=realm)

        self.publish(u'{}.on_realm_started'.format(self._uri_prefix), realm_id)

    @wamp.register(None)
    def stop_router_realm(self, realm_id, details=None):
        """
        Stop a realm currently running on this router worker.

        When a realm has stopped, no new session will be allowed to attach to the realm.
        Optionally, close all sessions currently attached to the realm.

        :param id: ID of the realm to stop.
        :type id: str
        """
        self.log.info("{name}.stop_router_realm", name=self.__class__.__name__)

        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        rlm = self.realms[realm_id]
        realm_name = rlm.config['name']

        detached_sessions = self._router_factory.stop_realm(realm_name)

        del self.realms[realm_id]
        del self.realm_to_id[realm_name]

        realm_stopped = {
            u'id': realm_id,
            u'name': realm_name,
            u'detached_sessions': sorted(detached_sessions)
        }

        return realm_stopped

    @wamp.register(None)
    def get_router_realm_roles(self, id, details=None):
        """
        Get roles currently running on a realm running on this router worker.

        :param id: The ID of the realm to list roles for.
        :type id: str

        :returns: A list of roles.
        :rtype: list of dicts
        """
        self.log.debug("{name}.get_router_realm_roles({id})", name=self.__class__.__name__, id=id)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        return self.realms[id].roles.values()

    @wamp.register(None)
    def start_router_realm_role(self, realm_id, role_id, role_config, details=None):
        """
        Start a role on a realm running on this router worker.

        :param id: The ID of the realm the role should be started on.
        :type id: str
        :param role_id: The ID of the role to start under.
        :type role_id: str
        :param config: The role configuration.
        :type config: dict
        """
        self.log.debug("{name}.start_router_realm_role", name=self.__class__.__name__)

        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if role_id in self.realms[realm_id].roles:
            raise ApplicationError(u"crossbar.error.already_exists", "A role with ID '{}' already exists in realm with ID '{}'".format(role_id, realm_id))

        self.realms[realm_id].roles[role_id] = RouterRealmRole(role_id, role_config)

        realm = self.realms[realm_id].config['name']
        self._router_factory.add_role(realm, role_config)

        topic = u'{}.on_router_realm_role_started'.format(self._uri_prefix)
        event = {
            u'id': role_id
        }
        caller = details.caller if details else None
        self.publish(topic, event, options=PublishOptions(exclude=caller))

        self.log.info('role {role_id} on realm {realm_id} started', realm_id=realm_id, role_id=role_id, role_config=role_config)

    @wamp.register(None)
    def stop_router_realm_role(self, id, role_id, details=None):
        """
        Stop a role currently running on a realm running on this router worker.

        :param id: The ID of the realm of the role to be stopped.
        :type id: str
        :param role_id: The ID of the role to be stopped.
        :type role_id: str
        """
        self.log.debug("{name}.stop_router_realm_role", name=self.__class__.__name__)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        if role_id not in self.realms[id].roles:
            raise ApplicationError(u"crossbar.error.no_such_object", "No role with ID '{}' in realm with ID '{}'".format(role_id, id))

        del self.realms[id].roles[role_id]

    @wamp.register(None)
    def get_router_realm_uplinks(self, id, details=None):
        """
        Get uplinks currently running on a realm running on this router worker.

        :param id: The ID of the router realm to list uplinks for.
        :type id: str

        :returns: A list of uplinks.
        :rtype: list of dicts
        """
        self.log.debug("{name}.get_router_realm_uplinks", name=self.__class__.__name__)

        if id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(id))

        return self.realms[id].uplinks.values()

    @wamp.register(None)
    @inlineCallbacks
    def start_router_realm_uplink(self, realm_id, uplink_id, uplink_config, details=None):
        """
        Start an uplink on a realm running on this router worker.

        :param realm_id: The ID of the realm the uplink should be started on.
        :type realm_id: unicode
        :param uplink_id: The ID of the uplink to start.
        :type uplink_id: unicode
        :param uplink_config: The uplink configuration.
        :type uplink_config: dict
        """
        self.log.debug("{name}.start_router_realm_uplink", name=self.__class__.__name__)

        # check arguments
        if realm_id not in self.realms:
            raise ApplicationError(u"crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if uplink_id in self.realms[realm_id].uplinks:
            raise ApplicationError(u"crossbar.error.already_exists", "An uplink with ID '{}' already exists in realm with ID '{}'".format(uplink_id, realm_id))

        # create a representation of the uplink
        self.realms[realm_id].uplinks[uplink_id] = RouterRealmUplink(uplink_id, uplink_config)

        # create the local session of the bridge
        realm = self.realms[realm_id].config['name']
        extra = {
            'onready': Deferred(),
            'uplink': uplink_config
        }
        uplink_session = uplink.LocalSession(ComponentConfig(realm, extra))
        self._router_session_factory.add(uplink_session, authrole=u'trusted')

        # wait until the uplink is ready
        try:
            uplink_session = yield extra['onready']
        except Exception:
            self.log.failure(None)
            raise

        self.realms[realm_id].uplinks[uplink_id].session = uplink_session

        self.log.info("Realm is connected to Crossbar.io uplink router")

    @wamp.register(None)
    def stop_router_realm_uplink(self, id, uplink_id, details=None):
        """
        Stop an uplink currently running on a realm running on this router worker.

        :param id: The ID of the realm to stop an uplink on.
        :type id: str
        :param uplink_id: The ID of the uplink within the realm to stop.
        :type uplink_id: str
        """
        self.log.debug("{name}.stop_router_realm_uplink", name=self.__class__.__name__)

        raise NotImplementedError()

    @wamp.register(None)
    def get_router_components(self, details=None):
        """
        Get app components currently running in this router worker.

        :returns: List of app components currently running.
        :rtype: list of dict
        """
        self.log.debug("{name}.get_router_components", name=self.__class__.__name__)

        res = []
        for component in sorted(self.components.values(), key=lambda c: c.created):
            res.append({
                u'id': component.id,
                u'created': utcstr(component.created),
                u'config': component.config,
            })
        return res

    @wamp.register(None)
    def start_router_component(self, id, config, details=None):
        """
        Start an app component in this router worker.

        :param id: The ID of the component to start.
        :type id: str
        :param config: The component configuration.
        :type config: obj
        """
        self.log.debug("{name}.start_router_component", name=self.__class__.__name__)

        # prohibit starting a component twice
        #
        if id in self.components:
            emsg = "Could not start component: a component with ID '{}'' is already running (or starting)".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        # check configuration
        #
        try:
            checkconfig.check_router_component(config)
        except Exception as e:
            emsg = "Invalid router component configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
        else:
            self.log.debug("Starting {type}-component on router.",
                           type=config['type'])

        # resolve references to other entities
        #
        references = {}
        for ref in config.get('references', []):
            ref_type, ref_id = ref.split(':')
            if ref_type == u'connection':
                if ref_id in self._connections:
                    references[ref] = self._connections[ref_id]
                else:
                    emsg = "cannot resolve reference '{}' - no '{}' with ID '{}'".format(ref, ref_type, ref_id)
                    self.log.error(emsg)
                    raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
            else:
                emsg = "cannot resolve reference '{}' - invalid reference type '{}'".format(ref, ref_type)
                self.log.error(emsg)
                raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)

        # create component config
        #
        realm = config['realm']
        extra = config.get('extra', None)
        component_config = ComponentConfig(realm=realm,
                                           extra=extra,
                                           keyring=None,
                                           controller=self if self.config.extra.expose_controller else None,
                                           shared=self.components_shared if self.config.extra.expose_shared else None)
        create_component = _appsession_loader(config)

        # .. and create and add an WAMP application session to
        # run the component next to the router
        #
        try:
            session = create_component(component_config)

            # any exception spilling out from user code in onXXX handlers is fatal!
            def panic(fail, msg):
                self.log.error(
                    "Fatal error in component: {msg} - {log_failure.value}",
                    msg=msg, log_failure=fail
                )
                session.disconnect()
            session._swallow_error = panic
        except Exception:
            self.log.error(
                "Component instantiation failed",
                log_failure=Failure(),
            )
            raise

        # Note that 'join' is fired to listeners *before* onJoin runs,
        # so if you do 'yield self.leave()' in onJoin we'll still
        # publish "started" before "stopped".

        def publish_stopped(session, stop_details):
            self.log.info(
                "stopped component: {session} id={session_id}",
                session=class_name(session),
                session_id=session._session_id,
            )
            topic = self._uri_prefix + '.on_component_stop'
            event = {u'id': id}
            caller = details.caller if details else None
            self.publish(topic, event, options=PublishOptions(exclude=caller))
            return event

        def publish_started(session, start_details):
            self.log.info(
                "started component: {session} id={session_id}",
                session=class_name(session),
                session_id=session._session_id,
            )
            topic = self._uri_prefix + '.on_component_start'
            event = {u'id': id}
            caller = details.caller if details else None
            self.publish(topic, event, options=PublishOptions(exclude=caller))
            return event
        session.on('leave', publish_stopped)
        session.on('join', publish_started)

        self.components[id] = RouterComponent(id, config, session)
        self._router_session_factory.add(session, authrole=config.get('role', u'anonymous'))
        self.log.debug(
            "Added component {id} (type '{name}')",
            id=id,
            name=class_name(session),
        )

    @wamp.register(None)
    def stop_router_component(self, id, details=None):
        """
        Stop an app component currently running in this router worker.

        :param id: The ID of the component to stop.
        :type id: str
        """
        self.log.debug("{name}.stop_router_component({id})", name=self.__class__.__name__, id=id)

        if id in self.components:
            self.log.debug("Worker {worker}: stopping component {id}", worker=self.config.extra.worker, id=id)

            try:
                # self._components[id].disconnect()
                self._session_factory.remove(self.components[id])
                del self.components[id]
            except Exception as e:
                raise ApplicationError(u"crossbar.error.cannot_stop", "Failed to stop component {}: {}".format(id, e))
        else:
            raise ApplicationError(u"crossbar.error.no_such_object", "No component {}".format(id))

    @wamp.register(None)
    def get_router_transports(self, details=None):
        """
        Get transports currently running in this router worker.

        :returns: List of transports currently running.
        :rtype: list of dict
        """
        self.log.debug("{name}.get_router_transports", name=self.__class__.__name__)

        res = []
        for transport in sorted(self.transports.values(), key=lambda c: c.created):
            res.append({
                u'id': transport.id,
                u'created': utcstr(transport.created),
                u'config': transport.config,
            })
        return res

    @wamp.register(None)
    def start_router_transport(self, id, config, create_paths=False, details=None):
        """
        Start a transport on this router worker.

        :param id: The ID of the transport to start.
        :type id: str
        :param config: The transport configuration.
        :type config: dict
        """
        self.log.debug("{name}.start_router_transport", name=self.__class__.__name__)

        # prohibit starting a transport twice
        #
        if id in self.transports:
            emsg = "Could not start transport: a transport with ID '{}' is already running (or starting)".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.already_running', emsg)

        d = self.personality.create_router_transport(
            self.personality, self._reactor, id, config, self.config.extra.cbdir, self.log, self,
            _router_session_factory=self._router_session_factory,
            _web_templates=self._templates, create_paths=create_paths
        )

        def ok(router_transport):
            self.transports[id] = router_transport
            self.log.debug("Router transport '{id}'' started and listening", id=id)
            return

        def fail(err):
            emsg = "Cannot listen on transport endpoint: {log_failure}"
            self.log.error(emsg, log_failure=err)
            raise ApplicationError(u"crossbar.error.cannot_listen", emsg)

        d.addCallbacks(ok, fail)
        return d

    @wamp.register(None)
    def stop_router_transport(self, id, details=None):
        """
        Stop a transport currently running in this router worker.

        :param id: The ID of the transport to stop.
        :type id: str
        """
        self.log.debug("{name}.stop_router_transport", name=self.__class__.__name__)

        # FIXME
        if id not in self.transports:
            #      if not id in self.transports or self.transports[id].status != 'started':
            emsg = "Cannot stop transport: no transport with ID '{}' or transport is already stopping".format(id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        self.log.debug("Stopping transport with ID '{id}'", id=id)

        d = self.transports[id].port.stopListening()

        def ok(_):
            del self.transports[id]

        def fail(err):
            raise ApplicationError(u"crossbar.error.cannot_stop", "Failed to stop transport: {}".format(str(err.value)))

        d.addCallbacks(ok, fail)
        return d

    @wamp.register(None)
    def start_web_transport_service(self, transport_id, path, config, details=None):
        """
        Start a service on a Web transport.

        :param transport_id: The ID of the transport to start the Web transport service on.
        :type transport_id: str

        :param path: The path (absolute URL, eg "/myservice1") on which to start the service.
        :type path: str

        :param config: The Web service configuration.
        :type config: dict
        """
        self.log.info("{name}[{personality}].start_web_transport_service(transport_id={transport_id}, path={path}, config={config})",
                      personality=self.personality.NAME,
                      name=self.__class__.__name__,
                      transport_id=transport_id,
                      path=path,
                      config=config)

        transport = self.transports.get(transport_id, None)
        if not (transport and (transport.config[u'type'] == u'web' or (transport.config[u'type'] == u'universal' and transport.config.get(u'web', {})))):
            emsg = "Cannot start service on Web transport: no transport with ID '{}' or transport is not a Web transport".format(transport_id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        caller = details.caller if details else None
        self.publish(self._uri_prefix + u'.on_web_transport_service_starting',
                     transport_id,
                     path,
                     options=PublishOptions(exclude=caller))

        paths = {
            path: config
        }
        print('5'*100, self.personality)
        self.personality.add_web_services(self.personality,
                                          self._reactor,
                                          transport.root_resource,
                                          paths,
                                          self._templates,
                                          self.log,
                                          self.config.extra.cbdir,
                                          self._router_session_factory,
                                          self)

        on_web_transport_service_started = {
            u'transport_id': transport_id,
            u'path': path,
            u'config': config
        }
        caller = details.caller if details else None
        self.publish(self._uri_prefix + u'.on_web_transport_service_started',
                     transport_id,
                     path,
                     on_web_transport_service_started,
                     options=PublishOptions(exclude=caller))

        return on_web_transport_service_started

    @wamp.register(None)
    def stop_web_transport_service(self, transport_id, path, details=None):
        """
        Stop a service on a Web transport.

        :param transport_id: The ID of the transport to stop the Web transport service on.
        :type transport_id: str

        :param path: The path (absolute URL, eg "/myservice1") of the service to stop.
        :type path: str
        """
        self.log.info("{name}.stop_web_transport_service(transport_id={transport_id}, path={path})",
                      name=self.__class__.__name__,
                      transport_id=transport_id,
                      path=path)

        transport = self.transports.get(transport_id, None)
        if not transport or transport.config[u'type'] != u'web':
            emsg = "Cannot stop service on Web transport: no transport with ID '{}' or transport is not a Web transport".format(transport_id)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        if isinstance(path, six.text_type):
            webPath = path.encode('utf8')
        else:
            webPath = path

        if webPath not in transport.root_resource.children:
            emsg = "Cannot stop service on Web transport {}: no service running on path '{}'".format(transport_id, path)
            self.log.error(emsg)
            raise ApplicationError(u'crossbar.error.not_running', emsg)

        caller = details.caller if details else None
        self.publish(self._uri_prefix + u'.on_web_transport_service_stopping',
                     transport_id,
                     path,
                     options=PublishOptions(exclude=caller))

        remove_paths(self._reactor, transport.root_resource, [path])

        on_web_transport_service_stopped = {
            u'transport_id': transport_id,
            u'path': path,
            u'config': transport.config
        }
        caller = details.caller if details else None
        self.publish(self._uri_prefix + u'.on_web_transport_service_starting',
                     transport_id,
                     path,
                     on_web_transport_service_stopped,
                     options=PublishOptions(exclude=caller))
