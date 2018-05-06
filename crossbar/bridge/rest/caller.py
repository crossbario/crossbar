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

from __future__ import absolute_import, division

from twisted.internet.defer import maybeDeferred

from autobahn.wamp.types import CallResult

from crossbar._util import dump_json
from crossbar.bridge.rest.common import _CommonResource

__all__ = ('CallerResource',)


class CallerResource(_CommonResource):
    """
    A HTTP/POST to WAMP-Caller bridge.
    """

    def _process(self, request, event):

        if 'procedure' not in event:
            return self._deny_request(
                request, 400,
                key='procedure',
                log_category="AR455")

        procedure = event.pop('procedure')

        args = event['args'] if 'args' in event and event['args'] else []
        kwargs = event['kwargs'] if 'kwargs' in event and event['kwargs'] else {}

        def _call(*args, **kwargs):
            return self._session.call(*args, **kwargs)

        d = maybeDeferred(_call, procedure, *args, **kwargs)

        def on_call_ok(value):
            # a WAMP procedure call result may have a single return value, but also
            # multiple, positional return values as well as keyword-based return values
            #
            if isinstance(value, CallResult):
                res = {}
                if value.results:
                    res['args'] = value.results
                if value.kwresults:
                    res['kwargs'] = value.kwresults
            else:
                res = {'args': [value]}

            body = dump_json(res, True).encode('utf8')

            return self._complete_request(
                request, 200, body,
                log_category="AR202")

        def on_call_error(err):
            # a WAMP procedure call returning with error should be forwarded
            # to the HTTP-requestor still successfully
            #
            return self._fail_request(request, failure=err,
                                      log_category="AR458")

        return d.addCallbacks(on_call_ok, on_call_error)
