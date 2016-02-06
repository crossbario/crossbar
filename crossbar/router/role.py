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

import six

from pytrie import StringTrie

from autobahn.wamp.uri import convert_starred_uri

from crossbar._logging import make_logger

__all__ = (
    'RouterRole',
    'RouterTrustedRole',
    'RouterRoleStaticAuth',
    'RouterRoleDynamicAuth',
)


class RouterPermissions(object):

    __slots__ = (
        'uri',
        'match',
        'call',
        'register',
        'publish',
        'subscribe',
        'disclose_caller',
        'disclose_publisher',
        'cache'
    )

    def __init__(self,
                 uri, match=u'exact',
                 call=False, register=False, publish=False, subscribe=False,
                 disclose_caller=False, disclose_publisher=False,
                 cache=True):
        """

        :param uri: The URI to match.
        """
        assert(type(uri) == six.text_type)
        assert(match in [u'exact', u'prefix', u'wildcard'])
        assert(type(call) == bool)
        assert(type(register) == bool)
        assert(type(publish) == bool)
        assert(type(subscribe) == bool)
        assert(type(disclose_caller) == bool)
        assert(type(disclose_publisher) == bool)
        assert(type(cache) == bool)

        self.uri = uri
        self.match = match
        self.call = call
        self.register = register
        self.publish = publish
        self.subscribe = subscribe
        self.disclose_caller = disclose_caller
        self.disclose_publisher = disclose_publisher
        self.cache = cache

    def __repr__(self):
        return u'RouterPermissions(uri="{}", match="{}", call={}, register={}, publish={}, subscribe={}, disclose_caller={}, disclose_publisher={}, cache={})'.format(self.uri, self.match, self.call, self.register, self.publish, self.subscribe, self.disclose_caller, self.disclose_publisher, self.cache)

    def marshal(self):
        return {
            u'uri': self.uri,
            u'match': self.match,
            u'call': self.call,
            u'register': self.register,
            u'publish': self.publish,
            u'subscribe': self.subscribe,
            u'disclose_caller': self.disclose_caller,
            u'disclose_publisher': self.disclose_publisher,
            u'cache': self.cache,
        }


class RouterRole(object):
    """
    Base class for router roles.
    """
    log = make_logger()

    def __init__(self, router, uri, allow_by_default=False):
        """
        Ctor.

        :param uri: The URI of the role.
        :type uri: str
        """
        self.router = router
        self.uri = uri
        self.allow_by_default = allow_by_default

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
        return self.allow_by_default


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
        :type uri: unicode
        :param permissions: A permissions configuration, e.g. a list
           of permission dicts like `{'uri': 'com.example.*', 'call': True}`
        :type permissions: list
        """
        RouterRole.__init__(self, router, uri)
        self.permissions = permissions or []

        self._urimap = StringTrie()
        self._default = default_permissions or RouterPermissions(u'', u'prefix')

        for p in self.permissions:

            uri = p[u'uri']

            # support "starred" URIs:
            if u'match' in p:
                # when a match policy is explicitly configured, the starred URI
                # conversion logic is skipped! we want to preserve the higher
                # expressiveness of regular WAMP URIs plus explicit match policy
                match = p[u'match']
            else:
                # when no explicit match policy is selected, we assume the use
                # of starred URIs and convert to regular URI + detected match policy
                uri, match = convert_starred_uri(uri)

            perms = RouterPermissions(uri,
                                      match,
                                      call=p.get(u'call', False),
                                      register=p.get(u'register', False),
                                      publish=p.get(u'publish', False),
                                      subscribe=p.get(u'subscribe', False),
                                      disclose_caller=p.get(u'disclose_caller', False),
                                      disclose_publisher=p.get(u'disclose_publisher', False),
                                      cache=p.get(u'cache', True))

            self._urimap[uri] = perms

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
        try:
            permissions = self._urimap.longest_prefix_value(uri)
            if permissions.match != u'prefix' and uri != permissions.uri:
                return False, permissions.marshal()
            return getattr(permissions, action), permissions.marshal()
        except KeyError:
            # workaround because of https://bitbucket.org/gsakkis/pytrie/issues/4/string-keys-of-zero-length-are-not
            if u'' in self._urimap:
                permissions = self._urimap[u'']
            else:
                permissions = self._default
            return getattr(permissions, action), permissions.marshal()


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
