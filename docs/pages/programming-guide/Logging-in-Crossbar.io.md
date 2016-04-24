[Documentation](.) > [Programming Guide](Programming Guide) > Crossbar.io Features > Logging in Crossbar.io

# Logging in Crossbar.io

> Crossbar's structured logging system is present in versions 0.11 and above.

Crossbar.io uses Twisted's new Logger facilities to provide structured logging for Crossbar.io and components run inside of it.


## Twisted Logger

[Twisted Logger](http://twistedmatrix.com/documents/current/core/howto/logger.html), introduced in Twisted 15.2, provides structured logging for Python applications.
Crossbar.io integrates with this and uses it internally, and your components can take advantage of it.
Crossbar.io also captures ``stdout``, so ``print()`` statements will also be captured.


## Writing Components that use Logger

A component that uses Logger is the [hello](https://github.com/crossbario/crossbarexamples/blob/master/hello/python/hello.py) example application.

To set your application up for logging, import ``Logger`` from ``twisted.logger`` and instantiate it.
If you have classes, making it a [class attribute](http://www.toptal.com/python/python-class-attributes-an-overly-thorough-guide) allows Logger to store some more information (more on that later).

The ``Logger`` instance has several methods, relating to the levels of events:

* ``critical``: For unhandled/unhandleable errors.
* ``error``: For handled errors.
* ``warn``: For warnings which may affect the component but is not an error (for example: deprecated configuration, or having to make assumptions)
* ``info``: For general information messages.
* ``debug``: For debugging information.

These methods take at least one argument (the "format string") which will be used to produce a textual representation of the log event.
This argument follows the standard Python format string representation as in [PEP-3101](https://www.python.org/dev/peps/pep-3101/).
Further keyword arguments can be given which will be used in the formatting.

> The formatting may not be done straight away -- if the log event is never observed (for example, if it is a debug message, and the log observer level is set to info) the event will never be formatted into a string. This can be more efficient, as it means debug calls essentially turn into no-ops when the log level of the listener is not on debug as well.

As an example, if we have a variable named ``counter`` which is set to ``1``, and a Logger instance at ``self.log``, we could do the following:

```
self.log.info("published to 'oncounter' with counter {counter}", counter=counter)
```

This message would show up in the Crossbar logs as:

```
2015-08-17T13:45:10+0800 [Container    7326] published to 'oncounter' with counter 1
```


### Log recovery at all costs

If your log message cannot be formatted, Logger will try and preserve as much as possible.
For example, if you forgot to pass the ``counter`` keyword argument to the ``self.log.info`` call...

```
self.log.info("published to 'oncounter' with counter {counter}")
```

...it would produce the following in Crossbar's log:

```
2015-08-17T14:22:47+0800 [Container    7676] Unable to format event {'log_logger': <Logger 'hello.hello.AppSession'>, 'log_time': 1439792567.720701, 'log_source': <hello.hello.AppSession object at 0x10af0e290>, 'log_format': "published to 'oncounter' with counter {counter}"}: u'counter'
```

Logger will try and preserve as much information as possible, no matter what errors may occur, rather than eating the message.


### Class instance Loggers

If you make your Logger a class attribute (as in the [hello example](https://github.com/crossbario/crossbarexamples/blob/master/hello/python/hello/hello.py)), it captures some extra information.
The ``log_source`` attribute in the log event is set automatically when it is a class attribute, which points to the instance of the class that it was called from.
This means that you can get information from the class instance without having to individually pass it into the log call.
For example:

```
from twisted.logger import Logger
from autobahn.twisted.wamp import ApplicationSession

class AppSession(ApplicationSession):

    log = Logger()

    def onJoin(self, details):

        self.x = "Hello Crossbar!"
        self.log.info("x on self is {log_source.x}")
```

When this application component is run under Crossbar, it will produce the following log message:

```
2015-08-17T14:28:13+0800 [Container    7825] x on self is Hello Crossbar!
```

Plus, when Crossbar's logger is set to debug, each log message comes with where it came from in the log, to help trace down where errors may be occurring:

```
2015-08-17T13:43:52+0800 [Container    7310 hello.hello.AppSession] published to 'oncounter' with counter 2
```


## Configuring the Crossbar logger

For more information on configuring the Crossbar.io logging output (for example, to turn on debug, change the output format, or write to a file), see [Configuring Crossbar.io's Logging](Configuring Crossbario Logging).
