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

from txaio import make_logger

import twisted
from twisted.internet.defer import inlineCallbacks, returnValue, maybeDeferred

from autobahn.wamp import ApplicationError

import crossbar
from crossbar._util import hltype
from crossbar.common.twisted.web import Site
from crossbar.common.twisted.endpoint import create_listening_port_from_config
from crossbar.bridge.mqtt.wamp import WampMQTTServerFactory
from crossbar.router.protocol import WampRawSocketServerFactory, WampWebSocketServerFactory
from crossbar.router.unisocket import UniSocketServerFactory
from crossbar.webservice.flashpolicy import FlashPolicyFactory

from crossbar.worker.testee import WebSocketTesteeServerFactory, StreamTesteeServerFactory

# monkey patch the Twisted Web server identification
twisted.web.server.version = "Crossbar/{}".format(crossbar.__version__)


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
        :type worker: crossbar.worker.router.RouterController

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
        self._transport_factory = None
        self._root_webservice = None

        # twisted.internet.interfaces.IListeningPort
        self._port = None

    @property
    def root(self):
        """

        :return: The root (on path "/")  Web service.
        """
        return self._root_webservice

    @property
    def worker(self):
        """

        :return: The worker (controller session) this transport was created from.
        """
        return self._worker

    @property
    def id(self):
        """

        :return: The transport ID.
        """
        return self._transport_id

    @property
    def type(self):
        """

        :return: The transport type.
        """
        return self._type

    @property
    def cbdir(self):
        """

        :return: Node directory.
        """
        return self._cbdir

    @property
    def templates(self):
        """

        :return: Templates directory.
        """
        return self._templates

    @property
    def config(self):
        """

        :return: The original configuration as supplied to this router transport.
        """
        return self._config

    @property
    def created(self):
        """

        :return: When this transport was created (the run-time, in-memory object instantiated).
        """
        return self._created_at

    @property
    def state(self):
        """

        :return: The state of this transport.
        """
        return self._state

    @property
    def port(self):
        """

        :return: The network listening transport of this router transport.
        """
        return self._port

    @inlineCallbacks
    def start(self, start_children=False, ignore=[]):
        """
        Start this transport (starts listening on the respective network listening port).

        :param start_children:
        :return:
        """
        if self._state != RouterTransport.STATE_CREATED:
            raise Exception('invalid state')

        # note that we are starting ..
        self._state = RouterTransport.STATE_STARTING

        # create transport factory
        self._transport_factory, self._root_webservice = yield self._create_factory(start_children, ignore)

        # create transport endpoint / listening port from transport factory
        #
        port = yield create_listening_port_from_config(
            self._config['endpoint'],
            self._cbdir,
            self._transport_factory,
            self._worker._reactor,
            self.log,
        )

        # when listening:
        self._port = port
        self._listening_since = datetime.utcnow()

        # note that we started.
        self._state = RouterTransport.STATE_STARTED

        returnValue(self)

    def _create_web_factory(self, create_paths=False, ignore=[]):
        raise NotImplemented()

    @inlineCallbacks
    def _create_factory(self, create_paths=False, ignore=[]):

        # Twisted (listening endpoint) transport factory
        transport_factory = None

        # Root Web service: only set (down below) when running a Web transport or
        # a Universal transport with Web support
        root_webservice = None

        # standalone WAMP-RawSocket transport
        #
        if self._config['type'] == 'rawsocket':
            transport_factory = WampRawSocketServerFactory(self._worker.router_session_factory, self._config)
            transport_factory.noisy = False

        # standalone WAMP-WebSocket transport
        #
        elif self._config['type'] == 'websocket':
            assert (self._templates)
            transport_factory = WampWebSocketServerFactory(self._worker.router_session_factory, self._cbdir, self._config,
                                                           self._templates)
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
            transport_factory, root_webservice = yield maybeDeferred(self._create_web_factory, create_paths, ignore)

        # Universal transport
        #
        elif self._config['type'] == 'universal':
            if 'web' in self._config:
                assert (self._templates)
                web_factory, root_webservice = yield maybeDeferred(self._create_web_factory, create_paths, ignore)
            else:
                web_factory, root_webservice = None, None

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
                assert (self._templates)
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

            transport_factory = UniSocketServerFactory(web_factory,
                                                       websocket_factory_map,
                                                       rawsocket_factory,
                                                       mqtt_factory)

        # this is to allow subclasses to reuse this method
        elif self._config['type'] in ignore:
            pass

        # unknown transport type
        else:
            # should not arrive here, since we did check_transport() in the beginning
            raise Exception("logic error")

        returnValue((transport_factory, root_webservice))

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


class RouterWebTransport(RouterTransport):
    """
    Web transport or Universal transport with Web sub-service.
    """

    log = make_logger()

    def __init__(self, worker, transport_id, config):
        RouterTransport.__init__(self, worker, transport_id, config)

    @inlineCallbacks
    def _create_web_factory(self, create_paths=False, ignore=[]):

        # web transport options
        options = self._config.get('options', {})

        # create root web service
        if '/' in self._config.get('paths', []):
            root_config = self._config['paths']['/']
        else:
            root_config = {'type': 'path', 'paths': {}}
        root_factory = self._worker.personality.WEB_SERVICE_FACTORIES[root_config['type']]
        if not root_factory:
            raise Exception('internal error: missing web service factory for type "{}"'.format(root_config['type']))

        root_webservice = yield maybeDeferred(root_factory.create, self, '/', root_config)

        # create the actual transport factory
        transport_factory = Site(
            root_webservice._resource,
            client_timeout=options.get('client_timeout', None),
            access_log=options.get('access_log', False),
            display_tracebacks=options.get('display_tracebacks', False),
            hsts=options.get('hsts', False),
            hsts_max_age=int(options.get('hsts_max_age', 31536000))
        )

        returnValue((transport_factory, root_webservice))


def create_router_transport(worker, transport_id, config):
    """
    Factory for creating router (listening) transports.

    :param worker:
    :param transport_id:
    :param config:
    :return:
    """
    worker.log.info('Creating router transport for "{transport_id}" {factory}',
                    transport_id=transport_id,
                    factory=hltype(create_router_transport))

    if config['type'] == 'web' or (config['type'] == 'universal' and config.get('web', {})):
        transport = RouterWebTransport(worker, transport_id, config)
    else:
        transport = RouterTransport(worker, transport_id, config)

    worker.log.info('Router transport created for "{transport_id}" {transport_class}',
                    transport_id=transport_id,
                    transport_class=hltype(transport.__class__))
    return transport
