##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

from autobahn import wamp

__all__ = ('MarketPlace', )


class MarketPlace(object):
    """
    XBR Market Maker.
    """
    @wamp.register(None)
    def publish(self, publisher_id, api_id, service_id, price=None, details=None):
        """
        Publish a data service implementing a data service API to the market place.

        :param api_id:
        :param service_id:
        :param price:
        :param details:
        :return:
        """
        raise NotImplementedError()
