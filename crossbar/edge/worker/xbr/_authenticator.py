# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import binascii

import txaio

from crossbar._util import hlid

txaio.use_twisted()  # noqa
from txaio import make_logger, time_ns

import numpy as np

from autobahn.wamp import register, CallDetails
from autobahn.xbr import recover_eip712_market_member_login, is_cs_pubkey, is_signature, \
    is_address
from autobahn.util import generate_serial_number, without_0x
from autobahn.wamp.exception import ApplicationError

import cfxdb
from cfxdb.xbr import ActorType


class Authenticator:

    ERROR_INVALID_AUTH_REQUEST = 'xbr.marketmaker.error.invalid-auth-request'
    ERROR_INVALID_AUTH_REQUEST_MSG = 'invalid parameter(s) in authentication request: {}'

    log = make_logger()

    def __init__(self, db, market_session, reactor, market_oid):
        self._db = db
        self._schema = cfxdb.xbr.schema.Schema.attach(db)
        self._xbrmm = cfxdb.xbrmm.schema.Schema.attach(db)
        self._market_session = market_session
        self._market_oid = market_oid
        self._reactor = reactor
        self._pubkey_by_session = {}

    @register('xbr.marketmaker.authenticator.authenticate')
    async def _authenticate(self, realm, authid, details, call_details):
        self.log.info('{klass}.authenticate(realm="{realm}", authid="{authid}", details={details})',
                      klass=self.__class__.__name__,
                      realm=realm,
                      authid=authid,
                      details=details)

        if 'authmethod' not in details:
            msg = 'missing "authmethod" in authentication details (WAMP HELLO message details)'
            raise ApplicationError(self.ERROR_INVALID_AUTH_REQUEST, self.ERROR_INVALID_AUTH_REQUEST_MSG.format(msg))

        authmethod = details['authmethod']

        if authmethod != 'cryptosign':
            msg = 'authmethod "{}" not permissible'.format(authmethod)
            raise ApplicationError(self.ERROR_INVALID_AUTH_REQUEST, self.ERROR_INVALID_AUTH_REQUEST_MSG.format(msg))

        if 'authextra' not in details:
            msg = 'Must provide authextra for authmethod cryptosign'
            raise ApplicationError(self.ERROR_INVALID_AUTH_REQUEST, self.ERROR_INVALID_AUTH_REQUEST_MSG.format(msg))

        authextra = details['authextra']

        if 'pubkey' not in authextra:
            msg = 'missing public key in authextra for authmethod cryptosign'
            raise ApplicationError(self.ERROR_INVALID_AUTH_REQUEST, self.ERROR_INVALID_AUTH_REQUEST_MSG.format(msg))

        pubkey = authextra['pubkey']
        if isinstance(pubkey, str):
            pubkey = binascii.a2b_hex(without_0x(pubkey))
        assert is_cs_pubkey(pubkey)

        session_id = details['session']
        assert type(session_id) == int

        # FIXME: find a more elegant way to query the db.
        def get_actor(_txn, address):
            _actor = self._schema.actors[_txn, (self._market_oid, address, ActorType.PROVIDER)]
            if _actor:
                return _actor

            _actor = self._schema.actors[_txn, (self._market_oid, address, ActorType.CONSUMER)]
            if _actor:
                return _actor

            _actor = self._schema.actors[_txn, (self._market_oid, address, ActorType.PROVIDER_CONSUMER)]
            if _actor:
                return _actor

        if ('wallet_address' not in authextra or not authextra['wallet_address']) and \
                ('signature' not in authextra or not authextra['signature']):
            with self._db.begin() as txn:
                user_key = self._xbrmm.user_keys[txn, pubkey]
                actor = None
                if user_key:
                    actor = get_actor(txn, bytes(user_key.wallet_address))
                    if actor:
                        authrole = 'user'
                        authid = 'member-{}'.format(binascii.b2a_hex(user_key.wallet_address).decode())
                    else:
                        authrole = 'anonymous'
                        authid = 'anonymous-{}'.format(generate_serial_number())
                else:
                    authrole = 'anonymous'
                    authid = 'anonymous-{}'.format(generate_serial_number())

                self._pubkey_by_session[session_id] = pubkey

                auth = {
                    'pubkey': binascii.b2a_hex(pubkey),
                    'realm': realm,
                    'authid': authid,
                    'role': authrole,
                    'cache': True,
                    'extra': {
                        'actor_type': actor.actor_type if actor else 0
                    }
                }

                self.log.info('{klass}.authenticate(..) => {auth}', klass=self.__class__.__name__, auth=auth)

                return auth

        if ('wallet_address' not in authextra or not authextra['wallet_address']) or \
                ('signature' not in authextra or not authextra['signature']):
            msg = 'Should provide `pubkey`, `wallet_address` and `signature` in authextra ' \
                  'to authenticate new member. To authenticate existing member, only provide ' \
                  '`pubkey`'
            raise ApplicationError(self.ERROR_INVALID_AUTH_REQUEST, self.ERROR_INVALID_AUTH_REQUEST_MSG.format(msg))

        wallet_address = authextra['wallet_address']
        assert is_address(wallet_address)

        signature = authextra['signature']
        assert is_signature(signature)

        try:
            signer_address = recover_eip712_market_member_login(wallet_address, pubkey, signature)
        except Exception as e:
            self.log.warn('EIP712 signature recovery failed (wallet_adr={wallet_adr}): {err}',
                          wallet_adr=wallet_address,
                          err=str(e))
            raise ApplicationError('xbr.error.invalid_signature', 'EIP712 signature recovery failed ({})'.format(e))

        if signer_address != wallet_address:
            self.log.warn('EIP712 signature invalid: signer_address={signer_address}, wallet_adr={wallet_adr}',
                          signer_address=signer_address,
                          wallet_adr=wallet_address)
            raise ApplicationError('xbr.error.invalid_signature', 'EIP712 signature invalid')

        with self._db.begin(write=True) as txn:
            account = self._schema.members[txn, wallet_address]
            actor = None
            if account:
                actor = get_actor(txn, wallet_address)
                if actor:
                    user_key = self._xbrmm.user_keys[txn, pubkey]
                    if not user_key:
                        user_key = cfxdb.xbrmm.UserKey()
                        user_key.owner = account.account_oid
                        user_key.pubkey = pubkey
                        user_key.created = np.datetime64(txaio.time_ns(), 'ns')
                        user_key.wallet_address = wallet_address
                        user_key.signature = signature
                        self._xbrmm.user_keys[txn, pubkey] = user_key

                    self._pubkey_by_session[session_id] = pubkey

                    authrole = 'user'
                    # authid = 'member-{}'.format(account.account_oid)
                    # account.account_oid returns a pseudo value because
                    # the "emit" from the xbr contracts does not include
                    # account_oid in it, hence we don't really have that.
                    # To compensate that, we could include wallet address
                    # in authid, so that API calls could validate
                    # if the caller really is the "owner" of a resource.
                    authid = 'member-{}'.format(binascii.b2a_hex(wallet_address).decode())
                else:
                    authrole = 'anonymous'
                    authid = 'anonymous-{}'.format(generate_serial_number())

            else:
                authrole = 'anonymous'
                authid = 'anonymous-{}'.format(generate_serial_number())

        auth = {
            'pubkey': binascii.b2a_hex(pubkey),
            'realm': realm,
            'authid': authid,
            'role': authrole,
            'cache': True,
            'extra': {
                'actor_type': actor.actor_type if actor else 0
            }
        }

        self.log.info('{klass}.authenticate(..) => {auth}', klass=self.__class__.__name__, auth=auth)

        return auth

    @register('xbr.marketmaker.authenticator.logout')
    async def _logout(self, call_details: CallDetails):
        caller_session_id = call_details.caller

        caller_pubkey = self._pubkey_by_session.pop(caller_session_id, None)
        assert is_cs_pubkey(caller_pubkey)
        self.log.info('{klass}.logout_member with caller pubkey {caller_pubkey})',
                      klass=self.__class__.__name__,
                      caller_pubkey=hlid(binascii.b2a_hex(caller_pubkey).decode()))

        with self._db.begin(write=True) as txn:
            del self._xbrmm.user_keys[txn, caller_pubkey]

        logout_info = {
            'logged_out': time_ns(),
            'from_session': caller_session_id,
            'pubkey': caller_pubkey,
        }

        def kill():
            self._market_session.call('wamp.session.kill_by_authid', call_details.caller_authid)
            self.log.info('Ok, session {caller_session} logged out for client with pubkey {caller_pubkey} ',
                          caller_session=hlid(caller_session_id),
                          caller_pubkey=hlid(binascii.b2a_hex(caller_pubkey).decode()))

        # first return from this call, before killing its session ..
        self._reactor.callLater(0, kill)

        return logout_info
