#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from typing import Dict, Any, Union

from twisted.internet.defer import inlineCallbacks

from autobahn.wamp.types import ComponentConfig
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError

from crossbar.bridge.rest import PublisherResource, CallerResource
from crossbar.bridge.rest import WebhookResource

from crossbar.webservice.base import RouterWebService

from crossbar.worker.proxy import ProxyController
from crossbar.worker.router import RouterController

__all__ = ('RouterWebServiceRestPublisher', 'RouterWebServiceRestCaller', 'RouterWebServiceWebhook')


@inlineCallbacks
def _create_resource(resource_klass: Union[PublisherResource, CallerResource, WebhookResource], worker,
                     config: Dict[str, Any]):
    """
    Create a new Twisted Web resource wrapping a WAMP action.

    :param resource_klass: WAMP action wrapper class.
    :param transport: Web transport
    :param config:
    :return: Twisted Web resource
    """
    # the WAMP realm and authid to use for the WAMP session backing this resource
    realm = config['realm']
    authrole = config.get('role', 'anonymous')

    # create a service session on the router/proxy controller: this will be used
    # to forward HTTP requests to WAMP
    if isinstance(worker, RouterController):
        session = ApplicationSession(ComponentConfig(realm=realm, extra=None))
        router = worker._router_session_factory._routerFactory._routers[realm]
        worker._router_session_factory.add(session, router, authrole=authrole)
    elif isinstance(worker, ProxyController):
        if not worker.has_realm(realm):
            raise ApplicationError('crossbar.error.no_such_object',
                                   'no realm "{}" in configured routes of proxy worker'.format(realm))
        if not worker.has_role(realm, authrole):
            raise ApplicationError(
                'crossbar.error.no_such_object',
                'no role "{}" on realm "{}" in configured routes of proxy worker'.format(authrole, realm))
        session = yield worker.get_service_session(realm, authrole)
        if not session or not session.is_attached():
            raise ApplicationError(
                'crossbar.error.cannot_start',
                'could not attach service session for HTTP bridge (role "{}" on realm "{}")'.format(authrole, realm))

        # session.authextra:
        # {'x_cb_node': 'intel-nuci7-61704', 'x_cb_worker': 'worker001', 'x_cb_peer': 'unix:None', 'x_cb_pid': 61714}

        assert session.realm == realm, 'service session: requested realm "{}", but got "{}"'.format(
            realm, session.realm)
        assert session.authrole == authrole, 'service session: requested authrole "{}", but got "{}"'.format(
            authrole, session.authrole)
    else:
        assert False, 'logic error: unexpected worker type {} in RouterWebServiceRestCaller.create'.format(
            type(worker))

    # now create the caller Twisted Web resource
    resource = resource_klass(config.get('options', {}), session)

    return resource


class RouterWebServiceRestPublisher(RouterWebService):
    """
    HTTP/REST-to-WAMP Publisher Web service (part of REST-bridge).
    """
    @staticmethod
    @inlineCallbacks
    def create(transport, path: str, config: Dict[str, Any]):
        """
        Create a new HTTP/REST-to-WAMP Publisher Web service (part of REST-bridge).

        :param transport: Web transport on which to add the web service.
        :param path: HTTP path on which to add the web service.
        :param config: Web service configuration.
        :return: Web service instance.
        """
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['publisher'](personality, config)

        # the realm container on which to add the resource
        worker: Union[RouterController, ProxyController] = transport._worker

        resource = yield _create_resource(PublisherResource, worker, config)
        return RouterWebServiceRestPublisher(transport, path, config, resource)


class RouterWebServiceRestCaller(RouterWebService):
    """
    HTTP/REST-to-WAMP Caller Web service (part of REST-bridge).
    """
    @staticmethod
    @inlineCallbacks
    def create(transport, path: str, config: Dict[str, Any]):
        """
        Create a new HTTP/REST-to-WAMP Caller Web service (part of REST-bridge).

        :param transport: Web transport on which to add the web service.
        :param path: HTTP path on which to add the web service.
        :param config: Web service configuration.
        :return: Web service instance.
        """
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['caller'](personality, config)

        # the realm container on which to add the resource
        worker: Union[RouterController, ProxyController] = transport._worker

        resource = yield _create_resource(CallerResource, worker, config)
        return RouterWebServiceRestCaller(transport, path, config, resource)


class RouterWebServiceWebhook(RouterWebService):
    """
    HTTP/POST Webhook service (part of REST-bridge).
    """
    @staticmethod
    def create(transport, path: str, config: Dict[str, Any]):
        """
        Create a new HTTP/POST Webhook service (part of REST-bridge).

        :param transport: Web transport on which to add the web service.
        :param path: HTTP path on which to add the web service.
        :param config: Web service configuration.
        :return: Web service instance.
        """
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['webhook'](personality, config)

        # the realm container on which to add the resource
        worker: Union[RouterController, ProxyController] = transport._worker

        resource = yield _create_resource(WebhookResource, worker, config)
        return RouterWebServiceWebhook(transport, path, config, resource)
