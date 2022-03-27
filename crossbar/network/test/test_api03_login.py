# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import os
import sys
import binascii
import argparse
import cbor2
from uuid import UUID
from pprint import pformat

import eth_keys

import txaio
txaio.use_twisted()

from txaio import time_ns
from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.serializer import CBORSerializer
from autobahn.wamp import cryptosign

from autobahn.xbr import sign_eip712_member_login


class XbrDelegate(ApplicationSession):
    def __init__(self, config=None):
        self.log.info('{klass}.__init__(config={config})', klass=self.__class__.__name__, config=config)

        ApplicationSession.__init__(self, config)

        self._verifications = config.extra['verifications']

        self._ethkey_raw = config.extra['ethkey']
        self._ethkey = eth_keys.keys.PrivateKey(self._ethkey_raw)
        self.log.info("Client (delegate) Ethereum key loaded (adr={adr})",
                      adr=self._ethkey.public_key.to_canonical_address())

        self._key = cryptosign.SigningKey.from_key_bytes(config.extra['cskey'])
        self.log.info("Client (delegate) WAMP-cryptosign authentication key loaded (pubkey={pubkey})",
                      pubkey=self._key.public_key())

        self._running = True

    def onUserError(self, fail, msg):
        self.log.error(msg)
        self.leave('wamp.error', msg)

    def onConnect(self):
        self.log.info('{klass}.onConnect()', klass=self.__class__.__name__)

        authextra = {
            'pubkey': self._key.public_key(),
            'trustroot': None,
            'challenge': None,
            'channel_binding': 'tls-unique'
        }
        self.join(self.config.realm, authmethods=['cryptosign'], authextra=authextra)

    def onChallenge(self, challenge):
        self.log.info('{klass}.onChallenge(challenge={challenge})', klass=self.__class__.__name__, challenge=challenge)

        if challenge.method == 'cryptosign':
            signed_challenge = self._key.sign_challenge(self, challenge)
            return signed_challenge
        else:
            raise RuntimeError('unable to process authentication method {}'.format(challenge.method))

    async def onJoin(self, details):
        self.log.info('{klass}.onJoin(details={details})', klass=self.__class__.__name__, details=details)

        try:
            # delegate ethereum private key object
            wallet_key = self._ethkey
            wallet_raw = self._ethkey_raw

            # delegate ethereum account canonical address
            wallet_adr = wallet_key.public_key.to_canonical_address()

            config = await self.call('xbr.network.get_config')
            status = await self.call('xbr.network.get_status')

            verifyingChain = config['verifying_chain_id']
            verifyingContract = binascii.a2b_hex(config['verifying_contract_adr'][2:])

            loggedIn = status['block']['number']
            timestamp = time_ns()

            member_email = self.config.extra['member_email']
            client_pubkey = binascii.a2b_hex(self._key.public_key())

            signature = sign_eip712_member_login(wallet_raw, verifyingChain, verifyingContract, wallet_adr, loggedIn,
                                                 timestamp, member_email, client_pubkey)

            # https://xbr.network/docs/network/api.html#xbrnetwork.XbrNetworkApi.login_member
            login_request_submitted = await self.call('xbr.network.login_member', member_email, client_pubkey,
                                                      verifyingChain, loggedIn, verifyingContract, timestamp,
                                                      wallet_adr, signature)
            self.log.info('login_request_submitted:\n{login_request_submitted}',
                          login_request_submitted=pformat(login_request_submitted))

            assert type(login_request_submitted) == dict
            assert 'vaction_oid' in login_request_submitted

            vaction_oid = login_request_submitted['vaction_oid']
            assert type(vaction_oid) == bytes and len(vaction_oid) == 16
            vaction_oid = UUID(bytes=vaction_oid)

            self.log.info('Login member - verification "{vaction_oid}" created', vaction_oid=vaction_oid)

            # fd = 'cloud/planet_xbr_crossbar/.crossbar/.verifications'
            fd = self._verifications
            if not os.path.isdir(fd):
                os.mkdir(fd)
            fn = 'login-member-email-verification.{}'.format(vaction_oid)
            verification_file = os.path.abspath(os.path.join(fd, fn))
            with open(verification_file, 'rb') as f:
                data = f.read()
                verified_data = cbor2.loads(data)

            self.log.info('Verified data:\n{verified_data}', verified_data=verified_data)

            vaction_code = verified_data['login_vcode']

            self.log.info('Verifying member using vaction_oid={vaction_oid}, vaction_code={vaction_code} ..',
                          vaction_oid=vaction_oid,
                          vaction_code=vaction_code)

            result = await self.call('xbr.network.verify_login_member', vaction_oid.bytes, vaction_code)

            assert type(result) == dict
            assert 'member_oid' in result
            assert type(result['member_oid']) == bytes and len(result['member_oid']) == 16
            member_oid = UUID(bytes=result['member_oid'])

            self.log.info('SUCCESS! Existing XBR Member logged in: member_oid={member_oid}', member_oid=member_oid)

        except Exception as e:
            self.log.failure()
            self.config.extra['error'] = e
        finally:
            self.leave()

    def onLeave(self, details):
        self.log.info('{klass}.onLeave(details={details})', klass=self.__class__.__name__, details=details)

        self._running = False

        if details.reason == 'wamp.close.normal':
            self.log.info('Shutting down ..')
            # user initiated leave => end the program
            self.config.runner.stop()
            self.disconnect()
        else:
            # continue running the program (let ApplicationRunner perform auto-reconnect attempts ..)
            self.log.info('Will continue to run (reconnect)!')

    def onDisconnect(self):
        self.log.info('{klass}.onDisconnect()', klass=self.__class__.__name__)

        try:
            reactor.stop()
        except ReactorNotRunning:
            pass


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output.')

    parser.add_argument('--url',
                        dest='url',
                        type=str,
                        default='ws://localhost:8080/ws',
                        help='The router URL (default: "ws://localhost:8080/ws").')

    parser.add_argument('--realm',
                        dest='realm',
                        type=str,
                        default='xbr',
                        help='The realm to join (default: "realm1").')

    parser.add_argument('--ethkey',
                        dest='ethkey',
                        type=str,
                        help='Private Ethereum key (32 bytes as HEX encoded string)')

    parser.add_argument('--cskey',
                        dest='cskey',
                        type=str,
                        help='Private WAMP-cryptosign authentication key (32 bytes as HEX encoded string)')

    parser.add_argument('--email',
                        dest='email',
                        type=str,
                        default='somebody@nodomain',
                        help='Member email address (the one used to register the member in the first place).')

    parser.add_argument('--verifications',
                        dest='verifications',
                        default='.crossbar/.verifications',
                        type=str,
                        help='XBR node verifications directory')

    parser.add_argument(
        '--wallet',
        dest='wallet',
        type=str,
        default='E11BA2b4D45Eaed5996Cd0823791E0C93114882d',
        help='HEX encoded member wallet address (the one used to register the member in the first place).')

    args = parser.parse_args()

    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    extra = {
        'ethkey': binascii.a2b_hex(args.ethkey),
        'cskey': binascii.a2b_hex(args.cskey),
        'member_email': args.email,
        'wallet_adr': args.wallet,
        'verifications': args.verifications,
    }

    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra, serializers=[CBORSerializer()])

    try:
        runner.run(XbrDelegate, auto_reconnect=True)
    except Exception as e:
        print(e)
        sys.exit(1)
    else:
        sys.exit(0)
