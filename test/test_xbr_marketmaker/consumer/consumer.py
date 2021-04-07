import os
import argparse
import six
import txaio
from pprint import pformat

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.util import sleep
from autobahn.wamp.types import RegisterOptions
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.exception import ApplicationError


class XBRConsumer(ApplicationSession):

    log = txaio.make_logger()

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info('XBRConsumer connected: {details}', details=details)

        self._xbr_prefix = 'xbr.consumer'

        def on_counter(enc_keyid, enc_data):
            self.log.info('event received for com.example.oncounter')

        yield self.subscribe(on_counter, 'com.example.oncounter')
        self.log.info('subscribed to topic "com.example.oncounter"')


if __name__ == '__main__':

    # Crossbar.io connection configuration
    url = os.environ.get('CBURL', u'ws://localhost:8080/ws')
    realm = os.environ.get('CBREALM', u'realm1')

    # parse command line parameters
    parser = argparse.ArgumentParser()

    parser.add_argument('-d',
                        '--debug',
                        action='store_true',
                        help='Enable debug output.')

    parser.add_argument('--url',
                        dest='url',
                        type=six.text_type,
                        default=url,
                        help='The router URL (default: "ws://localhost:8080/ws").')

    parser.add_argument('--realm',
                        dest='realm',
                        type=six.text_type,
                        default=realm,
                        help='The realm to join (default: "realm1").')

    parser.add_argument('--service_name',
                        dest='service_name',
                        type=six.text_type,
                        default=None,
                        help='Optional service name.')

    parser.add_argument('--service_uuid',
                        dest='service_uuid',
                        type=six.text_type,
                        default=None,
                        help='Optional service UUID.')

    args = parser.parse_args()

    # start logging
    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    # any extra info we want to forward to our ClientSession (in self.config.extra)
    extra = {
        u'service_name': args.service_name,
        u'service_uuid': args.service_uuid,
    }

    # now actually run a WAMP client using our session class ClientSession
    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra)
    runner.run(XBRConsumer, auto_reconnect=True)
