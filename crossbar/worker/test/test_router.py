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

from twisted.trial.unittest import TestCase

from crossbar.worker import router
from crossbar._logging import make_logger

from autobahn.wamp.message import Register, Registered, Hello, Welcome
from autobahn.wamp.message import Publish, Published
from autobahn.wamp.role import RoleBrokerFeatures
from autobahn.wamp.types import ComponentConfig


class DottableDict(dict):
    def __getattr__(self, name):
        return self[name]


class FakeWAMPTransport(object):
    """
    A fake WAMP transport that responds to all messages with successes.
    """
    def __init__(self, session):
        self._messages = []
        self._session = session

    def send(self, message):
        """
        Send the message, respond with it's success message synchronously.
        Append it to C{self._messages} for later analysis.
        """
        self._messages.append(message)

        if isinstance(message, Hello):
            self._session.onMessage(
                Welcome(1, {u"broker": RoleBrokerFeatures()}))

        if isinstance(message, Register):
            self._session.onMessage(
                Registered(message.request, message.request))

        if isinstance(message, Publish):
            self._session.onMessage(
                Published(message.request, message.request))

    def _get(self, klass):
        return list(filter(lambda x: isinstance(x, klass), self._messages))


class RouterWorkerSessionTests(TestCase):

    def setUp(self):

        self.realm = "realm1"
        config_extras = DottableDict({"node": "testnode",
                                      "worker": "worker1",
                                      "cbdir": self.mktemp()})
        self.config = ComponentConfig(self.realm, extra=config_extras)

    def test_basic(self):
        """
        We can instantiate a RouterWorkerSession.
        """
        log_list = []

        r = router.RouterWorkerSession(config=self.config)
        r.log = make_logger(observer=log_list.append, log_level="debug")

        transport = FakeWAMPTransport(r)

        # Open the transport
        r.onOpen(transport)

        # Should have 35 registers, all for the management interface
        self.assertEqual(len(transport._get(Register)), 35)
