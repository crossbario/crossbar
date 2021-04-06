#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import json

from autobahn.wamp.types import PublishOptions
from autobahn.wamp.exception import ApplicationError

from crossbar._compat import native_string
from crossbar.bridge.rest.common import _CommonResource

__all__ = ('WebhookResource', )


class WebhookResource(_CommonResource):
    """
    A HTTP WebHook to WAMP-Publisher bridge.
    """
    decode_as_json = False

    def _process(self, request, event):

        # The topic we're going to send to
        topic = self._options["topic"]

        message = {}
        message["headers"] = {
            native_string(x): [native_string(z) for z in y]
            for x, y in request.requestHeaders.getAllRawHeaders()
        }
        message["body"] = event

        publish_options = PublishOptions(acknowledge=True)

        def _succ(result):
            response_text = self._options.get("success_response", "OK").encode('utf8')
            return self._complete_request(
                request,
                202,
                response_text,
                reason="Successfully sent webhook from {ip} to {topic}",
                topic=topic,
                ip=request.getClientIP(),
                log_category="AR201",
            )

        def _err(result):
            response_text = self._options.get("error_response", "NOT OK").encode('utf8')
            error_message = str(result.value)
            authorization_problem = False
            if isinstance(result.value, ApplicationError):
                error_message = '{}: {}'.format(
                    result.value.error,
                    result.value.args[0],
                )
                if result.value.error == "wamp.error.not_authorized":
                    authorization_problem = True
            self.log.error(
                "Unable to send webhook from {ip} to '{topic}' topic: {err}",
                ip=request.getClientIP(),
                body=response_text,
                log_failure=result,
                log_category="AR457",
                topic=topic,
                err=error_message,
            )
            if authorization_problem:
                self.log.error(
                    "Session realm={realm} role={role}",
                    realm=self._session._realm,
                    role=self._session._authrole,
                )
            request.setResponseCode(500)
            request.write(response_text)
            request.finish()

        d = self._session.publish(topic, json.loads(json.dumps(message)), options=publish_options)
        d.addCallback(_succ)
        d.addErrback(_err)
        return d
