# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import sys
import os
import random
import uuid
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

from autobahn.xbr import pack_uint256
from autobahn.xbr import sign_eip712_market_create


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

            coin_adr = binascii.a2b_hex(config['contracts']['xbrtoken'][2:])

            status = await self.call('xbr.network.get_status')
            block_number = status['block']['number']

            # count all markets before we create a new one:
            res = await self.call('xbr.network.find_markets')
            cnt_market_before = len(res)

            res = await self.call('xbr.network.get_markets_by_owner', member_id.bytes)
            cnt_market_by_owner_before = len(res)

            # create a new market ..
            market_oid = uuid.uuid4()

            # collect information for market creation that is stored on-chain

            # terms text: encode in utf8 and compute BIP58 multihash string
            terms_data = 'these are my market terms (randint={})'.format(random.randint(0, 1000)).encode('utf8')
            h = hashlib.sha256()
            h.update(terms_data)
            terms_hash = str(multihash.to_b58_string(multihash.encode(h.digest(), 'sha2-256')))

            # market maker address
            maker = os.urandom(20)

            # provider and consumer security
            provider_security = 0 * 10**18
            consumer_security = 0 * 10**18

            # market operator fee
            market_fee = 0 * 10**18

            # market meta data that doesn't change. the hash of this is part of the data that is signed and also
            # stored on-chain (only the hash, not the meta data!)
            meta_obj = {
                'chain_id': verifyingChain,
                'block_number': block_number,
                'contract_adr': verifyingContract,
                'member_adr': member_adr,
                'member_oid': member_id.bytes,
                'market_oid': market_oid.bytes,
            }
            meta_data = cbor2.dumps(meta_obj)
            h = hashlib.sha256()
            h.update(meta_data)
            meta_hash = multihash.to_b58_string(multihash.encode(h.digest(), 'sha2-256'))

            # create signature for pre-signed transaction
            signature = sign_eip712_market_create(self._ethkey_raw, verifyingChain, verifyingContract, member_adr,
                                                  block_number, market_oid.bytes, coin_adr, terms_hash, meta_hash,
                                                  maker, provider_security, consumer_security, market_fee)

            # for wire transfer, convert to bytes
            provider_security = pack_uint256(provider_security)
            consumer_security = pack_uint256(consumer_security)
            market_fee = pack_uint256(market_fee)

            # market settings that can change. even though changing might require signing, neither the data nor
            # and signatures are stored on-chain. however, even when only signed off-chain, this establishes
            # a chain of signature anchored in the on-chain record for this market!
            attributes = {
                'title': 'International Data Monetization Award',
                'label': 'IDMA',
                'homepage': 'https://markets.international-data-monetization-award.com/',
            }

            # now provide everything of above:
            #   - market operator (owning member) and market oid
            #   - signed market data and signature
            #   - settings
            createmarket_request_submitted = await self.call('xbr.network.create_market', member_id.bytes,
                                                             market_oid.bytes, verifyingChain, block_number,
                                                             verifyingContract, coin_adr, terms_hash, meta_hash,
                                                             meta_data, maker, provider_security, consumer_security,
                                                             market_fee, signature, attributes)

            self.log.info('Create market request submitted: \n{createmarket_request_submitted}\n',
                          createmarket_request_submitted=pformat(createmarket_request_submitted))

            assert type(createmarket_request_submitted) == dict
            assert 'timestamp' in createmarket_request_submitted and type(
                createmarket_request_submitted['timestamp']) == int and createmarket_request_submitted['timestamp'] > 0
            assert 'action' in createmarket_request_submitted and createmarket_request_submitted[
                'action'] == 'create_market'
            assert 'vaction_oid' in createmarket_request_submitted and type(
                createmarket_request_submitted['vaction_oid']) == bytes and len(
                    createmarket_request_submitted['vaction_oid']) == 16

            vaction_oid = UUID(bytes=createmarket_request_submitted['vaction_oid'])
            self.log.info('Create market verification "{vaction_oid}" created', vaction_oid=vaction_oid)

            # fd = 'cloud/planet_xbr_crossbar/.crossbar/.verifications'
            fd = self._verifications
            if not os.path.isdir(fd):
                os.mkdir(fd)
            fn = 'create-market-email-verification.{}'.format(vaction_oid)
            verification_file = os.path.abspath(os.path.join(fd, fn))
            with open(verification_file, 'rb') as f:
                data = f.read()
                verified_data = cbor2.loads(data)

            self.log.info('Verified data:\n{verified_data}', verified_data=verified_data)

            vaction_code = verified_data['vcode']

            self.log.info('Verifying create market using vaction_oid={vaction_oid}, vaction_code={vaction_code} ..',
                          vaction_oid=vaction_oid,
                          vaction_code=vaction_code)

            create_market_request_verified = await self.call('xbr.network.verify_create_market', vaction_oid.bytes,
                                                             vaction_code)

            self.log.info('Create market request verified: \n{create_market_request_verified}\n',
                          create_market_request_verified=pformat(create_market_request_verified))

            assert type(create_market_request_verified) == dict
            assert 'market_oid' in create_market_request_verified and type(
                create_market_request_verified['market_oid']) == bytes and len(
                    create_market_request_verified['market_oid']) == 16
            assert 'created' in create_market_request_verified and type(
                create_market_request_verified['created']) == int and create_market_request_verified['created'] > 0

            market_oid = create_market_request_verified['market_oid']
            self.log.info('SUCCESS! New XBR market created: market_oid={market_oid}, result=\n{result}',
                          market_oid=UUID(bytes=market_oid),
                          result=pformat(create_market_request_verified))

            market_oids = await self.call('xbr.network.find_markets')
            self.log.info('SUCCESS - find_markets: found {cnt_markets} markets', cnt_markets=len(market_oids))

            # count all markets after we created a new market:
            cnt_market_after = len(market_oids)
            cnt_new_markets = cnt_market_after - cnt_market_before

            assert cnt_new_markets == 1, 'expected 1 market, but found {} new ones!'.format(cnt_new_markets)
            assert market_oid in market_oids, 'expected to find market ID {}, but not found in {} returned market IDs'.format(
                UUID(bytes=market_oid), len(market_oids))

            market_oids = await self.call('xbr.network.get_markets_by_owner', member_id.bytes)
            self.log.info('SUCCESS - get_markets_by_owner: found {cnt_markets} markets', cnt_markets=len(market_oids))

            # count all markets after we created a new market:
            cnt_market_by_owner_after = len(market_oids)
            cnt_new_markets_by_owner = cnt_market_by_owner_after - cnt_market_by_owner_before

            assert cnt_new_markets_by_owner == 1, 'expected 1 market, but found {} new ones!'.format(
                cnt_new_markets_by_owner)
            assert market_oid in market_oids, 'expected to find market ID {}, but not found in {} returned market IDs'.format(
                UUID(bytes=market_oid), len(market_oids))

            for market_oid in market_oids:
                self.log.info('xbr.network.get_market(market_oid={market_oid}) ..', market_oid=market_oid)
                market = await self.call('xbr.network.get_market', market_oid, include_attributes=True)
                self.log.info('SUCCESS: got market information\n\n{market}\n', market=pformat(market))

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

    parser.add_argument(
        '--wallet',
        dest='wallet',
        type=str,
        default='E11BA2b4D45Eaed5996Cd0823791E0C93114882d',
        help='HEX encoded member wallet address (the one used to register the member in the first place).')

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
