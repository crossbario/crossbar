import os
import argparse
import six
import txaio

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import inlineCallbacks, DeferredList

from autobahn.twisted.util import sleep
from autobahn.wamp.types import RegisterOptions, PublishOptions
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.exception import ApplicationError


class ClientSession(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):

        self.log.info("Connected:  {details}", details=details)

        self._ident = details.authid
        self._type = u'Python'

        self.log.info("Component ID is  {ident}", ident=self._ident)
        self.log.info("Component type is  {type}", type=self._type)

        # REGISTER
        def add2(a, b):
            print('----------------------------')
            print("add2 called on {}".format(self._ident))
            return [ a + b, self._ident, self._type]

        yield self.register(add2, u'com.example.add2', options=RegisterOptions(invoke=u'roundrobin'))
        print('----------------------------')
        print('procedure registered: com.myexample.add2')

        # SUBSCRIBE
        self._kk = 0
        def oncounter(counter, id, type):
            self._kk += 1
            if self._kk % 1000 == 0:
                self._kk = 0
                print('----------------------------')
                self.log.info("'oncounter' event, counter value: {counter} from component {id} ({type})", counter=counter, id=id, type=type)

        yield self.subscribe(oncounter, u'com.example.oncounter')
        print('----------------------------')
        self.log.info("subscribed to topic 'oncounter'")

        x = 0
        counter = 0
        while True:

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
                yield self.publish(u'com.example.oncounter', counter, self._ident, self._type, options=PublishOptions(acknowledge=True, exclude_me=False))
                #published.append(self.publish(u'com.example.oncounter', counter, self._ident, self._type, options=PublishOptions(acknowledge=True, exclude_me=False)))
                counter += 1
            #yield DeferredList(published)
            print('----------------------------')
            self.log.info("published to 'oncounter' with counter {counter}",
                          counter=counter)
            yield sleep(2)



if __name__ == '__main__':

    # Crossbar.io connection configuration
    url = u'ws://localhost:8080/ws'
    realm = u'realm1'

    # parse command line parameters
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true', default=True, help='Enable debug output.')
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
    runner.run(ClientSession, auto_reconnect=True)
