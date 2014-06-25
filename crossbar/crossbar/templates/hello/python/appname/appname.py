from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.util import sleep
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError



class AppSession(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):

        ## SUBSCRIBE to a topic and receive events
        ##
        def onhello(msg):
            print("onhello(): {}".format(msg))

        sub = yield self.subscribe(onhello, 'com.example.onhello')
        print("subscribed to topic 'onhello'")


        ## REGISTER a procedure for remote calling
        ##
        def add2(x, y):
            print("add2() called with {} and {}".format(x, y))
            return x + y

        reg = yield self.register(add2, 'com.example.add2')
        print("procedure add2() registered")


        ## PUBLISH and CALL every second .. forever
        ##
        counter = 0
        while True:

            ## PUBLISH an event
            ##
            yield self.publish('com.example.oncounter', counter)
            print("published to 'oncounter' with counter {}".format(counter))
            counter += 1


            ## CALL a remote procedure
            ##
            try:
                res = yield self.call('com.example.mul2', counter, 3)
                print("mul2() result: {}".format(res))
            except ApplicationError as e:
                ## ignore errors due to the frontend not yet having
                ## registered the procedure we would like to call
                if e.error != 'wamp.error.no_such_procedure':
                    raise e


            yield sleep(1)
