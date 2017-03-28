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


class RouterOptions(object):

    """
    Router options for creating routers.
    """

    URI_CHECK_LOOSE = "loose"
    URI_CHECK_STRICT = "strict"

    def __init__(self, uri_check=None, event_dispatching_chunk_size=None):
        """

        :param uri_check: Method which should be applied to check WAMP URIs.
        :type uri_check: str
        """
        self.uri_check = uri_check or RouterOptions.URI_CHECK_STRICT
        self.event_dispatching_chunk_size = event_dispatching_chunk_size or 100

    def __str__(self):
        return (
            "RouterOptions(uri_check = {0}, "
            "event_dispatching_chunk_size = {1})".format(
                self.uri_check,
                self.event_dispatching_chunk_size,
            )
        )
