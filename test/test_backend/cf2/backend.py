# Copyright (c) Crossbar.io Technologies GmbH, licensed under The MIT License (MIT)

import os

from twisted.internet.defer import inlineCallbacks

from autobahn.wamp.types import RegisterOptions
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner


class MyComponent(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):
        self._ident = 'MyComponent[pid={}, session={}]'.format(os.getpid(), details.session)

        yield self.register(self.add2,
                            u'com.example.add2',
                            options=RegisterOptions(invoke=u'roundrobin'))

        self.log.info('{ident}.add2 registered', ident=self._ident)

    def add2(self, a, b):
        self.log.info('{ident}.add2(a={a} b={b}) called', ident=self._ident, a=a, b=b)
        return {u'result': a + b, u'ident': self._ident}
