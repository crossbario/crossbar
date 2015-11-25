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

__all__ = (
    'PendingAuth',
    'PendingAuthPersona',
    'PendingAuthWampCra',
    'PendingAuthTicket'
)


class PendingAuth:

    """
    Base class for pending WAMP authentications.
    """


class PendingAuthPersona(PendingAuth):

    """
    Pending Mozilla Persona authentication.
    """

    def __init__(self, provider, audience, role=None):
        self.authmethod = u"mozilla_persona"
        self.provider = provider
        self.audience = audience
        self.role = role


class PendingAuthWampCra(PendingAuth):

    """
    Pending WAMP-CRA authentication.
    """

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
        self.authmethod = u"wampcra"
        self.authid = authid
        self.authrole = authrole
        self.authprovider = authprovider

        challenge_obj = {
            'authid': self.authid,
            'authrole': self.authrole,
            'authmethod': u'wampcra',
            'authprovider': self.authprovider,
            'session': self.session,
            'nonce': util.newid(),
            'timestamp': util.utcnow()
        }

        self.challenge = json.dumps(challenge_obj, ensure_ascii=False)

        # Sometimes, if it doesn't have to be Unicode, PyPy won't make it
        # Unicode. Make it Unicode, even if it's just ASCII.
        if not isinstance(self.challenge, six.text_type):
            self.challenge = self.challenge.decode('utf8')

        self.signature = auth.compute_wcs(secret, self.challenge.encode('utf8')).decode('ascii')


class PendingAuthTicket(PendingAuth):

    """
    Pending Ticket-based authentication.
    """

    def __init__(self, realm, authid, authrole, authprovider, ticket):
        """
        :param authid: The authentication ID of the authenticating principal.
        :type authid: unicode
        :param authrole: The role under which the principal will be authenticated when
           the authentication succeeds.
        :type authrole: unicode
        :param authprovider: Optional authentication provider (URI of procedure to call).
        :type authprovider: unicode or None
        :param ticket: The secret/ticket the authenticating principal will need to provide (or `None` when using dynamic authenticator).
        :type ticket: bytes or None
        """
        self.authmethod = u"ticket"
        self.realm = realm
        self.authid = authid
        self.authrole = authrole
        self.authprovider = authprovider
        self.ticket = ticket
