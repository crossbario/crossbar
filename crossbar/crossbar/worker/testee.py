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


import crossbar

from autobahn.twisted.websocket import WebSocketServerFactory, \
                                       WebSocketServerProtocol

from autobahn.websocket.compress import *

from crossbar.router.protocol import set_websocket_options


class TesteeServerProtocol(WebSocketServerProtocol):

   def onMessage(self, payload, isBinary):
      self.sendMessage(payload, isBinary)

   def sendServerStatus(self, redirectUrl = None, redirectAfter = 0):
      """
      Used to send out server status/version upon receiving a HTTP/GET without
      upgrade to WebSocket header (and option serverStatus is True).
      """
      try:
         page = self.factory._templates.get_template('cb_ws_testee_status.html')
         self.sendHtml(page.render(redirectUrl = redirectUrl,
                                   redirectAfter = redirectAfter,
                                   cbVersion = crossbar.__version__,
                                   wsUri = self.factory.url))
      except Exception as e:         
         log.msg("Error rendering WebSocket status page template: %s" % e)



class StreamingTesteeServerProtocol(WebSocketServerProtocol):

   def onMessageBegin(self, isBinary):
      #print "onMessageBegin"
      WebSocketServerProtocol.onMessageBegin(self, isBinary)
      self.beginMessage(isBinary = isBinary)

   def onMessageFrameBegin(self, length):
      #print "onMessageFrameBegin"
      WebSocketServerProtocol.onMessageFrameBegin(self, length)
      self.beginMessageFrame(length)

   def onMessageFrameData(self, data):
      #print "onMessageFrameData", len(data)
      self.sendMessageFrameData(data)

   def onMessageFrameEnd(self):
      #print "onMessageFrameEnd"
      pass

   def onMessageEnd(self):
      #print "onMessageEnd"
      self.endMessage()




class TesteeServerFactory(WebSocketServerFactory):

   protocol = TesteeServerProtocol
   #protocol = StreamingTesteeServerProtocol

   def __init__(self, config, templates):
      """
      Ctor.

      :param factory: WAMP session factory.
      :type factory: An instance of ..
      :param config: Crossbar transport configuration.
      :type config: dict 
      """
      options = config.get('options', {})

      server = "Crossbar/{}".format(crossbar.__version__)
      externalPort = options.get('external_port', None)


      WebSocketServerFactory.__init__(self,
                                      url = config.get('url', None),
                                      server = server,
                                      externalPort = externalPort,
                                      debug = config.get('debug', False))

      ## transport configuration
      self._config = config

      ## Jinja2 templates for 404 etc
      self._templates = templates

      ## set WebSocket options
      set_websocket_options(self, options)
