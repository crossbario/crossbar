#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.util import sleep


class LogTester(ApplicationSession):
    """
    Sample WAMP component to test logging at run-time.
    """
    @inlineCallbacks
    def onJoin(self, details):
        LOG_PREFIX = '*** SAMPLE *** [{}]'.format(details.session)
        config = self.config.extra or {'iterations': 300, 'delay': .2}

        self.log.info('{prefix} joined realm "{realm}"', prefix=LOG_PREFIX, realm=details.realm)
        self.log.info('{prefix} config={config}', prefix=LOG_PREFIX, config=self.config.extra)

        self._tick = 1
        for i in range(config['iterations']):
            self.log.info('{prefix} TICK:', prefix=LOG_PREFIX)
            for fn, lvl in [(self.log.trace, 'TRACE'), (self.log.debug, 'DEBUG'), (self.log.info, 'INFO '),
                            (self.log.warn, 'WARN '), (self.log.error, 'ERROR')]:
                fn('{prefix} {lvl} - TICK {tick}', prefix=LOG_PREFIX, lvl=lvl, tick=self._tick)
            self._tick += 1
            yield sleep(config['delay'])

        self.log.info('{prefix} DONE!', prefix=LOG_PREFIX)

        self.leave()
