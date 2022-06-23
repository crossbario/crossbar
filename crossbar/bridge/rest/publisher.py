#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.wamp.types import PublishOptions

from crossbar._util import dump_json
from crossbar.bridge.rest.common import _CommonResource

__all__ = ('PublisherResource', )


class PublisherResource(_CommonResource):
    """
    A HTTP/POST to WAMP-Publisher bridge.
    """
    def _process(self, request, event):

        if 'topic' not in event:
            return self._deny_request(request, 400, key="topic", log_category="AR455")

        topic = event.pop('topic')

        args = event['args'] if 'args' in event and event['args'] else []
        kwargs = event['kwargs'] if 'kwargs' in event and event['kwargs'] else {}
        options = event['options'] if 'options' in event and event['options'] else {}

        publish_options = PublishOptions(acknowledge=True,
                                         forward_for=options.get('forward_for', None),
                                         retain=options.get('retain', None),
                                         exclude_me=options.get('exclude_me', None),
                                         exclude_authid=options.get('exclude_authid', None),
                                         exclude_authrole=options.get('exclude_authrole', None),
                                         exclude=options.get('exclude', None),
                                         eligible_authid=options.get('eligible_authid', None),
                                         eligible_authrole=options.get('eligible_authrole', None),
                                         eligible=options.get('eligible', None))

        kwargs['options'] = publish_options

        # http://twistedmatrix.com/documents/current/web/howto/web-in-60/asynchronous-deferred.html

        d = self._session.publish(topic, *args, **kwargs)

        def on_publish_ok(pub):
            res = {'id': pub.id}
            body = dump_json(res, True).encode('utf8')
            self._complete_request(request, 200, body, log_category="AR200", reason="OK")

        def on_publish_error(err):
            self._fail_request(request, failure=err, log_category="AR456")

        return d.addCallbacks(on_publish_ok, on_publish_error)
