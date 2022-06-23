###############################################################################
#
# Crossbar.io Master
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

from pprint import pformat
from txaio import make_logger

from twisted.internet.defer import inlineCallbacks

from autobahn.wamp.exception import ApplicationError
from autobahn.twisted.wamp import ApplicationSession

from autobahn.util import hl, hltype, hlid

# a simple principals database. in real world use, this likey would be
# replaced by some persistent database used to store principals.
PRINCIPALS = [
    {
        # when a session is authenticating use one of the authorized_keys,
        # then assign it all the data below
        "authid": "client01@example.com",
        "realm": "devices_nonexist1",
        "role": "frontend",
        "extra": {
            "foo": 23
        },
        "authorized_keys": ["545efb0a2192db8d43f118e9bf9aee081466e1ef36c708b96ee6f62dddad9122"]
    },
    {
        "authid": "client02@example.com",
        "realm": "devices_nonexist2",
        "role": "frontend",
        "extra": {
            "foo": 42,
            "bar": "baz"
        },
        "authorized_keys": ["585df51991780ee8dce4766324058a04ecae429dffd786ee80839c9467468c28"]
    },
    {
        "authid": "cosmotron-authenticator",
        "realm": "cosmotron-auth",
        "role": "authenticator",
        "authorized_keys": ["9c194391af3bf566fc11a619e8df200ba02efb35b91bdd98b424f20f4163875e"]
    }
]

log = make_logger()


async def create_rlink_authenticator(config, controller):
    """
    Create an authenticator function for the listening transport of router workers
    in a worker group of a router cluster to authenticate rlink connections incoming
    from other workers in this worker group.

    The actual authentication method will be called like:

        authenticate(realm, authid, session_details)

    Note that this function can itself do async work (as can the
    "authenticate" method). For example, we could connect to a
    database here (and then use that connection in the authenticate()
    method)

    'controller' will be None unless `"expose_controller": true` is in
    the config.
    """
    log.info(
        '{func}(config={config}, controller={controller})',
        config=pformat(config),
        func=hltype(create_rlink_authenticator),
        controller=hltype(controller),
    )

    pubkey_to_principals = {}
    for p in PRINCIPALS:
        for k in p['authorized_keys']:
            if k in pubkey_to_principals:
                raise Exception("ambiguous key {}".format(k))
            else:
                pubkey_to_principals[k] = p

    async def authenticate(realm, authid, details):
        """
        this is our dynamic authenticator procedure that will be called by Crossbar.io
        when a session is authenticating
        """
        log.info(
            'authenticate(realm="{realm}", authid="{authid}", details={details}) {func}',
            realm=hl(realm),
            authid=hl(authid),
            details=details,
            func=hltype(create_rlink_authenticator),
        )

        assert ('authmethod' in details)
        assert (details['authmethod'] == 'cryptosign')
        assert ('authextra' in details)
        assert ('pubkey' in details['authextra'])

        pubkey = details['authextra']['pubkey']
        log.info(
            'authenticating session using realm="{realm}", pubkey={pubkey} .. {func}',
            realm=hl(realm),
            pubkey=hl(pubkey),
            func=hltype(create_rlink_authenticator),
        )

        if pubkey in pubkey_to_principals:
            principal = pubkey_to_principals[pubkey]
            auth = {
                'pubkey': pubkey,
                'realm': principal['realm'],
                'authid': principal['authid'],
                'role': principal['role'],
                'extra': principal['extra'],
                'cache': True
            }

            # Note: with WAMP-cryptosign, even though a client may or may not request a `realm`, but in any case, the
            # effective realm the client is authenticated will be returned in the principal `auth['role']` (!)
            effective_realm = auth['realm']

            log.info(
                'found valid principal authid="{authid}", authrole="{authrole}", realm="{realm}" matching given client public key {func}',
                func=hltype(create_rlink_authenticator),
                authid=hl(auth['authid']),
                authrole=hl(auth['role']),
                realm=hl(effective_realm),
            )

            # only now that we know the effective realm a client is to be joined to (see above), maybe active (start)
            # the desired application realm to let the client join to subsequently
            # await _maybe_activate_realm(controller, effective_realm)

            return auth
        else:
            msg = 'no principal with matching public key 0x{}'.format(pubkey)
            log.warn(msg)
            raise ApplicationError('com.example.no_such_user', msg)

    return authenticate


class AuthenticatorSession(ApplicationSession):
    @inlineCallbacks
    def onJoin(self, details):
        def authenticate(realm, authid, details):
            self.log.info('{func}(realm="{realm}", authid="{authid}", details=details)',
                          func=authenticate,
                          realm=hlid(realm),
                          authid=hlid(authid),
                          details=details)
            return 'anonymous'

        yield self.register(authenticate, 'crossbarfabriccenter.mrealm.arealm.authenticate')

        self.log.info('{func}() Application realm authenticator ready!', func=hltype(self.onJoin))
