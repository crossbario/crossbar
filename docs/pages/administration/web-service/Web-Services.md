title: Web Services
toc: [Documentation, Administration, Web Services]

# Web Services

Crossbar.io has a built-in Web server that provides various configurable Web services and [scales](https://github.com/crossbario/crossbarexamples/tree/master/benchmark/web) to 100k's requests per second on multi-core.

To use these Web services, configure a Crossbar.io [Router Worker](Router-Configuration) with a [Web Transport](Web Transport and Services), and then configure the Web services you want to run on that transport:

* [Path Service](Path-Service)
* [Static Web Service](Static-Web-Service)
* [File Upload Service](File-Upload-Service)
* [WebSocket Service](WebSocket-Service)
* [Long-poll Service](Long-Poll-Service)
* [Web Redirection Service](Web-Redirection-Service)
* [Reverse Proxy Service](Reverse-Proxy-Service)
* [JSON Value Service](JSON-Value-Service)
* [CGI Script Service](CGI-Script-Service)
* [WSGI Host Service](WSGI-Host-Service)
* [Resource Service](Resource-Service)

The following features of the [HTTP Bridge](HTTP Bridge) are also run as Web services on a Web transport of a router:

* [HTTP Bridge Publisher](HTTP Bridge Publisher)
* [HTTP Bridge Subscriber](HTTP Bridge Subscriber)
* [HTTP Bridge Caller](HTTP Bridge Caller)
* [HTTP Bridge Callee](HTTP Bridge Callee)
* [HTTP Bridge Webhook](HTTP Bridge Webhook)
