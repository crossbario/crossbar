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

from __future__ import absolute_import, division, print_function

import os
import shutil

from uuid import uuid4

from twisted.internet.endpoints import UNIXServerEndpoint
from twisted.internet.selectreactor import SelectReactor
from twisted.internet.protocol import Factory
from twisted.protocols.wire import Echo
from twisted.python.runtime import platform

from crossbar.test import TestCase
from crossbar.twisted.endpoint import create_listening_endpoint_from_config

from txaio import make_logger


class ListeningEndpointTests(TestCase):

    log = make_logger()

    def setUp(self):
        self.cbdir = self.mktemp()
        os.makedirs(self.cbdir)
        return super(ListeningEndpointTests, self).setUp()

    def test_unix(self):
        """
        A config with type = "unix" will create an endpoint for a UNIX socket
        at the given path.
        """
        path = os.path.join("/", "tmp", uuid4().hex)
        self.addCleanup(os.remove, path)

        reactor = SelectReactor()
        config = {
            "type": "unix",
            "path": path
        }

        endpoint = create_listening_endpoint_from_config(config, self.cbdir, reactor, self.log)
        self.assertTrue(isinstance(endpoint, UNIXServerEndpoint))

        factory = Factory.forProtocol(Echo)
        endpoint.listen(factory)

        self.assertIn(
            factory,
            [getattr(x, "factory", None) for x in reactor.getReaders()])

    def test_unix_already_listening(self):
        """
        A config with type = "unix" will create an endpoint for a UNIX socket
        at the given path, and delete it if required.
        """
        path = os.path.join("/", "tmp", uuid4().hex)
        self.addCleanup(os.remove, path)

        # Something is already there
        open(path, "w").close()

        reactor = SelectReactor()
        config = {
            "type": "unix",
            "path": path
        }

        endpoint = create_listening_endpoint_from_config(config, self.cbdir,
                                                         reactor, self.log)
        self.assertTrue(isinstance(endpoint, UNIXServerEndpoint))

        factory = Factory.forProtocol(Echo)
        endpoint.listen(factory)

        self.assertIn(
            factory,
            [getattr(x, "factory", None) for x in reactor.getReaders()])

    def test_unix_already_listening_cant_delete(self):
        """
        A config with type = "unix" will create an endpoint for a UNIX socket
        at the given path, and delete it if required. If it can't delete it, it
        will raise an exception.
        """
        parent_fp = os.path.join("/", "tmp", uuid4().hex)
        os.makedirs(parent_fp)
        fp = os.path.join(parent_fp, uuid4().hex)

        # Something is already there
        open(fp, "w").close()
        os.chmod(fp, 0o544)
        os.chmod(parent_fp, 0o544)

        reactor = SelectReactor()
        config = {
            "type": "unix",
            "path": fp
        }

        with self.assertRaises(OSError) as e:
            create_listening_endpoint_from_config(config, self.cbdir,
                                                  reactor, self.log)
        self.assertEqual(e.exception.errno, 13)  # Permission Denied

        os.chmod(parent_fp, 0o700)
        shutil.rmtree(parent_fp)

    if platform.isWindows():
        _ = "Windows does not have UNIX sockets"
        test_unix.skip = _
        test_unix_already_listening.skip = _
        test_unix_already_listening_cant_delete.skip = _
        del _
    elif os.getuid() == 0:
        _ = "Cannot run as root"
        test_unix_already_listening_cant_delete.skip = _
        del _
