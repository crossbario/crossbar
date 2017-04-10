title: Application Scenarios
toc: [Documentation, Application Scenarios]

# Application Scenarios

Crossbar.io was designed to flexibly support different application scenarios. Here are some examples

1. [Polyglot backends](#polyglot-backends)
1. [Polyglot frontends](#polyglot-frontends)
1. [Serving static Web and CGI](#serving-static-web-and-cgi)
1. [JavaScript-only Web applications](#javascript-only-web-applications)
1. [Adding Chat to Web applications](#adding-chat-to-web-applications)
1. [Adding real-time to Web applications](#adding-real-time-to-web-applications)
1. [Internet of Things](#internet-of-things)

<br><br>

## Polyglot backends

Crossbar.io allows to create application components in different languages, running under their native language run-time:

Application components can freely talk to each other, completely unaware of the implementation language or run-time of the peer component. You can mix and match application components as needed.

*More information:*

 * [[Getting Started]] with Crossbar.io in different languages.

_____________

<br>

## Polyglot frontends

The ability of Crossbar.io to connect application components written in different programming languages extends to frontend components for user interfaces. Using Crossbar.io, you can serve different UIs from the same backend:

You need a Web frontend, but want to also package this as a hybrid mobile app? No problem. Want to create a native mobile app as well? Again, no issue. Crossbar.io was designed to give you freedom and choice.

*More information:*

 * [AutobahnJS](https://github.com/crossbario/autobahn-js)
 * [AutobahnAndroid](https://github.com/crossbario/autobahn-android)
 * [MDWamp (WAMP for iOS)](https://github.com/mogui/MDWamp)

_____________
<br>

## JavaScript-only Web applications

Since JavaScript nowadays runs great on the server, and browsers are a ubiquitous UI technology, for some applications it is now feasible to implement the complete app in one language (JavaScript). Crossbar.io directly supports such scenarios:

With the above, you are not only using the *same* language (JavaScript) to implement both front- and backend components, but you are using the *same* communication patterns and library ([AutobahnJS](https://github.com/crossbario/autobahn-js)) as well.

In fact (depending on what dependencies your code has) you can write functions that can be freely moved between the browser or NodeJS!

*More information:*

 * [Getting started with NodeJS](Getting started with NodeJS)
 * [AutobahnJS](https://github.com/crossbario/autobahn-js)

_____________
<br>

## Adding Chat to Web applications

Sometimes you might want to add a specific, self-contained real-time feature like "Chat" to an existing Web application, with minimal changes to existing code. Crossbar.io supports this:

As can be seen, there is zero change to the existing backend. Regarding the frontend, the new code and elements for "Chat" are completely independent of the existing assets. Adding something like "Chat" becomes a matter of a little HTML, CSS and JavaScript. We have a complete "Chat" demo with open-source code (see below) which you can just copy over. No big deal.

*More information:*

* [Crossbar.io Chat Demo](https://demo.crossbar.io/chat/index.html#ch1)
* [Crossbar.io Chat Demo Source Code](https://github.com/crossbario/crossbarexamples/tree/master/demos/chat)

_____________
<br>

## Adding real-time to Web applications

Another scenario is when you have an existing, classical Web application to which you just want to *add* some real-time features without rewriting the app.

Crossbar.io features [*HTTP REST* bridge](HTTP Bridge) which allows interaction between WAMP application components and REST services.

As an example, the *HTTP Publisher* service of Crossbar.io **can be used from any Web application framework that is able to do (outgoing) HTTP/POST requests**. It does not matter whether the framework is asynchronous, threaded, blocking or something else, as long as it can trigger HTTP/POSTs.

Which means it'll work from e.g.

* [Django](https://www.djangoproject.com/), [Flask](http://flask.pocoo.org/), [CherryPy](http://www.cherrypy.org/) or any other [WSGI](http://en.wikipedia.org/wiki/Web_Server_Gateway_Interface) based framework
* [PHP](http://www.php.net/)
* [Rails](http://rubyonrails.org/)
* [ASP.NET](http://www.asp.net/)
* Java [Servlet](http://en.wikipedia.org/wiki/Servlets), [JSP](http://en.wikipedia.org/wiki/JavaServer_Pages), [JSF](http://en.wikipedia.org/wiki/JavaServer_Faces), [Apache Struts](http://en.wikipedia.org/wiki/Apache_Struts_2), ..

*More information:*

* [*HTTP REST* bridge](HTTP Bridge)

_____________
<br>

## Serving static Web and CGI

As soon as your application includes some "Web stuff" like a frontend, this will require to host the Web assets (static files like HTML, CSS, images, etc) *somewhere*. Crossbar.io includes a Web server for serving static Web assets to relieve you from having to run yet another wheel:

The Web server built into Crossbar.io has some more features which are useful sometimes, like ability to server CGI scripts or setup HTTP redirections.

> The builtin Web Server is quite capable - it will suffice for static serving in most cases. However, it's less performant than say Nginx (e.g. it reaches 20-50% performance) at static serving.

*More information:*

* [Crossbar.io Web services](Web-Transports-and-Services#path-services)

_____________
<br>


## Internet of Things

Crossbar.io works great for connecting devices like an [Arduino Yun](http://arduino.cc/en/Main/ArduinoBoardYun) or a [RaspberryPi](http://www.raspberrypi.org/) to the Web and to server components - in real-time.

_____________
<br>


*Read more:*

* [Arduino Yun with Autobahn](http://crossbario.com/blog/post/arduino-yun-with-autobahn/)
* [Getting started with the RaspberryPi and Autobahn](http://crossbario.com/blog/post/pypy-on-the-pi/)
* [Why WAMP?](http://wamp.ws/why/)
