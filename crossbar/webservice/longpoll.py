#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os

from txaio import make_logger

import crossbar
from crossbar.router import longpoll
from crossbar.webservice.base import RouterWebService


class WampLongPollResourceSession(longpoll.WampLongPollResourceSession):
    """

    """
    def __init__(self, parent, transport_details):
        longpoll.WampLongPollResourceSession.__init__(self, parent, transport_details)
        self._transport_info = {
            'type': 'longpoll',
            'protocol': transport_details['protocol'],
            'peer': transport_details['peer'],
            'http_headers_received': transport_details['http_headers_received'],
            'http_headers_sent': transport_details['http_headers_sent']
        }
        self._cbtid = None


class WampLongPollResource(longpoll.WampLongPollResource):
    """

    """

    protocol = WampLongPollResourceSession
    log = make_logger()

    def getNotice(self, peer, redirectUrl=None, redirectAfter=0):
        try:
            page = self._templates.get_template('cb_lp_notice.html')
            content = page.render(redirectUrl=redirectUrl,
                                  redirectAfter=redirectAfter,
                                  cbVersion=crossbar.__version__,
                                  peer=peer,
                                  workerPid=os.getpid())
            content = content.encode('utf8')
            return content
        except Exception:
            self.log.failure("Error rendering LongPoll notice page template: {log_failure.value}")


class RouterWebServiceLongPoll(RouterWebService):
    """
    HTTP-Long-Polling based WAMP transport wrapped as a Web service.
    """
    @staticmethod
    def create(transport, path, config):
        personality = transport.worker.personality
        personality.WEB_SERVICE_CHECKERS['longpoll'](personality, config)

        options = config.get('options', {})

        resource = WampLongPollResource(transport._worker._router_session_factory,
                                        timeout=options.get('request_timeout', 10),
                                        killAfter=options.get('session_timeout', 30),
                                        queueLimitBytes=options.get('queue_limit_bytes', 128 * 1024),
                                        queueLimitMessages=options.get('queue_limit_messages', 100),
                                        debug_transport_id=options.get('debug_transport_id', None))
        resource._templates = transport.templates

        return RouterWebServiceLongPoll(transport, path, config, resource)
