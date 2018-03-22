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

from __future__ import absolute_import

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
            for fn, lvl in [(self.log.trace, 'TRACE'),
                            (self.log.debug, 'DEBUG'),
                            (self.log.info, 'INFO '),
                            (self.log.warn, 'WARN '),
                            (self.log.error, 'ERROR')]:
                fn('{prefix} {lvl} - TICK {tick}', prefix=LOG_PREFIX, lvl=lvl, tick=self._tick)
            self._tick += 1
            yield sleep(config['delay'])

        self.log.info('{prefix} DONE!', prefix=LOG_PREFIX)

        self.leave()
