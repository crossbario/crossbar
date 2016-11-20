title: Progressive Call Results
toc: [Documentation, Programming Guide, Progressive Call Results]

# Progressive Call Results

> **Progressive Call Results** is a feature from the WAMP Advanced Profile. The specification can be found [here](https://github.com/tavendo/WAMP/blob/master/spec/advanced/progressive-call-results.md).

As a default, a call returns a single result. For some calls it may be desirable to have a series of call results, e.g. a longer user list may be sent in chunks which the caller can already process while the entire transfer of the user list is still in progress.

In WAMP, this is possible via **Progressive Call Results**. With these, a call can return a series of partial results, with a final result which signals that the series has endeded.

For example, call which requests progressive call results in a JavaScript component using Autobahn|JS could be

```javascript
session.call('com.myapp.longop', [3], {}, {receive_progress: true}).then(
      function (res) {
         console.log("Final:", res);
         connection.close();
      },
      function (err) {
      },
      function (progress) {
         console.log("Progress:", progress);
      }
   );
```

With progressive call results, there is a need for two result handlers: one for the progressive results and one for the final result.

> Depending on whether there is any need to handle the two differently, you may pass the same handler.

The same call in a Python component using Autobahn|Python would be

```python
def on_progress(i):
            print("Progress: {}".format(i))

        res = yield self.call('com.myapp.longop', 3, options=CallOptions(onProgress=on_progress))

        print("Final: {}".format(res))
```

For the above calls, a callee in JavaScript/Autobahn|JS would be


```javascript
function longop(args, kwargs, details) {

      var n = args[0];
      var interval_id = null;

      if (details.progress) {
         var i = 0;
         details.progress([i]);
         i += 1;
         interval_id = setInterval(function () {
            if (i < n) {
               details.progress([i]);
               i += 1;
            } else {
               clearInterval(interval_id);
            }
         }, 1000);
      }

      var d = when.defer();

      setTimeout(function () {
         d.resolve(n);
      }, 1000 * n);

      return d.promise;
   }
```

The procedure here uses timers to simulate long operations. It returns a promise since the timers execute after the body of the procedure has been executed. The progressive results are sent via the `progress` method on the call `details`, and the final result is sent by resolving the promise.

The equivalent Python procedure would be:


```python
@inlineCallbacks
        def longop(n, details=None):
            if details.progress:
                # caller can (and requested to) consume progressive results
                for i in range(n):
                    details.progress(i)
                    yield sleep(1)
            else:
                # process like a normal call (not producing progressive results)
                yield sleep(1 * n)
            returnValue(n)

        yield self.register(longop, 'com.myapp.longop', RegisterOptions(details_arg='details'))
```

You can also take a look at a full [working example](https://github.com/crossbario/autobahn-python/tree/master/examples/twisted/wamp/basic/rpc/progress).
