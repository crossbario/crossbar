[Documentation](.) > [Programming Guide](Programming Guide) > [WAMP Features](WAMP Features) > RPC > Basic Registrations

# Basic Registrations

As a default, registrations use exact matching, i.e. a callee which registers a procedure URI `com.myapp.procedure1` will receive calls for `com.myapp.procedure1` only. There are, however, also [pattern-based registrations](Pattern Based Registrations) which can be selected via an option when registering.

> Note: There are some [specific rules regarding URI formatting](URI Format).

Further, as a default only a single registration for a URI is allowed, i.e. once one component has registered a procedure for an URI `com.myapp.topic1`, all further attempts to register a procedure for this URI will be rejected. There are, however, [shared registrations](Shared Registrations) which can be seleted via an option when registering.

Here's an example for a simple registration in JavaScript using Autobahn|JS:

```javascript
session.register("com.myapp.procedure1", procedure1);
```

This is equivalent to

```javascript
session.register("com.myapp.procedure1", procedure1, { match: "exact", invoke: "single" })
```

## Returning a Promise

A lot of functions that you register will just return synchronously, but when code within your function runs asynchronously, you can return a promise from the function, which is then resolved once the async code has finished. Here is an example for JavaScript, using Autobahn|JS and its default promises library (when.js):

```javascript
function procedure1 (args, kwargs, details) {

    var d = autobahn.when.defer();

    setTimeout(function() {
       d.resolve("async finished");
    }, 1000);

    return d.promise;    
}
```
