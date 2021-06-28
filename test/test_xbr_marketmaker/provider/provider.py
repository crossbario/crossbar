import os
import argparse
import six
import txaio
from pprint import pformat
import json

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import inlineCallbacks

from autobahn import wamp

from autobahn.twisted.util import sleep
from autobahn.wamp.types import RegisterOptions, PublishOptions
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.exception import ApplicationError


class XBRKey(object):

    def __init__(self, price):
        self.id = None
        self.seq = 0
        self.price = price
        self.rotate()

    def id(self):
        return self.id + self.seq

    def rotate(self):
        self.priv = os.urandom(32)
        self.seq += 1

    def encrypt(self, data):
        # FIXME: use pynacl/cryptobox
        enc_id, enc_data = None, data
        return enc_id, enc_data


class XBRRing(object):

    def __init__(self, session):
        self._session = session
        self._keys = {}

    @wamp.register(None)
    def quote(self, key_id, details=None):
        if key_id not in self._keys:
            raise Exception('no such key')
        key = self._keys[key_id]
        return key.price

    @wamp.register(None)
    def buy(self, key_id, credits, details=None):
        if key_id not in self._keys:
            raise Exception('no such key')
        key = self._keys[key_id]

        # FIXME: check market maker and consumer signatures
        # FIXME: encrypt private key to consumer public key
        # FIXME: underwrite transaction and send back

        raise Exception('XBRRing.buy: not implemented')

    def issue_key(self, price):
        if type(price) not in six.integer_types or price < 1 or price > 1000:
            raise Exception('invalid price')
        key = XBRKey(price)
        self._keys[key.id] = key
        return key

    def rotate_key(self, key_id, retire=False):
        if key_id not in self._keys:
            raise Exception('no such key')

        key = self._keys[key_id]
        key.rotate()

        # FIXME: call market maker and stop selling key
        return key.seq


class XBRProducer(ApplicationSession):

    log = txaio.make_logger()

    @inlineCallbacks
    def onJoin(self, details):
        self.log.info('XBRProducer connected: {details}', details=details)

        self._xbr_prefix = 'xbr.producer'

        self._xbr_keyring = XBRRing(self)
        yield self.register(self._xbr_keyring, self._xbr_prefix, options=RegisterOptions(details_arg='details'))

        enc_key = self._xbr_keyring.issue_key(10)

        #price_quote = yield self.call('xbr.maker.quote', 'key123')
        #self.log.info('GOT PRICE QUOTE!!! {price_quote}', price_quote=price_quote)

        counter = 0
        while True:
            # event payload to publish
            obj = {
                'cnt_sq': counter * counter,
                'msg': 'Hello, world! This is my message {}'.format(counter)
            }

            # serialize to bytes
            data = json.dumps(obj, ensure_ascii=False).encode('utf8')

            # encrypt event payload with current enc_key
            enc_keyid, enc_data = enc_key.encrypt(data)

            # publish encrypted payload
            yield self.publish('com.example.oncounter',
                               enc_keyid,
                               enc_data,
                               options=PublishOptions(acknowledge=True))

            self.log.info('counter {counter}', counter=counter)

            # rotate key every 100 publications
            counter += 1
            if counter % 100 == 0:
                yield enc_key.rotate()
                self.log.info('key rotated: {seq}', seq=enc_key.seq)

            # publish every 200ms
            yield sleep(.2)


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
    runner.run(XBRProducer, auto_reconnect=True)
