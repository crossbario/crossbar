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

from crossbar.router.auth.anonymous import PendingAuthAnonymous  # noqa
from crossbar.router.auth.anonymous import PendingAuthAnonymousProxy  # noqa
from crossbar.router.auth.wampcra import PendingAuthWampCra  # noqa
from crossbar.router.auth.ticket import PendingAuthTicket  # noqa
from crossbar.router.auth.tls import PendingAuthTLS  # noqa
from crossbar.router.auth.scram import PendingAuthScram  # noqa


AUTHMETHODS = set([
    'ticket',
    'wampcra',
    'tls',
    'cryptosign',
    'cryptosign-proxy',
    'cookie',
    'anonymous',
    'anonymous-proxy',
    'scram',
])

# map of authmethod name to processor class
# note that not all of AUTHMETHODS need to have an
# entry here .. eg when dependencies are missing
AUTHMETHOD_MAP = {
    'anonymous': PendingAuthAnonymous,
    'anonymous-proxy': PendingAuthAnonymousProxy,
    'ticket': PendingAuthTicket,
    'wampcra': PendingAuthWampCra,
    'tls': PendingAuthTLS,
    'cookie': None,
    'scram': PendingAuthScram,
}

AUTHMETHOD_PROXY_MAP = {
    'anonymous-proxy': PendingAuthAnonymousProxy,
}

try:
    import nacl  # noqa
    HAS_CRYPTOSIGN = True
except ImportError:
    HAS_CRYPTOSIGN = False

__all__ = [
    'AUTHMETHODS',
    'AUTHMETHOD_MAP',
    'HAS_CRYPTOSIGN',
    'PendingAuthWampCra',
    'PendingAuthTicket',
    'PendingAuthTLS',
]

if HAS_CRYPTOSIGN:
    from crossbar.router.auth.cryptosign import PendingAuthCryptosign  # noqa
    from crossbar.router.auth.cryptosign import PendingAuthCryptosignProxy  # noqa
    __all__.append('PendingAuthCryptosign')
    __all__.append('PendingAuthCryptosignProxy')
    AUTHMETHOD_MAP['cryptosign'] = PendingAuthCryptosign
    AUTHMETHOD_MAP['cryptosign-proxy'] = PendingAuthCryptosignProxy
    AUTHMETHOD_PROXY_MAP['cryptosign-proxy'] = PendingAuthCryptosignProxy
