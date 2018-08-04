
from os import environ
import os
import argparse
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner


class ClientSession(ApplicationSession):
    """
    An application component using the time service.
    """

    @inlineCallbacks
    def onJoin(self, details):
        print("session attached")
        try:
            now = yield self.call(u'my.com.date')
        except Exception as e:
            print("Error: {}".format(e))
        else:
            print("Current time from time service: {}".format(now))

        self.leave()

    def onDisconnect(self):
        print("disconnected")
        reactor.stop()


if __name__ == '__main__':
    import six
    url = os.environ.get('CBURL', u'ws://localhost:8080/ws')
    realm = os.environ.get('CBREALM', u'realm1')

    # parse command line parameters
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output.')
    parser.add_argument('--url', dest='url', type=six.text_type, default=url, help='The router URL (default: "ws://localhost:8080/ws").')
    parser.add_argument('--realm', dest='realm', type=six.text_type, default=realm, help='The realm to join (default: "realm1").')

    args = parser.parse_args()
    # any extra info we want to forward to our ClientSession (in self.config.extra)
    extra = {
        u'foobar': u'A custom value'
    }
 
    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra)
    runner.run(ClientSession, auto_reconnect=True)

