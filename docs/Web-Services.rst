:orphan:

Web Services
============

Crossbar.io has a built-in Web server that provides various configurable
Web services and
`scales <https://github.com/crossbario/crossbarexamples/tree/master/benchmark/web>`__
to 100k's requests per second on multi-core.

To use these Web services, configure a Crossbar.io :doc:`Router
Worker <Router-Configuration>` with a :doc:`Web
Transport <Web-Transport-and-Services>`, and then configure the
Web services you want to run on that transport:

-  :doc:`Path Service <Path-Service>`
-  :doc:`Static Web Service <Static-Web-Service>`
-  :doc:`File Upload Service <File-Upload-Service>`
-  :doc:`WebSocket Service <WebSocket-Service>`
-  :doc:`Long-poll Service <Long-Poll-Service>`
-  :doc:`Web Redirection Service <Web-Redirection-Service>`
-  :doc:`Reverse Proxy Service <Reverse-Proxy-Service>`
-  :doc:`JSON Value Service <JSON-Value-Service>`
-  :doc:`CGI Script Service <CGI-Script-Service>`
-  :doc:`WSGI Host Service <WSGI-Host-Service>`
-  :doc:`Resource Service <Resource-Service>`
-  :doc:`Node Info Service <Node-Info-Service>`
-  :doc:`Archive Service <Web-Archive-Service>`

The following features of the :doc:`HTTP Bridge <HTTP-Bridge>` are also
run as Web services on a Web transport of a router:

-  :doc:`HTTP Bridge Publisher <HTTP-Bridge-Publisher>`
-  :doc:`HTTP Bridge Subscriber <HTTP-Bridge-Subscriber>`
-  :doc:`HTTP Bridge Caller <HTTP-Bridge-Caller>`
-  :doc:`HTTP Bridge Callee <HTTP-Bridge-Callee>`
-  :doc:`HTTP Bridge Webhook <HTTP-Bridge-Webhook>`
