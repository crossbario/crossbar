###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
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


import urlparse

from twisted.python import log
from twisted.application import service


def validateUri(uri, allowEmptyNetworkLocation = False):

   ## valid URI: absolute URI from http(s) scheme, no query component
   ##
   try:
      p = urlparse.urlparse(uri)

      if p.scheme == "":
         return False, "URI '%s' does not contain a scheme." % uri
      else:
         if p.scheme not in ['http', 'https']:
            return False, "URI '%s' scheme '%s' is invalid (only 'http' or 'https' allowed." % (uri, p.scheme)

      if p.netloc == "" and not allowEmptyNetworkLocation:
         return False, "URI '%s' does not contain a network location." % uri

      if p.query != "":
         return False, "URI '%s' contains a query component '%s'." % (uri, p.query)

      normalizedUri = urlparse.urlunparse(p)

      return True, normalizedUri

   except Exception, e:

      return False, "Invalid URI '%s' - could not parse URI (%s)" % (uri, str(e))



class Pusher(service.Service):

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False


   def startService(self):
      log.msg("Starting %s service ..." % self.SERVICENAME)
      self.isRunning = True


   def stopService(self):
      log.msg("Stopping %s service ..." % self.SERVICENAME)
      self.isRunning = False
