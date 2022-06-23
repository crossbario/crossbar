#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import binascii
import getpass
import os
import socket
import subprocess
from collections import OrderedDict

import pkg_resources
import pyqrcode

from nacl import signing
from nacl import encoding

from eth_keys import KeyAPI
from eth_keys.backends import NativeECCBackend

import txaio
from autobahn.util import utcnow
from autobahn.wamp import cryptosign

from twisted.python.runtime import platform

import crossbar
from crossbar._util import hlid

log = txaio.make_logger()


def _machine_id():
    """
    for informational purposes, try to get a machine unique id thing
    """
    if platform.isLinux():
        try:
            # why this? see: http://0pointer.de/blog/projects/ids.html
            with open('/var/lib/dbus/machine-id', 'r') as f:
                return f.read().strip()
        except:
            # Non-dbus using Linux, get a hostname
            return socket.gethostname()

    elif platform.isMacOSX():
        # Get the serial number of the platform
        import plistlib
        plist_data = subprocess.check_output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice", "-a"])
        return plistlib.loads(plist_data)[0]["IOPlatformSerialNumber"]
    else:
        # Something else, just get a hostname
        return socket.gethostname()


def _creator():
    """
    for informational purposes, try to identify the creator (user@hostname)
    """
    try:
        return '{}@{}'.format(getpass.getuser(), socket.gethostname())
    except:
        return None


def _read_release_key():
    release_pubkey_file = 'crossbar-{}.pub'.format('-'.join(crossbar.__version__.split('.')[0:2]))
    release_pubkey_path = os.path.join(pkg_resources.resource_filename('crossbar', 'common/keys'), release_pubkey_file)

    release_pubkey_hex = binascii.b2a_hex(cryptosign._read_signify_ed25519_pubkey(release_pubkey_path)).decode('ascii')

    with open(release_pubkey_path) as f:
        release_pubkey_base64 = f.read().splitlines()[1]

    release_pubkey_qrcode = cryptosign._qrcode_from_signify_ed25519_pubkey(release_pubkey_path)

    release_pubkey = {'base64': release_pubkey_base64, 'hex': release_pubkey_hex, 'qrcode': release_pubkey_qrcode}

    return release_pubkey


def _parse_node_key(key_path: str, private: bool = True) -> OrderedDict:
    """
    Internal helper. This parses a ``key.pub`` or ``key.priv`` file and
    returns a dict mapping from tags to values.

    :param key_path: Path to key file.
    :param private: Flag indicating whether to parse the file as a private key file.
    :returns: Tags parsed from key file (ordered as appearing in the file).
    """
    if os.path.exists(key_path) and not os.path.isfile(key_path):
        raise Exception("Key file '{}' exists, but isn't a file".format(key_path))

    allowed_tags = [
        'public-key-ed25519', 'public-adr-eth', 'machine-id', 'node-authid', 'node-cluster-ip', 'created-at', 'creator'
    ]
    if private:
        allowed_tags.extend(['private-key-ed25519', 'private-key-eth'])

    tags = OrderedDict()
    with open(key_path, 'r') as key_file:
        got_blankline = False
        for line in key_file.readlines():
            if line.strip() == '':
                got_blankline = True
            elif got_blankline:
                tag, value = line.split(':', 1)
                tag = tag.strip().lower()
                value = value.strip()
                if tag not in allowed_tags:
                    raise Exception("Invalid tag '{}' in key file {}".format(tag, key_path))
                if tag in tags:
                    raise Exception("Duplicate tag '{}' in key file {}".format(tag, key_path))
                tags[tag] = value
    return tags


def _read_node_key(cbdir, privkey_path='key.priv', pubkey_path='key.pub', private=False):
    if private:
        node_key_path = os.path.join(cbdir, privkey_path)
    else:
        node_key_path = os.path.join(cbdir, pubkey_path)

    if not os.path.exists(node_key_path):
        raise Exception('no node key file found at {}'.format(node_key_path))

    node_key_tags = _parse_node_key(node_key_path)

    if private:
        node_key_hex = node_key_tags['private-key-ed25519']
        # eth_privkey_seed_hex = node_key_tags['private-key-eth']
    else:
        node_key_hex = node_key_tags['public-key-ed25519']
        # eth_pubadr = node_key_tags['public-adr-eth']

    qr = pyqrcode.create(node_key_hex, error='L', mode='binary')
    mode = 'text'
    if mode == 'text':
        node_key_qr = qr.terminal()
    elif mode == 'svg':
        import io
        data_buffer = io.BytesIO()
        qr.svg(data_buffer, omithw=True)
        node_key_qr = data_buffer.getvalue()
    else:
        raise Exception('logic error')

    node_key = {'hex': node_key_hex, 'qrcode': node_key_qr}

    return node_key


def _write_node_key(filepath, tags, msg):
    """
    Internal helper, write the given tags to the given file.
    """
    with open(filepath, 'w') as f:
        f.write(msg)
        for (tag, value) in tags.items():
            if value is None:
                value = 'unknown'
            f.write('{}: {}\n'.format(tag, value))


def _maybe_generate_node_key(cbdir, privfile='key.priv', pubfile='key.pub'):

    privkey_path = os.path.join(cbdir, privfile)
    pubkey_path = os.path.join(cbdir, pubfile)

    # node private key seems to exist already: read and check!
    if os.path.exists(privkey_path):

        # read all tags, including private tags
        priv_tags = _parse_node_key(privkey_path, private=True)

        # check mandatory tags - the following tags are optional:
        #   - node-authid
        #   - node-cluster-ip
        #   - public-adr-eth
        #   - private-key-eth
        for tag in ['creator', 'created-at', 'machine-id', 'public-key-ed25519', 'private-key-ed25519']:
            if tag not in priv_tags:
                raise Exception("Corrupt node private key file {} - {} tag not found".format(privkey_path, tag))

        privkey_hex = priv_tags['private-key-ed25519']
        privkey = signing.SigningKey(privkey_hex, encoder=encoding.HexEncoder)
        pubkey = privkey.verify_key
        pubkey_hex = pubkey.encode(encoder=encoding.HexEncoder).decode('ascii')

        # check that the public key in the key file matches the private key therein
        if priv_tags['public-key-ed25519'] != pubkey_hex:
            raise Exception(("Inconsistent node private key file {} - public-key-ed25519 doesn't"
                             " correspond to private-key-ed25519").format(privkey_path))

        eth_pubadr = None
        eth_privkey_seed_hex = priv_tags.get('private-key-eth', None)
        if eth_privkey_seed_hex:
            eth_privkey_seed = binascii.a2b_hex(eth_privkey_seed_hex)
            eth_privkey = KeyAPI(NativeECCBackend).PrivateKey(eth_privkey_seed)
            eth_pubadr = eth_privkey.public_key.to_checksum_address()
            if 'public-adr-eth' in priv_tags:
                if priv_tags['public-adr-eth'] != eth_pubadr:
                    raise Exception(("Inconsistent node private key file {} - public-adr-eth doesn't"
                                     " correspond to private-key-eth").format(privkey_path))

        if os.path.exists(pubkey_path):
            pub_tags = _parse_node_key(pubkey_path, private=False)
            # node-authid and node-cluster-ip are optional!
            for tag in ['creator', 'created-at', 'machine-id', 'public-key-ed25519']:
                if tag not in pub_tags:
                    raise Exception("Corrupt node public key file {} - {} tag not found".format(pubkey_path, tag))

            if pub_tags['public-key-ed25519'] != pubkey_hex:
                raise Exception(
                    ("Inconsistent node public key file {} - public-key-ed25519 doesn't"
                     " correspond to private-key-ed25519 in private key file {}").format(pubkey_path, privkey_path))

            if pub_tags.get('public-adr-eth', None) != eth_pubadr:
                raise Exception(
                    ("Inconsistent node public key file {} - public-adr-eth doesn't"
                     " correspond to private-key-eth in private key file {}").format(pubkey_path, privkey_path))
        else:
            log.info(
                "Node public key file {pub_path} not found - re-creating from node private key file {priv_path}",
                pub_path=pubkey_path,
                priv_path=privkey_path,
            )
            pub_tags = OrderedDict([
                ('creator', priv_tags['creator']),
                ('created-at', priv_tags['created-at']),
                ('machine-id', priv_tags['machine-id']),
                ('node-authid', priv_tags.get('node-authid', None)),
                ('node-cluster-ip', priv_tags.get('node-cluster-ip', None)),
                ('public-key-ed25519', pubkey_hex),
                ('public-adr-eth', eth_pubadr),
            ])
            msg = 'Crossbar.io node public key\n\n'
            _write_node_key(pubkey_path, pub_tags, msg)

        log.info('Node key files exist and are valid. Node public key is {pubkey}', pubkey=hlid('0x' + pubkey_hex))

        was_new = False

    else:
        # node private key does not yet exist: generate a new one

        # Node key (Ed25519)
        privkey = signing.SigningKey.generate()
        privkey_hex = privkey.encode(encoder=encoding.HexEncoder).decode('ascii')
        pubkey = privkey.verify_key
        pubkey_hex = pubkey.encode(encoder=encoding.HexEncoder).decode('ascii')

        # Node Ethereum key
        eth_privkey_seed = os.urandom(32)
        eth_privkey_seed_hex = binascii.b2a_hex(eth_privkey_seed).decode()
        eth_privkey = KeyAPI(NativeECCBackend).PrivateKey(eth_privkey_seed)
        eth_pubadr = eth_privkey.public_key.to_checksum_address()

        if 'CROSSBAR_NODE_ID' in os.environ and os.environ['CROSSBAR_NODE_ID'].strip() != '':
            node_authid = os.environ['CROSSBAR_NODE_ID']
            log.info('using node_authid from environment variable CROSSBAR_NODE_ID: "{node_authid}"',
                     node_authid=node_authid)
        else:
            node_authid = socket.gethostname()
            log.info('using node_authid from hostname: "{node_authid}"', node_authid=node_authid)

        if 'CROSSBAR_NODE_CLUSTER_IP' in os.environ and os.environ['CROSSBAR_NODE_CLUSTER_IP'].strip() != '':
            node_cluster_ip = os.environ['CROSSBAR_NODE_CLUSTER_IP']
            log.info('using node_cluster_ip from environment variable CROSSBAR_NODE_CLUSTER_IP: "{node_cluster_ip}"',
                     node_cluster_ip=node_cluster_ip)
        else:
            node_cluster_ip = '127.0.0.1'
            log.info('using node_cluster_ip for localhost (builtin): "{node_cluster_ip}"',
                     node_cluster_ip=node_cluster_ip)

        # first, write the public file
        tags = OrderedDict([
            ('creator', _creator()),
            ('created-at', utcnow()),
            ('machine-id', _machine_id()),
            ('node-authid', node_authid),
            ('node-cluster-ip', node_cluster_ip),
            ('public-key-ed25519', pubkey_hex),
            ('public-adr-eth', eth_pubadr),
        ])
        msg = 'Crossbar.io node public key\n\n'
        _write_node_key(pubkey_path, tags, msg)

        # now, add the private key and write the private file
        tags['private-key-ed25519'] = privkey_hex
        tags['private-key-eth'] = eth_privkey_seed_hex
        msg = 'Crossbar.io node private key - KEEP THIS SAFE!\n\n'
        _write_node_key(privkey_path, tags, msg)

        log.info(
            'New node key pair generated! public-key-ed25519={pubkey}, node-authid={node_authid}, public-adr-eth={eth_pubadr}',
            pubkey=hlid('0x' + pubkey_hex),
            node_authid=node_authid,
            eth_pubadr=hlid(eth_pubadr))

        was_new = True

    # fix file permissions on node public/private key files
    # note: we use decimals instead of octals as octal literals have changed between Py2/3
    #
    if os.stat(pubkey_path).st_mode & 511 != 420:  # 420 (decimal) == 0644 (octal)
        os.chmod(pubkey_path, 420)
        log.info("File permissions on node public key fixed")

    if os.stat(privkey_path).st_mode & 511 != 384:  # 384 (decimal) == 0600 (octal)
        os.chmod(privkey_path, 384)
        log.info("File permissions on node private key fixed")

    log.info(
        'Node key loaded from {priv_path}',
        priv_path=hlid(privkey_path),
    )
    return was_new, cryptosign.CryptosignKey(privkey, can_sign=True)
