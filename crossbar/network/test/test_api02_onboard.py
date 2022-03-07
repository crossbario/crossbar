# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import os
import binascii
import argparse
import uuid
import cbor2
from pprint import pformat

import txaio
txaio.use_twisted()

import hashlib
import multihash

import eth_keys

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.exception import ApplicationError
from autobahn.wamp.serializer import CBORSerializer
from autobahn.wamp import cryptosign
from autobahn.xbr import sign_eip712_member_register


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
        self.log.info('>>>>>>>>>>>>>>>> onUserError:')
        print(fail)
        print(msg)
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
            member_username = self.config.extra['username']
            member_email = self.config.extra['email']
            client_pubkey = binascii.a2b_hex(self._key.public_key())

            # fake wallet type "metamask"
            wallet_type = 'metamask'

            # delegate ethereum private key object
            wallet_key = self._ethkey
            wallet_raw = self._ethkey_raw

            # delegate ethereum account canonical address
            wallet_adr = wallet_key.public_key.to_canonical_address()

            config = await self.call('xbr.network.get_config')
            status = await self.call('xbr.network.get_status')

            verifyingChain = config['verifying_chain_id']
            verifyingContract = binascii.a2b_hex(config['verifying_contract_adr'][2:])

            registered = status['block']['number']
            eula = config['eula']['hash']

            # create an aux-data object with info only stored off-chain (in our xbrbackend DB) ..
            profile_obj = {
                'member_username': member_username,
                'member_email': member_email,
                'client_pubkey': client_pubkey,
                'wallet_type': wallet_type,
            }

            # .. hash the serialized aux-data object ..
            profile_data = cbor2.dumps(profile_obj)
            h = hashlib.sha256()
            h.update(profile_data)

            # .. compute the sha256 multihash b58-encoded string from that ..
            profile = multihash.to_b58_string(multihash.encode(h.digest(), 'sha2-256'))

            signature = sign_eip712_member_register(wallet_raw, verifyingChain, verifyingContract, wallet_adr,
                                                    registered, eula, profile)

            # https://xbr.network/docs/network/api.html#xbrnetwork.XbrNetworkApi.onboard_member
            try:
                result = await self.call('xbr.network.onboard_member', member_username, member_email, client_pubkey,
                                         wallet_type, wallet_adr, verifyingChain, registered, verifyingContract, eula,
                                         profile, profile_data, signature)
            except ApplicationError as e:
                self.log.error('ApplicationError: {error}', error=e)
                self.leave('wamp.error', str(e))
                return
            except Exception as e:
                raise e

            assert type(result) == dict
            assert 'timestamp' in result and type(result['timestamp']) == int and result['timestamp'] > 0
            assert 'action' in result and result['action'] == 'onboard_member'
            assert 'vaction_oid' in result and type(result['vaction_oid']) == bytes and len(
                result['vaction_oid']) == 16

            vaction_oid = uuid.UUID(bytes=result['vaction_oid'])
            self.log.info('On-boarding member - verification "{vaction_oid}" created', vaction_oid=vaction_oid)

            # fd = 'cloud/planet_xbr_crossbar/.crossbar/.verifications'
            fd = self._verifications
            if not os.path.isdir(fd):
                os.mkdir(fd)
            fn = 'onboard-member-email-verification.{}'.format(vaction_oid)
            verification_file = os.path.abspath(os.path.join(fd, fn))
            with open(verification_file, 'rb') as f:
                data = f.read()
                verified_data = cbor2.loads(data)

            self.log.info('Verified data:\n{verified_data}', verified_data=verified_data)

            vaction_code = verified_data['onboard_vcode']

            self.log.info('Verifying member using vaction_oid={vaction_oid}, vaction_code={vaction_code} ..',
                          vaction_oid=vaction_oid,
                          vaction_code=vaction_code)

            try:
                result = await self.call('xbr.network.verify_onboard_member', vaction_oid.bytes, vaction_code)
            except ApplicationError as e:
                self.log.error('ApplicationError: {error}', error=e)
                raise e

            assert type(result) == dict
            assert 'member_oid' in result and type(result['member_oid']) == bytes and len(result['member_oid']) == 16
            assert 'created' in result and type(result['created']) == int and result['created'] > 0

            member_oid = result['member_oid']
            self.log.info('SUCCESS! New XBR Member onboarded: member_oid={member_oid}, result=\n{result}',
                          member_oid=uuid.UUID(bytes=member_oid),
                          result=pformat(result))

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

    parser.add_argument('--username',
                        dest='username',
                        default='somebody',
                        type=str,
                        help='XBR network member: username')

    parser.add_argument('--email', dest='email', default=None, type=str, help='XBR network member: email')

    parser.add_argument('--verifications',
                        dest='verifications',
                        default='.crossbar/.verifications',
                        type=str,
                        help='XBR node verifications directory')

    args = parser.parse_args()

    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    if not args.email:
        args.email = '{}@nodomain'.format(args.username)

    extra = {
        'ethkey': binascii.a2b_hex(args.ethkey),
        'cskey': binascii.a2b_hex(args.cskey),
        'username': args.username,
        'email': args.email,
        'verifications': args.verifications,
    }

    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra, serializers=[CBORSerializer()])
    runner.run(XbrDelegate, auto_reconnect=True)
