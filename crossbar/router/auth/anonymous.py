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

from twisted.internet.defer import inlineCallbacks, returnValue

from autobahn import util
from autobahn.wamp import types

from crossbar.router.auth.pending import PendingAuth
from crossbar._logging import make_logger

__all__ = ('PendingAuthAnonymous',)


class PendingAuthAnonymous(PendingAuth):

    """
    Pending authentication information for WAMP-Anonymous authentication.
    """

    log = make_logger()

    AUTHMETHOD = u'anonymous'

    @inlineCallbacks
    def hello(self, realm, details):

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # WAMP-Ticket "static"
        if self._config[u'type'] == u'static':

            self._authprovider = u'static'
            self._authid = util.generate_serial_number()

            # FIXME: if cookie tracking is enabled, set authid to cookie value
            # self._authid = self._transport._cbtid

            principal = self._config

            error = yield self._assign_principal(principal)
            if error:
                returnValue(error)

            x = yield self._accept()
            returnValue(x)

        # WAMP-Ticket "dynamic"
        elif self._config[u'type'] == u'dynamic':

            self._authprovider = u'dynamic'
            self._authid = util.generate_serial_number()

            error = self._init_dynamic_authenticator()
            if error:
                returnValue(error)

            d = self._authenticator_session.call(self._authenticator, self._realm, self._authid, self._session_details)

            @inlineCallbacks
            def on_authenticate_ok(principal):
                error = yield self._assign_principal(principal)
                if error:
                    returnValue(error)

                returnValue(self._accept())

            def on_authenticate_error(err):
                return self._marshal_dynamic_authenticator_error(err)

            d.addCallbacks(on_authenticate_ok, on_authenticate_error)
            x = yield d
            returnValue(x)

        else:
            # should not arrive here, as config errors should be caught earlier
            returnValue(types.Deny(message=u'invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type'])))
