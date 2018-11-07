:orphan:

HTTP Bridge
===========

Quick Links
-----------

-  `HTTP Bridge Webhook <HTTP%20Bridge%20Webhook>`__
-  `HTTP Bridge Publisher <HTTP%20Bridge%20Publisher>`__
-  `HTTP Bridge Subscriber <HTTP%20Bridge%20Subscriber>`__
-  `HTTP Bridge Caller <HTTP%20Bridge%20Caller>`__
-  `HTTP Bridge Callee <HTTP%20Bridge%20Callee>`__

Background
----------

Imagine you have an existing application which isn't based on WAMP
components -- say, a REST or classical Web application using HTTP.

Now what if you just want to *add* some real-time features *without*
changing your existing app to use WAMP or migrate from synchronous,
blocking to asynchronous, non-blocking code? Or if you want to access
your existing HTTP services using WAMP?

This is where the *HTTP bridge services* of Crossbar can help. They
provide WAMP components which provide interoperability with existing
code by using HTTP.

-  The `HTTP Bridge Webhook <HTTP%20Bridge%20Webhook>`__ is a service
   that parses incoming WebHook requests (e.g. from GitLab or GitHub)
   and pushes all the arguments to a configured topic
-  The `HTTP Publisher <HTTP%20Bridge%20Publisher>`__ is a service that
   allows clients to submit PubSub events via HTTP/POST requests.
   Crossbar will receive the event data via the request and forward the
   event via standard WAMP to any connected subscribers in real-time.
-  The `HTTP Caller <HTTP%20Bridge%20Caller>`__ is a service that allows
   clients to perform WAMP calls via HTTP/POST requests. Crossbar will
   forward the call to the performing server and return the result.
-  The `HTTP Subscriber <HTTP%20Bridge%20Subscriber>`__ is a service
   that forwards WAMP PubSub events to HTTP endpoints.
-  The `HTTP Callee <HTTP%20Bridge%20Callee>`__ is a service that
   translates WAMP procedure calls to HTTP requests.
