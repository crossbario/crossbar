[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > Error Handling

# Error Handling

**Write me.**

## Serialization Errors

When you publish an event, call a procedure or return from a called procedure, you can use any positional- and keyword-based application payload - as long as the payload can be *serialized*.

When you try to use non-serializable payload, this will fail:


```python
from twisted.internet.defer import inlineCallbacks

from autobahn.wamp.types import PublishOptions
from autobahn.wamp.exception import ApplicationError, SerializationError

from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.wamp import ApplicationRunner


class Foo:
    def __init__(self, a, b):
        self.a = a
        self.b = b


class MyComponent(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):
        print("session ready")

        # this object can't be serialized, so we can't use it "as is"
        # in any application payload
        foo = Foo(23, u"hello")

        # try to publish .. this will fail!
        #
        try:
            yield self.publish(u"com.example.topic1", foo, options=PublishOptions(acknowledge=True))
        except SerializationError as e:
            print("publish error: {}".format(e))

        # try to call a procedure that returns a non-serializable value .. will fail!
        #
        def get_a_foo():
            return foo

        yield self.register(get_a_foo, u"com.example.get_a_foo")

        try:
            res = yield self.call(u"com.example.get_a_foo")
        except SerializationError as e:
            print("call 1 error: {}".format(e))

        # demonstrates raising an error with valid custom payload .. will "succeed"!
        #
        def get_a_foo2():
            raise ApplicationError(u"com.example.error1", "hello", 123)

        yield self.register(get_a_foo2, u"com.example.get_a_foo2")

        try:
            res = yield self.call(u"com.example.get_a_foo2")
        except ApplicationError as e:
            print("call 2 error: {}".format(e))

        # demonstrates raising an error with non-serializable custom payload .. will "fail"!
        #
        def get_a_foo3():
            raise ApplicationError(u"com.example.error1", foo)

        yield self.register(get_a_foo3, u"com.example.get_a_foo3")

        try:
            res = yield self.call(u"com.example.get_a_foo3")
        except SerializationError as e:
            print("call 3 error: {}".format(e))

        print("Done!")


if __name__ == '__main__':
    runner = ApplicationRunner(url=u"ws://localhost:8080/ws", realm=u"realm1",
        debug=False, debug_wamp=False)
    runner.run(MyComponent)
```
