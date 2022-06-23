from __future__ import print_function

import os
import argparse
import six
import txaio
import random

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import inlineCallbacks, DeferredList

from autobahn.twisted.util import sleep
from autobahn.wamp.types import RegisterOptions, PublishOptions
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.exception import ApplicationError


class ClientSession(ApplicationSession):

    @inlineCallbacks
    def test2(self):
        """
        The following produces this trace:

        https://gist.githubusercontent.com/oberstet/510b1d5d1fe6a65f78d439dc6b678c33/raw/2a9c6959db987716d3ccbc20c5bec5ccb146aee9/gistfile1.txt
        """

        # unacked publish to topic with no subscribers
        #
        topic = u'com.example.r{}'.format(random.randint(0, 10000))
        self.publish(topic, u'hey')

        # acked publish to topic with no subscribers
        #
        topic = u'com.example.r{}'.format(random.randint(0, 10000))
        yield self.publish(topic, u'hey', options=PublishOptions(acknowledge=True))

        # unacked publish to topic with 1 subscriber (ourself)
        #
        topic = u'com.example.r{}'.format(random.randint(0, 10000))
        sub = yield self.subscribe(lambda msg: print(msg), topic)
        self.publish(topic, u'hey', options=PublishOptions(exclude_me=False))

        # acked publish to topic with 1 subscriber (ourself)
        #
        topic = u'com.example.r{}'.format(random.randint(0, 10000))
        sub = yield self.subscribe(lambda msg: print(msg), topic)
        yield self.publish(topic, u'hey', options=PublishOptions(acknowledge=True, exclude_me=False))

        # resubscribe to a topic we are already subscribed to
        #
        sub = yield self.subscribe(lambda msg: print(msg), topic)

    @inlineCallbacks
    def test1(self):
        """
        The following produces this trace when ran alone (only one instance of the component):

        https://gist.githubusercontent.com/oberstet/4280447fe9b6691819a7287f5b0f9663/raw/76932f731cc54a8cbc3e8f5b32b145f3e493f9f2/gistfile1.txt

        and produces this trace when 2 instances are run in parallel:

        https://gist.githubusercontent.com/oberstet/21bbd4f66c04a767627576ff92a05eee/raw/51b5ca58e4a44f76dba42654b0b0b37006592829/gistfile1.txt
        """
        # REGISTER
        def add2(a, b):
            print('----------------------------')
            print("add2 called on {}".format(self._ident))
            return [ a + b, self._ident, self._type]

        reg = yield self.register(add2,
                                  u'com.example.add2',
                                  options=RegisterOptions(invoke=u'random'))
        print('----------------------------')
        print('procedure registered: com.myexample.add2')

        # SUBSCRIBE
        def oncounter(counter, id, type):
            print('----------------------------')
            self.log.info("'oncounter' event, counter value: {counter} from component {id} ({type})", counter=counter, id=id, type=type)

        sub = yield self.subscribe(oncounter, u'com.example.oncounter')
        print('----------------------------')
        self.log.info("subscribed to topic 'oncounter'")

        x = 0
        counter = 0
        while counter < 5 or True:

            # CALL
            try:
                res = yield self.call(u'com.example.add2', x, 3)
                print('----------------------------')
                self.log.info("add2 result: {result} from {callee} ({callee_type})", result=res[0], callee=res[1], callee_type=res[2])
                x += 1
            except ApplicationError as e:
                ## ignore errors due to the frontend not yet having
                ## registered the procedure we would like to call
                if e.error != 'wamp.error.no_such_procedure':
                    raise e

            # PUBLISH
            published = []
            for i in range(1):
                yield published.append(self.publish(u'com.example.oncounter', counter, self._ident, self._type, options=PublishOptions(acknowledge=True, exclude_me=False)))
            #yield DeferredList(published)
            print('----------------------------')
            self.log.info("published to 'oncounter' with counter {counter}",
                          counter=counter)
            counter += 1

            yield sleep(1)

        yield reg.unregister()
        yield sub.unsubscribe()

        self.leave()

    @inlineCallbacks
    def onJoin(self, details):

        self.log.info("Connected:  {details}", details=details)

        self._ident = details.authid
        self._type = u'Python'

        self.log.info("Component ID is  {ident}", ident=self._ident)
        self.log.info("Component type is  {type}", type=self._type)

        yield self.test1()
        #yield self.test2()


if __name__ == '__main__':

    # Crossbar.io connection configuration
    url = u'ws://localhost:8080/ws'
    realm = u'realm1'

    # parse command line parameters
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true', default=False, help='Enable debug output.')
    parser.add_argument('--url', dest='url', type=six.text_type, default=url, help='The router URL (default: "ws://localhost:8080/ws").')
    parser.add_argument('--realm', dest='realm', type=six.text_type, default=realm, help='The realm to join (default: "realm1").')
    parser.add_argument('--service', dest='service', type=six.text_type, default=u'unknown', help='The service name.')

    args = parser.parse_args()

    # start logging
    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    # any extra info we want to forward to our ClientSession (in self.config.extra)
    extra = {
        u'authextra': {
            u'service': args.service
        }
    }

    print('connecting to {}@{}'.format(realm, url))

    # now actually run a WAMP client using our session class ClientSession
    runner = ApplicationRunner(url=args.url, realm=args.realm, extra=extra)
    runner.run(ClientSession, auto_reconnect=False)
