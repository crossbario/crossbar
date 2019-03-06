:orphan:

Application Scenarios
=====================

Crossbar.io was designed to flexibly support different application
scenarios. Here are some examples

1. `Polyglot backends <#polyglot-backends>`__
2. `Polyglot frontends <#polyglot-frontends>`__
3. `Serving static Web and CGI <#serving-static-web-and-cgi>`__
4. `JavaScript-only Web
   applications <#javascript-only-web-applications>`__
5. `Adding Chat to Web
   applications <#adding-chat-to-web-applications>`__
6. `Adding real-time to Web
   applications <#adding-real-time-to-web-applications>`__
7. `Internet of Things <#internet-of-things>`__

Polyglot backends
-----------------

Crossbar.io allows to create application components in different
languages, running under their native language run-time:

Application components can freely talk to each other, completely unaware
of the implementation language or run-time of the peer component. You
can mix and match application components as needed.

*More information:*

-  :doc:`Getting Started <../Getting-Started>` with Crossbar.io in different languages.

--------------

Polyglot frontends
------------------

The ability of Crossbar.io to connect application components written in
different programming languages extends to frontend components for user
interfaces. Using Crossbar.io, you can serve different UIs from the same
backend:

You need a Web frontend, but want to also package this as a hybrid
mobile app? No problem. Want to create a native mobile app as well?
Again, no issue. Crossbar.io was designed to give you freedom and
choice.

*More information:*

-  `AutobahnJS <https://github.com/crossbario/autobahn-js>`__
-  `AutobahnAndroid <https://github.com/crossbario/autobahn-android>`__
-  `MDWamp (WAMP for iOS) <https://github.com/mogui/MDWamp>`__

--------------

JavaScript-only Web applications
--------------------------------

Since JavaScript nowadays runs great on the server, and browsers are a
ubiquitous UI technology, for some applications it is now feasible to
implement the complete app in one language (JavaScript). Crossbar.io
directly supports such scenarios:

With the above, you are not only using the *same* language (JavaScript)
to implement both front- and backend components, but you are using the
*same* communication patterns and library
(`AutobahnJS <https://github.com/crossbario/autobahn-js>`__) as well.

In fact (depending on what dependencies your code has) you can write
functions that can be freely moved between the browser or NodeJS!

*More information:*

-  `Getting started with NodeJS <Getting-started-with-NodeJS>`__
-  `AutobahnJS <https://github.com/crossbario/autobahn-js>`__

 
Adding Chat to Web applications
-------------------------------

Sometimes you might want to add a specific, self-contained real-time
feature like "Chat" to an existing Web application, with minimal changes
to existing code. Crossbar.io supports this:

As can be seen, there is zero change to the existing backend. Regarding
the frontend, the new code and elements for "Chat" are completely
independent of the existing assets. Adding something like "Chat" becomes
a matter of a little HTML, CSS and JavaScript. We have a complete "Chat"
demo with open-source code (see below) which you can just copy over. No
big deal.

*More information:*

-  `Crossbar.io Chat
   Demo <https://demo.crossbar.io/chat/index.html#ch1>`__
-  `Crossbar.io Chat Demo Source
   Code <https://github.com/crossbario/crossbarexamples/tree/master/demos/chat>`__

 
Adding real-time to Web applications
------------------------------------

Another scenario is when you have an existing, classical Web application
to which you just want to *add* some real-time features without
rewriting the app.

Crossbar.io features :doc:`HTTP REST bridge <HTTP-Bridge>` which allows
interaction between WAMP application components and REST services.

As an example, the *HTTP Publisher* service of Crossbar.io **can be used
from any Web application framework that is able to do (outgoing)
HTTP/POST requests**. It does not matter whether the framework is
asynchronous, threaded, blocking or something else, as long as it can
trigger HTTP/POSTs.

Which means it'll work from e.g.

-  `Django <https://www.djangoproject.com/>`__,
   `Flask <http://flask.pocoo.org/>`__,
   `CherryPy <http://www.cherrypy.org/>`__ or any other
   `WSGI <http://en.wikipedia.org/wiki/Web_Server_Gateway_Interface>`__
   based framework
-  `PHP <http://www.php.net/>`__
-  `Rails <http://rubyonrails.org/>`__
-  `ASP.NET <http://www.asp.net/>`__
-  Java `Servlet <http://en.wikipedia.org/wiki/Servlets>`__,
   `JSP <http://en.wikipedia.org/wiki/JavaServer_Pages>`__,
   `JSF <http://en.wikipedia.org/wiki/JavaServer_Faces>`__, `Apache
   Struts <http://en.wikipedia.org/wiki/Apache_Struts_2>`__, ..

*More information:*

-  :doc:`HTTP REST bridge <HTTP-Bridge>`

--------------

Serving static Web and CGI
--------------------------

As soon as your application includes some "Web stuff" like a frontend,
this will require to host the Web assets (static files like HTML, CSS,
images, etc) *somewhere*. Crossbar.io includes a Web server for serving
static Web assets to relieve you from having to run yet another wheel:

The Web server built into Crossbar.io has some more features which are
useful sometimes, like ability to server CGI scripts or setup HTTP
redirections.

    The builtin Web Server is quite capable - it will suffice for static
    serving in most cases. However, it's less performant than say Nginx
    (e.g. it reaches 20-50% performance) at static serving.

*More information:*

-  :doc:`Crossbar.io Web services <Web-Services>`

--------------

Internet of Things
------------------

Crossbar.io works great for connecting devices like an `Arduino
Yun <http://arduino.cc/en/Main/ArduinoBoardYun>`__ or a
`RaspberryPi <http://www.raspberrypi.org/>`__ to the Web and to server
components - in real-time.

--------------

*Read more:*

-  `Arduino Yun with
   Autobahn <https://crossbario.com/blog/Arduino-Yun-With-Autobahn/>`__
-  `Getting started with the RaspberryPi and
   Autobahn <https://crossbario.com/blog/Pypy-on-the-Pi/>`__
-  `Why WAMP? <https://wamp-proto.org/intro.html#wamp>`__
