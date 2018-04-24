title: Registration Options
toc: [Documentation, Programming Guide, Registration Options]

# Registration Options

There are a number of options you can set when making a new registration; for all of the options below you make a [RegistrationOptions](http://autobahn.readthedocs.io/en/latest/reference/autobahn.wamp.html#autobahn.wamp.types.RegisterOptions) instance.

## match

The `match=` registration option can be set to one of three values and affects how the dealer matching incoming "call" URIs.

 - `exact`: only a call to the exact URI will succeed
 - `prefix`: if the first part of the URI matches, the procedure will be invoked
 - `wildcard`: accepts any value for the portions of the URI accepting wildcards (denoted by two dots together, like `com.example..postfix`). So calling `com.example.42.postfix` would match with the wildcard matcher.


## invoke

The `invoke=` registration option controls whether multiple components can register at the same URIs and how to behave when they are.

 - `single`: only one session may register at a time
 - `first`: multiple sessions may register, but only the first one is invoked
 - `last`: multiple sessions may register, and only the last one is invoked
 - `roundrobin`: multiple sessions may register each is invoked in order
 - `random`: multiple sessions may register and an arbitrary one is invoked


## concurrency

Controlling the number of concurrent, outstanding calls that can exist for a single endpoint. An "outstanding call" is when we've invoked a procedure, but its coroutine/Future/Deferred hasn't completed yet. If `concurrency=0` (the default) than any number of calls can exist at once. Otherwise, once the concurrency limit is reached any subsequent callers will get an error message.


## force_reregister

When set to `True` this allows subsequent sessions to "kick out" any current registrations; those previous registration must have also specified `force_reregister=True`.


## details_arg

If you want the invoked procedure to receive a `CallDetails` instance, specify which argument-name to send it in with `details_arg`. For example, `details_arg="details"` will cause all calls to the registered procedure to receive a `details=CallDatails()` kwarg.


## correlation_id, correlation_uri, correlation_is_anchor, correlation_is_last

These options all relate to the "tracing" feature.
