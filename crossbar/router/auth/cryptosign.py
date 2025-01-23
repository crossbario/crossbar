#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

import os
import binascii
from pprint import pformat
from typing import Optional, Union, Dict, Any

import nacl
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

import web3

from twisted.internet.defer import Deferred

import txaio

from autobahn import util
from autobahn.util import hltype, hlid, hlval
from autobahn.wamp.types import Accept, Deny, HelloDetails, Challenge, TransportDetails
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.message import identify_realm_name_category
from autobahn.xbr import EIP712AuthorityCertificate, parse_certificate_chain

from crossbar.router.auth.pending import PendingAuth
from crossbar.interfaces import IRealmContainer, IPendingAuth

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

    def __init__(self, pending_session_id: int, transport_details: TransportDetails, realm_container: IRealmContainer,
                 config: Dict[str, Any]):
        super(PendingAuthCryptosign, self).__init__(
            pending_session_id,
            transport_details,
            realm_container,
            config,
        )
        # https://tools.ietf.org/html/rfc5056
        # https://tools.ietf.org/html/rfc5929
        # https://www.ietf.org/proceedings/90/slides/slides-90-uta-0.pdf
        self._channel_id = transport_details.channel_id.get('tls-unique',
                                                            None) if transport_details.channel_id else None

        self._verify_key: Optional[VerifyKey] = None
        self._challenge: Optional[bytes] = None
        self._expected_signed_message: Optional[bytes] = None

        # map `pubkey -> authid` from `config['principals']`, this is to allow clients to
        # authenticate without specifying an authid
        self._pubkey_to_authid = None

        # map `realm_name -> trustroot` from `config['trustroots']`
        self._realms_to_trustroots = None

        if self._config['type'] == 'static':
            if 'principals' in self._config:
                self._pubkey_to_authid = {}
                for authid, principal in self._config.get('principals', {}).items():
                    for pubkey in principal['authorized_keys']:
                        self._pubkey_to_authid[pubkey] = authid
                self.log.info('{func} using principals ({pubkeys_cnt} pubkeys loaded)',
                              pubkeys_cnt=hlval(len(self._pubkey_to_authid), color='green'),
                              func=hltype(PendingAuthCryptosign.__init__))
            elif 'trustroots' in self._config:
                self._realms_to_trustroots = {}
                for _realm, _trustroot in self._config['trustroots'].items():
                    _realm_category = identify_realm_name_category(_realm)
                    if _realm_category == 'standalone':
                        _trustroot_fn = os.path.join(self._realm_container.config.extra.cbdir,
                                                     _trustroot['certificate'])  # noqa
                        self._realms_to_trustroots[_realm] = EIP712AuthorityCertificate.load(_trustroot_fn)
                    elif _realm_category in ['eth', 'ens', 'reverse_ens']:
                        assert False, 'FIXME-' * 10
                    else:
                        assert False, 'invalid realm name "{}" in static cryptosign configuration'.format(_realm)
            else:
                assert False, 'neither "principals" nor "trustroots" attribute found in static cryptosign configuration'

    def _compute_challenge(self, requested_channel_binding: Optional[str]) -> Dict[str, Any]:
        self._challenge = os.urandom(32)
        if self._channel_id and requested_channel_binding == 'tls-unique':
            self._expected_signed_message = util.xor(self._challenge, self._channel_id)
        else:
            self._expected_signed_message = self._challenge

        extra = {
            'challenge': binascii.b2a_hex(self._challenge).decode(),
            'channel_binding': requested_channel_binding,
        }
        self.log.info(
            '{func}::_compute_challenge(channel_binding={channel_binding})[channel_id={channel_id}] -> extra=\n{extra}',
            func=hltype(self.hello),
            channel_id=hlid('0x' + binascii.b2a_hex(self._channel_id).decode()) if self._channel_id else None,
            channel_binding=hlval('"' + requested_channel_binding +
                                  '"') if requested_channel_binding is not None else None,
            extra=pformat(extra))
        return extra

    def hello(self, realm: str, details: HelloDetails) -> Union[Accept, Deny, Challenge]:
        self.log.info(
            '{func}::hello(realm="{realm}", details.authid="{authid}", details.authrole="{authrole}", '
            'details.authextra="{authextra}")',
            func=hltype(self.hello),
            realm=hlid(realm),
            authid=hlid(details.authid),
            authrole=hlid(details.authrole),
            authextra=details.authextra)

        # the channel binding requested by the client authenticating
        requested_channel_binding = details.authextra.get('channel_binding', None) if details.authextra else None
        if requested_channel_binding is not None and requested_channel_binding not in ['tls-unique']:
            return Deny(message='invalid channel binding type "{}" requested'.format(requested_channel_binding))
        else:
            self.log.info(
                "WAMP-cryptosign CHANNEL BINDING requested: channel_binding={channel_binding}, channel_id={channel_id}",
                channel_binding=requested_channel_binding,
                channel_id=self._channel_id)

        # remember the realm the client requested to join (if any)
        self._realm = realm

        # remember the authid the client wants to identify as (if any)
        self._authid = details.authid

        # get trustroot presented by the client
        client_trustroot = details.authextra.get('trustroot', None) if details.authextra else None
        if client_trustroot:
            client_trustroot_name_category = identify_realm_name_category(client_trustroot)
            if client_trustroot_name_category not in ['eth', 'ens', 'reverse_ens']:
                return Deny(message='invalid client trustroot "{}" provided'.format(client_trustroot))
            self.log.info('{func} using client trustroot {trustroot_name_category} "{trustroot}" from client HELLO',
                          trustroot=hlid(client_trustroot),
                          trustroot_name_category=hlval(client_trustroot_name_category, color='green'),
                          func=hltype(self.hello))

        # get certificates presented by the client
        client_certificates = details.authextra.get('certificates', None) if details.authextra else None
        if client_certificates:
            if not isinstance(client_certificates, list):
                return Deny(message='invalid type {} for client certificates'.format(type(client_certificates)))
            for cc_i, cc_and_sig in enumerate(client_certificates):
                cc_hash, cc, cc_sig = cc_and_sig
                if not isinstance(cc, dict):
                    return Deny(
                        message='invalid type {} for certificate {} in client certificates'.format(type(cc), cc_i))
            client_certificates = parse_certificate_chain(client_certificates)
            self.log.info('{func} using {cnt_cc} client certificates from client HELLO:\n{client_certificates}',
                          cnt_cc=hlval(len(client_certificates), color='green'),
                          client_certificates=client_certificates,
                          func=hltype(self.hello))

        if self._config['type'] == 'static':

            self._authprovider = 'static'

            # get client's pubkey, if it was provided in authextra
            pubkey = None
            if details.authextra and 'pubkey' in details.authextra:
                pubkey = details.authextra['pubkey']

            # use trustroots configured (if trustroots are indeed configured and the client provided
            # a certificate chain to verify)
            if client_certificates and realm in self._realms_to_trustroots:
                # root CA configured as trustroot for realm
                root_ca_cert = self._realms_to_trustroots[realm]

                if client_trustroot != web3.Web3.toChecksumAddress(root_ca_cert.issuer):
                    return Deny(message='trustroot {} provided by client for realm "{}" does not match '
                                'root CA with issuer {} configured for that realm'.format(
                                    client_trustroot, realm, web3.Web3.toChecksumAddress(root_ca_cert.issuer)))

                # trustroot to consider is the issuer of the last certificate (the root CA cert) in
                # the certificate chain provided by the client
                trustroot = client_certificates[-1].issuer
                if trustroot != root_ca_cert.issuer:
                    return Deny(
                        message=
                        'trustroot {} provided by client in last certificate of certificate chain does not match '
                        'root CA with issuer {} configured for realm "{}"'.format(
                            web3.Web3.toChecksumAddress(trustroot), realm,
                            web3.Web3.toChecksumAddress(root_ca_cert.issuer)))

                principal = {
                    # use delegate address as synthetic authid
                    'authid': web3.Web3.toChecksumAddress(client_certificates[0].delegate),

                    # FIXME: the authrole somehow needs to be configurable
                    'role': 'user'
                }

            # use static principal database from configuration
            elif 'principals' in self._config:
                # if the client provides its public key, that's enough to identify,
                # and we can infer the authid from that. BUT: that requires that
                # there is a 1:1 relation between authids and pubkeys !! see below (*)
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
                                    return Deny(message='cannot infer client identity from pubkey: multiple authids '
                                                'in principal database have this pubkey')
                        if self._authid is None:
                            return Deny(message='cannot identify client: no authid requested and no principal found '
                                        'for provided extra.pubkey')
                    else:
                        return Deny(message='cannot identify client: no authid requested and no extra.pubkey provided')

                principals = self._config.get('principals', {})
                if self._authid in principals:
                    principal = principals[self._authid]
                    if pubkey and (pubkey not in principal['authorized_keys']):
                        self.log.warn(
                            'extra.pubkey {pubkey} provided does not match any one of authorized_keys for the principal [func="{func}"]:\n{principals}',
                            func=hltype(self.hello),
                            realm=hlid(realm),
                            authid=hlid(details.authid),
                            pubkey=hlval(pubkey),
                            principals=pformat(principals))
                        return Deny(
                            message='extra.pubkey provided does not match any one of authorized_keys for the principal'
                        )
                else:
                    self.log.warn(
                        'no principal with authid "{authid}" exists in principals for realm "{realm}" [func="{func}"]:\n{principals}',
                        func=hltype(self.hello),
                        realm=hlid(realm),
                        authid=hlid(self._authid),
                        principals=pformat(principals))
                    return Deny(message='no principal with authid "{}" exists'.format(self._authid))

            # neither "principals" nor "trustroots" configured
            else:
                return Deny(
                    message='neither "principals", nor "trustroots" configured (and client certificates provided)')

            error = self._assign_principal(principal)
            if error:
                return error

            self._verify_key = VerifyKey(pubkey, encoder=nacl.encoding.HexEncoder)

            extra = self._compute_challenge(requested_channel_binding)

            if 'challenge' in details.authextra and details.authextra['challenge']:
                challenge_raw = binascii.a2b_hex(details.authextra['challenge'])
                if requested_channel_binding == 'tls-unique':
                    data = util.xor(challenge_raw, self._channel_id)
                else:
                    data = challenge_raw

                # sign the client challenge with our node private Ed25519 key on node controller
                signature_d = self._realm_container.get_controller_session().call('crossbar.sign', data)

                def _on_sign_ok(signature):
                    # return the concatenation of the signature and the message signed (96 bytes)
                    extra['signature'] = binascii.b2a_hex(signature).decode() + binascii.b2a_hex(data).decode()

                signature_d.addCallback(_on_sign_ok)

                # get node public key from node controller
                pubkey_d = self._realm_container.get_controller_session().call('crossbar.get_public_key')

                def _on_pubkey_ok(pubkey):
                    # return router public key
                    extra['pubkey'] = pubkey

                pubkey_d.addCallback(_on_pubkey_ok)

                # FIXME: add router certificate
                # FIXME: add router trustroot

                d = txaio.gather([signature_d, pubkey_d])

                def _on_final(_):
                    return Challenge(self._authmethod, extra)

                d.addCallback(_on_final)
                return d

            else:
                return Challenge(self._authmethod, extra)

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

                self.log.debug(
                    'Calling dynamic authenticator [proc="{proc}", realm="{realm}", session={session}, authid="{authid}", authrole="{authrole}"]',
                    proc=self._authenticator,
                    realm=self._authenticator_session._realm,
                    session=self._authenticator_session._session_id,
                    authid=self._authenticator_session._authid,
                    authrole=self._authenticator_session._authrole)

                d2 = self._authenticator_session.call(self._authenticator, realm, details.authid,
                                                      self._session_details)

                def on_authenticate_ok(principal):
                    self.log.debug(
                        '{klass}.hello(realm="{realm}", details={details}) -> on_authenticate_ok(principal={principal})',
                        klass=self.__class__.__name__,
                        realm=realm,
                        details=details,
                        principal=principal)
                    _error = self._assign_principal(principal)
                    if _error:
                        d.callback(_error)
                        return

                    self._verify_key = VerifyKey(principal['pubkey'], encoder=nacl.encoding.HexEncoder)

                    extra = self._compute_challenge(requested_channel_binding)
                    challenge = Challenge(self._authmethod, extra)
                    d.callback(challenge)

                def on_authenticate_error(_error):
                    self.log.debug(
                        '{klass}.hello(realm="{realm}", details={details}) -> on_authenticate_error(error={error})',
                        klass=self.__class__.__name__,
                        realm=realm,
                        details=details,
                        error=_error)
                    try:
                        d.callback(self._marshal_dynamic_authenticator_error(_error))
                    except:
                        self.log.failure()
                        d.callback(_error)

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

            def init(_error):
                if _error:
                    return _error

                self._session_details['authmethod'] = self._authmethod  # from AUTHMETHOD, via base
                self._session_details['authid'] = details.authid
                self._session_details['authrole'] = details.authrole
                self._session_details['authextra'] = details.authextra

                auth_d = txaio.as_future(self._authenticator, realm, details.authid, self._session_details)

                def on_authenticate_ok(principal):
                    self.log.debug(
                        '{klass}.hello(realm="{realm}", details={details}) -> on_authenticate_ok(principal={principal})',
                        klass=self.__class__.__name__,
                        realm=realm,
                        details=details,
                        principal=principal)
                    _error = self._assign_principal(principal)
                    if _error:
                        return _error

                    self._verify_key = VerifyKey(principal['pubkey'], encoder=nacl.encoding.HexEncoder)

                    _extra = self._compute_challenge(requested_channel_binding)
                    return Challenge(self._authmethod, _extra)

                def on_authenticate_error(err):
                    self.log.warn(
                        '{klass}.hello(realm="{realm}", details={details}) -> on_authenticate_error(err={err})',
                        klass=self.__class__.__name__,
                        realm=realm,
                        details=details,
                        err=err)
                    try:
                        return self._marshal_dynamic_authenticator_error(err)
                    except Exception as e:
                        _error = ApplicationError.AUTHENTICATION_FAILED
                        message = 'marshalling of function-based authenticator error return failed: {}'.format(e)
                        self.log.warn('{klass}.hello.on_authenticate_error() - {msg}', msg=message)
                        return Deny(_error, message)

                auth_d.addCallbacks(on_authenticate_ok, on_authenticate_error)
                return auth_d

            init_d.addBoth(init)
            return init_d

        else:
            # should not arrive here, as config errors should be caught earlier
            return Deny(message='invalid authentication configuration (authentication type "{}" is unknown)'.format(
                self._config['type']))

    def authenticate(self, signature: str) -> Union[Accept, Deny]:
        """
        Verify the signed message sent by the client. With WAMP-cryptosign, this must be 96 bytes (as a string
        in HEX encoding): the concatenation of the Ed25519 signature (64 bytes) and the 32 bytes we sent
        as a challenge previously, XORed with the 32 bytes transport channel ID (if available).
        """
        try:
            if not isinstance(signature, str):
                return Deny(message='invalid type {} for signed message'.format(type(signature)))

            try:
                signed_message = binascii.a2b_hex(signature)
            except TypeError:
                return Deny(message='signed message is invalid (not a HEX encoded string)')

            if len(signed_message) != 96:
                return Deny(message='signed message has invalid length (was {}, but should have been 96)'.format(
                    len(signed_message)))

            # now verify the signed message versus the client public key
            assert self._verify_key
            try:
                message = self._verify_key.verify(signed_message)
            except BadSignatureError:
                return Deny(message='signed message has invalid signature')

            # and check that the message signed by the client is really what we expect
            assert self._expected_signed_message
            if message != self._expected_signed_message:
                return Deny(message='message signed is bogus [got 0x{}, expected 0x{}]'.format(
                    binascii.b2a_hex(message).decode(),
                    binascii.b2a_hex(self._expected_signed_message).decode()))

            # signature was valid _and_ the message that was signed is equal to
            # what we expected => accept the client
            return self._accept()

        # should not arrive here, but who knows
        except Exception as e:
            self.log.failure()
            return Deny(message='INTERNAL ERROR ({})'.format(e))


class PendingAuthCryptosignProxy(PendingAuthCryptosign):
    """
    Pending Cryptosign authentication with additions for proxy
    """

    log = txaio.make_logger()
    AUTHMETHOD = 'cryptosign-proxy'

    def hello(self, realm, details):
        self.log.debug('{klass}.hello(realm={realm}, details={details}) ...',
                       klass=self.__class__.__name__,
                       realm=realm,
                       details=details)
        if not details.authextra:
            return Deny(message='missing required details.authextra')
        for attr in ['proxy_authid', 'proxy_authrole', 'proxy_realm']:
            if attr not in details.authextra:
                return Deny(message='missing required attribute {} in details.authextra'.format(attr))

        if details.authrole is None:
            details.authrole = details.authextra.get('proxy_authrole', None)
        if details.authid is None:
            details.authid = details.authextra.get('proxy_authid', None)

        # with authenticators of type "*-proxy", the principal returned in authenticating the
        # incoming backend connection is ignored ..
        f = txaio.as_future(super(PendingAuthCryptosignProxy, self).hello, realm, details)

        def assign(res):
            if isinstance(res, Deny):
                return res

            # the incoming backend connection from the proxy frontend is authenticated as the principal
            # the frontend proxy has _already_ authenticated the actual client (before even connecting and
            # authenticating to the backend here)
            principal = {
                'realm': details.authextra['proxy_realm'],
                'authid': details.authextra['proxy_authid'],
                'role': details.authextra['proxy_authrole'],

                # the authextra intended for the principal is forwarded from the proxy
                'extra': details.authextra.get('proxy_authextra', None)
            }
            self._assign_principal(principal)

            self.log.debug(
                '{klass}.hello(realm={realm}, details={details}) -> principal={principal}',
                klass=self.__class__.__name__,
                realm=realm,
                details=details,
                principal=principal,
            )
            return self._accept()

        def error(_err):
            return Deny("Internal error: {}".format(_err))

        txaio.add_callbacks(f, assign, error)
        return f


IPendingAuth.register(PendingAuthCryptosign)
