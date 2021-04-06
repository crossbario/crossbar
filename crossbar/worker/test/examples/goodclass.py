#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.types import PublishOptions

from twisted.internet.defer import inlineCallbacks

_ = []


class AppSession(ApplicationSession):
    @inlineCallbacks
    def onJoin(self, details):
        yield self.subscribe(_.append, "com.test")
        yield self.publish("com.test", "woo", options=PublishOptions(exclude_me=False))
