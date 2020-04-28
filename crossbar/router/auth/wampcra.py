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

import json

from autobahn import util
from autobahn.wamp import auth
from autobahn.wamp import types

from crossbar.router.auth.pending import PendingAuth

import txaio


__all__ = ('PendingAuthWampCra',)


class PendingAuthWampCra(PendingAuth):
    """
    Pending WAMP-CRA authentication.
    """

    AUTHMETHOD = 'wampcra'

    def __init__(self, pending_session_id, transport_info, realm_container, config):
        super(PendingAuthWampCra, self).__init__(
            pending_session_id, transport_info, realm_container, config,
        )

        # The signature we expect the client to send in AUTHENTICATE.
        self._signature = None

    def _compute_challenge(self, user):
        """
        Returns: challenge, signature
        """
        challenge_obj = {
            'authid': self._authid,
            'authrole': self._authrole,
            'authmethod': self._authmethod,
            'authprovider': self._authprovider,
            'session': self._session_details['session'],
            'nonce': util.newid(64),
            'timestamp': util.utcnow()
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
            'challenge': challenge
        }

        # when using salted passwords, provide the client with
        # the salt and then PBKDF2 parameters used
        if 'salt' in user:
            extra['salt'] = user['salt']
            extra['iterations'] = user.get('iterations', 1000)
            extra['keylen'] = user.get('keylen', 32)

        return extra, signature

    def hello(self, realm, details):

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config['type'] == 'static':

            self._authprovider = 'static'

            if self._authid in self._config.get('users', {}):

                principal = self._config['users'][self._authid]

                error = self._assign_principal(principal)
                if error:
                    return error

                # now compute CHALLENGE.Extra and signature as
                # expected for WAMP-CRA
                extra, self._signature = self._compute_challenge(principal)

                return types.Challenge(self._authmethod, extra)
            else:
                return types.Deny(message='no principal with authid "{}" exists'.format(details.authid))

        # use configured procedure to dynamically get a ticket for the principal
        elif self._config['type'] == 'dynamic':

            self._authprovider = 'dynamic'

            init_d = txaio.as_future(self._init_dynamic_authenticator)

            def init(result):
                if result:
                    return result

                self._session_details['authmethod'] = self._authmethod  # from AUTHMETHOD, via base
                self._session_details['authextra'] = details.authextra

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
            init_d.addBoth(init)
            return init_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

    def authenticate(self, signature):

        if signature == self._signature:
            # signature was valid: accept the client
            return self._accept()
        else:
            # signature was invalid: deny the client
            return types.Deny(message="WAMP-CRA signature is invalid")
