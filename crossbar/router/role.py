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

from txaio import make_logger

__all__ = (
    'RouterRole',
    'RouterTrustedRole',
    'RouterRoleStaticAuth',
    'RouterRoleDynamicAuth',
    'RouterRoleLMDBAuth'
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
                 uri, match,
                 call=False, register=False, publish=False, subscribe=False,
                 disclose_caller=False, disclose_publisher=False,
                 cache=True):
        """

        :param uri: The URI to match.
        """
        assert(uri is None or type(uri) == six.text_type)
        assert(match is None or match in [u'exact', u'prefix', u'wildcard'])
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

    def to_dict(self):
        return {
            u'uri': self.uri,
            u'match': self.match,
            u'allow': {
                u'call': self.call,
                u'register': self.register,
                u'publish': self.publish,
                u'subscribe': self.subscribe
            },
            u'disclose': {
                u'caller': self.disclose_caller,
                u'publisher': self.disclose_publisher
            },
            u'cache': self.cache
        }

    @staticmethod
    def from_dict(obj):
        assert(type(obj) == dict)

        uri = obj.get(u'uri', None)

        # support "starred" URIs:
        if u'match' in obj:
            # when a match policy is explicitly configured, the starred URI
            # conversion logic is skipped! we want to preserve the higher
            # expressiveness of regular WAMP URIs plus explicit match policy
            match = obj[u'match']
        else:
            # when no explicit match policy is selected, we assume the use
            # of starred URIs and convert to regular URI + detected match policy
            uri, match = convert_starred_uri(uri)

        allow = obj.get(u'allow', {})
        assert(type(allow) == dict)
        allow_call = allow.get(u'call', False)
        allow_register = allow.get(u'register', False)
        allow_publish = allow.get(u'publish', False)
        allow_subscribe = allow.get(u'subscribe', False)

        disclose = obj.get(u'disclose', {})
        assert(type(disclose) == dict)
        disclose_caller = disclose.get(u'caller', False)
        disclose_publisher = disclose.get(u'publisher', False)

        cache = obj.get(u'cache', False)

        return RouterPermissions(uri, match,
                                 call=allow_call,
                                 register=allow_register,
                                 publish=allow_publish,
                                 subscribe=allow_subscribe,
                                 disclose_caller=disclose_caller,
                                 disclose_publisher=disclose_publisher,
                                 cache=cache)


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

        :param router: The router this role is defined on.
        :type router: obj
        :param uri: The URI of the role.
        :type uri: unicode
        :param permissions: A permissions configuration, e.g. a list
           of permission dicts like `{'uri': 'com.example.*', 'call': True}`
        :type permissions: list of dict
        :param default_permissions: The default permissions to apply when no other
            configured permission matches. The default permissions when not explicitly
            set is to deny all actions on all URIs!
        :type default_permissions: dict
        """
        RouterRole.__init__(self, router, uri)
        assert(permissions is None or type(permissions) == list)
        if permissions:
            for p in permissions:
                assert(type(p) == dict)
        assert(default_permissions is None or type(default_permissions) == dict)

        # default permissions (used when nothing else is matching)
        # note: default permissions have their matching URI and match policy set to None!
        if default_permissions:
            self._default = RouterPermissions.from_dict(default_permissions)
        else:
            self._default = RouterPermissions(None, None,
                                              call=False,
                                              register=False,
                                              publish=False,
                                              subscribe=False,
                                              disclose_caller=False,
                                              disclose_publisher=False,
                                              cache=True)

        # Trie of explicitly configured permissions
        self._permissions = StringTrie()

        for obj in permissions or []:
            perms = RouterPermissions.from_dict(obj)
            self._permissions[perms.uri] = perms

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
            # longest prefix match of the URI to be authorized against our Trie
            # of configured URIs for permissions
            permissions = self._permissions.longest_prefix_value(uri)

            # if there is a _prefix_ matching URI, check that this is actually the
            # match policy on the permission (otherwise, apply default permissions)!
            if permissions.match != u'prefix' and uri != permissions.uri:
                permissions = self._default

        except KeyError:
            # workaround because of https://bitbucket.org/gsakkis/pytrie/issues/4/string-keys-of-zero-length-are-not
            if u'' in self._permissions:
                permissions = self._permissions[u'']
            else:
                permissions = self._default

        if action == u'publish':
            return {
                u'allow': permissions.publish,
                u'disclose': permissions.disclose_publisher,
                u'cache': permissions.cache
            }

        elif action == u'subscribe':
            return {
                u'allow': permissions.subscribe,
                u'cache': permissions.cache
            }

        elif action == u'call':
            return {
                u'allow': permissions.call,
                u'disclose': permissions.disclose_caller,
                u'cache': permissions.cache
            }

        elif action == u'register':
            return {
                u'allow': permissions.register,
                u'cache': permissions.cache
            }

        else:
            # should not arrive here
            raise Exception('logic error')


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


class RouterRoleLMDBAuth(RouterRole):
    """
    A role on a router realm that is authorized from a node LMDB embedded database.
    """

    def __init__(self, router, uri, store):
        """

        :param uri: The URI of the role.
        :type uri: unicode
        """
        RouterRole.__init__(self, router, uri)
        self._store = store

    def authorize(self, session, uri, action):
        """
        Authorize a session connected under this role to perform the given
        action on the given URI.

        :param session: The WAMP session that requests the action.
        :type session: Instance of :class:`autobahn.wamp.protocol.ApplicationSession`
        :param uri: The URI on which to perform the action.
        :type uri: unicode
        :param action: The action to be performed.
        :type action: unicode

        :returns: The authorization
        :rtype: dict
        """
        # FIXME: for the realm the router (self._router) is working for,
        # and for the role URI on that realm, lookup the authorization
        # in the respective node LMDB embedded database. returning a
        # Deferred that fires when the data was loaded from the database.
        # we expect being able to do millions of lookups per second, so this
        # should not be a bottleneck.
        raise Exception('not implemented yet')
