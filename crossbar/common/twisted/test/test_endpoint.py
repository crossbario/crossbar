#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import shutil

from uuid import uuid4

from twisted.internet.endpoints import UNIXServerEndpoint, TCP4ServerEndpoint
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.selectreactor import SelectReactor
from twisted.internet.protocol import Factory
from twisted.protocols.wire import Echo
from twisted.python.runtime import platform

from crossbar.test import TestCase
from crossbar.common.twisted.endpoint import create_listening_endpoint_from_config
from crossbar.common.twisted.endpoint import create_connecting_endpoint_from_config

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
        config = {"type": "unix", "path": path}

        endpoint = create_listening_endpoint_from_config(config, self.cbdir, reactor, self.log)
        self.assertTrue(isinstance(endpoint, UNIXServerEndpoint))

        factory = Factory.forProtocol(Echo)
        endpoint.listen(factory)

        self.assertIn(factory, [getattr(x, "factory", None) for x in reactor.getReaders()])

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
        config = {"type": "unix", "path": path}

        endpoint = create_listening_endpoint_from_config(config, self.cbdir, reactor, self.log)
        self.assertTrue(isinstance(endpoint, UNIXServerEndpoint))

        factory = Factory.forProtocol(Echo)
        endpoint.listen(factory)

        self.assertIn(factory, [getattr(x, "factory", None) for x in reactor.getReaders()])

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
        config = {"type": "unix", "path": fp}

        with self.assertRaises(OSError) as e:
            create_listening_endpoint_from_config(config, self.cbdir, reactor, self.log)
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

    def test_twisted_client(self):
        reactor = SelectReactor()
        config = {
            "type": "twisted",
            "client_string": "tcp:host=127.0.0.1:port=9876",
        }

        endpoint = create_connecting_endpoint_from_config(config, self.cbdir, reactor, self.log)
        self.assertTrue(isinstance(endpoint, TCP4ClientEndpoint))

    def test_twisted_server(self):
        reactor = SelectReactor()
        config = {
            "type": "twisted",
            "server_string": "tcp:9876:interface=127.0.0.1",
        }

        endpoint = create_listening_endpoint_from_config(config, self.cbdir, reactor, self.log)
        self.assertTrue(isinstance(endpoint, TCP4ServerEndpoint))
