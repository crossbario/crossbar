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


from zope.interface import implements

from twisted.python import failure, log
from twisted.internet import defer
from twisted.application import service
from twisted.protocols.ftp import FTPFactory, FTPRealm

from twisted.cred.portal import Portal
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred import error, credentials

from crossbar.txutil import CustomFTPFactory


class FtpUserDb:
   """
   Database backed FTP credentials checker.
   """

   implements(ICredentialsChecker)

   credentialInterfaces = (IUsernamePassword, )

   def __init__(self, service):
      self.service = service

   def _cbPasswordMatch(self, matched, username):
      if matched:
         # return user directory within FTP root dir
         return ""
         #return username
      else:
         log.msg("invalid password for FTP login '%s'" % username)
         return failure.Failure(error.UnauthorizedLogin())

   def _getSecretOk(self, res, c):
      if len(res) == 0:
         log.msg("unauthorized FTP login for '%s'" % c.username)
         return failure.Failure(error.UnauthorizedLogin())
      else:
         secret = res[0][0]
         return defer.maybeDeferred(c.checkPassword, secret).addCallback(self._cbPasswordMatch, c.username)

   def _getSecretFailed(self, err):
      log.msg("FTP user authentication internal error")
      log.msg(err)
      return failure.Failure(error.UnauthorizedLogin())

   def requestAvatarId(self, c):
      d = self.service.dbpool.runQuery("SELECT password FROM ftpuser WHERE user = ?", [c.username])
      d.addCallbacks(self._getSecretOk, self._getSecretFailed, [c])
      return d


class FtpService(service.Service):
   """
   Embedded FTP service.
   """

   SERVICENAME = "FTP"

   def __init__(self, dbpool, services, reactor = None):
      ## lazy import to avoid reactor install upon module import
      if reactor is None:
         from twisted.internet import reactor
      self.reactor = reactor

      self.dbpool = dbpool
      self.services = services
      self.isRunning = False

      self.port = services["config"]["ftp-port"]
      self.passivePortStart = services["config"]["ftp-passive-port-start"]
      self.passivePortEnd = services["config"]["ftp-passive-port-end"]
      self.passivePublicIp = str(services["config"]["ftp-passive-public-ip"]) if services["config"]["ftp-passive-public-ip"] else None
      self.homedir = str(self.services["master"].webdata)

      self.listener = None

   def startService(self):
      log.msg("Starting %s service .." % self.SERVICENAME)
      p = Portal(FTPRealm(anonymousRoot = '/dev/null', userHome = self.homedir), [FtpUserDb(self)])
      f = CustomFTPFactory(p)
      f.allowAnonymous = False
      f.passivePortRange = xrange(self.passivePortStart, self.passivePortEnd + 1)
      f.welcomeMessage = "crossbar.io FTP at your service."
      f.passivePublicIp = self.passivePublicIp
      self.listener = self.reactor.listenTCP(self.port, f)
      self.isRunning = True
      log.msg("embedded FTP server running on port %d (passive FTP ports %d - %d, homedir %s)" % (self.port, self.passivePortStart, self.passivePortEnd, self.homedir))

   def stopService(self):
      log.msg("Stopping %s service .." % self.SERVICENAME)
      if self.listener:
         self.listener.stopListening()
         self.listener = None
      self.isRunning = False
