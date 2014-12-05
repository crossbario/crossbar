###############################################################################
##
##  Copyright (C) 2014, Tavendo GmbH and/or collaborators. All rights reserved.
##
##  Redistribution and use in source and binary forms, with or without
##  modification, are permitted provided that the following conditions are met:
##
##  1. Redistributions of source code must retain the above copyright notice,
##     this list of conditions and the following disclaimer.
##
##  2. Redistributions in binary form must reproduce the above copyright notice,
##     this list of conditions and the following disclaimer in the documentation
##     and/or other materials provided with the distribution.
##
##  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
##  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
##  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
##  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
##  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
##  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
##  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
##  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
##  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
##  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
##  POSSIBILITY OF SUCH DAMAGE.
##
###############################################################################

from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError



class MyAuthenticator(ApplicationSession):

   PRINCIPALS_DB = {
      'joe': {
         'ticket': 'secret!!!',
         'role': 'frontend'
      }
   }

   @inlineCallbacks
   def onJoin(self, details):

      def authenticate(realm, authid, ticket):
         print("MyAuthenticator.authenticate called: realm = '{}', authid = '{}', ticket = '{}'".format(realm, authid, ticket))

         if authid in self.PRINCIPALS_DB:
            if ticket == self.PRINCIPALS_DB[authid]['ticket']:
               return self.PRINCIPALS_DB[authid]['role']
            else:
               raise ApplicationError("com.example.invalid_ticket", "could not authenticate session - invalid ticket '{}' for principal {}".format(ticket, authid))
         else:
            raise ApplicationError("com.example.no_such_user", "could not authenticate session - no such principal {}".format(authid))

      try:
         yield self.register(authenticate, 'com.example.authenticate')
         print("custom Ticket-based authenticator registered")
      except Exception as e:
         print("could not register custom Ticket-based authenticator: {0}".format(e))
