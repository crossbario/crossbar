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

from random import randint

from collections import namedtuple

from twisted.internet.defer import maybeDeferred

publishedMessage = namedtuple("pub", ["id"])


class MockPusherSession(object):
    """
    A mock WAMP session.
    """
    def __init__(self, testCase):
        self._published_messages = []

        def publish(topic, *args, **kwargs):
            messageID = randint(0, 100000)

            self._published_messages.append({
                "id": messageID,
                "topic": topic,
                "args": args,
                "kwargs": kwargs
            })

            return publishedMessage(id=messageID)

        def _publish(topic, *args, **kwargs):
            return maybeDeferred(publish, topic, *args, **kwargs)

        setattr(self, "publish", _publish)
