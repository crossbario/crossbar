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

from __future__ import absolute_import

import six

from autobahn.wamp import types

from txaio import make_logger

from crossbar.router.auth.pending import PendingAuth

__all__ = ('PendingAuthTicket',)


class PendingAuthTicket(PendingAuth):

    """
    Pending authentication information for WAMP-Ticket authentication.
    """

    log = make_logger()

    AUTHMETHOD = u'ticket'

    def __init__(self, session, config):
        PendingAuth.__init__(self, session, config)

        # The secret/ticket the authenticating principal will need to provide (filled only in static mode).
        self._signature = None

    def hello(self, realm, details):

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config[u'type'] == u'static':

            self._authprovider = u'static'

            if self._authid in self._config.get(u'principals', {}):

                principal = self._config[u'principals'][self._authid]
                principal[u'extra'] = details.authextra

                error = self._assign_principal(principal)
                if error:
                    return error

                # now set set signature as expected for WAMP-Ticket
                self._signature = principal[u'ticket']

                return types.Challenge(self._authmethod)
            else:
                return types.Deny(message=u'no principal with authid "{}" exists'.format(self._authid))

        # use configured procedure to dynamically get a ticket for the principal
        elif self._config[u'type'] == u'dynamic':

            self._authprovider = u'dynamic'

            error = self._init_dynamic_authenticator()
            if error:
                return error

            self._session_details[u'authmethod'] = self._authmethod  # from AUTHMETHOD, via base
            self._session_details[u'authextra'] = details.authextra

            return types.Challenge(self._authmethod)

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message=u'invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

    def authenticate(self, signature):

        # WAMP-Ticket "static"
        if self._authprovider == u'static':

            # when doing WAMP-Ticket from static configuration, the ticket we
            # expect was previously stored in self._signature
            if signature == self._signature:
                # ticket was valid: accept the client
                self.log.debug("WAMP-Ticket: ticket was valid!")
                return self._accept()
            else:
                # ticket was invalid: deny client
                self.log.debug(
                    'WAMP-Ticket (static): expected ticket "{expected}"" ({expected_type}), but got "{sig}" ({sig_type})',
                    expected=self._signature,
                    expected_type=type(self._signature),
                    sig=signature,
                    sig_type=type(signature),
                )
                return types.Deny(message=u"ticket in static WAMP-Ticket authentication is invalid")

        # WAMP-Ticket "dynamic"
        elif self._authprovider == u'dynamic':

            self._session_details[u'ticket'] = signature
            d = self._authenticator_session.call(self._authenticator, self._realm, self._authid, self._session_details)

            def on_authenticate_ok(principal):
                # backwards compatibility: dynamic ticket authenticator
                # was expected to return a role directly
                if type(principal) == six.text_type:
                    principal = {u'role': principal}

                error = self._assign_principal(principal)
                if error:
                    return error

                return self._accept()

            def on_authenticate_error(err):
                return self._marshal_dynamic_authenticator_error(err)

            d.addCallbacks(on_authenticate_ok, on_authenticate_error)

            return d

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message=u'invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))
