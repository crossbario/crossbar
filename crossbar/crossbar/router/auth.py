###############################################################################
##
##  Copyright (C) 2014 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################

from __future__ import absolute_import

__all__ = (
   'PendingAuth',
   'PendingAuthPersona',
   'PendingAuthWampCra',
   'PendingAuthTicket'
)


import json

from autobahn import util
from autobahn.wamp import auth



class PendingAuth:
   """
   Base class for pending WAMP authentications.
   """



class PendingAuthPersona(PendingAuth):
   """
   Pending Mozilla Persona authentication.
   """

   def __init__(self, provider, audience, role = None):
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

      self.challenge = json.dumps(challenge_obj)
      self.signature = auth.compute_wcs(secret, self.challenge)



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
