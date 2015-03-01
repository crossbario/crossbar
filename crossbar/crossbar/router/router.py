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

from twisted.python import log

from autobahn.wamp import message
from autobahn.twisted.wamp import FutureMixin
from autobahn.wamp.exception import ProtocolError

from crossbar.router.interfaces import IRouter
from crossbar.router.broker import Broker
from crossbar.router.dealer import Dealer
from crossbar.router.types import RouterOptions
from crossbar.router.role import CrossbarRouterRole, \
    CrossbarRouterTrustedRole, CrossbarRouterRoleStaticAuth, \
    CrossbarRouterRoleDynamicAuth


class Router(FutureMixin):

    """
    Basic WAMP router.
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
        self.debug = False
        self.factory = factory
        self.realm = realm
        self._options = options or RouterOptions()
        self._realm = None

        # map: session_id -> session
        self._session_id_to_session = {}

        self._broker = self.broker(self, self._options)
        self._dealer = self.dealer(self, self._options)
        self._attached = 0

    def attach(self, session):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.attach`
        """
        if session._session_id not in self._session_id_to_session:
            if hasattr(session, '_session_details'):
                self._session_id_to_session[session._session_id] = session
            else:
                if self.debug:
                    print("attaching non-client session {}".format(session))
        else:
            raise Exception("session with ID {} already attached".format(session._session_id))

        self._broker.attach(session)
        self._dealer.attach(session)

        self._attached += 1

        return [self._broker._role_features, self._dealer._role_features]

    def detach(self, session):
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
            self.factory.onLastDetach(self)

    def process(self, session, msg):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.process`
        """
        if self.debug:
            print("Router.process: {0}".format(msg))

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

    def authorize(self, session, uri, action):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.authorize`
        """
        if self.debug:
            print("Router.authorize: {0} {1} {2}".format(session, uri, action))
        return True

    def validate(self, payload_type, uri, args, kwargs):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouter.validate`
        """
        if self.debug:
            print("Router.validate: {0} {1} {2} {3}".format(payload_type, uri, args, kwargs))


class RouterFactory:

    """
    Basic WAMP Router factory.
    """

    router = Router
    """
   The router class this factory will create router instances from.
   """

    def __init__(self, options=None, debug=False):
        """

        :param options: Default router options.
        :type options: Instance of :class:`autobahn.wamp.types.RouterOptions`.
        """
        self._routers = {}
        self.debug = debug
        self._options = options or RouterOptions()

    def get(self, realm):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouterFactory.get`
        """
        if realm not in self._routers:
            self._routers[realm] = self.router(self, realm, self._options)
            if self.debug:
                print("Router created for realm '{0}'".format(realm))
        return self._routers[realm]

    def onLastDetach(self, router):
        assert(router.realm in self._routers)
        del self._routers[router.realm]
        if self.debug:
            print("Router destroyed for realm '{0}'".format(router.realm))


class CrossbarRouter(Router):

    """
    Crossbar.io core router class.
    """

    RESERVED_ROLES = ["trusted"]
    """
   Roles with these URIs are built-in and cannot be added/dropped.
   """

    def __init__(self, factory, realm, options=None):
        """
        Ctor.
        """
        uri = realm.config['name']
        Router.__init__(self, factory, uri, options)
        self._roles = {
            "trusted": CrossbarRouterTrustedRole(self, "trusted", debug=self.debug)
        }
        self._realm = realm
        # self.debug = True

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
        if self.debug:
            log.msg("CrossbarRouter.add_role", role)

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
        if self.debug:
            log.msg("CrossbarRouter.drop_role", role)

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
        action = IRouter.ACTION_TO_STRING[action]

        authorized = False
        if role in self._roles:
            authorized = self._roles[role].authorize(session, uri, action)

        if self.debug:
            log.msg("CrossbarRouter.authorize: {} {} {} {} {} {} {} -> {}".format(session._session_id, uri, action, session._authid, session._authrole, session._authmethod, session._authprovider, authorized))

        return authorized


class CrossbarRouterFactory(RouterFactory):

    """
    Crossbar.io core router factory.
    """

    def __init__(self, options=None, debug=False):
        """
        Ctor.
        """
        options = RouterOptions(uri_check=RouterOptions.URI_CHECK_LOOSE)
        RouterFactory.__init__(self, options, debug)

    def __getitem__(self, realm):
        return self._routers[realm]

    def __contains__(self, realm):
        return realm in self._routers

    def get(self, realm):
        """
        Implements :func:`autobahn.wamp.interfaces.IRouterFactory.get`
        """
        return self._routers[realm]

    def start_realm(self, realm):
        """
        Starts a realm on this router.

        :param realm: The realm to start.
        :type realm: instance of :class:`crossbar.worker.router.RouterRealm`.

        :returns: The router instance for the started realm.
        :rtype: instance of :class:`crossbar.router.session.CrossbarRouter`
        """
        if self.debug:
            log.msg("CrossbarRouterFactory.start_realm(realm = {})".format(realm))

        uri = realm.config['name']
        assert(uri not in self._routers)

        router = CrossbarRouter(self, realm, self._options)

        self._routers[uri] = router
        if self.debug:
            log.msg("Router created for realm '{}'".format(uri))

        return router

    def stop_realm(self, realm):
        if self.debug:
            log.msg("CrossbarRouterFactory.stop_realm(realm = {})".format(realm))

    def add_role(self, realm, config):
        if self.debug:
            log.msg("CrossbarRouterFactory.add_role(realm = {}, config = {})".format(realm, config))

        assert(realm in self._routers)

        router = self._routers[realm]
        uri = config['name']

        if 'permissions' in config:
            role = CrossbarRouterRoleStaticAuth(router, uri, config['permissions'], debug=self.debug)
        elif 'authorizer' in config:
            role = CrossbarRouterRoleDynamicAuth(router, uri, config['authorizer'], debug=self.debug)
        else:
            role = CrossbarRouterRole(router, uri, debug=self.debug)

        router.add_role(role)

    def drop_role(self, realm, role):
        if self.debug:
            log.msg("CrossbarRouterFactory.drop_role(realm = {}, role = {})".format(realm, role))
