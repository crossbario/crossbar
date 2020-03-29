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

import abc
from autobahn.wamp import types
from autobahn.wamp.interfaces import ISession
from autobahn.wamp.exception import ApplicationError

__all__ = ('PendingAuth',)


class IRealmContainer(abc.ABC):
    """
    An object the authentication system can query about the existince
    of realms and roles.
    """

    @abc.abstractmethod
    def has_realm(self, realm: str) -> bool:
        """
        :returns: True if the given realm exists
        """

    @abc.abstractmethod
    def has_role(self, realm: str, role: str) -> bool:
        """
        :returns: True if the given role exists inside the realm
        """

    @abc.abstractmethod
    def get_service_session(self, realm: str) -> ISession:
        """
        :returns: ApplicationSession suitable for use by dynamic
            authenticators
        """


class PendingAuth:

    """
    Base class for pending WAMP authentications.

    After creating a pending authentication first call ``open()`` and
    then ``verify()`` (each should be called exactly once, and in this order).
    """

    AUTHMETHOD = 'abstract'

    def __init__(self, pending_session_id, transport_info, realm_container, config):
        """
        :param int pending_session_id: the Session ID if this succeeds

        :param dict transport_info: information about the session's transport

        :param IRealmContainer realm_container: access configured realms / roles

        :param dict config: Authentication configuration to apply for the pending auth.
        """

        # Details about the authenticating session
        self._session_details = {
            'transport': transport_info,
            'session': pending_session_id,
            'authmethod': None,
            'authextra': None
        }

        # The router factory we are working for
        self._realm_container = realm_container

        # WAMP-Ticket configuration to apply for the pending auth
        self._config = config

        # The authentication ID of the authenticating principal.
        self._authid = None

        # The role under which the principal will be authenticated when
        # the authentication succeeds.
        self._authrole = None

        # Optional authentication provider (URI of procedure to call).
        self._authprovider = None

        # The authentication method
        self._authmethod = self.AUTHMETHOD

        # Application-specific extra data forwarded to the authenticating client in WELCOME
        self._authextra = None

        # The URI of the authenticator procedure to call (filled only in dynamic mode).
        self._authenticator = None

        # The session over which to issue the call to the authenticator (filled only in dynamic mode).
        self._authenticator_session = None

    def _assign_principal(self, principal):
        if isinstance(principal, str):
            # FIXME: more strict authrole checking
            pass
        elif isinstance(principal, dict):
            # FIXME: check principal
            pass
        else:
            error = ApplicationError.AUTHENTICATION_FAILED
            message = 'got invalid return type "{}" from dynamic authenticator'.format(type(principal))
            return types.Deny(error, message)

        # backwards compatibility: dynamic authenticator
        # was expected to return a role directly
        if isinstance(principal, str):
            principal = {
                'role': principal
            }

        # allow to override realm request, redirect realm or set default realm
        if 'realm' in principal:
            self._realm = principal['realm']

        # allow overriding effectively assigned authid
        if 'authid' in principal:
            self._authid = principal['authid']

        # determine effectively assigned authrole
        if 'role' in principal:
            self._authrole = principal['role']
        elif 'default-role' in self._config:
            self._authrole = self._config['default-role']

        # allow forwarding of application-specific "welcome data"
        if 'extra' in principal:
            self._authextra = principal['extra']

        # a realm must have been assigned by now, otherwise bail out!
        if not self._realm:
            return types.Deny(ApplicationError.NO_SUCH_REALM, message='no realm assigned')

        # an authid MUST be set at least by here - otherwise bail out now!
        if not self._authid:
            return types.Deny(ApplicationError.NO_SUCH_PRINCIPAL, message='no authid assigned')

        # an authrole MUST be set at least by here - otherwise bail out now!
        if not self._authrole:
            return types.Deny(ApplicationError.NO_SUCH_ROLE, message='no authrole assigned')

        # if realm is not started on router, bail out now!
        if not self._realm_container.has_realm(self._realm):
            return types.Deny(
                ApplicationError.NO_SUCH_REALM,
                message='no realm "{}" exists on this router'.format(self._realm)
            )

        # if role is not running on realm, bail out now!
        if self._authrole and not self._realm_container.has_role(self._realm, self._authrole):
            return types.Deny(
                ApplicationError.NO_SUCH_ROLE,
                message='realm "{}" has no role "{}"'.format(self._realm, self._authrole)
            )

    def _init_dynamic_authenticator(self):
        self._authenticator = self._config['authenticator']

        authenticator_realm = None
        if 'authenticator-realm' in self._config:
            authenticator_realm = self._config['authenticator-realm']
            if not self._realm_container.has_realm(authenticator_realm):
                return types.Deny(
                    ApplicationError.NO_SUCH_REALM,
                    message="explicit realm <{}> configured for dynamic authenticator does not exist".format(authenticator_realm)
                )
        else:
            if not self._realm:
                return types.Deny(
                    ApplicationError.NO_SUCH_REALM,
                    message="client did not specify a realm to join (and no explicit realm was configured for dynamic authenticator)"
                )
            authenticator_realm = self._realm

        self._authenticator_session = self._realm_container.get_service_session(authenticator_realm)

    def _marshal_dynamic_authenticator_error(self, err):
        if isinstance(err.value, ApplicationError):
            # forward the inner error URI and message (or coerce the first args item to str)
            msg = None
            if err.value.args:
                msg = '{}'.format(err.value.args[0])
            return types.Deny(err.value.error, msg)
        else:
            # wrap the error
            error = ApplicationError.AUTHENTICATION_FAILED
            message = 'dynamic authenticator failed: {}'.format(err.value)
            return types.Deny(error, message)

    def _accept(self):
        return types.Accept(realm=self._realm,
                            authid=self._authid,
                            authrole=self._authrole,
                            authmethod=self._authmethod,
                            authprovider=self._authprovider,
                            authextra=self._authextra)

    def hello(self, realm, details):
        """
        When a HELLO message is received, this gets called to open the pending authentication.

        :param realm: The realm to client wishes to join (if the client did announance a realm).
        :type realm: unicode or None
        :param details: The details of the client provided for HELLO.
        :type details: dict
        """
        raise Exception("not implemented {})".format(self.__class__.__name__))

    def authenticate(self, signature):
        """
        The WAMP client has answered with a WAMP AUTHENTICATE message. Verify the message and
        return `types.Accept` or `types.Deny`.
        """
        raise Exception("not implemented")
