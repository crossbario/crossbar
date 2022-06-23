#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from typing import Dict, Type

from crossbar.router.auth.pending import PendingAuth  # noqa
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
AUTHMETHOD_MAP: Dict[str, Type[PendingAuth]] = {
    'anonymous': PendingAuthAnonymous,
    'anonymous-proxy': PendingAuthAnonymousProxy,
    'ticket': PendingAuthTicket,
    'wampcra': PendingAuthWampCra,
    'tls': PendingAuthTLS,
    'cookie': PendingAuth,
    'scram': PendingAuthScram,
}

AUTHMETHOD_PROXY_MAP: Dict[str, Type[PendingAuth]] = {
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
    'PendingAuth',
    'PendingAuthWampCra',
    'PendingAuthScram',
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
