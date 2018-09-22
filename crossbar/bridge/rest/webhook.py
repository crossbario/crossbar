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

import json

from autobahn.wamp.types import PublishOptions
from autobahn.wamp.exception import ApplicationError

from crossbar._compat import native_string
from crossbar.bridge.rest.common import _CommonResource

__all__ = ('WebhookResource',)


class WebhookResource(_CommonResource):
    """
    A HTTP WebHook to WAMP-Publisher bridge.
    """
    decode_as_json = False

    def _process(self, request, event):

        # The topic we're going to send to
        topic = self._options["topic"]

        message = {}
        message[u"headers"] = {
            native_string(x): [native_string(z) for z in y]
            for x, y in request.requestHeaders.getAllRawHeaders()}
        message[u"body"] = event

        publish_options = PublishOptions(acknowledge=True)

        def _succ(result):
            response_text = self._options.get("success_response", u"OK").encode('utf8')
            return self._complete_request(
                request, 202, response_text,
                reason="Successfully sent webhook from {ip} to {topic}",
                topic=topic,
                ip=request.getClientIP(),
                log_category="AR201",
            )

        def _err(result):
            response_text = self._options.get("error_response", u"NOT OK").encode('utf8')
            error_message = str(result.value)
            authorization_problem = False
            if isinstance(result.value, ApplicationError):
                error_message = '{}: {}'.format(
                    result.value.error,
                    result.value.args[0],
                )
                if result.value.error == u"wamp.error.not_authorized":
                    authorization_problem = True
            self.log.error(
                u"Unable to send webhook from {ip} to '{topic}' topic: {err}",
                ip=request.getClientIP(),
                body=response_text,
                log_failure=result,
                log_category="AR457",
                topic=topic,
                err=error_message,
            )
            if authorization_problem:
                self.log.error(
                    u"Session realm={realm} role={role}",
                    realm=self._session._realm,
                    role=self._session._authrole,
                )
            request.setResponseCode(500)
            request.write(response_text)
            request.finish()

        d = self._session.publish(topic,
                                  json.loads(json.dumps(message)),
                                  options=publish_options)
        d.addCallback(_succ)
        d.addErrback(_err)
        return d
