title: Web Services toc: [Documentation, Administration, Web Services]

Web Services
============

Crossbar.io has a built-in Web server that provides various configurable
Web services and
`scales <https://github.com/crossbario/crossbarexamples/tree/master/benchmark/web>`__
to 100k's requests per second on multi-core.

To use these Web services, configure a Crossbar.io `Router
Worker <Router-Configuration>`__ with a `Web
Transport <Web%20Transport%20and%20Services>`__, and then configure the
Web services you want to run on that transport:

-  `Path Service <Path-Service>`__
-  `Static Web Service <Static-Web-Service>`__
-  `File Upload Service <File-Upload-Service>`__
-  `WebSocket Service <WebSocket-Service>`__
-  `Long-poll Service <Long-Poll-Service>`__
-  `Web Redirection Service <Web-Redirection-Service>`__
-  `Reverse Proxy Service <Reverse-Proxy-Service>`__
-  `JSON Value Service <JSON-Value-Service>`__
-  `CGI Script Service <CGI-Script-Service>`__
-  `WSGI Host Service <WSGI-Host-Service>`__
-  `Resource Service <Resource-Service>`__
-  `Node Info Service <Node-Info-Service>`__

The following features of the `HTTP Bridge <HTTP%20Bridge>`__ are also
run as Web services on a Web transport of a router:

-  `HTTP Bridge Publisher <HTTP%20Bridge%20Publisher>`__
-  `HTTP Bridge Subscriber <HTTP%20Bridge%20Subscriber>`__
-  `HTTP Bridge Caller <HTTP%20Bridge%20Caller>`__
-  `HTTP Bridge Callee <HTTP%20Bridge%20Callee>`__
-  `HTTP Bridge Webhook <HTTP%20Bridge%20Webhook>`__
