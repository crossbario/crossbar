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
from crossbar.worker.transport import TransportController
from crossbar.worker.types import RouterComponent, RouterRealm, RouterRealmRole
from twisted.internet.defer import Deferred, DeferredList, maybeDeferred, returnValue
from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure
from twisted.internet.defer import succeed

from autobahn import wamp
from autobahn.util import utcstr
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import PublishOptions, ComponentConfig, CallDetails, SessionIdent

from crossbar._util import class_name, hltype, hlid, hlval

from crossbar.router.session import RouterSessionFactory
from crossbar.router.service import RouterServiceAgent
from crossbar.router.router import RouterFactory

from crossbar.worker import _appsession_loader
from crossbar.worker.controller import WorkerController
from crossbar.worker.rlink import RLinkConfig


__all__ = ('RouterController',)


class RouterController(TransportController):
    """
    A native Crossbar.io worker that runs a WAMP router which can manage
    multiple realms, run multiple transports and links, as well as host
    multiple (embedded) application components.
    """
    WORKER_TYPE = 'router'
    WORKER_TITLE = 'Router'
    router_realm_class = RouterRealm
    router_factory_class = RouterFactory

    def __init__(self, config=None, reactor=None, personality=None):
        super(RouterController, self).__init__(
            config=config,
            reactor=reactor,
            personality=personality,
        )

        # factory for producing (per-realm) routers
        self._router_factory = self.router_factory_class(self.config.extra.node, self.config.extra.worker, self)

        # factory for producing router sessions
        self._router_session_factory = RouterSessionFactory(self._router_factory)

        # map: realm ID -> RouterRealm
        self.realms = {}

        # map: realm URI -> realm ID
        self.realm_to_id = {}

        self._service_sessions = {}

        # map: component ID -> RouterComponent
        self.components = {}

        # "global" shared between all components
        self.components_shared = {
            'reactor': reactor
        }

        # map: transport ID -> RouterTransport
        self.transports = {}

    def realm_by_name(self, name):
        realm_id = self.realm_to_id.get(name, None)
        assert(realm_id in self.realms)
        return self.realms[realm_id]

    @property
    def router_factory(self):
        """

        :return: The router factory used for producing (per-realm) routers.
        """
        return self._router_factory

    @property
    def router_session_factory(self):
        """

        :return: The router session factory for producing router sessions.
        """
        return self._router_session_factory

    def onWelcome(self, msg):
        # this is a hook for authentication methods to deny the
        # session after the Welcome message -- do we need to do
        # anything in this impl?
        pass

    @inlineCallbacks
    def onJoin(self, details, publish_ready=True):
        """
        Called when worker process has joined the node's management realm.
        """
        self.log.info('Router worker session for "{worker_id}" joined realm "{realm}" on node router {method}',
                      realm=self._realm,
                      worker_id=self._worker_id,
                      session_id=details.session,
                      method=hltype(RouterController.onJoin))

        yield WorkerController.onJoin(self, details, publish_ready=False)

        # WorkerController.publish_ready()
        self.publish_ready()

        self.log.info('Router worker session for "{worker_id}" ready',
                      worker_id=self._worker_id)

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
        dl.addBoth(lambda _: super(RouterController, self).onLeave(details))

    @wamp.register(None)
    def get_router_realms(self, details=None):
        """
        Get realms currently running on this router worker.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of realms currently running.
        :rtype: list[str]
        """
        self.log.debug("{name}.get_router_realms", name=self.__class__.__name__)

        return sorted(self.realms.keys())

    @wamp.register(None)
    def get_router_realm(self, realm_id, details=None):
        """
        Return realm detail information.

        :param realm_id: Realm ID within router worker.
        :type realm_id: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: realm information object
        :rtype: dict
        """
        self.log.debug("{name}.get_router_realm(realm_id={realm_id})", name=self.__class__.__name__, realm_id=realm_id)

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        return self.realms[realm_id].marshal()

    @wamp.register(None)
    def get_router_realm_by_name(self, realm_name, details=None):
        """
        Return realm detail information.

        :param realm_name: Realm name.
        :type realm_name: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: realm information object
        :rtype: dict
        """
        self.log.debug('{klass}.get_router_realm_by_name(realm_name="{realm_name}")',
                       klass=self.__class__.__name__, realm_name=realm_name)

        if realm_name not in self.realm_to_id:
            raise ApplicationError('crossbar.error.no_such_object', 'No realm with name "{}"'.format(realm_name))

        return self.realms[self.realm_to_id[realm_name]].marshal()

    @wamp.register(None)
    def get_router_realm_stats(self, realm_id=None, details=None):
        """
        Return realm messaging statistics.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: realm statistics object
        :rtype: dict
        """
        self.log.debug("{name}.get_router_realm_stats(realm_id={realm_id})", name=self.__class__.__name__, realm_id=realm_id)

        if realm_id is not None and realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if realm_id:
            realm_ids = [realm_id]
        else:
            realm_ids = self.realms.keys()

        res = {}
        for realm_id in realm_ids:
            realm = self.realms[realm_id]
            if realm.router:
                res[realm_id] = realm.router.stats()

        return res

    @wamp.register(None)
    @inlineCallbacks
    def start_router_realm(self, realm_id, realm_config, details=None):
        """
        Starts a realm on this router worker.

        :param realm_id: The ID of the realm to start.
        :type realm_id: str

        :param realm_config: The realm configuration.
        :type realm_config: dict

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        self.log.info('Starting router realm {realm_id} {method}',
                      realm_id=hlid(realm_id), method=hltype(RouterController.start_router_realm))

        # prohibit starting a realm twice
        #
        if realm_id in self.realms:
            emsg = "Could not start realm: a realm with ID '{}' is already running (or starting)".format(realm_id)
            self.log.error(emsg)
            raise ApplicationError('crossbar.error.already_running', emsg)

        # check configuration
        #
        try:
            self.personality.check_router_realm(self.personality, realm_config)
        except Exception as e:
            emsg = "Invalid router realm configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.invalid_configuration", emsg)

        # URI of the realm to start
        realm_name = realm_config['name']

        # router/realm wide options
        options = realm_config.get('options', {})

        enable_meta_api = options.get('enable_meta_api', True)

        # expose router/realm service API additionally on local node management router
        bridge_meta_api = options.get('bridge_meta_api', False)
        if bridge_meta_api:
            # FIXME
            bridge_meta_api_prefix = 'crossbar.worker.{worker_id}.realm.{realm_id}.root.'.format(worker_id=self._worker_id, realm_id=realm_id)
        else:
            bridge_meta_api_prefix = None

        # track realm
        rlm = self.router_realm_class(self, realm_id, realm_config)
        self.realms[realm_id] = rlm
        self.realm_to_id[realm_name] = realm_id

        # create a new router for the realm
        rlm.router = self._router_factory.start_realm(rlm)

        if rlm.router._store and hasattr(rlm.router._store, 'start'):
            yield rlm.router._store.start()

        # add a router/realm service session
        extra = {
            # the RouterServiceAgent will fire this when it is ready
            'onready': Deferred(),

            # if True, forward the WAMP meta API (implemented by RouterServiceAgent)
            # that is normally only exposed on the app router/realm _additionally_
            # to the local node management router.
            'enable_meta_api': enable_meta_api,
            'bridge_meta_api': bridge_meta_api,
            'bridge_meta_api_prefix': bridge_meta_api_prefix,

            # the management session on the local node management router to which
            # the WAMP meta API is exposed to additionally, when the bridge_meta_api option is set
            'management_session': self,
        }
        cfg = ComponentConfig(realm_name, extra)
        # each worker is run under its own dedicated WAMP auth role
        # svc_authrole = 'crossbar.worker.{}'.format(self._worker_id)
        # wamp meta api only allowed for "trusted" sessions
        svc_authrole = 'trusted'
        svc_authid = 'routerworker-{}-realm-{}-serviceagent'.format(self._worker_id, realm_id)
        rlm.session = RouterServiceAgent(cfg, rlm.router)
        self._router_session_factory.add(rlm.session, rlm.router, authid=svc_authid, authrole=svc_authrole)

        yield extra['onready']
        self.set_service_session(rlm.session, realm_name, authrole=svc_authrole)
        self.log.info('RouterServiceAgent started on realm="{realm_name}" with authrole="{authrole}", authid="{authid}"',
                      realm_name=realm_name, authrole=svc_authrole, authid=svc_authid)

        self.publish('{}.on_realm_started'.format(self._uri_prefix), realm_id)

        topic = '{}.on_realm_started'.format(self._uri_prefix)
        event = rlm.marshal()
        caller = details.caller if details else None
        self.publish(topic, event, options=PublishOptions(exclude=caller))

        self.log.info('Realm "{realm_id}" (name="{realm_name}", authrole="{authrole}", authid="{authid}") started', realm_id=realm_id,
                      realm_name=rlm.session._realm, authrole=svc_authrole, authid=svc_authid)
        return event

    @wamp.register(None)
    @inlineCallbacks
    def stop_router_realm(self, realm_id, details=None):
        """
        Stop a realm currently running on this router worker.

        When a realm has stopped, no new session will be allowed to attach to the realm.
        Optionally, close all sessions currently attached to the realm.

        :param id: ID of the realm to stop.
        :type id: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        self.log.info("{name}.stop_router_realm", name=self.__class__.__name__)

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        rlm = self.realms[realm_id]
        realm_name = rlm.config['name']

        # stop the RouterServiceAgent living on the realm
        yield rlm.session.leave()
        self._router_session_factory.remove(rlm.session)
        self.log.info('RouterServiceAgent stopped on realm "{realm_name}"', realm_name=realm_name)

        detached_sessions = self._router_factory.stop_realm(realm_name)

        del self.realms[realm_id]
        del self.realm_to_id[realm_name]

        realm_stopped = {
            'id': realm_id,
            'name': realm_name,
            'detached_sessions': sorted(detached_sessions)
        }

        self.publish('{}.on_realm_stopped'.format(self._uri_prefix), realm_id)
        returnValue(realm_stopped)

    def has_realm(self, realm: str) -> bool:
        """
        Check if a realm with the given name is currently running.

        :param realm: Realm name (_not_ ID).
        :type realm: str

        :returns: True if realm is running.
        :rtype: bool
        """
        result = realm in self.realm_to_id and self.realm_to_id[realm] in self.realms
        self.log.debug('{func}(realm="{realm}") -> {result}', func=hltype(RouterController.has_realm),
                       realm=hlid(realm), result=hlval(result))
        return result

    def has_role(self, realm: str, authrole: str) -> bool:
        """
        Check if a role with the given name is currently running in the given realm.

        :param realm: WAMP realm (name, _not_ run-time ID).
        :type realm: str

        :param authrole: WAMP authentication role (URI, _not_ run-time ID).
        :type authrole: str

        :returns: True if realm is running.
        :rtype: bool
        """
        authrole = authrole or 'trusted'
        result = realm in self.realm_to_id and self.realm_to_id[realm] in self.realms
        if result:
            realm_id = self.realm_to_id[realm]
            result = (authrole in self.realms[realm_id].role_to_id and self.realms[realm_id].role_to_id[authrole] in self.realms[realm_id].roles)

            # note: this is to enable eg built-in "trusted" authrole
            result = result or authrole in self._service_sessions[realm]

        self.log.debug('{func}(realm="{realm}", authrole="{authrole}") -> {result}',
                       func=hltype(RouterController.has_role), realm=hlid(realm), authrole=hlid(authrole),
                       result=hlval(result))
        return result

    def set_service_session(self, session, realm, authrole):
        authrole = authrole or 'trusted'
        if realm not in self._service_sessions:
            self._service_sessions[realm] = {}
        self._service_sessions[realm][authrole] = session
        self.log.info('{func}(session={session}, realm="{realm}", authrole="{authrole}")',
                      func=hltype(self.set_service_session), session=session,
                      realm=hlid(realm), authrole=hlid(authrole))

    def get_service_session(self, realm, authrole):
        authrole = authrole or 'trusted'
        session = None
        if realm in self._service_sessions:
            if authrole in self._service_sessions[realm]:
                session = self._service_sessions[realm][authrole]
        self.log.debug('{func}(realm="{realm}", authrole="{authrole}") -> {session}',
                       func=hltype(self.get_service_session), session=session,
                       realm=hlid(realm), authrole=hlid(authrole))
        return succeed(session)

    @wamp.register(None)
    def get_router_realm_roles(self, realm_id, details=None):
        """
        Get roles currently running on a realm running on this router worker.

        :param realm_id: The ID of the realm to list roles for.
        :type realm_id: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: A list of roles.
        :rtype: list[dict]
        """
        self.log.debug("{name}.get_router_realm_roles({realm_id})", name=self.__class__.__name__, realm_id=realm_id)

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        return self.realms[realm_id].roles.values()

    @wamp.register(None)
    def get_router_realm_role(self, realm_id, role_id, details=None):
        """
        Return role detail information.

        :param realm_id: The ID of the realm to get a role for.
        :type realm_id: str

        :param role_id: The ID of the role to get.
        :type role_id: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: role information object
        :rtype: dict
        """
        self.log.debug("{name}.get_router_realm_role(realm_id={realm_id}, role_id={role_id})",
                       name=self.__class__.__name__, realm_id=realm_id, role_id=role_id)

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if role_id not in self.realms[realm_id].roles:
            raise ApplicationError("crossbar.error.no_such_object", "No role with ID '{}' on realm '{}'".format(role_id, realm_id))

        return self.realms[realm_id].roles[role_id].marshal()

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

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        self.log.debug('Starting role "{role_id}" on realm "{realm_id}" {method}',
                       role_id=role_id, realm_id=realm_id, method=hltype(self.start_router_realm_role))

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if role_id in self.realms[realm_id].roles:
            raise ApplicationError("crossbar.error.already_exists", "A role with ID '{}' already exists in realm with ID '{}'".format(role_id, realm_id))

        realm = self.realms[realm_id].config['name']
        role = RouterRealmRole(role_id, role_config)
        role_name = role.config['name']

        if role_name in self.realms[realm_id].role_to_id:
            raise ApplicationError("crossbar.error.already_exists", "A role with name '{}' already exists in realm with ID '{}'".format(role_name, realm_id))

        self.realms[realm_id].roles[role_id] = role
        self.realms[realm_id].role_to_id[role_name] = role_id
        self._router_factory.add_role(realm, role_config)

        topic = '{}.on_router_realm_role_started'.format(self._uri_prefix)
        event = self.realms[realm_id].roles[role_id].marshal()
        caller = details.caller if details else None
        self.publish(topic, event, options=PublishOptions(exclude=caller))

        self.log.info('Role {role_id} named "{role_name}" started on realm "{realm}"', role_id=hlid(role_id),
                      role_name=hlid(role_name), realm=hlid(realm), func=hltype(self.start_router_realm_role))
        return event

    @wamp.register(None)
    def stop_router_realm_role(self, realm_id, role_id, details=None):
        """
        Stop a role currently running on a realm running on this router worker.

        :param realm_id: The ID of the realm of the role to be stopped.
        :type realm_id: str

        :param role_id: The ID of the role to be stopped.
        :type role_id: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        self.log.debug("{name}.stop_router_realm_role", name=self.__class__.__name__)

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        if role_id not in self.realms[realm_id].roles:
            raise ApplicationError("crossbar.error.no_such_object", "No role with ID '{}' in realm with ID '{}'".format(role_id, realm_id))

        role = self.realms[realm_id].roles.pop(role_id)
        del self.realms[realm_id].role_to_id[role.config['name']]

        topic = '{}.on_router_realm_role_stopped'.format(self._uri_prefix)
        event = role.marshal()
        caller = details.caller if details else None
        self.publish(topic, event, options=PublishOptions(exclude=caller))

        self.log.info('role {role_id} on realm {realm_id} stopped', realm_id=realm_id, role_id=role_id)
        return event

    @wamp.register(None)
    def get_router_components(self, details=None):
        """
        Get app components currently running in this router worker.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of app components currently running.
        :rtype: list[dict]
        """
        self.log.debug("{name}.get_router_components", name=self.__class__.__name__)

        res = []
        for component in sorted(self.components.values(), key=lambda c: c.created):
            res.append({
                'id': component.id,
                'created': utcstr(component.created),
                'config': component.config,
            })
        return res

    @wamp.register(None)
    def get_router_component(self, id, details=None):
        """
        Get details about a router component

        :param id: The ID of the component to get
        :type id: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: Details of component
        :rtype: dict
        """
        self.log.debug("{name}.get_router_component({id})", name=self.__class__.__name__, id=id)
        if id in self.components:
            return self.components[id].marshal()
        else:
            raise ApplicationError("crossbar.error.no_such_object", "No component {}".format(id))

    @wamp.register(None)
    def start_router_component(self, id, config, details=None):
        """
        Start an app component in this router worker.

        :param id: The ID of the component to start.
        :type id: str

        :param config: The component configuration.
        :type config: dict

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        self.log.debug("{name}.start_router_component", name=self.__class__.__name__)

        # prohibit starting a component twice
        #
        if id in self.components:
            emsg = "Could not start component: a component with ID '{}'' is already running (or starting)".format(id)
            self.log.error(emsg)
            raise ApplicationError('crossbar.error.already_running', emsg)

        started_d = Deferred()

        # check configuration
        #
        try:
            self.personality.check_router_component(self.personality, config)
        except Exception as e:
            emsg = "Invalid router component configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.invalid_configuration", emsg)
        else:
            self.log.debug("Starting {type}-component on router.",
                           type=config['type'])

        # resolve references to other entities
        #
        references = {}
        for ref in config.get('references', []):
            ref_type, ref_id = ref.split(':')
            if ref_type == 'connection':
                if ref_id in self._connections:
                    references[ref] = self._connections[ref_id]
                else:
                    emsg = "cannot resolve reference '{}' - no '{}' with ID '{}'".format(ref, ref_type, ref_id)
                    self.log.error(emsg)
                    raise ApplicationError("crossbar.error.invalid_configuration", emsg)
            else:
                emsg = "cannot resolve reference '{}' - invalid reference type '{}'".format(ref, ref_type)
                self.log.error(emsg)
                raise ApplicationError("crossbar.error.invalid_configuration", emsg)

        # create component config
        #
        realm = config.get('realm', None)
        assert isinstance(realm, str)

        extra = config.get('extra', {})
        assert isinstance(extra, dict)

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
            self.log.error('component loading failed', log_failure=Failure())
            if 'No module named' in str(e):
                self.log.error('  Python module search paths:')
                for path in e.kwargs['pythonpath']:
                    self.log.error('    {path}', path=path)
            raise

        # check component extra configuration
        #
        if hasattr(create_component, 'check_config') and callable(create_component.check_config) and extra:
            try:
                create_component.check_config(self.personality, extra)
            except Exception as e:
                emsg = 'invalid router component extra configuration: {}'.format(e)
                self.log.debug(emsg)
                raise ApplicationError('crossbar.error.invalid_configuration', emsg)
            else:
                self.log.debug('starting router component "{component_id}" ..', component_id=id)

        # .. and create and add an WAMP application session to
        # run the component next to the router
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
            event = {'id': id}
            caller = details.caller if details else None
            self.publish(topic, event, options=PublishOptions(exclude=caller))
            if not started_d.called:
                started_d.errback(Exception("Session left before being ready"))
            return event

        def publish_ready(session):
            """
            when our component is ready, we publish .on_component_ready
            """
            self.log.info(
                "component ready: {session} id={session_id}",
                session=class_name(session),
                session_id=session._session_id,
            )
            topic = self._uri_prefix + '.on_component_ready'
            event = {'id': id}
            self.publish(topic, event)
            started_d.callback(event)
            return event

        def publish_started(session, start_details):
            """
            when our component starts, we publish .on_component_start
            """

            # hook up handlers for "session is ready"
            session.on('ready', publish_ready)

            # publish .on_component_start
            self.log.info(
                "started component: {session} id={session_id}",
                session=class_name(session),
                session_id=session._session_id,
            )
            topic = self._uri_prefix + '.on_component_start'
            event = {'id': id}
            caller = details.caller if details else None
            self.publish(topic, event, options=PublishOptions(exclude=caller))
            return event

        session.on('leave', publish_stopped)
        session.on('join', publish_started)

        self.components[id] = RouterComponent(id, config, session)
        router = self._router_factory.get(realm)
        self._router_session_factory.add(session, router, authrole=config.get('role', 'anonymous'))
        self.log.debug(
            "Added component {id} (type '{name}')",
            id=id,
            name=class_name(session),
        )
        return started_d

    @wamp.register(None)
    def stop_router_component(self, id, details=None):
        """
        Stop an app component currently running in this router worker.

        :param id: The ID of the component to stop.
        :type id: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        self.log.debug("{name}.stop_router_component({id})", name=self.__class__.__name__, id=id)

        if id in self.components:
            self.log.debug("Worker {worker}: stopping component {id}", worker=self.config.extra.worker, id=id)

            try:
                # self._components[id].disconnect()
                self._session_factory.remove(self.components[id])
                del self.components[id]
            except Exception as e:
                raise ApplicationError("crossbar.error.cannot_stop", "Failed to stop component {}: {}".format(id, e))
        else:
            raise ApplicationError("crossbar.error.no_such_object", "No component {}".format(id))

    @wamp.register(None)
    def get_router_transports(self, details=None):
        """
        Get transports currently running in this router worker.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of transports currently running.
        :rtype: list[dict]
        """
        self.log.debug("{name}.get_router_transports", name=self.__class__.__name__)

        res = []
        for transport in sorted(self.transports.values(), key=lambda c: c.created):
            res.append(transport.marshal())
        return res

    @wamp.register(None)
    def get_router_transport(self, transport_id, details=None):
        """
        Get transports currently running in this router worker.

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`

        :returns: List of transports currently running.
        :rtype: list[dict]
        """
        self.log.debug("{name}.get_router_transport", name=self.__class__.__name__)

        if transport_id in self.transports:
            transport = self.transports[transport_id]
            obj = transport.marshal()
            return obj
        else:
            raise ApplicationError("crossbar.error.no_such_object", "No transport {}".format(transport_id))

    @wamp.register(None)
    def start_router_transport(self, transport_id, config, create_paths=False, details=None):
        """
        Start a transport on this router worker.

        :param transport_id: The ID of the transport to start.
        :type transport_id: str

        :param config: The transport configuration.
        :type config: dict

        :param create_paths: If set, start subservices defined in the configuration too.
            This currently only applies to Web services, which are part of a Web transport.
        :type create_paths: bool

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        self.log.info('Starting router transport "{transport_id}" {method}',
                      transport_id=transport_id, method=hltype(self.start_router_transport))

        # prohibit starting a transport twice
        if transport_id in self.transports:
            _emsg = 'Could not start transport: a transport with ID "{}" is already running (or starting)'.format(transport_id)
            self.log.error(_emsg)
            raise ApplicationError('crossbar.error.already_running', _emsg)

        # create a transport and parse the transport configuration
        router_transport = self.personality.create_router_transport(self, transport_id, config)

        caller = details.caller if details else None
        event = {
            'id': transport_id
        }
        topic = '{}.on_router_transport_starting'.format(self._uri_prefix)
        self.publish(topic, event, options=PublishOptions(exclude=caller))

        # start listening ..
        d = router_transport.start(create_paths)

        def ok(_):
            self.transports[transport_id] = router_transport
            if config['endpoint']['type'] == 'tcp':
                endpoint = 'TCP port {}'.format(config['endpoint']['port'])
                if 'portrange' in config['endpoint']:
                    transport_type = 'TCP/{} transport'.format(config['endpoint']['portrange'])
                else:
                    transport_type = 'TCP/{} transport'.format(config['endpoint']['port'])
            elif config['endpoint']['type'] == 'unix':
                endpoint = 'UDS path "{}"'.format(config['endpoint']['path'])
                transport_type = 'Unix domain socket transport'
            else:
                endpoint = 'unknown'
                transport_type = 'unknown'
            self.log.info('Router {transport_type} started as transport "{transport_id}" and listening on {endpoint}',
                          transport_type=hlval(transport_type),
                          transport_id=hlid(transport_id),
                          endpoint=hlval(endpoint))

            topic = '{}.on_router_transport_started'.format(self._uri_prefix)
            self.publish(topic, event, options=PublishOptions(exclude=caller))

            return router_transport.marshal()

        def fail(err):
            _emsg = "Cannot listen on transport endpoint: {log_failure}"
            self.log.error(_emsg, log_failure=err)

            topic = '{}.on_router_transport_stopped'.format(self._uri_prefix)
            self.publish(topic, event, options=PublishOptions(exclude=caller))

            raise ApplicationError("crossbar.error.cannot_listen", _emsg)

        d.addCallbacks(ok, fail)
        return d

    @wamp.register(None)
    def stop_router_transport(self, transport_id, details=None):
        """
        Stop a transport currently running in this router worker.

        :param transport_id: The ID of the transport to stop.
        :type transport_id: str

        :param details: Call details.
        :type details: :class:`autobahn.wamp.types.CallDetails`
        """
        self.log.debug("{name}.stop_router_transport", name=self.__class__.__name__)

        if transport_id not in self.transports or self.transports[transport_id].state != self.personality.RouterTransport.STATE_STARTED:
            emsg = "Cannot stop transport: no transport with ID '{}' or transport is already stopping".format(transport_id)
            self.log.error(emsg)
            raise ApplicationError('crossbar.error.not_running', emsg)

        router_transport = self.transports[transport_id]

        self.log.debug("Stopping transport with ID '{transport_id}'", transport_id=transport_id)

        caller = details.caller if details else None
        event = router_transport.marshal()
        topic = '{}.on_router_transport_stopping'.format(self._uri_prefix)
        self.publish(topic, event, options=PublishOptions(exclude=caller))

        # stop listening ..
        d = router_transport.stop()

        def ok(_):
            del self.transports[transport_id]

            topic = '{}.on_router_transport_stopped'.format(self._uri_prefix)
            self.publish(topic, event, options=PublishOptions(exclude=caller))

            return event

        def fail(err):
            emsg = "Cannot stop listening on transport endpoint: {log_failure}"
            self.log.error(emsg, log_failure=err)

            raise ApplicationError("crossbar.error.cannot_stop", emsg)

        d.addCallbacks(ok, fail)
        return d

    @wamp.register(None)
    def kill_by_authid(self, realm_id, authid, reason, message=None, details=None):
        self.log.info('Killing sessions by authid="{authid}" ..',
                      realm_id=hlid(realm_id), authid=hlid(authid),
                      method=hltype(RouterController.start_router_realm))

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        # forward call directly to service agent
        return self.realms[realm_id].session.session_kill_by_authid(authid, reason, message=message, details=details)

    @wamp.register(None)
    def get_router_realm_links(self, realm_id, details=None):
        """
        Returns the currently running routing links to remote router realms.

        :param realm_id: The ID of the (local) realm to get links for.
        :type realm_id: str

        :returns: List of router link IDs.
        :rtype: list[str]
        """
        assert type(realm_id) == str
        assert isinstance(details, CallDetails)

        self.log.info(
            '{method} Getting router links for realm {realm_id}',
            realm_id=hlid(realm_id),
            method=hltype(RouterController.get_router_realm_links))

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        rlink_manager = self.realms[realm_id].rlink_manager

        return sorted([str(k) for k in rlink_manager.keys()])

    @wamp.register(None)
    def get_router_realm_link(self, realm_id, link_id, details=None):
        """
        Get router link detail information.

        :param realm_id: The ID of the (local) realm of the link.
        :type realm_id: str

        :param link_id: The ID of the router link to return.
        :type link_id: str

        :returns: Router link detail information.
        :rtype: dict
        """
        assert type(realm_id) == str
        assert type(link_id) == str
        assert isinstance(details, CallDetails)

        self.log.info(
            '{method} Get router link {link_id} on realm {realm_id}',
            link_id=hlid(link_id),
            realm_id=hlid(realm_id),
            method=hltype(RouterController.get_router_realm_link))

        if realm_id not in self.realms:
            raise ApplicationError("crossbar.error.no_such_object", "No realm with ID '{}'".format(realm_id))

        rlink_manager = self.realms[realm_id].rlink_manager

        if link_id not in rlink_manager:
            raise ApplicationError("crossbar.error.no_such_object", "No link with ID '{}'".format(link_id))

        rlink = rlink_manager[link_id]

        return rlink.marshal()

    @wamp.register(None)
    @inlineCallbacks
    def start_router_realm_link(self, realm_id, link_id, link_config, details=None):
        """
        Start a new router link to a remote router on a (local) realm.

        The link configuration (``link_config``) must include the transport definition
        to the remote router. Here is an example:

        .. code-block:: json

            {
                "realm": "realm1",
                "transport": {
                    "type": "websocket",
                    "endpoint": {
                        "type": "tcp",
                        "host": "localhost",
                        "port": 8002
                    },
                    "url": "ws://localhost:8002/ws"
                }
            }

        :param realm_id: The ID of the (local) realm on which to start the link.
        :type realm_id: str

        :param link_id: The ID of the router link to start.
        :type link_id: str

        :param link_config: The router link configuration.
        :type link_config: dict

        :returns: The new link detail information.
        :rtype: dict
        """
        assert type(realm_id) == str
        assert type(link_id) == str
        assert type(link_config) == dict
        assert isinstance(details, CallDetails)

        self.log.info(
            '{method} Router link {link_id} starting on realm {realm_id} ..',
            link_id=hlid(link_id),
            realm_id=hlid(realm_id),
            method=hltype(RouterController.start_router_realm_link))

        try:
            if realm_id not in self.realms:
                self.log.warn('{func} realm "{realm}" not found in {realms}',
                              func=hltype(self.start_router_realm_link),
                              realm=hlval(realm_id),
                              realms=sorted(self.realms.keys()))
                raise ApplicationError('crossbar.error.no_such_object', 'no realm with ID {}'.format(realm_id))

            rlink_manager = self.realms[realm_id].rlink_manager

            if link_id in rlink_manager:
                raise ApplicationError('crossbar.error.already_running',
                                       'router link {} already running'.format(link_id))
            link_config = RLinkConfig.parse(self.personality, link_config, id=link_id)
            caller = SessionIdent.from_calldetails(details)
            rlink = yield rlink_manager.start_link(link_id, link_config, caller)
            started = rlink.marshal()
        except:
            self.log.failure()
            raise
        else:
            self.publish('{}.on_router_realm_link_started'.format(self._uri_prefix), started)

            self.log.info('Router link {link_id} started on realm {realm_id}',
                          link_id=hlid(link_id), realm_id=hlid(realm_id))

            returnValue(started)

    @wamp.register(None)
    @inlineCallbacks
    def stop_router_realm_link(self, realm_id, link_id, details=None):
        """
        Stop a currently running router link.

        :param realm_id: The ID of the (local) realm on which the link is running that is to be stopped.
        :type realm_id: str

        :param link_id: The ID of the router link to stop.
        :type link_id: str

        :returns: The stopped link detail information.
        :rtype: dict
        """
        assert type(realm_id) == str
        assert type(link_id) == str
        assert isinstance(details, CallDetails)

        self.log.info(
            '{method} Router link {link_id} stopping on realm {realm_id}',
            link_id=hlid(link_id),
            realm_id=hlid(realm_id),
            method=hltype(RouterController.stop_router_realm_link))

        if realm_id not in self.realms:
            raise ApplicationError('crossbar.error.no_such_object', 'no realm with ID {}'.format(realm_id))

        rlink_manager = self.realms[realm_id].rlink_manager

        if link_id not in self.rlink_manager:
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no router link with ID {}'.format(link_id))

        caller = SessionIdent.from_calldetails(details)

        rlink = yield rlink_manager.stop_link(link_id, caller)

        stopped = rlink.marshal()

        self.publish('{}.on_router_realm_link_stopped'.format(self._uri_prefix), stopped)

        self.log.info('Router link {link_id} stopped', link_id=hlid(link_id))

        returnValue(stopped)
