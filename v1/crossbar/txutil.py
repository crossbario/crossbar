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


import re
from urlparse import urlunparse

from zope.interface import implements
from twisted.python import log

## the following does a module level import of reactor
## http://twistedmatrix.com/trac/browser/tags/releases/twisted-13.2.0/twisted/web/client.py#L31
## https://twistedmatrix.com/trac/ticket/6849
##
# from twisted.web.client import HTTPClientFactory

from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer
from twisted.internet.protocol import Protocol

## the following does a module level import of reactor
## http://twistedmatrix.com/trac/browser/tags/releases/twisted-13.2.0/twisted/protocols/ftp.py#L28
## https://twistedmatrix.com/trac/ticket/6849
##
#from twisted.protocols.ftp import FTPFactory, FTP, DTPFactory, ENTERING_PASV_MODE, encodeHostPort


## Starting from Twisted 13.1, this is removed. We replicate the code here. FIXME.
## http://twistedmatrix.com/trac/browser/tags/releases/twisted-13.0.0/twisted/web/client.py?format=txt

#from twisted.web.client import _parse
#from twisted.web import http


def _parse(url, defaultPort=None):
    """
    Split the given URL into the scheme, host, port, and path.

    @type url: C{bytes}
    @param url: An URL to parse.

    @type defaultPort: C{int} or C{None}
    @param defaultPort: An alternate value to use as the port if the URL does
    not include one.

    @return: A four-tuple of the scheme, host, port, and path of the URL.  All
    of these are C{bytes} instances except for port, which is an C{int}.
    """
    url = url.strip()
    parsed = http.urlparse(url)
    scheme = parsed[0]
    path = urlunparse((b'', b'') + parsed[2:])

    if defaultPort is None:
        if scheme == b'https':
            defaultPort = 443
        else:
            defaultPort = 80

    host, port = parsed[1], defaultPort
    if b':' in host:
        host, port = host.split(b':')
        try:
            port = int(port)
        except ValueError:
            port = defaultPort

    if path == b'':
        path = b'/'

    return (scheme, host, port, path)


def getDomain(str):
   try:
      import tldextract

      r = tldextract.extract(str)
      return r.domain + ("." + r.tld if r.tld != "" else "")
   except:
      return '.'.join(str.split('.')[-2:])


def isValidHostname(hostname):
   ## http://stackoverflow.com/a/2532344/884770
   if len(hostname) > 255:
      return False
   if hostname[-1:] == ".":
      hostname = hostname[:-1] # strip exactly one dot from the right, if present
   allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
   return all(allowed.match(x) for x in hostname.split("."))


class StringReceiver(Protocol):
   def __init__(self, finished):
      self.finished = finished
      self.response = []

   def dataReceived(self, bytes):
      #print bytes
      self.response.append(bytes)

   def connectionLost(self, reason):
      self.finished.callback("".join(self.response))


class StringProducer(object):
   implements(IBodyProducer)

   def __init__(self, body):
      self.body = body
      if body:
         self.length = len(body)
      else:
         self.length = 0

   def startProducing(self, consumer):
      if self.body:
         consumer.write(self.body)
      return succeed(None)

   def pauseProducing(self):
      pass

   def stopProducing(self):
      pass


def _makeGetterFactory(url, factoryFactory, contextFactory=None,
                       *args, **kwargs):
    """
    Create and connect an HTTP page getting factory.

    Any additional positional or keyword arguments are used when calling
    C{factoryFactory}.

    @param factoryFactory: Factory factory that is called with C{url}, C{args}
        and C{kwargs} to produce the getter

    @param contextFactory: Context factory to use when creating a secure
        connection, defaulting to C{None}

    @return: The factory created by C{factoryFactory}
    """
    scheme, host, port, path = _parse(url)

    ## extract connection timeout if present
    ##
    _kwargs = {}
    if kwargs.has_key('connectionTimeout'):
       _kwargs['timeout'] = kwargs['connectionTimeout']
       del kwargs['connectionTimeout']

    factory = factoryFactory(url, *args, **kwargs)

    from twisted.internet import reactor

    if scheme == 'https':
        from twisted.internet import ssl
        if contextFactory is None:
            contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory, **_kwargs)
    else:
        reactor.connectTCP(host, port, factory, **_kwargs)
    return factory


def getPage(url, contextFactory=None, *args, **kwargs):
    """
    Download a web page as a string.

    Download a page. Return a deferred, which will callback with a
    page (as a string) or errback with a description of the error.

    See L{HTTPClientFactory} to see what extra arguments can be passed.
    """
    return _makeGetterFactory(
        url,
        HTTPClientFactory,
        contextFactory=contextFactory,
        *args, **kwargs).deferred



class CustomFTP(object):
#class CustomFTP(FTP):
   def ftp_PASV(self):
      # if we have a DTP port set up, lose it.
      if self.dtpFactory is not None:
          # cleanupDTP sets dtpFactory to none.  Later we'll do
          # cleanup here or something.
          self.cleanupDTP()
      self.dtpFactory = DTPFactory(pi=self)
      self.dtpFactory.setTimeout(self.dtpTimeout)
      self.dtpPort = self.getDTPPort(self.dtpFactory)

      if self.factory.passivePublicIp is not None:
         # use explicit public IP for passive mode (when behind load-balancer or such)
         host = self.factory.passivePublicIp
         log.msg("using explicit public IP %s" % host)
      else:
         # use transport IP
         host = self.transport.getHost().host
         log.msg("using transport IP %s" % host)

      port = self.dtpPort.getHost().port
      self.reply(ENTERING_PASV_MODE, encodeHostPort(host, port))
      return self.dtpFactory.deferred.addCallback(lambda ign: None)


class CustomFTPFactory(object):
#class CustomFTPFactory(FTPFactory):
   protocol = CustomFTP
   passivePublicIp = None
