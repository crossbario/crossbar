# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import sys
import copy
from uuid import UUID
import binascii
import argparse
from pprint import pformat

import eth_keys
import web3

import txaio
txaio.use_twisted()

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.serializer import CBORSerializer
from autobahn.wamp import cryptosign


class XbrDelegate(ApplicationSession):
    def __init__(self, config=None):
        self.log.info('{klass}.__init__(config={config})', klass=self.__class__.__name__, config=config)

        ApplicationSession.__init__(self, config)

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

            market_oids = await self.call('xbr.network.find_markets')
            self.log.info('SUCCESS: found {cnt_markets} markets owned by {member_adr}',
                          cnt_markets=len(market_oids),
                          member_adr=member_adr)

            # iterate over all markets ..
            for market_oid in market_oids:
                # retrieve market information including attributes
                self.log.info('xbr.network.get_market(market_oid={market_oid}) ..', market_oid=market_oid)
                market = await self.call('xbr.network.get_market', market_oid, include_attributes=True)

                self.log.info('SUCCESS: got market information, including attributes\n\n{market}\n',
                              market=pformat(market))
                # {'attributes': {'homepage': 'https://markets.international-data-monetization-award.com/',
                #                 'label': 'IDMA',
                #                 'title': 'International Data Monetization Award'},
                #  'consumer_security': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                #                       b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02'
                #                       b'\xb5\xe3\xaf\x16\xb1\x88\x00\x00',
                #  'maker': b"c\x93\xb2'V\xb8;qa\x1cmO\xfa\xc84\xa3\x9a&\x0b\xab",
                #  'market': b'\xc7s\xc1S"\xd2J\xbf\x94\xb1\xf5n=\xa0]\x91',
                #  'market_fee': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                #                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1b\xc1mg'
                #                b'N\xc8\x00\x00',
                #  'meta': 'QmRxJ6f13zqRKpuUF41vRpo6xuDYEkgZaP1xQxbamXxjHw',
                #  'owner': b'?\xd6R\xc9=\xfa39y\xadv,\xf5\x81\xdf\x89\xba\xbag\x95',
                #  'provider_security': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                #                       b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                #                       b'\x8a\xc7#\x04\x89\xe8\x00\x00',
                #  'seq': 0,
                #  'signature': None,
                #  'terms': 'QmeZcoR2BWjaX4gCT9ZhtegaKV9sZXsmwfThX7kfSs2aYD',
                #  'timestamp': 1583592135823895829}

                attributes = market.get('attributes', {})

                new_attributes = copy.copy(attributes)
                for k in new_attributes:
                    new_attributes[k] = 'UPDATED!! {}'.format(new_attributes[k])

                # now update the market attributes ..
                self.log.info('xbr.network.update_market(market_oid={market_oid}, attributes={attributes}) ..',
                              market_oid=market_oid,
                              attributes=new_attributes)
                await self.call('xbr.network.update_market', market_oid, new_attributes)

                # fetch market info again and verify the update has actually happened
                market = await self.call('xbr.network.get_market', market_oid, include_attributes=True)
                attributes = market.get('attributes', {})
                assert attributes == new_attributes

                self.log.info('SUCCESS: market updated!')

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
    }

    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra, serializers=[CBORSerializer()])

    try:
        runner.run(XbrDelegate, auto_reconnect=True)
    except Exception as e:
        print(e)
        sys.exit(1)
    else:
        sys.exit(0)
