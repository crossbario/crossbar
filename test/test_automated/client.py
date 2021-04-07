import os
import binascii
import argparse

from twisted.internet.defer import inlineCallbacks
from twisted.internet.error import ReactorNotRunning

import txaio
txaio.use_twisted()

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.twisted.util import sleep
from autobahn.wamp.types import PublishOptions


class Client(ApplicationSession):
    # def onConnect(self):
    #     self.join(self.config.realm, ['ticket'], self.config.extra['authid'])
    #
    # def onChallenge(self, challenge):
    #     if challenge.method == 'ticket':
    #         return self.config.extra['ticket']
    #     else:
    #         raise RuntimeError('unable to process authentication method {}'.format(challenge.method))

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info("connected:  {details}", details=details)
        self._running = True

        topic_name = u"com.example.mytopic1"

        def _foo(*args, **kwargs):
            print("{}: {} {}".format(topic_name, args, kwargs))
            assert 'foo' in kwargs and type(kwargs['foo']) == str and len(kwargs['foo']) == 22
            assert 'baz' in kwargs and type(kwargs['baz']) == bytes and len(kwargs['baz']) == 10
            assert binascii.a2b_hex(kwargs['foo'][2:]) == kwargs['baz']

        self.subscribe(_foo, topic_name)
        print("subscribed")

        pid = os.getpid()
        counter = 0
        while self.is_connected():
            print("pid {} publish {} to '{}'".format(pid, counter, topic_name))
            data = os.urandom(10)
            yield self.publish(
                topic_name, pid, counter, foo='0x'+binascii.b2a_hex(data).decode(), baz=data,
                options=PublishOptions(acknowledge=True, exclude_me=False),
            )
            counter += 1
            yield sleep(1)

    async def onLeave(self, details):
        self.log.info("leaving: {}".format(details))
        self._running = False

        if details.reason == 'wamp.close.normal':
            self.log.info('Shutting down ..')
            # user initiated leave => end the program
            try:
                self.config.runner.stop()
                self.disconnect()
            except:
                self.log.failure()

            from twisted.internet import reactor
            if reactor.running:
                try:
                    reactor.stop()
                except ReactorNotRunning:
                    pass
        else:
            # continue running the program (let ApplicationRunner perform auto-reconnect attempts ..)
            self.log.info('Will continue to run (reconnect)!')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-d',
                        '--debug',
                        action='store_true',
                        help='Enable debug output.')
    parser.add_argument('--url',
                        dest='url',
                        type=str,
                        default='ws://localhost:8080/ws',
                        help='The router URL (default: "ws://localhost:8080/ws").')
    parser.add_argument('--realm',
                        dest='realm',
                        type=str,
                        default='myrealm1',
                        help='The realm to join (default: "myrealm1").')
    parser.add_argument('--authid',
                        dest='authid',
                        type=str,
                        default='backend',
                        help='Authentication ID to be used with WAMP-Ticket authentication (default: "backend")')
    parser.add_argument('--ticket',
                        dest='ticket',
                        type=str,
                        help='Secret (password) to be used with WAMP-Ticket authentication.')

    args = parser.parse_args()

    # start logging
    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    # any extra info we want to forward to our ClientSession (in self.config.extra)
    extra = {
        'authid': args.authid,
        'ticket': args.ticket,
    }

    print('Connecting to {}/{}@{} (ticket="{}")'.format(extra['authid'], args.realm, args.url, args.ticket))

    # now actually run a WAMP client using our session class ClientSession
    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra)
    runner.run(Client, auto_reconnect=True)
