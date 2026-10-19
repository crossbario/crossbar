#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import subprocess
import sys

from twisted.trial.unittest import TestCase

# Runs in a child process in which "bitstring" cannot be imported, so the MQTT
# bridge must parse and build packets without it (#2321).
_SCRIPT = """
import sys
sys.modules["bitstring"] = None

from crossbar.bridge.mqtt._utils import iterbytes
from crossbar.bridge.mqtt.protocol import Connect, MQTTParser, Publish

connect = b"\\x10\\x13\\x00\\x04MQTT\\x04\\x02\\x00x\\x00\\x07test123"
publish = Publish(
    duplicate=False, qos_level=1, retain=False, topic_name="a/b", packet_identifier=7, payload=b"hello"
)

events = []
p = MQTTParser()
for x in iterbytes(connect + publish.serialise()):
    events.extend(p.data_received(x))

assert len(events) == 2, events
assert isinstance(events[0], Connect), events
assert events[0].client_id == "test123", events
assert events[1] == publish, events
print("OK")
"""


class NoBitstringTests(TestCase):
    """
    The MQTT bridge does not depend on bitstring (#2321).
    """

    def test_parse_and_build_without_bitstring(self):
        """
        A CONNECT and a QoS 1 PUBLISH, fed byte by byte, are parsed with bitstring unavailable.
        """
        result = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "OK")
