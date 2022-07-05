# coding=utf8

##############################################################################
#
#                        Crossbar.io
#     Copyright (C) Crossbar.io Technologies GmbH. All rights reserved.
#
##############################################################################

import os
import binascii
from typing import Optional

import zlmdb

from autobahn.wamp import register
from autobahn.util import generate_serial_number
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.types import CallDetails

from cfxdb.xbrnetwork.schema import Schema


class Authenticator(ApplicationSession):

    ERROR_INVALID_AUTH_REQUEST = 'xbr.network.error.invalid-auth-request'
    ERROR_INVALID_AUTH_REQUEST_MSG = 'invalid parameter(s) in authentication request: {}'

    def __init__(self, config):
        ApplicationSession.__init__(self, config)

        # ZLMDB database configuration
        #
        self._dbpath = os.path.abspath(config.extra.get('dbpath', './.xbrnetwork'))
        # self._db = zlmdb.Database(dbpath=self._dbpath, maxsize=2**30, readonly=False, sync=True, context=self)
        self._db = zlmdb.Database.open(dbpath=self._dbpath, maxsize=2**30, readonly=False, sync=True, context=self)
        self._db.__enter__()
        self._schema = Schema.attach(self._db)

        self._pubkey_by_session = {}
        self._member_by_session = {}
        self._sessions_by_member = {}

        with self._db.begin() as txn:
            cnt_user_keys = self._schema.user_keys.count(txn)

        self.log.info('Database opened from {dbpath} (cnt_user_keys={cnt_user_keys})',
                      dbpath=self._dbpath,
                      cnt_user_keys=cnt_user_keys)

    async def onJoin(self, details):
        regs = await self.register(self)
        for reg in regs:
            self.log.info('{klass} registered procedure {proc}', klass=self.__class__.__name__, proc=reg.procedure)

    @register('xbr.network.authenticator.sessions_by_member')
    def _sessions_by_member(self, member_oid: bytes, details: Optional[CallDetails] = None) -> int:
        return self._sessions_by_member.get(member_oid, None)

    @register('xbr.network.authenticator.member_by_session')
    def _pubkey_by_session(self, session_id: int, details: Optional[CallDetails] = None) -> bytes:
        return self._member_by_session.get(session_id, None)

    @register('xbr.network.authenticator.pubkey_by_session')
    def _member_by_session(self, session_id: int, details: Optional[CallDetails] = None) -> bytes:
        return self._pubkey_by_session.get(session_id, None)

    @register('xbr.network.authenticator.authenticate')
    async def _authenticate(self, realm, authid, details):
        self.log.info('{klass}.authenticate(realm="{realm}", authid="{authid}", details={details})',
                      klass=self.__class__.__name__,
                      realm=realm,
                      authid=authid,
                      details=details)

        if 'authmethod' not in details:
            msg = 'missing "authmethod" in authentication details (WAMP HELLO message details)'
            raise ApplicationError(self.ERROR_INVALID_AUTH_REQUEST, self.ERROR_INVALID_AUTH_REQUEST_MSG.format(msg))

        authmethod = details['authmethod']

        if authmethod not in ['cryptosign']:
            msg = 'authmethod "{}" not permissible'.format(authmethod)
            raise ApplicationError(self.ERROR_INVALID_AUTH_REQUEST, self.ERROR_INVALID_AUTH_REQUEST_MSG.format(msg))

        if 'authextra' not in details or 'pubkey' not in details['authextra']:
            msg = 'missing public key in authextra for authmethod cryptosign'
            raise ApplicationError(self.ERROR_INVALID_AUTH_REQUEST, self.ERROR_INVALID_AUTH_REQUEST_MSG.format(msg))
        pubkey = details['authextra']['pubkey']
        pubkey_raw = binascii.a2b_hex(pubkey)
        assert type(pubkey_raw) == bytes and len(pubkey_raw) == 32

        session_id = details['session']
        assert type(session_id) == int

        with self._db.begin() as txn:
            # double check (again) for username collision, as the mailgun email submit happens async in above after
            # we initially checked for collision
            user_key = self._schema.user_keys[txn, pubkey_raw]
            if user_key:
                account = self._schema.accounts[txn, user_key.owner]
                authrole = 'member'
                # authid = account.username
                authid = 'member-{}'.format(account.oid)
            else:
                account = None
                authrole = 'anonymous'
                authid = 'anonymous-{}'.format(generate_serial_number())

            self._pubkey_by_session[session_id] = pubkey_raw
            if account:
                self._member_by_session[session_id] = account.oid
                if account.oid not in self._sessions_by_member:
                    self._sessions_by_member[account.oid] = []
                self._sessions_by_member[account.oid].append(session_id)

        auth = {'pubkey': pubkey, 'realm': realm, 'authid': authid, 'role': authrole, 'extra': None, 'cache': True}

        self.log.info('{klass}.authenticate(..) => {auth}', klass=self.__class__.__name__, auth=auth)

        return auth
