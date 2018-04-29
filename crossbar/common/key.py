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

import binascii
import getpass
import os
import socket
import subprocess
from collections import OrderedDict

import six
import pkg_resources
import pyqrcode

from autobahn.wamp.cryptosign import _read_signify_ed25519_pubkey, _qrcode_from_signify_ed25519_pubkey

from twisted.python.runtime import platform

import crossbar


def _read_release_pubkey():
    release_pubkey_file = 'crossbar-{}.pub'.format('-'.join(crossbar.__version__.split('.')[0:2]))
    release_pubkey_path = os.path.join(pkg_resources.resource_filename('crossbar', 'keys'), release_pubkey_file)

    release_pubkey_hex = binascii.b2a_hex(_read_signify_ed25519_pubkey(release_pubkey_path)).decode('ascii')

    with open(release_pubkey_path) as f:
        release_pubkey_base64 = f.read().splitlines()[1]

    release_pubkey_qrcode = _qrcode_from_signify_ed25519_pubkey(release_pubkey_path)

    release_pubkey = {
        u'base64': release_pubkey_base64,
        u'hex': release_pubkey_hex,
        u'qrcode': release_pubkey_qrcode
    }

    return release_pubkey


def _parse_keyfile(key_path, private=True):
    """
    Internal helper. This parses a node.pub or node.priv file and
    returns a dict mapping tags -> values.
    """
    if os.path.exists(key_path) and not os.path.isfile(key_path):
        raise Exception("Key file '{}' exists, but isn't a file".format(key_path))

    allowed_tags = [u'public-key-ed25519', u'machine-id', u'created-at',
                    u'creator']
    if private:
        allowed_tags.append(u'private-key-ed25519')

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


def _read_node_pubkey(cbdir, privkey_path=u'key.priv', pubkey_path=u'key.pub'):

    node_pubkey_path = os.path.join(cbdir, pubkey_path)

    if not os.path.exists(node_pubkey_path):
        raise Exception('no node public key found at {}'.format(node_pubkey_path))

    node_pubkey_tags = _parse_keyfile(node_pubkey_path)

    node_pubkey_hex = node_pubkey_tags[u'public-key-ed25519']

    qr = pyqrcode.create(node_pubkey_hex, error='L', mode='binary')

    mode = 'text'

    if mode == 'text':
        node_pubkey_qr = qr.terminal()

    elif mode == 'svg':
        import io
        data_buffer = io.BytesIO()

        qr.svg(data_buffer, omithw=True)

        node_pubkey_qr = data_buffer.getvalue()

    else:
        raise Exception('logic error')

    node_pubkey = {
        u'hex': node_pubkey_hex,
        u'qrcode': node_pubkey_qr
    }

    return node_pubkey


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

        if six.PY2:
            # Only API on 2.7
            return plistlib.readPlistFromString(plist_data)[0]["IOPlatformSerialNumber"]  # noqa
        else:
            # New, non-deprecated 3.4+ API
            return plistlib.loads(plist_data)[0]["IOPlatformSerialNumber"]

    else:
        # Something else, just get a hostname
        return socket.gethostname()


def _creator():
    """
    for informational purposes, try to identify the creator (user@hostname)
    """
    try:
        return u'{}@{}'.format(getpass.getuser(), socket.gethostname())
    except:
        return None


def _write_node_key(filepath, tags, msg):
    """
    Internal helper.
    Write the given tags to the given file
    """
    with open(filepath, 'w') as f:
        f.write(msg)
        for (tag, value) in tags.items():
            if value is None:
                value = 'unknown'
            f.write(u'{}: {}\n'.format(tag, value))
