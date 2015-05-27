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

from autobahn.wamp import message
from autobahn.wamp.exception import ProtocolError

from crossbar.router import RouterOptions, RouterAction
from crossbar.router.broker import Broker
from crossbar.router.dealer import Dealer
from crossbar.router.role import RouterRole, \
    RouterTrustedRole, RouterRoleStaticAuth, \
    RouterRoleDynamicAuth

from crossbar._logging import make_logger

__all__ = (
    'RouterFactory',
)


def _is_client_session(session):
    return hasattr(session, '_session_details')


class Router(object):
    """
    Crossbar.io core router class.
    """
    log = make_logger()

    RESERVED_ROLES = ["trusted"]
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

    def __init__(self, factory, realm, options=None):
        """

        :param factory: The router factory this router was created by.
        :type factory: Object that implements :class:`autobahn.wamp.interfaces.IRouterFactory`..
        :param realm: The realm this router is working for.
        :type realm: str
        :param options: Router options.
        :type options: Instance of :class:`autobahn.wamp.types.RouterOptions`.
        """
        self._factory = factory
        self._options = options or RouterOptions()
        self._realm = realm
        self.realm = realm.config['name']

        # map: session_id -> session
        self._session_id_to_session = {}

        self._broker = self.broker(self, self._options)
        self._dealer = self.dealer(self, self._options)
        self._attached = 0

        self._roles = {
            "trusted": RouterTrustedRole(self, "trusted")
        }

    def attach(self, session):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.attach`
        """
        if session._session_id not in self._session_id_to_session:
            if _is_client_session(session):
                self._session_id_to_session[session._session_id] = session
            else:
                self.log.debug("attaching non-client session {session}",
                               session=session)
        else:
            raise Exception("session with ID {} already attached".format(session._session_id))

        self._broker.attach(session)
        self._dealer.attach(session)

        self._attached += 1

        return {u'broker': self._broker._role_features, u'dealer': self._dealer._role_features}

    def detach(self, session):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.detach`
        """
        self._broker.detach(session)
        self._dealer.detach(session)

        if session._session_id in self._session_id_to_session:
            del self._session_id_to_session[session._session_id]
        else:
            if _is_client_session(session):
                raise Exception("session with ID {} not attached".format(session._session_id))

        self._attached -= 1
        if not self._attached:
            self._factory.onLastDetach(self)

    def process(self, session, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.process`
        """
        self.log.debug("Router.process: {msg}", msg=msg, cb_level="trace")

        # Broker
        #
        if isinstance(msg, message.Publish):
            self._broker.processPublish(session, msg)

        elif isinstance(msg, message.Subscribe):
            self._broker.processSubscribe(session, msg)

        elif isinstance(msg, message.Unsubscribe):
            self._broker.processUnsubscribe(session, msg)

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

    def has_role(self, uri):
        """
        Check if a role with given URI exists on this router.

        :returns: bool - `True` if a role under the given URI exists on this router.
        """
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

    def authorize(self, session, uri, action):
        """
        Authorizes a session for an action on an URI.

        Implements :func:`autobahn.wamp.interfaces.IRouter.authorize`
        """
        role = session._authrole
        action = RouterAction.ACTION_TO_STRING[action]

        authorized = False
        if role in self._roles:
            authorized = self._roles[role].authorize(session, uri, action)

        self.log.debug("CrossbarRouter.authorize: {session_id} {uri} {action} {authid} {authrole} {authmethod} {authprovider} -> {authorized}",
                       session_id=session._session_id, uri=uri, action=action,
                       authid=session._authid, authrole=session._authrole,
                       authmethod=session._authmethod,
                       authprovider=session._authprovider,
                       authorized=authorized, cb_level="trace")

        return authorized

    def validate(self, payload_type, uri, args, kwargs):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.validate`
        """
        self.log.debug("Router.validate: {payload_type} {uri} {args} {kwargs}",
                       payload_type=payload_type, uri=uri, args=args,
                       kwargs=kwargs, cb_level="trace")


class RouterFactory(object):
    """
    Crossbar.io core router factory.
    """
    log = make_logger()
    router = Router
    """
    The router class this factory will create router instances from.
    """

    def __init__(self, options=None):
        """

        :param options: Default router options.
        :type options: Instance of :class:`autobahn.wamp.types.RouterOptions`.
        """
        self._routers = {}
        self._options = options or RouterOptions(uri_check=RouterOptions.URI_CHECK_LOOSE)
        self._auto_create_realms = False

    def get(self, realm):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouterFactory.get`
        """
        if self._auto_create_realms:
            if realm not in self._routers:
                self._routers[realm] = self.router(self, realm, self._options)
                self.log.debug("Router created for realm '{realm}'",
                               realm=realm)
            return self._routers[realm]
        else:
            return self._routers[realm]

    def __getitem__(self, realm):
        return self._routers[realm]

    def __contains__(self, realm):
        return realm in self._routers

    def onLastDetach(self, router):
        assert(router.realm in self._routers)
        del self._routers[router.realm]
        self.log.debug("Router destroyed for realm '{realm}'",
                       realm=router.realm)

    def start_realm(self, realm):
        """
        Starts a realm on this router.

        :param realm: The realm to start.
        :type realm: instance of :class:`crossbar.worker.router.RouterRealm`.

        :returns: The router instance for the started realm.
        :rtype: instance of :class:`crossbar.router.session.CrossbarRouter`
        """
        self.log.debug("CrossbarRouterFactory.start_realm(realm = {realm})",
                       realm=realm)

        uri = realm.config['name']
        assert(uri not in self._routers)

        router = Router(self, realm, self._options)

        self._routers[uri] = router
        self.log.debug("Router created for realm '{uri}'", uri=uri)

        return router

    def stop_realm(self, realm):
        self.log.debug("CrossbarRouterFactory.stop_realm(realm = {realm})",
                       realm=realm)

    def add_role(self, realm, config):
        self.log.debug("CrossbarRouterFactory.add_role(realm = {realm}, config = {config})",
                       realm=realm, config=config)

        assert(realm in self._routers)

        router = self._routers[realm]
        uri = config['name']

        if 'permissions' in config:
            role = RouterRoleStaticAuth(router, uri, config['permissions'])
        elif 'authorizer' in config:
            role = RouterRoleDynamicAuth(router, uri, config['authorizer'])
        else:
            role = RouterRole(router, uri)

        router.add_role(role)

    def drop_role(self, realm, role):
        self.log.debug("CrossbarRouterFactory.drop_role(realm = {realm}, role = {role})",
                       realm=realm, role=role)
