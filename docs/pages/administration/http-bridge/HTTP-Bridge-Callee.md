[Documentation](.) > [Administration](Administration) > [HTTP Bridge](HTTP Bridge) > HTTP Bridge Callee

# HTTP Bridge Callee

> The *HTTP Callee* feature is available starting with Crossbar **0.10.3**.

* The *HTTP Callee* is a service that translates WAMP procedures to HTTP requests.


## Try it

Clone the [Crossbar.io examples repository](https://github.com/crossbario/crossbarexamples), and go to the `rest/callee` subdirectory.

Now start Crossbar:

```console
crossbar start
```

This example is configured to register a WAMP procedure named `com.myap.rest`, which sends requests to `httpbin.org`.
The procedure's complete keyword arguments are detailed further down, but if we use a kwargs of `{"url": "get", "method": "GET"}`, Crossbar will send a HTTP GET request to `httpbin.org/get` and respond with the result.
You can test this using the [HTTP Caller](HTTP Bridge Caller) configured in the example:

```shell
curl -H "Content-Type: application/json" \
	-d '{"procedure": "com.myapp.rest", "kwargs": {"url": "get", "method": "GET"}}' \
	http://127.0.0.1:8080/call
    ```

This will call the procedure and print the web response to the terminal.


## Configuration

The *HTTP Callee* is configured as a WAMP component.
Here it is as part of a Crossbar configuration:

```javascript
{
    "type": "container",
    "options": {
        "pythonpath": [".."]
    },
    "components": [
        {
            "type": "class",
            "classname": "crossbar.adapter.rest.RESTCallee",
            "realm": "realm1",
            "extra": {
                "procedure": "com.myapp.rest",
                "baseurl": "https://httpbin.org/"
            },
            "transport": {
                "type": "websocket",
                "endpoint": {
                    "type": "tcp",
                    "host": "127.0.0.1",
                    "port": 8080
                },
                "url": "ws://127.0.0.1:8080/ws"
            }
        }
    ]
}
```

The callee is configured through the `extra` dictionary:

option | description
---|---
**`procedure`** | The WAMP procedure name to register the callee as. (*required*)
**`baseurl`** | The base URL that the callee will use. All calls will work downward from this URL. If you wish to call any URL, set it as an empty string `""`. This URL must contain the protocol (e.g. `"https://"`) (*required*)

When making calls to the registered WAMP procedure, you can use the following keyword arguments:

argument | description
---|---
**`method`** | The HTTP method. (*required*)
**`url`** | The url which will be appended to the configurd base URL. For example, if the base URL was `"http://example.com"`, providing `"test"` as this argument would send the request to `http://example.com/test`. (optional, uses the configured base URL if not provided)
**`body`** | The body of the request as a string. (optional, empty if not provided)
**`headers`** | A dictionary, containing the header names as the key, and a *list* of header values as the value. For example, to send a `Content-Type` of `application/json`, you would use `{"Content-Type": ["application/json"]}` as the argument. (optional)
**`params`** | Request parameters to send, as a dictionary. (optional)


## Examples

### Wikipedia

Wikipedia has a web API that we can use for this demonstration.

Configure the `RESTCallee` WAMP component:

```javascript
"extra": {
    "procedure": "org.wikipedia.en.api",
    "baseurl": "http://en.wikipedia.org/w/api.php"
}
````

This code snippet calls the procedure with the parameters to look up the current revision of the Twisted Wikipedia page, reads the web response as JSON, and then pretty prints the response to the terminal.

```python
import json
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner

class AppSession(ApplicationSession):

    @inlineCallbacks
    def onJoin(self, details):
        res = yield self.call("org.wikipedia.en.api",
                              method="GET",
                              url="",
                              params={
                                  "format": "json",
                                  "action": "query",
                                  "titles": "Twisted (software)",
                                  "prop": "revisions",
                                  "rvprop": "content"
                              })

        pageContent = json.loads(res["content"])
        print(json.dumps(pageContent, sort_keys=True,
                         indent=4, separators=(',', ': ')))
        reactor.stop()

if __name__ == '__main__':
    from autobahn.twisted.wamp import ApplicationRunner
    runner = ApplicationRunner("ws://127.0.0.1:8080/ws", "realm1")
    runner.run(AppSession)
```
