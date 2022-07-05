#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import txaio
import uuid
from pprint import pformat
from typing import Optional, Dict, Any, Set, Tuple, List

from txaio import make_logger

from autobahn.util import hltype, hlid, hlval
from autobahn.wamp import message
from autobahn.wamp.exception import ProtocolError, InvalidPayload
from autobahn.wamp.interfaces import ISession
from autobahn.xbr import FbsObject

from crossbar.router import RouterOptions
from crossbar.router.broker import Broker
from crossbar.router.dealer import Dealer
from crossbar.router.role import RouterRole, \
    RouterTrustedRole, RouterRoleStaticAuth, \
    RouterRoleDynamicAuth
from crossbar.interfaces import IRealmStore, IInventory
from crossbar.worker.types import RouterRealm

__all__ = (
    'RouterFactory',
    'Router',
)


def _is_client_session(session):
    return hasattr(session, '_session_details')


class Router(object):
    """
    Crossbar.io core router class.
    """
    log = make_logger()

    RESERVED_ROLES = ['trusted']
    """
    Roles with these URIs are built-in and cannot be added/dropped.
    """

    broker = Broker
    """
    The broker class this router will use.
    """

    dealer = Dealer
    """
    The dealer class this router will use.
    """
    def __init__(self,
                 factory,
                 realm,
                 options: Optional[RouterOptions] = None,
                 store: Optional[IRealmStore] = None,
                 inventory: Optional[IInventory] = None):
        """

        :param factory: The router factory this router was created by.
        :type factory: Object that implements :class:`autobahn.wamp.interfaces.IRouterFactory`.

        :param realm: The realm this router is working for.
        :type realm: Instance of :class:`crossbar.worker.router.RouterRealm`.

        :param options: Router options.
        :param store: Router realm store to use (optional).
        """
        self._factory = factory
        self._realm = realm
        self._options = options or RouterOptions()
        self._store: Optional[IRealmStore] = store
        self._inventory: Optional[IInventory] = inventory

        self.realm = realm.config['name']

        self._trace_traffic = False
        self._trace_traffic_roles_include = None
        self._trace_traffic_roles_exclude = ['trusted']

        # map: session_id -> session
        self._session_id_to_session: Dict[int, ISession] = {}

        # map: authid -> set(session)
        self._authid_to_sessions: Dict[str, Set[ISession]] = {}

        # map: authrole -> set(session)
        self._authrole_to_sessions: Dict[str, Set[ISession]] = {}

        # map: (realm, authrole, uri, action) -> authorization
        self._authorization_cache: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}

        self._broker = self.broker(self, factory._reactor, self._options)
        self._dealer = self.dealer(self, factory._reactor, self._options)
        self._attached = 0

        self._roles = {'trusted': RouterTrustedRole(self, 'trusted')}

        # FIXME: this was previously just checking for existence of
        # self._factory._worker._maybe_trace_tx_msg / _maybe_trace_rx_msg
        self._is_traced = False

        self.reset_stats()

    def stats(self, reset=False):
        """
        Get WAMP message routing statistics.

        :param reset: Automatically reset statistics before returning.
        :type reset: bool

        :return: Dict with number of WAMP messages processed in total by the
            router, indexed by sent/received and by WAMP message type.
        """
        stats = {
            # number of WAMP authentication roles defined on this realm
            'roles': len(self._roles),

            # number of WAMP sessions currently joined on this realm
            'sessions': self._attached,

            # WAMP message routing statistics
            'messages': self._message_stats
        }
        if reset:
            self.reset_stats()
        return stats

    def reset_stats(self):
        """
        Reset WAMP message routing statistics.
        """
        self._message_stats = {
            # number of WAMP messages (by type) sent on total by the router
            'sent': {},

            # number of WAMP messages (by type) received in total by the router
            'received': {},
        }

    @property
    def is_traced(self):
        return self._is_traced

    def new_correlation_id(self):
        return str(uuid.uuid4())

    def is_attached(self, session):
        return session._session_id in self._session_id_to_session

    def attach(self, session: ISession):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.attach`
        """
        self.log.debug('{func}(session={session})', func=hltype(self.attach), session=session)

        if session._session_id not in self._session_id_to_session:
            self._session_id_to_session[session._session_id] = session
        else:
            raise Exception("session with ID {} already attached".format(session._session_id))

        self._broker.attach(session)
        self._dealer.attach(session)

        self._attached += 1

        self.log.info(
            '{func} new session attached for realm="{realm}", session={session}, authid="{authid}", '
            'authrole="{authrole}", authmethod="{authmethod}", authprovider="{authprovider}", authextra=\n{authextra}',
            func=hltype(self.attach),
            session=hlid(session._session_id) if session else '',
            authid=hlid(session._authid),
            authrole=hlid(session._authrole),
            authmethod=hlval(session._authmethod),
            authprovider=hlval(session._authprovider),
            authextra=pformat(session._authextra) if session._authextra else None,
            realm=hlid(session._realm))

        return {'broker': self._broker._role_features, 'dealer': self._dealer._role_features}

    def _session_joined(self, session, session_details):
        """
        Internal helper.
        """
        try:
            self._authrole_to_sessions[session_details.authrole].add(session)
        except KeyError:
            self._authrole_to_sessions[session_details.authrole] = set([session])

        try:
            self._authid_to_sessions[session_details.authid].add(session)
        except KeyError:
            self._authid_to_sessions[session_details.authid] = set([session])

        if self._store:
            self._store.store_session_joined(session, session_details)

        # log session details, but skip Crossbar.io internal sessions
        if self.realm != 'crossbar':
            self.log.debug(
                'session "{session_id}" joined realm "{realm}"',
                session_id=session_details.session,
                realm=self.realm,
            )
            self.log.trace('{session_details}', details=session_details)

    def _session_left(self, session, session_details, close_details):
        """
        Internal helper.
        """
        self._authid_to_sessions[session_details.authid].discard(session)
        if not self._authid_to_sessions[session_details.authid]:
            del self._authid_to_sessions[session_details.authid]
        self._authrole_to_sessions[session_details.authrole].discard(session)

        if self._store:
            self._store.store_session_left(session, close_details)

        # log session details, but skip Crossbar.io internal sessions
        if self.realm != 'crossbar':
            self.log.debug(
                'session "{session_id}" left realm "{realm}"',
                session_id=session_details.session,
                realm=self.realm,
            )
            self.log.trace('{details}', details=session_details)

    def detach(self, session=None) -> List[int]:
        self.log.debug('{func}(session={session})', func=hltype(self.detach), session=session)

        detached_session_ids = []
        if session is None:
            # detach all sessions from router
            for session in list(self._session_id_to_session.values()):
                self._detach(session)
                detached_session_ids.append(session._session_id)
        else:
            # detach single session from router
            self._detach(session)
            detached_session_ids.append(session._session_id)

        self.log.info(
            '{func} router session detached from realm "{realm}" (session={session}, '
            'detached_session_ids={detached_session_ids}, authid="{authid}", authrole="{authrole}", '
            'authmethod="{authmethod}", authprovider="{authprovider}")',
            func=hltype(self.detach),
            session=hlid(session._session_id) if session else '',
            authid=hlid(session._authid),
            authrole=hlid(session._authrole),
            authmethod=hlval(session._authmethod),
            authprovider=hlval(session._authprovider),
            detached_session_ids=hlval(len(detached_session_ids)),
            realm=hlid(session._realm))

        return detached_session_ids

    def _detach(self, session):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.detach`
        """
        self._broker.detach(session)
        self._dealer.detach(session)

        if session._session_id in self._session_id_to_session:
            del self._session_id_to_session[session._session_id]
        else:
            raise Exception("session with ID {} not attached".format(session._session_id))

        self._attached -= 1
        if not self._attached:
            self._factory.on_last_detach(self)

        return session._session_id

    def _check_trace(self, session, msg):
        if not self._trace_traffic:
            return False
        if self._trace_traffic_roles_include and session._authrole not in self._trace_traffic_roles_include:
            return False
        if self._trace_traffic_roles_exclude and session._authrole in self._trace_traffic_roles_exclude:
            return False
        return True

    def send(self, session, msg):
        if self._check_trace(session, msg):
            self.log.info("<<TX<< {msg}", msg=msg)

        if session._transport:
            session._transport.send(msg)

            if self._is_traced:
                self._factory._worker._maybe_trace_tx_msg(session, msg)
        else:
            self.log.debug('skip sending msg - transport already closed')

        # update WAMP message routing statistics
        msg_type = msg.__class__.__name__.lower()
        if msg_type not in self._message_stats['sent']:
            self._message_stats['sent'][msg_type] = 0
        self._message_stats['sent'][msg_type] += 1

    def process(self, session, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.process`
        """
        if self._check_trace(session, msg):
            self.log.info(">>RX>> {msg}", msg=msg)

        try:
            # Broker
            #
            if isinstance(msg, message.Publish):
                self._broker.processPublish(session, msg)

            elif isinstance(msg, message.Subscribe):
                self._broker.processSubscribe(session, msg)

            elif isinstance(msg, message.Unsubscribe):
                self._broker.processUnsubscribe(session, msg)

            # FIXME: implement EventReceived
            # elif isinstance(msg, message.EventReceived):
            #     self._broker.processEventReceived(session, msg)

            # Dealer
            #
            elif isinstance(msg, message.Register):
                self._dealer.processRegister(session, msg)

            elif isinstance(msg, message.Unregister):
                self._dealer.processUnregister(session, msg)

            elif isinstance(msg, message.Call):
                self._dealer.processCall(session, msg)

            elif isinstance(msg, message.Cancel):
                self._dealer.processCancel(session, msg)

            elif isinstance(msg, message.Yield):
                self._dealer.processYield(session, msg)

            elif isinstance(msg, message.Error) and msg.request_type == message.Invocation.MESSAGE_TYPE:
                self._dealer.processInvocationError(session, msg)

            else:
                raise ProtocolError("Unexpected message {0}".format(msg.__class__))
        except ProtocolError:
            raise
        except:
            self.log.error('INTERNAL ERROR in router incoming message processing')
            self.log.failure()

        # update WAMP message routing statistics
        msg_type = msg.__class__.__name__.lower()
        if msg_type not in self._message_stats['received']:
            self._message_stats['received'][msg_type] = 0
        self._message_stats['received'][msg_type] += 1

    def has_role(self, uri):
        """
        Check if a role with given URI exists on this router.

        :returns: bool - `True` if a role under the given URI exists on this router.
        """
        self.log.info('{func}: uri="{uri}", exists={exists}',
                      func=hltype(self.has_role),
                      uri=hlval(uri),
                      exists=(uri in self._roles))
        return uri in self._roles

    def add_role(self, role):
        """
        Adds a role to this router.

        :param role: The role to add.
        :type role: An instance of :class:`crossbar.router.session.CrossbarRouterRole`.

        :returns: bool -- `True` if a role under the given URI actually existed before and was overwritten.
        """
        self.log.debug("CrossbarRouter.add_role({role})", role=role)

        if role.uri in self.RESERVED_ROLES:
            raise Exception("cannot add reserved role '{}'".format(role.uri))

        overwritten = role.uri in self._roles

        self._roles[role.uri] = role

        return overwritten

    def drop_role(self, role):
        """
        Drops a role from this router.

        :param role: The role to drop.
        :type role: An instance of :class:`crossbar.router.session.CrossbarRouterRole`.

        :returns: bool -- `True` if a role under the given URI actually existed and was removed.
        """
        self.log.debug("CrossbarRouter.drop_role({role})", role=role)

        if role.uri in self.RESERVED_ROLES:
            raise Exception("cannot drop reserved role '{}'".format(role.uri))

        if role.uri in self._roles:
            del self._roles[role.uri]
            return True
        else:
            return False

    def authorize(self, session: ISession, uri: str, action: str, options: Dict[str, Any]):
        """
        Authorizes a session for an action on an URI.

        Implements :func:`autobahn.wamp.interfaces.IRouter.authorize`
        """
        assert (action in ['call', 'register', 'publish', 'subscribe'])

        # the realm, authid and authrole under which the session that wishes to perform the
        # given action on the given URI was authenticated under
        realm = session._realm
        # authid = session._authid
        authrole = session._authrole

        # the permission of a WAMP client is always determined (only) from
        # WAMP realm, authrole, URI and action already
        cache_key = (realm, authrole, uri, action)

        # if we do have a cache entry, use the authorization cached
        cached_authorization = self._authorization_cache.get(cache_key, None)

        # normally, the role should exist on the router (and hence we should not arrive
        # here), but the role might have been dynamically removed - and anyway, safety first!
        if authrole in self._roles:
            if cached_authorization:
                self.log.debug('{func} authorization cache entry found key {cache_key}:\n{authorization}',
                               func=hltype(self.authorize),
                               cache_key=hlval(cache_key),
                               authorization=pformat(cached_authorization))
                d = txaio.create_future_success(cached_authorization)
            else:
                # the authorizer procedure of the role which we will call
                authorize = self._roles[authrole].authorize
                d = txaio.as_future(authorize, session, uri, action, options)
        else:
            # remove cache entry
            if cached_authorization:
                del self._authorization_cache[cache_key]

            # outright deny, since the role isn't active anymore
            d = txaio.create_future_success(False)

        # XXX would be nicer for dynamic-authorizer authors if we
        # sanity-checked the return-value ('authorization') here
        # (i.e. is it a dict? does it have 'allow' in it? does it have
        # disallowed keys in it?)

        def got_authorization(authorization):
            # backward compatibility
            if isinstance(authorization, bool):
                authorization = {'allow': authorization, 'cache': False}
                if action in ['call', 'publish']:
                    authorization['disclose'] = False

            auto_disclose_trusted = True
            if auto_disclose_trusted and authrole == 'trusted' and action in ['call', 'publish']:
                authorization['disclose'] = True

            if not cached_authorization and authorization.get('cache', False):
                self._authorization_cache[cache_key] = authorization
                self.log.debug('{func} add authorization cache entry for key {cache_key}:\n{authorization}',
                               func=hltype(got_authorization),
                               cache_key=hlval(cache_key),
                               authorization=pformat(authorization))

            self.log.debug(
                "Authorized action '{action}' for URI '{uri}' by session {session_id} with authid '{authid}' and "
                "authrole '{authrole}' -> authorization: {authorization}",
                session_id=session._session_id,
                uri=uri,
                action=action,
                authid=session._authid,
                authrole=session._authrole,
                authorization=authorization)

            return authorization

        d.addCallback(got_authorization)
        return d

    def validate(self,
                 payload_type: str,
                 uri: str,
                 args: Optional[List[Any]],
                 kwargs: Optional[Dict[str, Any]],
                 validate: Optional[Dict[str, Any]] = None):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.validate`

        Called to validate application payloads sent in WAMP calls, call results and errors, as well
        as events from:

        * :class:`crossbar.router.dealer.Dealer`
        * :class:`crossbar.router.broker.Broker`

        When the application payload cannot be validated successfully against the respective validation type,
        this method will raise a :class:`InvalidPayload` exception.

        :param payload_type: The type of WAMP action/payload, that is one of
            ``"call", "call_progress", "call_result", "call_result_progress, "call_error"`` for RPC or one of
            ``"event", "event_result"`` for PubSub (Note: ``"call_progress"`` and ``"event_result"``
            are for future use).
        :param uri: The WAMP URI (e.g. procedure or topic URI) on which to
            validate the given application payload.
        :param args: The WAMP application payload, positional arguments to validate.
        :param kwargs: The WAMP application payload, keyword-based arguments to validate.
        :param validate: A mapping from ``payload_type`` to validation type (name of a FlatBuffers
            table in the inventory).
        :return:
        """
        assert payload_type in [
            # rpc_service.RequestType ##############################################################

            # WAMP event published either using normal or router-acknowledged publications
            'event',

            # WAMP call, the (only or the initial) caller request
            'call',

            # WAMP call, any call updates sent by the caller subsequently and while the call is
            # still active
            'call_progress',

            # rpc_service.ResponseType #############################################################

            # WAMP event confirmation sent by subscribers for subscribed-confirmed publications
            'event_result',

            # WAMP call result, the (only or the initial) callee response
            'call_result',

            # WAMP call progressive result, any call result updates sent by the callee subsequently
            # and while the call is still active
            'call_result_progress',

            # WAMP call error result, the callee error response payload
            'call_error',
        ]

        if self._inventory:
            if validate:
                if payload_type in validate:
                    # type against which we validate the application payload args/kwargs
                    validation_type = validate[payload_type]

                    self.log.info(
                        '{func} validate "{payload_type}" on URI "{uri}" for payload with '
                        'len(args)={args}, len(kwargs)={kwargs} using validation_type="{validation_type}"',
                        func=hltype(self.validate),
                        payload_type=hlval(payload_type.upper(), color='blue'),
                        uri=hlval(uri, color='magenta'),
                        args=hlval(len(args) if args is not None else '-'),
                        kwargs=hlval(len(kwargs) if kwargs is not None else '-'),
                        validation_type=hlval(validation_type, color='blue'),
                        cb_level="trace")

                    try:
                        vt: FbsObject = self._inventory.repo.validate(validation_type, args, kwargs)
                    except InvalidPayload as e:
                        self.log.warn('{func} {msg}',
                                      func=hltype(self.validate),
                                      msg=hlval('validation error: {}'.format(e), color='red'))
                        raise
                    else:
                        self.log.info('{func} {msg} (used validation type "{vt_name}" from "{vt_decl_fn}")',
                                      func=hltype(self.validate),
                                      msg=hlval('validation success!', color='green'),
                                      vt_name=hlval(vt.name),
                                      vt_decl_fn=hlval(vt.declaration_file))
                        self.log.debug('validated args={args}\nand kwargs={kwargs}\nagainst vt({vt_name})={vt}',
                                       args=pformat(args),
                                       kwargs=pformat(kwargs),
                                       vt_name=vt.name,
                                       vt=pformat(vt.marshal()))
                else:
                    self.log.warn(
                        '{func} {msg} (type inventory active, but no payload configuration for payload_type "{payload_type}" in validate for URI "{uri}"',
                        func=hltype(self.validate),
                        payload_type=hlval(payload_type, color='yellow'),
                        uri=hlval(uri),
                        msg=hlval('validation skipped!', color='yellow'))
            else:
                self.log.warn(
                    '{func} {msg} (type inventory active, but missing configuration for payload_type "{payload_type}" on URI "{uri}"',
                    func=hltype(self.validate),
                    uri=hlval(uri),
                    payload_type=hlval(payload_type, color='yellow'),
                    msg=hlval('validation skipped!', color='yellow'))


class RouterFactory(object):
    """
    Factory for creating router instances operating for application realms.
    """
    log = make_logger()
    router = Router
    """
    The router class this factory will create router instances from.
    """
    def __init__(self, node_id: str, worker_id: str, worker, options: Optional[RouterOptions] = None):
        """

        :param node_id: Node (management) ID.
        :param worker_id: (Router) worker (management) ID.
        :param worker: Router worker.
        :param options: Default router options.
        """
        self._node_id = node_id
        self._worker_id = worker_id
        self._worker = worker
        self._routers: Dict[str, Router] = {}
        self._options = options or RouterOptions(uri_check=RouterOptions.URI_CHECK_LOOSE)
        # XXX this should get passed in from somewhere
        from twisted.internet import reactor
        self._reactor = reactor

        from crossbar.worker.router import RouterController
        from crossbar.worker.proxy import ProxyController
        assert worker is None or isinstance(worker, RouterController) or isinstance(worker, ProxyController)

    @property
    def node_id(self):
        return self._node_id

    @property
    def worker(self):
        return self._worker

    def get(self, realm):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouterFactory.get`
        """
        return self._routers.get(realm, None)

    def __getitem__(self, realm):
        return self._routers[realm]

    def __contains__(self, realm):
        return realm in self._routers

    def on_last_detach(self, router):
        if router.realm in self._routers:
            del self._routers[router.realm]
            self.log.debug('{klass}.on_last_detach: router removed for realm "{realm}"',
                           klass=self.__class__.__name__,
                           realm=router.realm)
        else:
            self.log.warn(
                '{klass}.on_last_detach: realm "{realm}" not in router realms (skipped removal) - current realms: {realms}',
                klass=self.__class__.__name__,
                realm=router.realm,
                realms=sorted(self._routers.keys()))

    def start_realm(self, realm: RouterRealm) -> Router:
        """
        Starts a realm on this router.

        :param realm: The realm to start.
        :returns: The router instance for the started realm.
        :rtype: instance of :class:`crossbar.router.session.CrossbarRouter`
        """
        # extract name (URI in general) of realm from realm configuration
        assert 'name' in realm.config
        uri = realm.config['name']
        assert type(uri) == str
        self.log.info('{func}: realm={realm} with URI "{uri}"',
                      func=hltype(self.start_realm),
                      realm=realm,
                      uri=hlval(uri))

        if realm in self._routers:
            raise RuntimeError('router for realm "{}" already running'.format(uri))

        # setup optional store for realm persistence features
        store: Optional[IRealmStore] = None
        if 'store' in realm.config and realm.config['store']:
            # the worker's node personality
            psn = self._worker.personality
            store = psn.create_realm_store(psn, self, realm.config['store'])
            self.log.info('{func}: initialized realm store {store_class} for realm "{realm}"',
                          func=hltype(self.start_realm),
                          store_class=hlval(store.__class__, color='green'),
                          realm=hlval(uri))

        # setup optional inventory for realm API catalogs
        inventory: Optional[IInventory] = None
        if 'inventory' in realm.config and realm.config['inventory']:
            # the worker's node personality
            psn = self._worker.personality
            inventory = psn.create_realm_inventory(psn, self, realm.config['inventory'])
            assert inventory
            self.log.info(
                '{func}: initialized realm inventory <{inventory_type}> for realm "{realm}", '
                'loaded {total_count} types, from config:\n{config}',
                func=hltype(self.start_realm),
                inventory_type=hlval(inventory.type, color='green'),
                total_count=hlval(inventory.repo.total_count),
                realm=hlval(uri),
                config=pformat(realm.config['inventory']))

        # setup realm options
        options = RouterOptions(
            uri_check=self._options.uri_check,
            event_dispatching_chunk_size=self._options.event_dispatching_chunk_size,
        )
        for arg in ['uri_check', 'event_dispatching_chunk_size']:
            if arg in realm.config.get('options', {}):
                setattr(options, arg, realm.config['options'][arg])

        # now create a router for the realm
        router = self.router(self, realm, options, store=store, inventory=inventory)
        self._routers[uri] = router

        return router

    def stop_realm(self, realm: str) -> List[int]:
        """
        Stop a realm, detaching all active sessions.

        :param realm: The realm to stop.
        :return: A list of session IDs of sessions that have been detached as a consequence of stopping this realm.
        """
        self.log.info('{func}: realm="{realm}"', func=hltype(self.stop_realm), realm=realm)

        if realm not in self._routers:
            raise RuntimeError('no router started for realm "{}"'.format(realm))

        router = self._routers[realm]
        detached_sessions = router.detach()

        del self._routers[realm]

        return detached_sessions

    def add_role(self, realm: str, config: Dict[str, Any]) -> RouterRole:
        """
        Add a role to a realm.

        :param realm: The name of the realm to add the role to.
        :param config: The role configuration.
        :return: The new role object.
        """
        self.log.info('{func}: realm="{realm}", config=\n{config}',
                      func=hltype(self.add_role),
                      realm=hlval(realm),
                      config=pformat(config))

        if realm not in self._routers:
            raise RuntimeError('no router started for realm "{}"'.format(realm))

        router = self._routers[realm]
        uri = config['name']

        role: RouterRole
        if 'permissions' in config:
            role = RouterRoleStaticAuth(router, uri, config['permissions'])
        elif 'authorizer' in config:
            role = RouterRoleDynamicAuth(router, uri, config['authorizer'])
        else:
            allow_by_default = config.get('allow-by-default', False)
            role = RouterRole(router, uri, allow_by_default=allow_by_default)

        router.add_role(role)
        return role

    def drop_role(self, realm: str, role: str) -> RouterRole:
        """
        Drop a role from a realm.

        :param realm: The name of the realm to drop.
        :param role: The URI of the role (on the realm) to drop.
        :return: The dropped role object.
        """
        self.log.info('{func}: realm="{realm}", role="{role}"',
                      func=hltype(self.drop_role),
                      realm=hlval(realm),
                      role=hlval(role))

        if realm not in self._routers:
            raise RuntimeError('no router started for realm "{}"'.format(realm))

        router = self._routers[realm]

        if role not in router._roles:
            raise RuntimeError('no role "{}" started on router for realm "{}"'.format(role, realm))

        role_obj = router._roles[role]
        router.drop_role(role_obj)
        return role_obj
