#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from pytrie import StringTrie

from autobahn.wamp.uri import convert_starred_uri, Pattern
from autobahn.wamp.exception import ApplicationError
from twisted.python.failure import Failure

from txaio import make_logger

__all__ = ('RouterRole', 'RouterTrustedRole', 'RouterRoleStaticAuth', 'RouterRoleDynamicAuth', 'RouterRoleLMDBAuth')


class RouterPermissions(object):

    __slots__ = ('uri', 'match', 'call', 'register', 'publish', 'subscribe', 'disclose_caller', 'disclose_publisher',
                 'cache')

    def __init__(self,
                 uri,
                 match,
                 call=False,
                 register=False,
                 publish=False,
                 subscribe=False,
                 disclose_caller=False,
                 disclose_publisher=False,
                 cache=True):
        """

        :param uri: The URI to match.
        """
        assert (uri is None or isinstance(uri, str))
        assert (match is None or match in ['exact', 'prefix', 'wildcard'])
        assert (isinstance(call, bool))
        assert (isinstance(register, bool))
        assert (isinstance(publish, bool))
        assert (isinstance(subscribe, bool))
        assert (isinstance(disclose_caller, bool))
        assert (isinstance(disclose_publisher, bool))
        assert (isinstance(cache, bool))

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
        return 'RouterPermissions(uri="{}", match="{}", call={}, register={}, publish={}, subscribe={}, disclose_caller={}, disclose_publisher={}, cache={})'.format(
            self.uri, self.match, self.call, self.register, self.publish, self.subscribe, self.disclose_caller,
            self.disclose_publisher, self.cache)

    def to_dict(self):
        return {
            'uri': self.uri,
            'match': self.match,
            'allow': {
                'call': self.call,
                'register': self.register,
                'publish': self.publish,
                'subscribe': self.subscribe
            },
            'disclose': {
                'caller': self.disclose_caller,
                'publisher': self.disclose_publisher
            },
            'cache': self.cache
        }

    @staticmethod
    def from_dict(obj):
        assert (isinstance(obj, dict))

        uri = obj.get('uri', None)

        # support "starred" URIs:
        if 'match' in obj:
            # when a match policy is explicitly configured, the starred URI
            # conversion logic is skipped! we want to preserve the higher
            # expressiveness of regular WAMP URIs plus explicit match policy
            match = obj['match']
        else:
            # when no explicit match policy is selected, we assume the use
            # of starred URIs and convert to regular URI + detected match policy
            uri, match = convert_starred_uri(uri)

        allow = obj.get('allow', {})
        assert (isinstance(allow, dict))
        allow_call = allow.get('call', False)
        allow_register = allow.get('register', False)
        allow_publish = allow.get('publish', False)
        allow_subscribe = allow.get('subscribe', False)

        disclose = obj.get('disclose', {})
        assert (isinstance(disclose, dict))
        disclose_caller = disclose.get('caller', False)
        disclose_publisher = disclose.get('publisher', False)

        cache = obj.get('cache', False)

        return RouterPermissions(uri,
                                 match,
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

    def authorize(self, session, uri, action, options):
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
        self.log.debug("CrossbarRouterRole.authorize {uri} {action}", uri=uri, action=action)
        return self.allow_by_default


class RouterTrustedRole(RouterRole):
    """
    A router role that is trusted to do anything. This is used e.g. for the
    service session run internally run by a router.
    """
    def authorize(self, session, uri, action, options):
        self.log.debug("CrossbarRouterTrustedRole.authorize {myuri} {uri} {action} {options}",
                       myuri=self.uri,
                       uri=uri,
                       action=action,
                       options=options)
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
        assert (permissions is None or isinstance(permissions, list))
        if permissions:
            for p in permissions:
                assert (isinstance(p, dict))
        assert (default_permissions is None or isinstance(default_permissions, dict))

        # default permissions (used when nothing else is matching)
        # note: default permissions have their matching URI and match policy set to None!
        if default_permissions:
            self._default = RouterPermissions.from_dict(default_permissions)
        else:
            self._default = RouterPermissions(None,
                                              None,
                                              call=False,
                                              register=False,
                                              publish=False,
                                              subscribe=False,
                                              disclose_caller=False,
                                              disclose_publisher=False,
                                              cache=True)

        # Trie of explicitly configured permissions
        self._permissions = StringTrie()
        self._wild_permissions = StringTrie()

        # for "wildcard" URIs, there will be a ".." in them somewhere,
        # and so we want to match on the biggest prefix
        # (i.e. everything to the left of the first "..")
        for obj in permissions or []:
            perms = RouterPermissions.from_dict(obj)
            if '..' in perms.uri:
                trunc = perms.uri[:perms.uri.index('..')]
                self._wild_permissions[trunc] = perms
            else:
                self._permissions[perms.uri] = perms

    def authorize(self, session, uri, action, options):
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
        self.log.debug("CrossbarRouterRoleStaticAuth.authorize {myuri} {uri} {action}",
                       myuri=self.uri,
                       uri=uri,
                       action=action)

        try:
            # longest prefix match of the URI to be authorized against our Trie
            # of configured URIs for permissions
            permissions = self._permissions.longest_prefix_value(uri)

            # if there is a _prefix_ matching URI, check that this is actually the
            # match policy on the permission (otherwise, apply default permissions)!
            if permissions.match != 'prefix' and uri != permissions.uri:
                permissions = self._default

        except KeyError:
            # workaround because of https://bitbucket.org/gsakkis/pytrie/issues/4/string-keys-of-zero-length-are-not
            permissions = self._permissions.get('', self._default)

        # if we found a non-"exact" match, there might be a better one in the wildcards
        if permissions.match != 'exact':
            try:
                wildperm = self._wild_permissions.longest_prefix_value(uri)
                Pattern(wildperm.uri, Pattern.URI_TARGET_ENDPOINT).match(uri)
            except (KeyError, Exception):
                # match() raises Exception on no match
                wildperm = None

            if wildperm is not None:
                permissions = wildperm

        # we now have some permissions, either from matching something
        # or via self._default

        if action == 'publish':
            return {
                'allow': permissions.publish,
                'disclose': permissions.disclose_publisher,
                'cache': permissions.cache
            }

        elif action == 'subscribe':
            return {'allow': permissions.subscribe, 'cache': permissions.cache}

        elif action == 'call':
            return {'allow': permissions.call, 'disclose': permissions.disclose_caller, 'cache': permissions.cache}

        elif action == 'register':
            return {'allow': permissions.register, 'cache': permissions.cache}

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

        :param router: The router to which to add the role
        :type router: instance of ``crossbar.router.router.Router``
        :param id: The URI of the role.
        :type id: unicode
        :param authorizer: The dynamic authorizer configuration.
        :type authorizer: dict
        """
        RouterRole.__init__(self, router, uri)

        # the URI (identifying name) of the authorizer
        self._uri = uri

        # the dynamic authorizer configuration
        # {
        #     "name": "app",
        #     "authorizer": "com.example.auth"
        # }
        self._authorizer = authorizer

        # the session from which to call the dynamic authorizer: this is
        # the default service session on the realm
        self._session = router._realm.session

    def authorize(self, session, uri, action, options):
        """
        Authorize a session connected under this role to perform the given
        action on the given URI.

        :param session: The WAMP session that requests the action.
        :type session: Instance of :class:`autobahn.wamp.protocol.ApplicationSession`
        :param uri: The URI on which to perform the action.
        :type uri: str
        :param action: The action to be performed.
        :type action: str
        :param options:
        :type options:

        :return: bool -- Flag indicating whether session is authorized or not.
        """
        session_details = getattr(session, '_session_details', None)
        if session_details is None:
            # this happens for "embedded" sessions -- perhaps we
            # should have a better way to detect this -- also
            # session._transport should be a RouterApplicationSession
            details = {
                'session': session._session_id,
                'authid': session._authid,
                'authrole': session._authrole,
                'authmethod': session._authmethod,
                'authprovider': session._authprovider,
                'authextra': session._authextra,
                'transport': {
                    'type': 'stdio',  # or maybe "embedded"?
                }
            }
        else:
            _td = session._transport.transport_details.marshal() if session._transport.transport_details else None
            details = {
                'session': session_details.session,
                'authid': session_details.authid,
                'authrole': session_details.authrole,
                'authmethod': session_details.authmethod,
                'authprovider': session_details.authprovider,
                'authextra': session_details.authextra,
                'transport': _td
            }

        self.log.debug("CrossbarRouterRoleDynamicAuth.authorize {uri} {action} {details}",
                       uri=uri,
                       action=action,
                       details=details)

        d = self._session.call(self._authorizer, details, uri, action, options)

        # we could do backwards-compatibility for clients that didn't
        # yet add the 5th "options" argument to their authorizers like
        # so:
        def maybe_call_old_way(result):
            if isinstance(result, Failure):
                if isinstance(result.value, ApplicationError):
                    if 'takes exactly 4 arguments' in str(result.value):
                        self.log.warn(
                            "legacy authorizer '{auth}'; should take 5 arguments. Calling with 4.",
                            auth=self._authorizer,
                        )
                        return self._session.call(self._authorizer, session_details, uri, action)
            return result

        d.addBoth(maybe_call_old_way)

        def sanity_check(authorization):
            """
            Ensure the return-value we got from the user-supplied method makes sense
            """
            if isinstance(authorization, dict):
                # check keys
                for key in authorization.keys():
                    if key not in ['allow', 'cache', 'disclose', 'validate', 'meta']:
                        return Failure(ValueError("Authorizer returned unknown key '{key}'".format(key=key, )))
                # must have "allow" key
                if 'allow' not in authorization:
                    return Failure(ValueError("Authorizer must have 'allow' in returned dict"))
                # check bool-valued keys
                for key in ['allow', 'cache', 'disclose']:
                    if key in authorization:
                        value = authorization[key]
                        if not isinstance(value, bool):
                            return Failure(ValueError("Authorizer must have bool for '{}'".format(key)))
                # check dict-valued keys
                for key in ['validate', 'meta']:
                    if key in authorization:
                        value = authorization[key]
                        if value is not None and not isinstance(value, dict):
                            return Failure(
                                ValueError("Authorizer must have dict for '{}' (if present and not null)".format(key)))
                return authorization

            elif isinstance(authorization, bool):
                return authorization

            return Failure(
                ValueError("Authorizer returned unknown type '{name}'".format(name=type(authorization).__name__, )))

        d.addCallback(sanity_check)
        return d


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

    def authorize(self, session, uri, action, options):
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
