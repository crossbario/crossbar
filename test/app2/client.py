import os
import argparse
import six
import txaio

from pprint import pformat

from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.util import sleep
from autobahn.wamp.types import RegisterOptions, PublishOptions
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.exception import ApplicationError


class ClientSession(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):

        self.log.info("Connected:\n{details}\n", details=details)

        #
        # session metaevents
        #

        def on_ses_join(session_details):
            self.log.info('wamp.session.on_join(session_details={session_details})',
                          session_details=session_details)

        yield self.subscribe(on_ses_join, u'wamp.session.on_join')

        def on_ses_leave(session_id):
            self.log.info('wamp.session.on_leave(session_id={session_id})',
                          session_id=session_id)

        yield self.subscribe(on_ses_leave, u'wamp.session.on_leave')


        #
        # pubsub metaevents
        #

        def on_sub_create(session_id, subscription_details):
            self.log.info('wamp.subscription.on_create(session_id={session_id}, subscription_details={subscription_details})',
                          session_id=session_id,
                          subscription_details=subscription_details)

        yield self.subscribe(on_sub_create, u'wamp.subscription.on_create')

        def on_sub_subscribe(session_id, subscription_id):
            self.log.info('wamp.subscription.on_subscribe(session_id={session_id}, subscription_id={subscription_id})',
                          session_id=session_id,
                          subscription_id=subscription_id)

        yield self.subscribe(on_sub_subscribe, u'wamp.subscription.on_subscribe')

        def on_sub_unsubscribe(session_id, subscription_id):
            self.log.info('wamp.subscription.on_unsubscribe(session_id={session_id}, subscription_id={subscription_id})',
                          session_id=session_id,
                          subscription_id=subscription_id)

        yield self.subscribe(on_sub_unsubscribe, u'wamp.subscription.on_unsubscribe')

        def on_sub_delete(session_id, subscription_id):
            self.log.info('wamp.subscription.on_delete(session_id={session_id}, subscription_id={subscription_id})',
                          session_id=session_id,
                          subscription_id=subscription_id)

        yield self.subscribe(on_sub_delete, u'wamp.subscription.on_delete')


        #
        # rpc metaevents
        #

        def on_reg_create(session_id, registration_details):
            self.log.info('wamp.registration.on_create(session_id={session_id}, registration_details={registration_details})',
                          session_id=session_id,
                          registration_details=registration_details)

        yield self.subscribe(on_reg_create, u'wamp.registration.on_create')

        def on_reg_register(session_id, registration_id):
            self.log.info('wamp.registration.on_register(session_id={session_id}, registration_id={registration_id})',
                          session_id=session_id,
                          registration_id=registration_id)

        yield self.subscribe(on_reg_register, u'wamp.registration.on_register')

        def on_reg_unregister(session_id, registration_id):
            self.log.info('wamp.registration.on_unregister(session_id={session_id}, registration_id={registration_id})',
                          session_id=session_id,
                          registration_id=registration_id)

        yield self.subscribe(on_reg_unregister, u'wamp.registration.on_unregister')

        def on_reg_delete(session_id, registration_id):
            self.log.info('wamp.registration.on_delete(session_id={session_id}, registration_id={registration_id})',
                          session_id=session_id,
                          registration_id=registration_id)

        yield self.subscribe(on_reg_delete, u'wamp.registration.on_delete')

        # yield sleep(30)
        # yield sub.unsubscribe()
        # self.leave()

    def onLeave(self, details):
        self.log.info("Router session closed:\n{details}\n", details=details)
        self.disconnect()

    def onDisconnect(self):
        self.log.info("Router connection closed")
        try:
            reactor.stop()
        except ReactorNotRunning:
            pass


if __name__ == '__main__':

    # Crossbar.io connection configuration
    url = u'ws://localhost:8080/ws'
    realm = u'realm1'

    # parse command line parameters
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true', default=False, help='Enable debug output.')
    parser.add_argument('--url', dest='url', type=six.text_type, default=url, help='The router URL (default: "ws://localhost:8080/ws").')
    parser.add_argument('--realm', dest='realm', type=six.text_type, default=realm, help='The realm to join (default: "realm1").')

    args = parser.parse_args()

    # start logging
    if args.debug:
        txaio.start_logging(level='debug')
    else:
        txaio.start_logging(level='info')

    print('connecting to {}@{}'.format(realm, url))

    runner = ApplicationRunner(url=args.url, realm=args.realm)
    runner.run(ClientSession, auto_reconnect=True)
