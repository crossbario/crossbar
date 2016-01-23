#####################################################################################
#
#  Copyright (C) Tavendo GmbH
#
#  Unless a separate license agreement exists between you and Tavendo GmbH (e.g. you
#  have purchased a commercial license), the license terms below apply.
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

from __future__ import absolute_import, division

import json

from autobahn.wamp.types import PublishOptions

from crossbar.adapter.rest.common import _CommonResource

__all__ = ('PublisherResource',)


class PublisherResource(_CommonResource):
    """
    A HTTP/POST to WAMP-Publisher bridge.
    """

    def _process(self, request, event):

        if 'topic' not in event:
            return self._deny_request(request, 400,
                                      "invalid request event - missing 'topic' in HTTP/POST body",
                                      log_category="AR455")

        topic = event.pop('topic')

        args = event.pop('args', [])
        kwargs = event.pop('kwargs', {})
        options = event.pop('options', {})

        publish_options = PublishOptions(acknowledge=True,
                                         exclude=options.get('exclude', None),
                                         eligible=options.get('eligible', None))

        kwargs['options'] = publish_options

        # http://twistedmatrix.com/documents/current/web/howto/web-in-60/asynchronous-deferred.html

        d = self._session.publish(topic, *args, **kwargs)

        def on_publish_ok(pub):
            res = {'id': pub.id}
            body = json.dumps(res, separators=(',', ':'),
                              ensure_ascii=False).encode('utf8')
            request.setHeader(b'content-type',
                              b'application/json; charset=UTF-8')
            request.setHeader(b'cache-control',
                              b'no-store, no-cache, must-revalidate, max-age=0')
            self._complete_request(request, 202, body, log_category="AR200")

        def on_publish_error(err):
            return self._fail_request(request, 400, "PublisherResource failed with error {e}",
                                      e=err.value, log_category="AR456")

        return d.addCallbacks(on_publish_ok, on_publish_error)
