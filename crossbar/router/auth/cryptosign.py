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

import json
import six

import nacl
from nacl.signing import VerifyKey
from nacl.signing import SignedMessage
from nacl.exceptions import BadSignatureError

from autobahn import util
from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError

from crossbar.router.auth.pending import PendingAuth

__all__ = ('PendingAuthCryptosign',)


class PendingAuthCryptosign(PendingAuth):
    """
    Pending Cryptosign authentication.
    """

    AUTHMETHOD = u'cryptosign'

    def __init__(self, session, config):
        PendingAuth.__init__(self, session, config)
        self._verify_key = None

    def hello(self, realm, details):

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config['type'] == 'static':

            self._authprovider = u'static'

            if self._authid in self._config.get(u'users', {}):

                principal = self._config[u'users'][self._authid]

                error = self._assign_principal(principal)
                if error:
                    return error

                self._verify_key = VerifyKey(principal[u'pubkey'], encoder=nacl.encoding.HexEncoder)

                extra, self._challenge = self._compute_challenge()
                return types.Challenge(self.AUTHMETHOD, extra)
            else:
                return types.Deny(message=u'no principal with authid "{}" exists'.format(details.authid))

        elif self._config[u'type'] == u'dynamic':

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

            d = self._authenticator_session.call(self._authenticator, realm, details.authid, self._session_details)

            def on_authenticate_ok(principal):
                error = self._assign_principal(principal)
                if error:
                    return error

                self._verify_key = VerifyKey(principal[u'pubkey'], encoder=nacl.encoding.HexEncoder)

                extra, self._challenge = self._compute_challenge()
                return types.Challenge(self.AUTHMETHOD, extra)

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

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message=u'invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

    def _compute_challenge(self):

        challenge_obj = {
            u'authid': self._authid,
            u'authrole': self._authrole,
            u'authmethod': self.AUTHMETHOD,
            u'authprovider': self._authprovider,
            u'session': self._session_details[u'session'],
            u'nonce': util.newid(64),
            u'timestamp': util.utcnow()
        }
        challenge = json.dumps(challenge_obj, ensure_ascii=False)

        # Sometimes, if it doesn't have to be Unicode, PyPy won't make it
        # Unicode. Make it Unicode, even if it's just ASCII.
        if not isinstance(challenge, six.text_type):
            challenge = challenge.decode('utf8')

        extra = {
            u'challenge': challenge
        }
        return extra, challenge

    def authenticate(self, signature):
        signed = SignedMessage(signature + self._challenge)
        # Check the validity of a message's signature
        # Will raise nacl.exceptions.BadSignatureError if the signature check fails
        try:
            self._verify_key.verify(signed)

            # signature was valid: accept the client
            return types.Accept(realm=self._realm,
                                authid=self._authid,
                                authrole=self._authrole,
                                authmethod=self.AUTHMETHOD,
                                authprovider=self._authprovider)

        except BadSignatureError:
            # signature was invalid: deny the client
            return types.Deny(message=u"invalid signature")
