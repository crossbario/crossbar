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

from autobahn import util
from autobahn.wamp import auth

__all__ = [
    'PendingAuth',
    'PendingAuthWampCra',
    'PendingAuthTicket'
]


class PendingAuth:

    """
    Base class for pending WAMP authentications.
    """

    authmethod = u'abstract'


class PendingAuthWampCra(PendingAuth):

    """
    Pending WAMP-CRA authentication.
    """

    authmethod = u'wampcra'

    def __init__(self, session, authid, authrole, authprovider, secret):
        """
        :param session: The WAMP session ID of the session being authenticated.
        :type session: int
        :param authid: The authentication ID of the authenticating principal.
        :type authid: unicode
        :param authrole: The role under which the principal will be authenticated when
           the authentication succeeds.
        :type authrole: unicode
        :param authprovider: Optional authentication provider.
        :type authprovider: unicode or None
        :param secret: The secret of the principal being authenticated. Either a password
           or a salted password.
        :type secret: str
        """
        self.session = session
        self.authid = authid
        self.authrole = authrole
        self.authprovider = authprovider

        challenge_obj = {
            'authid': self.authid,
            'authrole': self.authrole,
            'authmethod': self.authmethod,
            'authprovider': self.authprovider,
            'session': self.session,
            'nonce': util.newid(64),
            'timestamp': util.utcnow()
        }

        self.challenge = json.dumps(challenge_obj, ensure_ascii=False)

        # Sometimes, if it doesn't have to be Unicode, PyPy won't make it
        # Unicode. Make it Unicode, even if it's just ASCII.
        if not isinstance(self.challenge, six.text_type):
            self.challenge = self.challenge.decode('utf8')

        self.signature = auth.compute_wcs(secret, self.challenge.encode('utf8')).decode('ascii')

    def verify(self, signature):
        return signature == self.signature


from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError


class PendingAuthTicket(PendingAuth):

    """
    Pending Ticket-based authentication.
    """

    authmethod = u'ticket'

    def __init__(self,
                 session,
                 realm=None,
                 authid=None,
                 authrole=None,
                 authprovider=None,
                 ticket=None,
                 authenticator=None,
                 authenticator_session=None):
        """
        Pending authentication information for WAMP-Ticket static and dynamic modes.
        For static WAMP-Ticket, all fields but `authenticator` and `authenticator_session` are filled.
        For dynamic WAMP-Ticket, all fields but `ticket` are filled.

        :param authid: The authentication ID of the authenticating principal.
        :type authid: unicode
        :param authrole: The role under which the principal will be authenticated when
           the authentication succeeds.
        :type authrole: unicode
        :param authprovider: Optional authentication provider (URI of procedure to call).
        :type authprovider: unicode or None
        :param ticket: The secret/ticket the authenticating principal will need to provide (filled only in static mode).
        :type ticket: bytes or None
        :param authenticator: The URI of the authenticator procedure to call (filled only in dynamic mode).
        :type authenticator: unicode or None
        :param authenticator_session: The session over which to issue the call to the authenticator (filled only in dynamic mode).
        :type authenticator_session: obj
        """
        self.session = session
        self.realm = realm
        self.authid = authid
        self.authrole = authrole
        self.authprovider = authprovider
        self.ticket = ticket
        self.authenticator = authenticator
        self.authenticator_session = authenticator_session

    def __str__(self):
        return u"PendingAuthTicket(realm={}, authid={}, authrole={}, authprovider={}, ticket={}, authenticator={}, authenticator_session={})".format(self.realm, self.authid, self.authrole, self.authprovider, self.ticket, self.authenticator, self.authenticator_session)

    def verify(self, signature):
        """
        The WAMP client has answered with a WAMP AUTHENTICATE message. Verify the message and
        return `types.Accept` or `types.Deny`.
        """
        # WAMP-Ticket "static"
        #
        if self.authprovider == 'static':

            # when doing WAMP-Ticket from static configuration, the ticket we
            # expect was store on the pending authentication object and we just compare ..
            if signature == self.ticket:
                # ticket was valid: accept the client
                return types.Accept(realm=self.realm,
                                    authid=self.authid,
                                    authrole=self.authrole,
                                    authmethod=self.authmethod,
                                    authprovider=self.authprovider)
            else:
                # ticket was invalid: deny client
                return types.Deny(message=u"ticket in static WAMP-Ticket authentication is invalid")

        # WAMP-Ticket "dynamic"
        #
        else:
            details = {
                'transport': self.session._transport._transport_info,
                'session': self.session._pending_session_id,
                'ticket': signature
            }
            d = self.authenticator_session.call(self.authenticator, self.realm, self.authid, details)

            def on_authenticate_ok(principal):
                if isinstance(principal, dict):
                    # dynamic ticket authenticator returned a dictionary (new)
                    realm = principal.get("realm", self.realm)
                    authid = principal.get("authid", self.authid)
                    authrole = principal["role"]
                else:
                    # backwards compatibility: dynamic ticket authenticator
                    # was expected to return a role directly
                    realm = self.realm
                    authid = self.authid
                    authrole = principal

                return types.Accept(realm=realm,
                                    authid=authid,
                                    authrole=authrole,
                                    authmethod=self.authmethod,
                                    authprovider=self.authprovider)

            def on_authenticate_error(err):
                error = None
                message = "WAMP-Ticket dynamic authenticator failed: {}".format(err)

                if isinstance(err.value, ApplicationError):
                    error = err.value.error
                    if err.value.args and len(err.value.args):
                        message = err.value.args[0]

                return types.Deny(error, message)

            d.addCallbacks(on_authenticate_ok, on_authenticate_error)

            return d


try:
    import nacl
    HAS_ED25519 = True
except ImportError:
    HAS_ED25519 = False

__all__.append('HAS_ED25519')


if HAS_ED25519:

    class PendingAuthEd25519(PendingAuth):
        """
        Pending Ed25519 authentication.
        """

        authmethod = u'ed25519'

        def __init__(self, session, authid, authrole, authprovider, verify_key):
            """
            :param session: The WAMP session ID of the session being authenticated.
            :type session: int
            :param authid: The authentication ID of the authenticating principal.
            :type authid: unicode
            :param authrole: The role under which the principal will be authenticated when
               the authentication succeeds.
            :type authrole: unicode
            :param authprovider: Optional authentication provider.
            :type authprovider: unicode or None
            :param verify_key: Hex representation of (public) verification key (64 chars for 32-byte value).
            :type verify_key: unicode
            """
            self.session = session
            self.authid = authid
            self.authrole = authrole
            self.authprovider = authprovider
            self.verify_key = verify_key
            self._verify_key = nacl.signing.VerifyKey(verify_key, encoder=nacl.encoding.HexEncoder)

            challenge_obj = {
                'authid': self.authid,
                'authrole': self.authrole,
                'authmethod': self.authmethod,
                'authprovider': self.authprovider,
                'session': self.session,
                'nonce': util.newid(64),
                'timestamp': util.utcnow()
            }

            self.challenge = json.dumps(challenge_obj, ensure_ascii=False)

            # Sometimes, if it doesn't have to be Unicode, PyPy won't make it
            # Unicode. Make it Unicode, even if it's just ASCII.
            if not isinstance(self.challenge, six.text_type):
                self.challenge = self.challenge.decode('utf8')

        def verify(self, signature):
            signed = nacl.signing.SignedMessage(signature + self.challenge)
            # Check the validity of a message's signature
            # Will raise nacl.exceptions.BadSignatureError if the signature check fails
            try:
                self._verify_key.verify(signed)
                return True
            except nacl.exceptions.BadSignatureError:
                return False

else:
    PendingAuthEd25519 = type(None)

__all__.append('PendingAuthEd25519')
