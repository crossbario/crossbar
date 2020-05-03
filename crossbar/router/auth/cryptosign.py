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

import os
import binascii

import nacl
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from autobahn import util
from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError

from twisted.internet.defer import Deferred

import txaio

from crossbar._util import hltype, hlid
from crossbar.router.auth.pending import PendingAuth

__all__ = (
    'PendingAuthCryptosign',
    'PendingAuthCryptosignProxy',
)


class PendingAuthCryptosign(PendingAuth):
    """
    Pending Cryptosign authentication.
    """

    log = txaio.make_logger()

    AUTHMETHOD = 'cryptosign'

    def __init__(self, pending_session_id, transport_info, realm_container, config):
        super(PendingAuthCryptosign, self).__init__(
            pending_session_id, transport_info, realm_container, config,
        )
        self._verify_key = None

        # https://tools.ietf.org/html/rfc5056
        # https://tools.ietf.org/html/rfc5929
        # https://www.ietf.org/proceedings/90/slides/slides-90-uta-0.pdf
        channel_id_hex = transport_info.get('channel_id', None)
        if channel_id_hex:
            self._channel_id = binascii.a2b_hex(channel_id_hex)
        else:
            self._channel_id = None

        self._challenge = None
        self._expected_signed_message = None

        # create a map: pubkey -> authid
        # this is to allow clients to authenticate without specifying an authid
        if config['type'] == 'static':
            self._pubkey_to_authid = {}
            for authid, principal in self._config.get('principals', {}).items():
                for pubkey in principal['authorized_keys']:
                    self._pubkey_to_authid[pubkey] = authid

    def _compute_challenge(self, channel_binding):
        self._challenge = os.urandom(32)

        if self._channel_id and channel_binding:
            self._expected_signed_message = util.xor(self._challenge, self._channel_id)
        else:
            self._expected_signed_message = self._challenge

        extra = {
            'challenge': binascii.b2a_hex(self._challenge).decode('ascii'),
            'channel_binding': channel_binding,
        }
        return extra

    def hello(self, realm: str, details: types.HelloDetails):
        self.log.debug('{func}::hello(realm="{realm}", details.authid="{authid}", details.authrole="{authrole}")',
                       func=hltype(self.hello), realm=hlid(realm), authid=hlid(details.authid),
                       authrole=hlid(details.authrole))

        # the channel binding requested by the client authenticating
        channel_binding = details.authextra.get('channel_binding', None) if details.authextra else None
        if channel_binding is not None and channel_binding not in ['tls-unique']:
            return types.Deny(message='invalid channel binding type "{}" requested'.format(channel_binding))
        else:
            self.log.debug(
                "WAMP-cryptosign CHANNEL BINDING requested: channel_binding={channel_binding}, channel_id={channel_id}",
                channel_binding=channel_binding,
                channel_id=self._channel_id
            )

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # use static principal database from configuration
        if self._config['type'] == 'static':

            self._authprovider = 'static'

            # get client's pubkey, if it was provided in authextra
            pubkey = None
            if details.authextra and 'pubkey' in details.authextra:
                pubkey = details.authextra['pubkey']

            # if the client provides it's public key, that's enough to identify,
            # and we can infer the authid from that. BUT: that requires that
            # there is a 1:1 relation between authid's and pubkey's !! see below (*)
            if self._authid is None:
                if pubkey:
                    # we do a naive search, but that is ok, since "static mode" is from
                    # node configuration, and won't contain a lot principals anyway
                    for _authid, _principal in self._config.get('principals', {}).items():
                        if pubkey in _principal['authorized_keys']:
                            # (*): this is necessary to detect multiple authid's having the same pubkey
                            # in which case we couldn't reliably map the authid from the pubkey
                            if self._authid is None:
                                self._authid = _authid
                            else:
                                return types.Deny(message='cannot infer client identity from pubkey: multiple authids in principal database have this pubkey')
                    if self._authid is None:
                        return types.Deny(message='cannot identify client: no authid requested and no principal found for provided extra.pubkey')
                else:
                    return types.Deny(message='cannot identify client: no authid requested and no extra.pubkey provided')

            if self._authid in self._config.get('principals', {}):

                principal = self._config['principals'][self._authid]

                if pubkey and (pubkey not in principal['authorized_keys']):
                    return types.Deny(message='extra.pubkey provided does not match any one of authorized_keys for the principal')

                error = self._assign_principal(principal)
                if error:
                    return error

                self._verify_key = VerifyKey(pubkey, encoder=nacl.encoding.HexEncoder)

                extra = self._compute_challenge(channel_binding)
                return types.Challenge(self._authmethod, extra)

            else:
                return types.Deny(message='no principal with authid "{}" exists'.format(details.authid))

        elif self._config['type'] == 'dynamic':

            self._authprovider = 'dynamic'

            d = Deferred()

            d1 = txaio.as_future(self._init_dynamic_authenticator)

            def initialized(error=None):
                if error:
                    d.errback(error)
                    return

                self._session_details['authmethod'] = self._authmethod  # from AUTHMETHOD, via base
                self._session_details['authid'] = details.authid
                self._session_details['authrole'] = details.authrole
                self._session_details['authextra'] = details.authextra

                self.log.debug('Calling dynamic authenticator [proc="{proc}", realm="{realm}", session={session}, authid="{authid}", authrole="{authrole}"]',
                               proc=self._authenticator,
                               realm=self._authenticator_session._realm,
                               session=self._authenticator_session._session_id,
                               authid=self._authenticator_session._authid,
                               authrole=self._authenticator_session._authrole)

                d2 = self._authenticator_session.call(self._authenticator, realm, details.authid, self._session_details)

                def on_authenticate_ok(principal):
                    self.log.debug('{klass}.hello(realm="{realm}", details={details}) -> on_authenticate_ok(principal={principal})',
                                   klass=self.__class__.__name__, realm=realm, details=details, principal=principal)
                    error = self._assign_principal(principal)
                    if error:
                        d.callback(error)
                        return

                    self._verify_key = VerifyKey(principal['pubkey'], encoder=nacl.encoding.HexEncoder)

                    extra = self._compute_challenge(channel_binding)
                    d.callback(types.Challenge(self._authmethod, extra))

                def on_authenticate_error(err):
                    self.log.debug('{klass}.hello(realm="{realm}", details={details}) -> on_authenticate_error(err={err})',
                                   klass=self.__class__.__name__, realm=realm, details=details, err=err)
                    try:
                        d.callback(self._marshal_dynamic_authenticator_error(err))
                    except:
                        self.log.failure()
                        d.callback(error)

                d2.addCallbacks(on_authenticate_ok, on_authenticate_error)
                return d2

            def initialized_error(fail):
                self.log.failure('Internal error (3): {log_failure.value}', failure=fail)
                d.errback(fail)

            d1.addCallbacks(initialized, initialized_error)

            return d

        elif self._config['type'] == 'function':
            self._authprovider = 'function'

            init_d = txaio.as_future(self._init_function_authenticator)

            def init(error):
                if error:
                    return error

                self._session_details['authmethod'] = self._authmethod  # from AUTHMETHOD, via base
                self._session_details['authid'] = details.authid
                self._session_details['authrole'] = details.authrole
                self._session_details['authextra'] = details.authextra

                auth_d = txaio.as_future(self._authenticator, realm, details.authid, self._session_details)

                def on_authenticate_ok(principal):
                    self.log.info('{klass}.hello(realm="{realm}", details={details}) -> on_authenticate_ok(principal={principal})',
                                  klass=self.__class__.__name__, realm=realm, details=details, principal=principal)
                    error = self._assign_principal(principal)
                    if error:
                        return error

                    self._verify_key = VerifyKey(principal['pubkey'], encoder=nacl.encoding.HexEncoder)

                    extra = self._compute_challenge(channel_binding)
                    return types.Challenge(self._authmethod, extra)

                def on_authenticate_error(err):
                    self.log.info('{klass}.hello(realm="{realm}", details={details}) -> on_authenticate_error(err={err})',
                                  klass=self.__class__.__name__, realm=realm, details=details, err=err)
                    try:
                        return self._marshal_dynamic_authenticator_error(err)
                    except Exception as e:
                        error = ApplicationError.AUTHENTICATION_FAILED
                        message = 'marshalling of function-based authenticator error return failed: {}'.format(e)
                        self.log.warn('{klass}.hello.on_authenticate_error() - {msg}', msg=message)
                        return types.Deny(error, message)

                auth_d.addCallbacks(on_authenticate_ok, on_authenticate_error)
                return auth_d

            init_d.addBoth(init)
            return init_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return types.Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(self._config['type']))

    def authenticate(self, signed_message):
        """
        Verify the signed message sent by the client. With WAMP-cryptosign, this must be 96 bytes (as a string
        in HEX encoding): the concatenation of the Ed25519 signature (64 bytes) and the 32 bytes we sent
        as a challenge previously, XORed with the 32 bytes transport channel ID (if available).
        """
        try:
            if not isinstance(signed_message, str):
                return types.Deny(message='invalid type {} for signed message'.format(type(signed_message)))

            try:
                signed_message = binascii.a2b_hex(signed_message)
            except TypeError:
                return types.Deny(message='signed message is invalid (not a HEX encoded string)')

            if len(signed_message) != 96:
                return types.Deny(message='signed message has invalid length (was {}, but should have been 96)'.format(len(signed_message)))

            # now verify the signed message versus the client public key ..
            try:
                message = self._verify_key.verify(signed_message)
            except BadSignatureError:
                return types.Deny(message='signed message has invalid signature')

            # .. and check that the message signed by the client is really what we expect
            if message != self._expected_signed_message:
                return types.Deny(message='message signed is bogus')

            # signature was valid _and_ the message that was signed is equal to
            # what we expected => accept the client
            return self._accept()

        except Exception as e:

            # should not arrive here .. but who knows
            return types.Deny(message='internal error: {}'.format(e))


class PendingAuthCryptosignProxy(PendingAuthCryptosign):
    """
    Pending Cryptosign authentication with additions for proxy
    """

    log = txaio.make_logger()
    AUTHMETHOD = 'cryptosign-proxy'

    def hello(self, realm, details):
        self.log.debug('{klass}.hello(realm={realm}, details={details}) ...',
                       klass=self.__class__.__name__, realm=realm, details=details)
        if not details.authextra:
            return types.Deny(message='missing required details.authextra')
        for attr in ['proxy_authid', 'proxy_authrole', 'proxy_realm']:
            if attr not in details.authextra:
                return types.Deny(message='missing required attribute {} in details.authextra'.format(attr))

        if details.authrole is None:
            details.authrole = details.authextra.get('proxy_authrole', None)
        if details.authid is None:
            details.authid = details.authextra.get('proxy_authid', None)

        # with authentictors of type "*-proxy", the principal returned in authenticating the
        # incoming backend connection is ignored ..
        f = super(PendingAuthCryptosignProxy, self).hello(realm, details)

        def assign(res):
            """
            .. and the incoming backend connection from the proxy frontend is authenticated as the principal
            the frontend proxy has _already_ authenticated the actual client (before even connecting and
            authenticating to the backend here)
            """
            if isinstance(res, types.Deny):
                return res

            principal = {}
            principal['realm'] = details.authextra['proxy_realm']
            principal['authid'] = details.authextra['proxy_authid']
            principal['role'] = details.authextra['proxy_authrole']
            principal['extra'] = details.authextra.get('proxy_authextra', None)
            self._assign_principal(principal)

            self.log.debug(
                '{klass}.hello(realm={realm}, details={details}) -> principal={principal}',
                klass=self.__class__.__name__,
                realm=realm,
                details=details,
                principal=principal,
            )
            return self._accept()

        def error(f):
            return types.Deny(
                "Internal error: {}".format(f)
            )

        txaio.add_callbacks(f, assign, error)
        return f
