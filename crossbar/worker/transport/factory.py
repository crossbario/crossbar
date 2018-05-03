#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#
#  Unless a separate license agreement exists between you and Crossbar.io GmbH (e.g.
#  you have purchased a commercial license), the license terms below apply.
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

from datetime import datetime

from autobahn.wamp import ApplicationError
import crossbar
import twisted

from crossbar.adapter.mqtt.wamp import WampMQTTServerFactory
from crossbar.router.protocol import WampRawSocketServerFactory, WampWebSocketServerFactory
from crossbar.router.unisocket import UniSocketServerFactory
from crossbar.twisted.endpoint import create_listening_port_from_config
from crossbar.twisted.flashpolicy import FlashPolicyFactory

from crossbar.twisted.resource import Resource404
from crossbar.twisted.site import createHSTSRequestFactory
from crossbar.worker.testee import WebSocketTesteeServerFactory, StreamTesteeServerFactory

from twisted.web.http import _GenericHTTPChannelProtocol, HTTPChannel
from twisted.web.server import Site

from txaio import make_logger

# monkey patch the Twisted Web server identification
twisted.web.server.version = "Crossbar/{}".format(crossbar.__version__)


def create_web_factory(personality, reactor, config, is_secure, templates, log, cbdir, _router_session_factory, node, create_paths=False):
    assert templates is not None

    options = config.get('options', {})

    # create Twisted Web root resource
    if '/' in config['paths']:
        root_config = config['paths']['/']
        root = personality.create_web_service(personality, reactor, root_config, templates, log, cbdir, _router_session_factory, node, nested=False)
    else:
        root = Resource404(templates, b'')

    # create Twisted Web resources on all non-root paths configured
    paths = config.get('paths', {})
    if create_paths and paths:
        personality.add_web_services(personality, reactor, root, paths, templates, log, cbdir, _router_session_factory, node)

    # create the actual transport factory
    transport_factory = Site(
        root,
        timeout=options.get('client_timeout', None),
    )
    transport_factory.noisy = False

    # we override this factory so that we can inject
    # _LessNoisyHTTPChannel to avoid info-level logging on timing
    # out web clients (which happens all the time).
    def channel_protocol_factory():
        return _GenericHTTPChannelProtocol(_LessNoisyHTTPChannel())
    transport_factory.protocol = channel_protocol_factory

    # Web access logging
    if not options.get('access_log', False):
        transport_factory.log = lambda _: None

    # Traceback rendering
    transport_factory.displayTracebacks = options.get('display_tracebacks', False)

    # HSTS
    if options.get('hsts', False):
        if is_secure:
            hsts_max_age = int(options.get('hsts_max_age', 31536000))
            transport_factory.requestFactory = createHSTSRequestFactory(transport_factory.requestFactory, hsts_max_age)
        else:
            log.warn("Warning: HSTS requested, but running on non-TLS - skipping HSTS")

    return transport_factory, root


class _LessNoisyHTTPChannel(HTTPChannel):
    """
    Internal helper.

    This is basically exactly what Twisted does, except without using
    "log.msg" so we can put it at debug log-level instead
    """
    log = make_logger()

    def timeoutConnection(self):
        self.log.debug(
            "Timing out client: {peer}",
            peer=self.transport.getPeer(),
        )
        if self.abortTimeout is not None:
            self._abortingCall = self.callLater(
                self.abortTimeout, self.forceAbortClient
            )
        self.loseConnection()


class RouterTransport(object):
    """
    A (listening) transport running on a router worker.
    """
    STATE_CREATED = 1
    STATE_STARTING = 2
    STATE_STARTED = 3
    STATE_FAILED = 4
    STATE_STOPPING = 5
    STATE_STOPPED = 6

    STATES = {
        STATE_CREATED: "created",
        STATE_STARTING: "starting",
        STATE_STARTED: "started",
        STATE_FAILED: "failed",
        STATE_STOPPING: "stopping",
        STATE_STOPPED: "stopped",
    }

    log = make_logger()

    def __init__(self, worker, transport_id, config):
        """

        :param worker: The (router) worker session the transport is created from.
        :type worker: crossbar.worker.router.RouterWorkerSession

        :param transport_id: The transport ID within the router.
        :type transport_id: str

        :param config: The transport's configuration.
        :type config: dict
        """
        self._worker = worker
        self._transport_id = transport_id

        try:
            self._worker.personality.check_router_transport(self._worker.personality, config)
        except Exception as e:
            emsg = "Invalid router transport configuration: {}".format(e)
            self.log.error(emsg)
            raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
        else:
            self.log.debug("Router transport parsed successfully (transport_id={transport_id}, transport_type={transport_type})",
                           transport_id=transport_id, transport_type=config['type'])

        self._config = config
        self._type = config['type']
        self._cbdir = self._worker.config.extra.cbdir
        self._templates = self._worker.templates()
        self._created_at = datetime.utcnow()
        self._listening_since = None
        self._state = RouterTransport.STATE_CREATED

        # twisted.internet.interfaces.IListeningPort
        self._port = None

    @property
    def id(self):
        """
        The transport ID.

        :return:
        """
        return self._transport_id

    @property
    def type(self):
        """
        The transport type.

        :return:
        """
        return self._type

    @property
    def config(self):
        """
        The original configuration as supplied to this router transport.

        :return:
        """
        return self._config

    @property
    def created(self):
        """
        When this transport was created (the run-time, in-memory object instantiated).

        :return:
        """
        return self._created_at

    @property
    def state(self):
        """
        The state of this transport.

        :return:
        """
        return self._state

    @property
    def port(self):
        """
        The network listening transport of this router transport.

        :return:
        """
        return self._port

    def start(self, start_children=False):
        """
        Start this transport (starts listening on the respective network listening port).

        :param start_children:
        :return:
        """
        if self._state != RouterTransport.STATE_CREATED:
            raise Exception('invalid state')

        self._state = RouterTransport.STATE_STARTING

        # only set (down below) when running a Web transport
        # twisted.web.resource.Resource
        root_resource = None

        # standalone WAMP-RawSocket transport
        #
        if self._config['type'] == 'rawsocket':
            transport_factory = WampRawSocketServerFactory(self._worker.router_session_factory, self._config)
            transport_factory.noisy = False

        # standalone WAMP-WebSocket transport
        #
        elif self._config['type'] == 'websocket':
            assert (self._templates)
            transport_factory = WampWebSocketServerFactory(self._worker.router_session_factory, self._cbdir, self._config, self._templates)
            transport_factory.noisy = False

        # Flash-policy file server pseudo transport
        #
        elif self._config['type'] == 'flashpolicy':
            transport_factory = FlashPolicyFactory(self._config.get('allowed_domain', None),
                                                   self._config.get('allowed_ports', None))

        # WebSocket testee pseudo transport
        #
        elif self._config['type'] == 'websocket.testee':
            assert (self._templates)
            transport_factory = WebSocketTesteeServerFactory(self._config, self._templates)

        # Stream testee pseudo transport
        #
        elif self._config['type'] == 'stream.testee':
            transport_factory = StreamTesteeServerFactory()

        # MQTT legacy adapter transport
        #
        elif self._config['type'] == 'mqtt':
            transport_factory = WampMQTTServerFactory(
                self._worker.router_session_factory, self._config, self._worker._reactor)
            transport_factory.noisy = False

        # Twisted Web based transport
        #
        elif self._config['type'] == 'web':
            assert (self._templates)
            transport_factory, root_resource = create_web_factory(
                self._worker.personality,
                self._worker._reactor,
                self._config,
                u'tls' in self._config[u'endpoint'],
                self._templates,
                self.log,
                self._cbdir,
                self._worker.router_session_factory,
                self._worker,
                create_paths=start_children
            )

        # Universal transport
        #
        elif self._config['type'] == 'universal':
            if 'web' in self._config:
                assert(self._templates)
                web_factory, root_resource = create_web_factory(
                    self._worker.personality,
                    self._worker._reactor,
                    self._config['web'],
                    u'tls' in self._config['endpoint'],
                    self._templates,
                    self.log,
                    self._cbdir,
                    self._worker.router_session_factory,
                    self._worker,
                    create_paths=start_children
                )
            else:
                web_factory = None

            if 'rawsocket' in self._config:
                rawsocket_factory = WampRawSocketServerFactory(self._worker.router_session_factory, self._config['rawsocket'])
                rawsocket_factory.noisy = False
            else:
                rawsocket_factory = None

            if 'mqtt' in self._config:
                mqtt_factory = WampMQTTServerFactory(
                    self._worker.router_session_factory, self._config['mqtt'], self._worker._reactor)
                mqtt_factory.noisy = False
            else:
                mqtt_factory = None

            if 'websocket' in self._config:
                assert(self._templates)
                websocket_factory_map = {}
                for websocket_url_first_component, websocket_config in self._config['websocket'].items():
                    websocket_transport_factory = WampWebSocketServerFactory(self._worker.router_session_factory, self._cbdir,
                                                                             websocket_config, self._templates)
                    websocket_transport_factory.noisy = False
                    websocket_factory_map[websocket_url_first_component] = websocket_transport_factory
                    self.log.debug('hooked up websocket factory on request URI {request_uri}',
                                   request_uri=websocket_url_first_component)
            else:
                websocket_factory_map = None

            transport_factory = UniSocketServerFactory(web_factory, websocket_factory_map, rawsocket_factory,
                                                       mqtt_factory)

        # Unknown transport type
        #
        else:
            # should not arrive here, since we did check_transport() in the beginning
            raise Exception("logic error")

        # create transport endpoint / listening port from transport factory
        #
        d = create_listening_port_from_config(
            self._config['endpoint'],
            self._cbdir,
            transport_factory,
            self._worker._reactor,
            self.log,
        )

        def _when_listening(port):
            self._port = port
            self._listening_since = datetime.utcnow()
            self._state = RouterTransport.STATE_STARTED
            return self

        d.addCallback(_when_listening)

        return d

    def stop(self):
        """
        Stops this transport (stops listening on the respective network port or interface).

        :return:
        """
        if self._state != RouterTransport.STATE_STARTED:
            raise Exception('invalid state')

        self._state = RouterTransport.STATE_STOPPING

        d = self._port.stopListening()

        def ok(_):
            self._state = RouterTransport.STATE_STOPPED
            self._port = None

        def fail(err):
            self._state = RouterTransport.STATE_FAILED
            self._port = None
            raise err

        d.addCallbacks(ok, fail)
        return d


class RouterWebService(object):
    """
    A Web service configured on a URL path on a Web transport.
    """

    log = make_logger()

    def __init__(self, path, config):
        self._path = path
        self._config = config

    @property
    def path(self):
        return self._path


class RouterWebTransport(RouterTransport):
    """
    Web transport or Universal transport with Web sub-service.
    """

    log = make_logger()

    def add_web_service(self, path, config):
        pass

    def remove_web_service(self, path):
        pass
#        self.personality.remove_web_services(self.personality, self._reactor, transport.root_resource, [path])

    def __contains__(self, path):
        return False


def create_router_transport(worker, transport_id, config):
    """
    Factory for creating router (listening) transports.

    :param worker:
    :param transport_id:
    :param config:
    :return:
    """
    if config['type'] == 'web' or (config['type'] == 'universal' and config.get('web', {})):
        return RouterWebTransport(worker, transport_id, config)
    else:
        return RouterTransport(worker, transport_id, config)
