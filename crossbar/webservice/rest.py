#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.wamp.types import ComponentConfig
from autobahn.twisted.wamp import ApplicationSession

from crossbar.bridge.rest import PublisherResource, CallerResource
from crossbar.bridge.rest import WebhookResource

from crossbar.webservice.base import RouterWebService


class RouterWebServiceRestPublisher(RouterWebService):
    """
    HTTP/REST-to-WAMP Publisher Web service (part of REST-bridge).
    """
    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['publisher'](personality, config)

        # create a vanilla session: the publisher will use this to inject events
        #
        publisher_session_config = ComponentConfig(realm=config['realm'], extra=None)
        publisher_session = ApplicationSession(publisher_session_config)

        # add the publisher session to the router
        #
        router = transport._worker._router_session_factory._routerFactory._routers[config['realm']]
        transport._worker._router_session_factory.add(publisher_session,
                                                      router,
                                                      authrole=config.get('role', 'anonymous'))

        # now create the publisher Twisted Web resource
        #
        resource = PublisherResource(config.get('options', {}), publisher_session)

        return RouterWebServiceRestPublisher(transport, path, config, resource)


class RouterWebServiceRestCaller(RouterWebService):
    """
    HTTP/REST-to-WAMP Caller Web service (part of REST-bridge).
    """
    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['caller'](personality, config)

        # create a vanilla session: the caller will use this to inject calls
        #
        caller_session_config = ComponentConfig(realm=config['realm'], extra=None)
        caller_session = ApplicationSession(caller_session_config)

        # add the calling session to the router
        #
        router = transport._worker._router_session_factory._routerFactory._routers[config['realm']]
        transport._worker._router_session_factory.add(caller_session, router, authrole=config.get('role', 'anonymous'))

        # now create the caller Twisted Web resource
        #
        resource = CallerResource(config.get('options', {}), caller_session)

        return RouterWebServiceRestCaller(transport, path, config, resource)


class RouterWebServiceWebhook(RouterWebService):
    """
    HTTP/POST Webhook service (part of REST-bridge).
    """
    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['webhook'](personality, config)

        # create a vanilla session: the webhook will use this to inject events
        #
        webhook_session_config = ComponentConfig(realm=config['realm'], extra=None)
        webhook_session = ApplicationSession(webhook_session_config)

        # add the webhook session to the router
        #
        router = transport._worker._router_session_factory._routerFactory._routers[config['realm']]
        transport._worker._router_session_factory.add(webhook_session,
                                                      router,
                                                      authrole=config.get('role', 'anonymous'))

        # now create the webhook Twisted Web resource
        #
        resource = WebhookResource(config.get('options', {}), webhook_session)

        return RouterWebServiceWebhook(transport, path, config, resource)
