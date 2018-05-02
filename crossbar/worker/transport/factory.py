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


def create_transport_from_config(personality, reactor, name, config, cbdir, log, node,
                                 _router_session_factory=None,
                                 _web_templates=None, create_paths=False):
    """
    :return: a Deferred that fires with a new RouterTransport instance
        (or error) representing the given transport using config for
        settings. Raises ApplicationError if the configuration is wrong.
    """

    # check configuration
    #
    try:
        personality.check_router_transport(personality, config)
    except Exception as e:
        emsg = "Invalid router transport configuration: {}".format(e)
        log.error(emsg)
        raise ApplicationError(u"crossbar.error.invalid_configuration", emsg)
    else:
        log.debug("Starting {type}-transport on router.", ttype=config['type'])

    # only set (down below) when running a Web transport
    root_resource = None

    # standalone WAMP-RawSocket transport
    #
    if config['type'] == 'rawsocket':

        transport_factory = WampRawSocketServerFactory(_router_session_factory, config)
        transport_factory.noisy = False

    # standalone WAMP-WebSocket transport
    #
    elif config['type'] == 'websocket':

        if _web_templates is None:
            raise ApplicationError(
                "Transport with type='websocket.testee' requires templates"
            )
        transport_factory = WampWebSocketServerFactory(_router_session_factory, cbdir, config, _web_templates)
        transport_factory.noisy = False

    # Flash-policy file server pseudo transport
    #
    elif config['type'] == 'flashpolicy':

        transport_factory = FlashPolicyFactory(config.get('allowed_domain', None), config.get('allowed_ports', None))

    # WebSocket testee pseudo transport
    #
    elif config['type'] == 'websocket.testee':

        if _web_templates is None:
            raise ApplicationError(
                "Transport with type='websocket.testee' requires templates"
            )
        transport_factory = WebSocketTesteeServerFactory(config, _web_templates)

    # Stream testee pseudo transport
    #
    elif config['type'] == 'stream.testee':

        transport_factory = StreamTesteeServerFactory()

    # MQTT legacy adapter transport
    #
    elif config['type'] == 'mqtt':

        transport_factory = WampMQTTServerFactory(
            _router_session_factory, config, reactor)
        transport_factory.noisy = False

    # Twisted Web based transport
    #
    elif config['type'] == 'web':

        if _web_templates is None:
            raise ApplicationError(
                u"Transport with type='web' requires templates"
            )
        transport_factory, root_resource = create_web_factory(
            personality,
            reactor,
            config,
            u'tls' in config[u'endpoint'],
            _web_templates,
            log,
            cbdir,
            _router_session_factory,
            node,
            create_paths=create_paths
        )

    # Universal transport
    #
    elif config['type'] == 'universal':
        if 'web' in config:
            if _web_templates is None:
                raise ApplicationError(
                    u"Universal transport with type='web' requires templates"
                )
            web_factory, root_resource = create_web_factory(
                personality,
                reactor,
                config['web'],
                u'tls' in config['endpoint'],
                _web_templates,
                log,
                cbdir,
                _router_session_factory,
                node,
                create_paths=create_paths
            )
        else:
            web_factory = None

        if 'rawsocket' in config:
            rawsocket_factory = WampRawSocketServerFactory(_router_session_factory, config['rawsocket'])
            rawsocket_factory.noisy = False
        else:
            rawsocket_factory = None

        if 'mqtt' in config:
            mqtt_factory = WampMQTTServerFactory(
                _router_session_factory, config['mqtt'], reactor)
            mqtt_factory.noisy = False
        else:
            mqtt_factory = None

        if 'websocket' in config:
            if _web_templates is None:
                raise ApplicationError(
                    "Transport with type='websocket.testee' requires templates"
                )
            websocket_factory_map = {}
            for websocket_url_first_component, websocket_config in config['websocket'].items():
                websocket_transport_factory = WampWebSocketServerFactory(_router_session_factory, cbdir, websocket_config, _web_templates)
                websocket_transport_factory.noisy = False
                websocket_factory_map[websocket_url_first_component] = websocket_transport_factory
                log.debug('hooked up websocket factory on request URI {request_uri}', request_uri=websocket_url_first_component)
        else:
            websocket_factory_map = None

        transport_factory = UniSocketServerFactory(web_factory, websocket_factory_map, rawsocket_factory, mqtt_factory)

    # Unknown transport type
    #
    else:
        # should not arrive here, since we did check_transport() in the beginning
        raise Exception("logic error")

    # create transport endpoint / listening port from transport factory
    #
    d = create_listening_port_from_config(
        config['endpoint'],
        cbdir,
        transport_factory,
        reactor,
        log,
    )

    def is_listening(port):
        return RouterTransport(id, config, transport_factory, root_resource, port)
    d.addCallback(is_listening)
    return d


class RouterTransport(object):

    """
    A (listening) transport running on a router worker.
    """

    def __init__(self, id, config, factory, root_resource, port):
        """

        :param id: The transport ID within the router.
        :type id: str

        :param config: The transport's configuration.
        :type config: dict

        :param factory: The transport factory in use.
        :type factory: obj

        :param root_resource: Twisted Web root resource (used with Site factory), when
            using a Web transport.
        :type root_resource: obj

        :param port: The transport's listening port (https://twistedmatrix.com/documents/current/api/twisted.internet.interfaces.IListeningPort.html)
        :type port: obj
        """
        self.id = id
        self.config = config
        self.factory = factory
        self.root_resource = root_resource
        self.port = port
        self.created = datetime.utcnow()
