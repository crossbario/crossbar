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

from collections import namedtuple

from pytrie import StringTrie

from crossbar._logging import make_logger

__all__ = (
    'RouterRole',
    'RouterTrustedRole',
    'RouterRoleStaticAuth',
    'RouterRoleDynamicAuth',
)


RouterPermissions = namedtuple(
    'RouterPermissions',
    ['uri', 'match_by_prefix', 'call', 'register', 'publish', 'subscribe'])


class RouterRole(object):
    """
    Base class for router roles.
    """
    log = make_logger()

    def __init__(self, router, uri):
        """
        Ctor.

        :param uri: The URI of the role.
        :type uri: str
        """
        self.router = router
        self.uri = uri

    def authorize(self, session, uri, action):
        """
        Authorize a session connected under this role to perform the given
        action on the given URI.

        :param session: The WAMP session that requests the action.
        :type session: Instance of :class:`autobahn.wamp.protocol.ApplicationSession`
        :param uri: The URI on which to perform the action.
        :type uri: str
        :param action: The action to be performed.
        :type action: str

        :return: bool -- Flag indicating whether session is authorized or not.
        """
        self.log.debug("CrossbarRouterRole.authorize {uri} {action}",
                       uri=uri, action=action)
        return False


class RouterTrustedRole(RouterRole):
    """
    A router role that is trusted to do anything. This is used e.g. for the
    service session run internally run by a router.
    """

    def authorize(self, session, uri, action):
        self.log.debug(
            "CrossbarRouterTrustedRole.authorize {myuri} {uri} {action}",
            myuri=self.uri, uri=uri, action=action)
        return True


class RouterRoleStaticAuth(RouterRole):
    """
    A role on a router realm that is authorized using a static configuration.
    """

    def __init__(self, router, uri, permissions=None, default_permissions=None):
        """
        Ctor.

        :param uri: The URI of the role.
        :type uri: str
        :param permissions: A permissions configuration, e.g. a list
           of permission dicts like `{'uri': 'com.example.*', 'call': True}`
        :type permissions: list
        """
        RouterRole.__init__(self, router, uri)
        self.permissions = permissions or []

        self._urimap = StringTrie()
        self._default = default_permissions or RouterPermissions('', True, False, False, False, False)

        for p in self.permissions:
            uri = p['uri']

            if len(uri) > 0 and uri[-1] == '*':
                match_by_prefix = True
                uri = uri[:-1]
            else:
                match_by_prefix = False

            perms = RouterPermissions(uri, match_by_prefix,
                                      call=p.get('call', False),
                                      register=p.get('register', False),
                                      publish=p.get('publish', False),
                                      subscribe=p.get('subscribe', False))

            if len(uri) > 0:
                self._urimap[uri] = perms
            else:
                self._default = perms

    def authorize(self, session, uri, action):
        """
        Authorize a session connected under this role to perform the given
        action on the given URI.

        :param session: The WAMP session that requests the action.
        :type session: Instance of :class:`autobahn.wamp.protocol.ApplicationSession`
        :param uri: The URI on which to perform the action.
        :type uri: str
        :param action: The action to be performed.
        :type action: str

        :return: bool -- Flag indicating whether session is authorized or not.
        """
        self.log.debug(
            "CrossbarRouterRoleStaticAuth.authorize {myuri} {uri} {action}",
            myuri=self.uri, uri=uri, action=action)
        # if action == 'publish':
        #   f = 1/0
        try:
            permissions = self._urimap.longest_prefix_value(uri)
            if not permissions.match_by_prefix and uri != permissions.uri:
                return False
            return getattr(permissions, action)
        except KeyError:
            return getattr(self._default, action)


class RouterRoleDynamicAuth(RouterRole):
    """
    A role on a router realm that is authorized by calling (via WAMP RPC)
    an authorizer function provided by the app.
    """

    def __init__(self, router, uri, authorizer):
        """
        Ctor.

        :param uri: The URI of the role.
        :type uri: str
        """
        RouterRole.__init__(self, router, uri)
        self._authorizer = authorizer
        self._session = router._realm.session

    def authorize(self, session, uri, action):
        """
        Authorize a session connected under this role to perform the given
        action on the given URI.

        :param session: The WAMP session that requests the action.
        :type session: Instance of :class:`autobahn.wamp.protocol.ApplicationSession`
        :param uri: The URI on which to perform the action.
        :type uri: str
        :param action: The action to be performed.
        :type action: str

        :return: bool -- Flag indicating whether session is authorized or not.
        """
        self.log.debug(
            "CrossbarRouterRoleDynamicAuth.authorize {myuri} {uri} {action}",
            myuri=self.uri, uri=uri, action=action)
        return self._session.call(self._authorizer, session._session_details,
                                  uri, action)
