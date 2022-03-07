# coding=utf8
# XBR Network - Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.

import six
import sys
import re
import binascii
import argparse
from pprint import pformat

import txaio
txaio.use_twisted()
from txaio import time_ns

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

from autobahn.twisted.util import sleep
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.serializer import CBORSerializer
from autobahn.wamp import cryptosign


class XbrDelegate(ApplicationSession):
    def __init__(self, config=None):
        self.log.info('{klass}.__init__(config={config})', klass=self.__class__.__name__, config=config)

        ApplicationSession.__init__(self, config)

        self._key = cryptosign.SigningKey.from_key_bytes(config.extra['cskey'])
        self.log.info("Client (delegate) WAMP-cryptosign authentication key loaded (pubkey={pubkey})",
                      pubkey=self._key.public_key())

        self._running = True

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
            # when we are not yet a member, the backend will authenticate us under authrole "anonymous"
            # and assign a randomly generated authid
            #
            assert details.authrole == 'anonymous'

            # eg "anonymous-GXCJ-JL5V-7CF4-9UNQ-7LGN-XEXL"
            _prefix = 'anonymous-'
            assert details.authid.startswith(_prefix)
            _suffix = details.authid[len(_prefix):]
            pat = re.compile(r"^[A-Z0-9]{4,4}-[A-Z0-9]{4,4}-[A-Z0-9]{4,4}-[A-Z0-9]{4,4}-[A-Z0-9]{4,4}-[A-Z0-9]{4,4}")
            assert pat.match(_suffix)

            # test API procedure "xbr.network.get_status"
            # https://xbr.network/docs/network/api.html#xbrnetwork.XbrNetworkApi.get_config
            await self._test_get_config()

            # test API procedure "xbr.network.get_status"
            # https://xbr.network/docs/network/api.html#xbrnetwork.XbrNetworkApi.get_status
            await self._test_get_status()

            # test API procedure "xbr.network.echo"
            # https://xbr.network/docs/network/api.html#xbrnetwork.XbrNetworkApi.echo
            await self._test_echo()

        except Exception as e:
            self.log.failure()
            self.config.extra['error'] = e
        finally:
            self.leave()

    async def _test_get_config(self):
        config = await self.call('xbr.network.get_config', include_eula_text=True)
        self.log.info('Backend config:\n\n{config}\n', config=pformat(config))

        assert type(config) == dict
        assert 'now' in config
        assert 'chain' in config
        assert 'contracts' in config
        assert 'eula' in config
        assert 'from' in config

        assert type(config['now']) == int and config['now'] > 0
        assert type(config['chain']) == int and config['chain'] > 0
        assert type(config['contracts']) == dict
        assert type(config['eula']) == dict
        assert type(config['from']) == str

        assert 'xbrtoken' in config['contracts']
        assert 'xbrnetwork' in config['contracts']
        assert type(config['contracts']['xbrtoken']) == str
        assert type(config['contracts']['xbrnetwork']) == str

        assert 'hash' in config['eula']
        assert 'url' in config['eula']
        assert 'text' in config['eula']
        assert type(config['eula']['hash']) == str
        assert type(config['eula']['url']) == str
        assert type(config['eula']['text']) == str

    async def _test_get_status(self):
        status = await self.call('xbr.network.get_status')
        self.log.info('Backend status:\n\n{status}\n', status=pformat(status))

        assert type(status) == dict
        assert 'now' in status
        assert 'status' in status
        assert 'chain' in status
        assert 'block' in status

        assert type(status['now']) == int and status['now'] > 0
        assert type(status['chain']) == int and status['chain'] > 0
        assert type(status['status']) == str and status['status'] == 'ready'
        assert type(status['block']) == dict

        assert 'number' in status['block'] and type(status['block']['number']) == int and status['block']['number'] > 0
        assert 'hash' in status['block'] and type(status['block']['hash']) == bytes and len(
            status['block']['hash']) == 32
        assert 'gas_limit' in status['block'] and type(
            status['block']['gas_limit']) == int and status['block']['gas_limit'] > 0

    async def _test_echo(self):
        counter = 1
        while self._running and counter < 6:
            msg = 'Hello {}'.format(counter)
            t1 = time_ns()
            res = await self.call('xbr.network.echo', counter, msg=msg)
            t2 = time_ns()
            assert res.results[0] == counter
            assert res.kwresults['msg'] == msg
            self.log.info('Echo result received in {duration} ms for counter value {counter}: {res}',
                          counter=counter,
                          res=res,
                          duration=int((t2 - t1) / 100000.) / 10.)
            counter += 1
            await sleep(1)

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
                        type=six.text_type,
                        default='ws://localhost:8080/ws',
                        help='The router URL (default: "ws://localhost:8080/ws").')

    parser.add_argument('--realm',
                        dest='realm',
                        type=six.text_type,
                        default='xbr',
                        help='The realm to join (default: "realm1").')

    parser.add_argument('--cskey',
                        dest='cskey',
                        type=six.text_type,
                        help='Private WAMP-cryptosign authentication key (32 bytes as HEX encoded string)')

    args = parser.parse_args()

    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    extra = {
        'cskey': binascii.a2b_hex(args.cskey),
    }

    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra, serializers=[CBORSerializer()])

    try:
        runner.run(XbrDelegate, auto_reconnect=True)
    except Exception as e:
        print(e)
        sys.exit(1)
    else:
        sys.exit(0)
