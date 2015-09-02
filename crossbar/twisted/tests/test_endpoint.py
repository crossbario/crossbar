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

from uuid import uuid4

from twisted.internet.endpoints import UNIXServerEndpoint
from twisted.internet.selectreactor import SelectReactor
from twisted.internet.protocol import Factory
from twisted.protocols.wire import Echo
from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.python.runtime import platform

from crossbar.twisted.endpoint import create_listening_endpoint_from_config


class ListeningEndpointTests(TestCase):

    def setUp(self):

        self.cbdir = self.mktemp()
        FilePath(self.cbdir).makedirs()

    def test_unix(self):
        """
        A config with type = "unix" will create an endpoint for a UNIX socket
        at the given path.
        """
        path = FilePath("/tmp").child(uuid4().hex).path
        self.addCleanup(os.remove, path)

        reactor = SelectReactor()
        config = {
            "type": "unix",
            "path": path
        }

        endpoint = create_listening_endpoint_from_config(config, self.cbdir,
                                                         reactor)
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
        path = FilePath("/tmp").child(uuid4().hex).path
        self.addCleanup(os.remove, path)

        # Something is already there
        FilePath(path).setContent(b"")

        reactor = SelectReactor()
        config = {
            "type": "unix",
            "path": path
        }

        endpoint = create_listening_endpoint_from_config(config, self.cbdir,
                                                         reactor)
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
        parent_fp = FilePath("/tmp").child(uuid4().hex)
        parent_fp.makedirs()
        fp = parent_fp.child(uuid4().hex)

        # Something is already there
        fp.setContent(b"")
        fp.chmod(0o544)
        parent_fp.chmod(0o544)

        reactor = SelectReactor()
        config = {
            "type": "unix",
            "path": fp.path
        }

        with self.assertRaises(OSError) as e:
            create_listening_endpoint_from_config(config, self.cbdir, reactor)
        self.assertEqual(e.exception.errno, 13)  # Permission Denied

        parent_fp.chmod(0o777)
        parent_fp.remove()

    if platform.isWindows():
        _ = "Windows does not have UNIX sockets"
        test_unix.skip = _
        test_unix_already_listening.skip = _
        test_unix_already_listening_cant_delete.skip = _
        del _
