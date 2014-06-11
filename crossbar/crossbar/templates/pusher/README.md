# Crossbar.io HTTP Pusher

Crossbar includes a HTTP Pusher service that is able to receive PubSub events via plain-old HTTP/POST requests, and forward those via WAMP to connected subscribers.

To configure the service, set up a Web transport with a path service of type `pusher` - e.g. see [.crossbar/config.json](.crossbar/config.json). For full documentation, please see [here](https://github.com/crossbario/crossbar/wiki/HTTP-Pusher-Service).

## Example

All HTML5 example code is in [web/index.html](web/index.html). Python example code for publishing events via HTTP/POSTs using the HTTP bridge built into Crossbar.io can be found here:

 * [publish.py](publish.py)
 * [publish_signed.py](publish_signed.py)

To publish using [curl](http://curl.haxx.se/) (unsigned publish):

```shell
curl -H "Content-Type: application/json" \
	-d '{"topic": "com.myapp.topic1", "args": ["Hello, world"]}' \
	http://127.0.0.1:8080/push
```
