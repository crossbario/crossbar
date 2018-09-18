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
        transport._worker._router_session_factory.add(publisher_session,
                                                      authrole=config.get('role', 'anonymous'))

        # now create the publisher Twisted Web resource
        #
        resource = PublisherResource(config.get('options', {}), publisher_session,
                                     auth_config=config.get('auth', {}))

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
        transport._worker._router_session_factory.add(caller_session,
                                                      authrole=config.get('role', 'anonymous'))

        # now create the caller Twisted Web resource
        #
        resource = CallerResource(
            config.get('options', {}),
            caller_session,
            auth_config=config.get('auth', {})
        )

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
        transport._worker._router_session_factory.add(webhook_session,
                                                      authrole=config.get('role', 'anonymous'))

        # now create the webhook Twisted Web resource
        #
        resource = WebhookResource(config.get('options', {}), webhook_session)

        return RouterWebServiceWebhook(transport, path, config, resource)
