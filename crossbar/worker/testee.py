#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.internet.defer import inlineCallbacks
from twisted.internet import protocol

from autobahn.twisted.websocket import WebSocketServerFactory, \
    WebSocketServerProtocol
from autobahn.wamp.exception import ApplicationError
from autobahn import wamp

from txaio import make_logger

import crossbar
from crossbar.router.protocol import set_websocket_options
from crossbar.worker.controller import WorkerController
from crossbar.common.twisted.endpoint import create_listening_port_from_config

__all__ = (
    'WebSocketTesteeServerFactory',
    'StreamTesteeServerFactory',
)


class StreamTesteeServerProtocol(protocol.Protocol):
    def dataReceived(self, data):
        self.transport.write(data)


class StreamTesteeServerFactory(protocol.Factory):

    protocol = StreamTesteeServerProtocol


class WebSocketTesteeServerProtocol(WebSocketServerProtocol):

    log = make_logger()

    def onMessage(self, payload, isBinary):
        self.sendMessage(payload, isBinary)

    def sendServerStatus(self, redirectUrl=None, redirectAfter=0):
        """
        Used to send out server status/version upon receiving a HTTP/GET without
        upgrade to WebSocket header (and option serverStatus is True).
        """
        try:
            page = self.factory._templates.get_template('cb_ws_testee_status.html')
            self.sendHtml(
                page.render(redirectUrl=redirectUrl,
                            redirectAfter=redirectAfter,
                            cbVersion=crossbar.__version__,
                            wsUri=self.factory.url))
        except Exception as e:
            self.log.warn("Error rendering WebSocket status page template: {e}", e=e)


class StreamingWebSocketTesteeServerProtocol(WebSocketServerProtocol):
    def onMessageBegin(self, isBinary):
        WebSocketServerProtocol.onMessageBegin(self, isBinary)
        self.beginMessage(isBinary=isBinary)

    def onMessageFrameBegin(self, length):
        WebSocketServerProtocol.onMessageFrameBegin(self, length)
        self.beginMessageFrame(length)

    def onMessageFrameData(self, data):
        self.sendMessageFrameData(data)

    def onMessageFrameEnd(self):
        pass

    def onMessageEnd(self):
        self.endMessage()


class WebSocketTesteeServerFactory(WebSocketServerFactory):

    protocol = WebSocketTesteeServerProtocol

    # FIXME: we currently don't use the streaming variant of the testee server protocol,
    # since it does not work together with WebSocket compression
    # protocol = StreamingWebSocketTesteeServerProtocol

    def __init__(self, config, templates):
        """
        :param config: Crossbar transport configuration.
        :type config: dict
        """
        options = config.get('options', {})

        server = "Crossbar/{}".format(crossbar.__version__)
        externalPort = options.get('external_port', None)

        WebSocketServerFactory.__init__(self, url=config.get('url', None), server=server, externalPort=externalPort)

        # transport configuration
        self._config = config

        # Jinja2 templates for 404 etc
        self._templates = templates

        # set WebSocket options
        set_websocket_options(self, options)


class WebSocketTesteeController(WorkerController):
    """
    A native Crossbar.io worker that runs a WebSocket testee.
    """
    WORKER_TYPE = 'websocket-testee'
    WORKER_TITLE = 'WebSocket Testee'

    def __init__(self, config=None, reactor=None, personality=None):
        # base ctor
        WorkerController.__init__(self, config=config, reactor=reactor, personality=personality)

    @inlineCallbacks
    def onJoin(self, details):
        """
        Called when worker process has joined the node's management realm.
        """
        yield WorkerController.onJoin(self, details, publish_ready=False)

        # WorkerController.publish_ready()
        yield self.publish_ready()

    @wamp.register(None)
    def get_websocket_testee_transport(self, details=None):
        """
        """
        self.log.debug("{name}.get_websocket_testee_transport", name=self.__class__.__name__)

    @wamp.register(None)
    def start_websocket_testee_transport(self, id, config, details=None):
        """
        """
        self.log.debug("{name}.start_websocket_testee_transport", name=self.__class__.__name__)

        # prohibit starting a transport twice
        #
        # FIXME
        # if id in self.transports:
        #     emsg = "Could not start transport: a transport with ID '{}' is already running (or starting)".format(id)
        #     self.log.error(emsg)
        #     raise ApplicationError('crossbar.error.already_running', emsg)

        # check configuration
        #
        try:
            self.personality.check_listening_transport_websocket(self.personality, config)
        except Exception as e:
            emsg = "Invalid WebSocket testee transport configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.invalid_configuration", emsg)
        else:
            self.log.debug("Starting {ttype}-transport on websocket-testee.", ttype=config['type'])

        # WebSocket testee pseudo transport
        #
        if config['type'] == 'websocket':

            transport_factory = WebSocketTesteeServerFactory(config, self._templates)

        # Unknown transport type
        #
        else:
            # should not arrive here, since we did check_transport() in the beginning
            raise Exception("logic error")

        # create transport endpoint / listening port from transport factory
        #
        d = create_listening_port_from_config(config['endpoint'], self.config.extra.cbdir, transport_factory,
                                              self._reactor, self.log)

        def ok(port):
            # FIXME
            # self.transports[id] = RouterTransport(id, config, transport_factory, port)
            self.log.debug("Router transport '{tid}'' started and listening", tid=id)
            return

        def fail(err):
            emsg = "Cannot listen on transport endpoint: {}".format(err.value)
            self.log.error(emsg)
            raise ApplicationError("crossbar.error.cannot_listen", emsg)

        d.addCallbacks(ok, fail)
        return d

    @wamp.register(None)
    def stop_websocket_testee_transport(self, id, details=None):
        """
        """
        self.log.debug("{name}.stop_websocket_testee_transport", name=self.__class__.__name__)
        raise NotImplementedError()
