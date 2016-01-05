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

import os
import binascii

import nacl
from nacl.signing import VerifyKey
from nacl.signing import SignedMessage
from nacl.exceptions import BadSignatureError

from autobahn.wamp import types

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
        if config['type'] == 'static':
            self._pubkey_to_authid = {}
            for authid, principal in self._config.get(u'principals', {}).items():
                self._pubkey_to_authid[principal[u'pubkey']] = authid

    def _compute_challenge(self):
        challenge = binascii.b2a_hex(os.urandom(32))
        extra = {
            u'challenge': challenge
        }
        return extra, challenge

    def hello(self, realm, details):

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config['type'] == 'static':

            self._authprovider = u'static'

            # get client's pubkey, if it was provided in authextra
            pubkey = None
            if details.authextra and u'pubkey' in details.authextra:
                pubkey = details.authextra[u'pubkey']

            # if the client provides it's public key, that's enough to identify,
            # and we can infer the authid from that. BUT: that requires that
            # there is a 1:1 relation between authid's and pubkey's !! see below (*)
            if self._authid is None:
                if pubkey:
                    # we do a naive search, but that is ok, since "static mode" is from
                    # node configuration, and won't contain a lot principals anyway
                    for _authid, _principal in self._config.get(u'principals', {}).items():
                        if _principal[u'pubkey'] == pubkey:
                            # (*): this is necessary to detect multiple authid's having the same pubkey
                            # in which case we couldn't reliably map the authid from the pubkey
                            if self._authid is None:
                                self._authid = _authid
                            else:
                                return types.Deny(message=u'cannot infer client identity from pubkey: multiple authids in principal database have this pubkey')
                    if self._authid is None:
                        return types.Deny(message=u'cannot identify client: no authid requested and no principal found for provided extra.pubkey')
                else:
                    return types.Deny(message=u'cannot identify client: no authid requested and no extra.pubkey provided')

            if self._authid in self._config.get(u'principals', {}):

                principal = self._config[u'principals'][self._authid]

                if pubkey and (principal[u'pubkey'] != pubkey):
                    return types.Deny(message=u'extra.pubkey provided does not match the one in principal database')

                error = self._assign_principal(principal)
                if error:
                    return error

                self._verify_key = VerifyKey(principal[u'pubkey'], encoder=nacl.encoding.HexEncoder)

                extra, self._challenge = self._compute_challenge()
                return types.Challenge(self._authmethod, extra)
            else:
                return types.Deny(message=u'no principal with authid "{}" exists'.format(details.authid))

        elif self._config[u'type'] == u'dynamic':

            self._authprovider = u'dynamic'

            error = self._init_dynamic_authenticator()
            if error:
                return error

            d = self._authenticator_session.call(self._authenticator, realm, details.authid, self._session_details)

            def on_authenticate_ok(principal):
                error = self._assign_principal(principal)
                if error:
                    return error

                self._verify_key = VerifyKey(principal[u'pubkey'], encoder=nacl.encoding.HexEncoder)

                extra, self._challenge = self._compute_challenge()
                return types.Challenge(self._authmethod, extra)

            def on_authenticate_error(err):
                return self._marshal_dynamic_authenticator_error(err)

            d.addCallbacks(on_authenticate_ok, on_authenticate_error)
            return d

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message=u'invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

    def authenticate(self, signature):
        # signatures in WAMP are strings, hence we roundtrip Hex
        signature = binascii.a2b_hex(signature)

        signed = SignedMessage(signature)
        try:
            # now verify the signed message versus the client public key
            self._verify_key.verify(signed)

            # signature was valid: accept the client
            return self._accept()

        except BadSignatureError:

            # signature was invalid: deny the client
            return types.Deny(message=u"invalid signature")

        except Exception as e:

            # should not arrive here .. but who knows
            return types.Deny(message=u"internal error: {}".format(e))
