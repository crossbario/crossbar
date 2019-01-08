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

import json

from autobahn import util
from autobahn.wamp import auth
from autobahn.wamp import types

from crossbar.router.auth.pending import PendingAuth

__all__ = ('PendingAuthWampCra',)


class PendingAuthWampCra(PendingAuth):
    """
    Pending WAMP-CRA authentication.
    """

    AUTHMETHOD = u'wampcra'

    def __init__(self, session, config):
        PendingAuth.__init__(self, session, config)

        # The signature we expect the client to send in AUTHENTICATE.
        self._signature = None

    def _compute_challenge(self, user):
        """
        Returns: challenge, signature
        """
        challenge_obj = {
            u'authid': self._authid,
            u'authrole': self._authrole,
            u'authmethod': self._authmethod,
            u'authprovider': self._authprovider,
            u'session': self._session_details[u'session'],
            u'nonce': util.newid(64),
            u'timestamp': util.utcnow()
        }
        challenge = json.dumps(challenge_obj, ensure_ascii=False)

        # Sometimes, if it doesn't have to be Unicode, PyPy won't make it
        # Unicode. Make it Unicode, even if it's just ASCII.
        if not isinstance(challenge, str):
            challenge = challenge.decode('utf8')

        secret = user['secret'].encode('utf8')
        signature = auth.compute_wcs(secret, challenge.encode('utf8')).decode('ascii')

        # extra data to send to client in CHALLENGE
        extra = {
            u'challenge': challenge
        }

        # when using salted passwords, provide the client with
        # the salt and then PBKDF2 parameters used
        if 'salt' in user:
            extra[u'salt'] = user['salt']
            extra[u'iterations'] = user.get('iterations', 1000)
            extra[u'keylen'] = user.get('keylen', 32)

        return extra, signature

    def hello(self, realm, details):

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config[u'type'] == u'static':

            self._authprovider = u'static'

            if self._authid in self._config.get(u'users', {}):

                principal = self._config[u'users'][self._authid]

                error = self._assign_principal(principal)
                if error:
                    return error

                # now compute CHALLENGE.Extra and signature as
                # expected for WAMP-CRA
                extra, self._signature = self._compute_challenge(principal)

                return types.Challenge(self._authmethod, extra)
            else:
                return types.Deny(message=u'no principal with authid "{}" exists'.format(details.authid))

        # use configured procedure to dynamically get a ticket for the principal
        elif self._config[u'type'] == u'dynamic':

            self._authprovider = u'dynamic'

            error = self._init_dynamic_authenticator()
            if error:
                return error

            self._session_details[u'authmethod'] = self._authmethod  # from AUTHMETHOD, via base
            self._session_details[u'authextra'] = details.authextra

            d = self._authenticator_session.call(self._authenticator, realm, details.authid, self._session_details)

            def on_authenticate_ok(principal):
                error = self._assign_principal(principal)
                if error:
                    return error

                # now compute CHALLENGE.Extra and signature expected
                extra, self._signature = self._compute_challenge(principal)
                return types.Challenge(self._authmethod, extra)

            def on_authenticate_error(err):
                return self._marshal_dynamic_authenticator_error(err)

            d.addCallbacks(on_authenticate_ok, on_authenticate_error)
            return d

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message=u'invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

    def authenticate(self, signature):

        if signature == self._signature:
            # signature was valid: accept the client
            return self._accept()
        else:
            # signature was invalid: deny the client
            return types.Deny(message=u"WAMP-CRA signature is invalid")
