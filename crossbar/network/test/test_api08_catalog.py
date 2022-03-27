# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import sys
from uuid import UUID
import binascii
import argparse
import os
import uuid
from pprint import pformat

import cbor2
import eth_keys
import web3

import txaio
txaio.use_twisted()

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.serializer import CBORSerializer
from autobahn.wamp import cryptosign, ApplicationError
from autobahn.xbr import sign_eip712_catalog_create


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

            # delegate ethereum private key object
            wallet_key = self._ethkey
            wallet_raw = self._ethkey_raw

            # delegate ethereum account canonical address
            wallet_adr = wallet_key.public_key.to_canonical_address()

            config = await self.call('xbr.network.get_config')
            status = await self.call('xbr.network.get_status')

            verifyingChain = config['verifying_chain_id']
            verifyingContract = binascii.a2b_hex(config['verifying_contract_adr'][2:])

            created = status['block']['number']
            # FIXME: Where to get ?
            terms_hash = config['eula']['hash']
            catalog_id = uuid.uuid4().bytes

            # https://ipfs.infura.io:5001/api/v0/cat?arg=QmenatrFHG1m5YSsRbCmoLyvVU4JX1fkbr9X7XM8FFSr1h
            meta_hash = 'QmenatrFHG1m5YSsRbCmoLyvVU4JX1fkbr9X7XM8FFSr1h'

            signature = sign_eip712_catalog_create(wallet_raw, verifyingChain, verifyingContract, wallet_adr, created,
                                                   catalog_id, terms_hash, meta_hash)

            # https://xbr.network/docs/network/api.html#xbrnetwork.XbrNetworkApi.onboard_member
            try:
                result = await self.call('xbr.network.create_catalog', member_id.bytes, catalog_id, verifyingChain,
                                         created, verifyingContract, terms_hash, meta_hash, None, signature, None)
                self.log.info("create_catalog results:\n\n{result}\n", result=pformat(result))
            except ApplicationError as e:
                self.log.error('ApplicationError: {error}', error=e)
                self.leave('wamp.error', str(e))
                return
            except Exception as e:
                raise e

            assert type(result) == dict
            assert 'created' in result and type(result['created']) == int and result['created'] > 0
            assert 'action' in result and result['action'] == 'create_catalog'
            assert 'vaction_oid' in result and type(result['vaction_oid']) == bytes and len(
                result['vaction_oid']) == 16

            vaction_oid = uuid.UUID(bytes=result['vaction_oid'])
            self.log.info('Create catalog - verification "{vaction_oid}" created', vaction_oid=vaction_oid)

            # fd = 'cloud/planet_xbr_crossbar/.crossbar/.verifications'
            fd = self._verifications
            if not os.path.isdir(fd):
                os.mkdir(fd)
            fn = 'create-catalog-email-verification.{}'.format(vaction_oid)
            verification_file = os.path.abspath(os.path.join(fd, fn))
            with open(verification_file, 'rb') as f:
                data = f.read()
                verified_data = cbor2.loads(data)

            self.log.info('Verified data:\n{verified_data}\n', verified_data=pformat(verified_data))

            vaction_code = verified_data['vcode']

            self.log.info('Verifying member using vaction_oid={vaction_oid}, vaction_code={vaction_code} ..',
                          vaction_oid=vaction_oid,
                          vaction_code=vaction_code)

            try:
                result = await self.call('xbr.network.verify_create_catalog', vaction_oid.bytes, vaction_code)
            except ApplicationError as e:
                self.log.error('ApplicationError: {error}', error=e)
                raise e

            assert type(result) == dict
            assert 'member_oid' in result and type(result['member_oid']) == bytes and len(result['member_oid']) == 16
            assert 'catalog_oid' in result and type(result['catalog_oid']) == bytes and len(
                result['catalog_oid']) == 16

            catalog_oid = result['catalog_oid']
            member_oid = result['member_oid']
            self.log.info(
                'SUCCESS! New XBR Catalog Created: member_oid={member_oid}, catalog_oid={catalog_id}, '
                'result: {result}\n',
                member_oid=uuid.UUID(bytes=member_oid).__str__(),
                catalog_id=uuid.UUID(bytes=catalog_oid).__str__(),
                result=pformat(result))

            # Lets see if we can now fetch the newly created catalog
            try:
                result = await self.call('xbr.network.get_catalog', catalog_oid)
            except ApplicationError as e:
                self.log.error('ApplicationError: {error}', error=e)
                raise e

            assert type(result) == dict
            assert 'oid' in result and type(result['oid']) == bytes and result['oid'] == catalog_oid
            assert 'owner' in result and type(result['owner']) == bytes and result['owner'] == member_adr

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
