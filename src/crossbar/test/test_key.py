#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import stat
from collections import OrderedDict
from unittest import mock

from nacl import encoding, signing
from twisted.trial import unittest
from xbr._secmod import SecurityModuleMemory

from crossbar.common.key import _maybe_generate_node_key, _parse_node_key, _write_node_key


def _mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def _write_legacy_private_key(path):
    """
    Write a node private key file as created by Crossbar.io <= 21.x: Ed25519 key only, no Ethereum key.
    """
    privkey = signing.SigningKey.generate()
    privkey_hex = privkey.encode(encoder=encoding.HexEncoder).decode("ascii")
    pubkey_hex = privkey.verify_key.encode(encoder=encoding.HexEncoder).decode("ascii")
    with open(path, "w") as f:
        f.write("Crossbar.io node private key - KEEP THIS SAFE!\n\n")
        f.write("creator: alice@example\n")
        f.write("created-at: 2023-01-09T16:55:58.391Z\n")
        f.write("machine-id: 419b381779c0c4a457f415dc5623ece0\n")
        f.write("node-authid: example\n")
        f.write("public-key-ed25519: {}\n".format(pubkey_hex))
        f.write("private-key-ed25519: {}\n".format(privkey_hex))
    os.chmod(path, 0o600)
    return privkey_hex, pubkey_hex


class NodeKeyFileModeTests(unittest.TestCase):
    """
    The node private key file is never readable by other users, not even briefly (#2323).
    """

    def setUp(self):
        self.cbdir = self.mktemp()
        os.makedirs(self.cbdir)
        self.privkey_path = os.path.join(self.cbdir, "key.priv")
        self.pubkey_path = os.path.join(self.cbdir, "key.pub")
        self._umask = os.umask(0o022)

    def tearDown(self):
        os.umask(self._umask)

    def test_new_key_files_created_with_final_mode(self):
        """
        With umask 0o022, a new key.priv is created with mode 0600 and key.pub with 0644, without relying
        on the later chmod repair.
        """
        with mock.patch("crossbar.common.key.os.chmod") as chmod:
            was_new, _ = _maybe_generate_node_key(self.cbdir)
        self.assertTrue(was_new)
        chmod.assert_not_called()
        self.assertEqual(_mode(self.privkey_path), 0o600)
        self.assertEqual(_mode(self.pubkey_path), 0o644)

    def test_write_refuses_existing_file(self):
        """
        Writing a key file never overwrites an existing file.
        """
        with open(self.privkey_path, "w") as f:
            f.write("existing\n")
        self.assertRaises(FileExistsError, _write_node_key, self.privkey_path, OrderedDict(), "msg\n\n")
        with open(self.privkey_path) as f:
            self.assertEqual(f.read(), "existing\n")

    def test_write_refuses_symlink(self):
        """
        Writing a key file never writes through a symlink planted at its path.
        """
        target = os.path.abspath(os.path.join(self.cbdir, "target"))
        with open(target, "w") as f:
            f.write("target\n")
        os.symlink(target, self.privkey_path)
        self.assertRaises(FileExistsError, _write_node_key, self.privkey_path, OrderedDict(), "msg\n\n")
        with open(target) as f:
            self.assertEqual(f.read(), "target\n")

    def test_existing_weak_mode_repaired(self):
        """
        The start-time permission repair still sets 0600 on an existing key.priv with a weaker mode.
        """
        _maybe_generate_node_key(self.cbdir)
        os.chmod(self.privkey_path, 0o644)
        was_new, _ = _maybe_generate_node_key(self.cbdir)
        self.assertFalse(was_new)
        self.assertEqual(_mode(self.privkey_path), 0o600)


class LegacyNodeKeyTests(unittest.TestCase):
    """
    A node private key file without an Ethereum key (Crossbar.io <= 21.x) is migrated on start (#2172).
    """

    def setUp(self):
        self.cbdir = self.mktemp()
        os.makedirs(self.cbdir)
        self.privkey_path = os.path.join(self.cbdir, "key.priv")
        self.pubkey_path = os.path.join(self.cbdir, "key.pub")
        self.privkey_hex, self.pubkey_hex = _write_legacy_private_key(self.privkey_path)

    def _assert_migrated(self):
        priv_tags = _parse_node_key(self.privkey_path, private=True)
        pub_tags = _parse_node_key(self.pubkey_path)

        # the node identity (Ed25519 key) is unchanged
        self.assertEqual(priv_tags["private-key-ed25519"], self.privkey_hex)
        self.assertEqual(priv_tags["public-key-ed25519"], self.pubkey_hex)
        self.assertEqual(pub_tags["public-key-ed25519"], self.pubkey_hex)

        # an Ethereum key was added, and key.pub carries its address
        self.assertIn("private-key-eth", priv_tags)
        self.assertEqual(pub_tags["public-adr-eth"], priv_tags["public-adr-eth"])
        self.assertEqual(_mode(self.privkey_path), 0o600)

        # the node's security module loads the migrated key file
        secmod = SecurityModuleMemory.from_keyfile(self.privkey_path)
        self.assertEqual(secmod[0].address(binary=False), priv_tags["public-adr-eth"])
        return priv_tags

    def test_legacy_key_migrated(self):
        was_new, key = _maybe_generate_node_key(self.cbdir)
        self.assertFalse(was_new)
        self.assertEqual(key.public_key(binary=False), self.pubkey_hex)
        self._assert_migrated()

    def test_legacy_key_with_legacy_public_key_migrated(self):
        """
        An existing key.pub without public-adr-eth is re-created as well.
        """
        with open(self.pubkey_path, "w") as f:
            f.write("Crossbar.io node public key\n\n")
            f.write("creator: alice@example\n")
            f.write("created-at: 2023-01-09T16:55:58.391Z\n")
            f.write("machine-id: 419b381779c0c4a457f415dc5623ece0\n")
            f.write("node-authid: example\n")
            f.write("public-key-ed25519: {}\n".format(self.pubkey_hex))
        _maybe_generate_node_key(self.cbdir)
        self._assert_migrated()

    def test_migration_runs_once(self):
        """
        A migrated key file is not changed again on the next start.
        """
        _maybe_generate_node_key(self.cbdir)
        priv_tags = self._assert_migrated()
        _maybe_generate_node_key(self.cbdir)
        self.assertEqual(_parse_node_key(self.privkey_path, private=True), priv_tags)
