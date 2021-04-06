#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
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
        return ("RouterOptions(uri_check = {0}, "
                "event_dispatching_chunk_size = {1})".format(
                    self.uri_check,
                    self.event_dispatching_chunk_size,
                ))


class NotAttached(RuntimeError):
    """
    Internal error: session not attached to router.
    """
