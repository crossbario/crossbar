#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from typing import Union

from twisted.internet.defer import inlineCallbacks

from autobahn.wamp.types import ComponentConfig
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from crossbar.bridge.rest import PublisherResource, CallerResource
from crossbar.bridge.rest import WebhookResource

from crossbar.webservice.base import RouterWebService

from crossbar.worker.proxy import ProxyController
from crossbar.worker.router import RouterController


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
    @inlineCallbacks
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['caller'](personality, config)

        # create a vanilla session: the caller will use this to inject calls
        _realm = config['realm']
        _authrole = config.get('role', 'anonymous')
        _worker: Union[RouterController, ProxyController] = transport._worker

        # add the calling session to the router
        if isinstance(_worker, RouterController):
            caller_session = ApplicationSession(ComponentConfig(realm=_realm, extra=None))
            router = _worker._router_session_factory._routerFactory._routers[_realm]
            _worker._router_session_factory.add(caller_session, router, authrole=_authrole)
        elif isinstance(_worker, ProxyController):
            if not _worker.has_realm(_realm):
                raise ApplicationError('crossbar.error.no_such_object',
                                       'no realm "{}" in configured routes of proxy worker'.format(_realm))
            if not _worker.has_role(_realm, _authrole):
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'no role "{}" on realm "{}" in configured routes of proxy worker'.format(_authrole, _realm))
            caller_session = yield _worker.get_service_session(_realm, _authrole)
            if not caller_session or not caller_session.is_attached():
                raise ApplicationError(
                    'crossbar.error.no_such_object',
                    'could not attach service session for HTTP bridge (role "{}" on realm "{}")'.format(
                        _authrole, _realm))
        else:
            assert False, 'logic error: unexpected worker type {} in RouterWebServiceRestCaller.create'.format(
                type(_worker))

        # now create the caller Twisted Web resource
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
