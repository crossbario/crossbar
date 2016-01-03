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

from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError

from crossbar.router.auth.pending import PendingAuth

__all__ = ('PendingAuthTicket',)


class PendingAuthTicket(PendingAuth):

    """
    Pending authentication information for WAMP-Ticket authentication.
    """

    AUTHMETHOD = u'ticket'

    def __init__(self, session, config):
        PendingAuth.__init__(self, session, config)

        # The secret/ticket the authenticating principal will need to provide (filled only in static mode).
        self._signature = None

        # The URI of the authenticator procedure to call (filled only in dynamic mode).
        self._authenticator = None

        # The session over which to issue the call to the authenticator (filled only in dynamic mode).
        self._authenticator_session = None

    def hello(self, realm, details):

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config[u'type'] == u'static':

            self._authprovider = u'static'

            if self._authid in self._config.get(u'principals', {}):

                principal = self._config[u'principals'][details._authid]

                error = self._assign_principal(principal)
                if error:
                    return error

                # now set set signature as expected for WAMP-Ticket
                self._signature = principal[u'ticket'].encode('utf8')

                return types.Challenge(self.AUTHMETHOD)
            else:
                return types.Deny(message=u'no principal with authid "{}" exists'.format(details.authid))

        # use configured procedure to dynamically get a ticket for the principal
        elif self._config['type'] == 'dynamic':

            self._authprovider = u'dynamic'

            self._authenticator = self._config['authenticator']

            authenticator_realm = None
            if u'authenticator-realm' in self._config:
                authenticator_realm = self._config[u'authenticator-realm']
                if authenticator_realm not in self._router_factory:
                    return types.Deny(ApplicationError.NO_SUCH_REALM, message=u"explicit realm <{}> configured for dynamic authenticator does not exist".format(authenticator_realm))
            else:
                if not realm:
                    return types.Deny(ApplicationError.NO_SUCH_REALM, message=u"client did not specify a realm to join (and no explicit realm was configured for dynamic authenticator)")
                authenticator_realm = realm

            self._authenticator_session = self._router_factory.get(authenticator_realm)._realm.session

            return types.Challenge(u'ticket')

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message=u'invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

    def authenticate(self, signature):

        # WAMP-Ticket "static"
        if self._authprovider == 'static':

            # when doing WAMP-Ticket from static configuration, the ticket we
            # expect was previously stored in self._signature
            if signature == self._signature:
                # ticket was valid: accept the client
                return types.Accept(realm=self._realm,
                                    authid=self._authid,
                                    authrole=self._authrole,
                                    authmethod=self._authmethod,
                                    authprovider=self._authprovider)
            else:
                # ticket was invalid: deny client
                return types.Deny(message=u"ticket in static WAMP-Ticket authentication is invalid")

        # WAMP-Ticket "dynamic"
        else:
            d = self._authenticator_session.call(self._authenticator, self._realm, self._authid, self._session_details)

            def on_authenticate_ok(principal):
                # backwards compatibility: dynamic ticket authenticator
                # was expected to return a role directly
                if type(principal) == six.text_type:
                    principal = {u'role': principal}

                error = self._assign_principal(principal)
                if error:
                    return error

                return types.Accept(realm=self._realm,
                                    authid=self._authid,
                                    authrole=self._authrole,
                                    authmethod=self.AUTHMETHOD,
                                    authprovider=self._authprovider)

            def on_authenticate_error(err):
                error = None
                message = u'dynamic authenticator failed: {}'.format(err)

                if isinstance(err.value, ApplicationError):
                    error = err.value.error
                    if err.value.args and len(err.value.args):
                        message = str(err.value.args[0])  # exception does not need to contain a string

                return types.Deny(error, message)

            d.addCallbacks(on_authenticate_ok, on_authenticate_error)

            return d
