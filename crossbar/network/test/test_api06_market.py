# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import sys
import os
from uuid import UUID
import binascii
import argparse
from pprint import pformat

import eth_keys
import web3
import hashlib
import multihash
import cbor2

import txaio
txaio.use_twisted()

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.serializer import CBORSerializer
from autobahn.wamp import cryptosign
from autobahn.xbr import sign_eip712_market_join

from cfxdb.xbr import ActorType


class XbrDelegate(ApplicationSession):
    def __init__(self, config=None):
        self.log.info('{klass}.__init__(config={config})', klass=self.__class__.__name__, config=config)

        ApplicationSession.__init__(self, config)

        self._verifications = config.extra['verifications']

        self._ethkey_raw = config.extra['ethkey']
        self._ethkey = eth_keys.keys.PrivateKey(self._ethkey_raw)
        self._ethadr = web3.Web3.toChecksumAddress(self._ethkey.public_key.to_canonical_address())

        self.log.info("Client (delegate) Ethereum key loaded (adr=0x{adr})", adr=self._ethadr)

        self._key = cryptosign.SigningKey.from_key_bytes(config.extra['cskey'])
        self.log.info("Client (delegate) WAMP-cryptosign authentication key loaded (pubkey=0x{pubkey})",
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
            assert details.authrole == 'member'

            # WAMP authid on xbrnetwork follows this format: "member-"
            member_id = details.authid[7:]
            member_id = UUID(member_id)

            member_data = await self.call('xbr.network.get_member', member_id.bytes)
            member_adr = member_data['address']

            config = await self.call('xbr.network.get_config')
            verifyingChain = config['verifying_chain_id']
            verifyingContract = binascii.a2b_hex(config['verifying_contract_adr'][2:])

            # remember the number of markets we joined before
            markets_by_actor_before = await self.call('xbr.network.get_markets_by_actor', member_id.bytes)
            cnt_markets_by_actor_before = len(markets_by_actor_before)

            # join the first market we find
            market_oids = await self.call('xbr.network.find_markets')
            assert len(market_oids) > 0, 'fatal: no markets defined that we could join'
            marketId = market_oids[0]

            for actorType in [ActorType.PROVIDER, ActorType.CONSUMER]:
                status = await self.call('xbr.network.get_status')
                block_number = status['block']['number']

                meta_obj = {}
                meta_data = cbor2.dumps(meta_obj)
                h = hashlib.sha256()
                h.update(meta_data)
                meta_hash = multihash.to_b58_string(multihash.encode(h.digest(), 'sha2-256'))

                signature = sign_eip712_market_join(self._ethkey_raw, verifyingChain, verifyingContract, member_adr,
                                                    block_number, marketId, actorType, meta_hash)

                request_submitted = await self.call('xbr.network.join_market', member_id.bytes, marketId,
                                                    verifyingChain, block_number, verifyingContract, actorType,
                                                    meta_hash, meta_data, signature)

                self.log.info(
                    'Join market request submitted (actorType={actorType}, member_id={member_id}, member_adr=0x{member_adr}): \n{request_submitted}\n',
                    member_id=member_id,
                    actorType=actorType,
                    member_adr=binascii.b2a_hex(member_adr).decode(),
                    request_submitted=pformat(request_submitted))

                assert type(request_submitted) == dict
                assert 'created' in request_submitted and type(
                    request_submitted['created']) == int and request_submitted['created'] > 0
                assert 'action' in request_submitted and request_submitted['action'] == 'join_market'
                assert 'vaction_oid' in request_submitted and type(request_submitted['vaction_oid']) == bytes and len(
                    request_submitted['vaction_oid']) == 16

                vaction_oid = UUID(bytes=request_submitted['vaction_oid'])
                self.log.info('Join market verification "{vaction_oid}" created', vaction_oid=vaction_oid)

                # fd = 'cloud/planet_xbr_crossbar/.crossbar/.verifications'
                fd = self._verifications
                if not os.path.isdir(fd):
                    os.mkdir(fd)
                fn = 'join-market-email-verification.{}'.format(vaction_oid)
                verification_file = os.path.abspath(os.path.join(fd, fn))
                with open(verification_file, 'rb') as f:
                    data = f.read()
                    verified_data = cbor2.loads(data)

                self.log.info('Verified data:\n{verified_data}', verified_data=verified_data)

                vaction_code = verified_data['vcode']

                self.log.info('Verifying join market using vaction_oid={vaction_oid}, vaction_code={vaction_code} ..',
                              vaction_oid=vaction_oid,
                              vaction_code=vaction_code)

                request_verified = await self.call('xbr.network.verify_join_market', vaction_oid.bytes, vaction_code)
                self.log.info('Join market request verified: \n{request_verified}\n',
                              request_verified=pformat(request_verified))

                assert type(request_verified) == dict
                assert 'market_oid' in request_verified and type(request_verified['market_oid']) == bytes and len(
                    request_verified['market_oid']) == 16
                assert 'created' in request_verified and type(
                    request_verified['created']) == int and request_verified['created'] > 0

                market_oid = request_verified['market_oid']
                self.log.info(
                    'SUCCESS! XBR market joined: market_oid={market_oid}, actor_type={actor_type}, result=\n{result}',
                    market_oid=UUID(bytes=market_oid),
                    actor_type=actorType,
                    result=pformat(request_verified))

            markets_by_actor_after = await self.call('xbr.network.get_markets_by_actor', member_id.bytes)
            cnt_markets_by_actor_after = len(markets_by_actor_after)
            cnt_new_joins = cnt_markets_by_actor_after - cnt_markets_by_actor_before

            print('markets_by_actor_before:     ', markets_by_actor_before)
            print('markets_by_actor_after:      ', markets_by_actor_after)
            print('cnt_markets_by_actor_before: ', cnt_markets_by_actor_before)
            print('cnt_markets_by_actor_after:  ', cnt_markets_by_actor_after)
            print('cnt_new_joins:               ', cnt_new_joins)

            # assert cnt_new_joins == 1, 'expected 1 market, but found {} new ones!'.format(cnt_new_joins)
            # assert market_oid in market_oids, 'expected to find market ID {}, but not found in {} returned market IDs'.format(UUID(bytes=market_oid), len(market_oids))

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
