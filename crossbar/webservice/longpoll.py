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
            u'type': 'longpoll',
            u'protocol': transport_details['protocol'],
            u'peer': transport_details['peer'],
            u'http_headers_received': transport_details['http_headers_received'],
            u'http_headers_sent': transport_details['http_headers_sent']
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
