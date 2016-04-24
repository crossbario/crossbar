[Documentation](.) > [Administration](Administration) > HTTP Bridge

# HTTP Bridge

## Quick Links

* [HTTP Bridge Publisher](HTTP Bridge Publisher)
* [HTTP Bridge Subscriber](HTTP Bridge Subscriber)
* [HTTP Bridge Caller](HTTP Bridge Caller)
* [HTTP Bridge Callee](HTTP Bridge Callee)
* [HTTP Bridge Webhook](HTTP Bridge Webhook)

## Background

Imagine you have an existing application which isn't based on WAMP components -- say, a REST or classical Web application using HTTP.

Now what if you just want to *add* some real-time features *without* changing your existing app to use WAMP or migrate from synchronous, blocking to asynchronous, non-blocking code?
Or if you want to access your existing HTTP services using WAMP?

This is where the *HTTP bridge services* of Crossbar can help.
They provide WAMP components which provide interoperability with existing code by using HTTP.

* The [HTTP Publisher](HTTP Bridge Publisher) is a service that allows clients to submit PubSub events via HTTP/POST requests.
Crossbar will receive the event data via the request and forward the event via standard WAMP to any connected subscribers in real-time.
* The [HTTP Caller](HTTP Bridge Caller) is a service that allows clients to perform WAMP calls via HTTP/POST requests.
Crossbar will forward the call to the performing server and return the result.
* The [HTTP Subscriber](HTTP Bridge Subscriber) is a service that forwards WAMP PubSub events to HTTP endpoints.
* The [HTTP Callee](HTTP Bridge Callee) is a service that translates WAMP procedure calls to HTTP requests.
