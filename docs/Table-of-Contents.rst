Table of Contents
=================

Getting Started
---------------

-  `Getting Started <Getting%20Started>`__

Administrators
--------------

-  `Basic Concepts <Basic%20Concepts>`__
-  `Installation <Installation>`__
-  Docker Images

   -  `Using Docker <Using%20Docker>`__

-  Other Platforms

   -  `Installation on (generic) Linux <Installation%20on%20Linux>`__
   -  `Installation on Mac OS X <Installation%20on%20Mac%20OS%20X>`__
   -  `Installation on Windows <Installation%20on%20Windows>`__

-  Setup on IaaS and PaaS Providers

   -  `Setup on Amazon EC2 <Setup-on-Amazon-EC2>`__
   -  `Setup on Heroku <Setup-on-Heroku>`__
   -  `Setup on OpenShift <Setup-on-OpenShift>`__

-  Demo Instance

   -  `Demo Instance <Demo%20Instance>`__

-  `Administration <Administration>`__
-  `The Command Line <Command%20Line>`__
-  `Node Configuration <Node%20Configuration>`__

   -  `Processes <Processes>`__

      -  `Controller Configuration <Controller%20Configuration>`__
      -  `Guest Configuration <Guest%20Configuration>`__
      -  `Native Worker Shared Options <Native%20Worker%20Options>`__
      -  `Container Configuration <Container%20Configuration>`__
      -  `Process Environments <Process%20Environments>`__
      -  `Router Configuration <Router%20Configuration>`__

         -  `Router Realms <Router%20Realms>`__
         -  `Router Components <Router%20Components>`__
         -  `Router Transports <Router%20Transports>`__
         -  `Transport Endpoints <Transport%20Endpoints>`__
         -  `WebSocket Transport <WebSocket%20Transport>`__

            -  `WebSocket Options <WebSocket%20Options>`__
            -  `WebSocket Compression <WebSocket%20Compression>`__
            -  `Cookie Tracking <Cookie%20Tracking>`__

         -  `RawSocket Transport <RawSocket%20Transport>`__
         -  `Web Transport and
            Services <Web%20Transport%20and%20Services>`__
         -  `Flash Policy Transport <Flash%20Policy%20Transport>`__
         -  `Web Services <Web%20Services>`__
         -  `Path Service <Path-Service>`__
         -  `Static Web Service <Static-Web-Service>`__
         -  `File Upload Service <File-Upload-Service>`__
         -  `WebSocket Service <WebSocket-Service>`__
         -  `Long-Poll Service <Long-Poll-Service>`__
         -  `Web Redirection Service <Web-Redirection-Service>`__
         -  `Reverse Proxy Service <Reverse%20Proxy%20Service>`__
         -  `JSON Value Service <JSON-Value-Service>`__
         -  `CGI Script Service <CGI-Script-Service>`__
         -  `WSGI Host Service <WSGI-Host-Service>`__
         -  `Resource Service <Resource-Service>`__
         -  `HTTP Bridge <HTTP%20Bridge>`__
         -  `HTTP Bridge Publisher <HTTP%20Bridge%20Publisher>`__
         -  `HTTP Bridge Subscriber <HTTP%20Bridge%20Subscriber>`__
         -  `HTTP Bridge Caller <HTTP%20Bridge%20Caller>`__
         -  `HTTP Bridge Callee <HTTP%20Bridge%20Callee>`__
         -  `HTTP Bridge Webhook <HTTP%20Bridge%20Webhook>`__
         -  `MQTT Broker <MQTT%20Broker>`__
         -  `Authentication <Authentication>`__
         -  `Anonymous Authentication <Anonymous%20Authentication>`__
         -  `Challenge-Response
            Authentication <Challenge-Response%20Authentication>`__
         -  `Cookie Authentication <Cookie%20Authentication>`__
         -  `Ticket Authentication <Ticket%20Authentication>`__
         -  `Cryptosign Authentication <Cryptosign%20Authentication>`__
         -  `TLS Client Certificate
            Authentication <TLS%20Client%20Certificate%20Authentication>`__
         -  `Dynamic Authenticators <Dynamic%20Authenticators>`__
         -  `Authorization <Authorization>`__

-  `Logging <Logging>`__
-  `Going to Production <Going-to-Production>`__

   -  `Running on privileged
      ports <Running%20on%20Privileged%20Ports>`__
   -  `Secure WebSocket and HTTPS <Secure%20WebSocket%20and%20HTTPS>`__
   -  `TLS Certificates <TLS%20Certificates>`__
   -  `Payload Encryption
      (Cryptobox) <Cryptobox%20Payload%20Encryption>`__
   -  `Automatic startup and
      restart <Automatic%20Startup%20and%20Restart>`__
   -  `Network Tuning <Network%20Tuning>`__
   -  `Reverse Proxies <Reverse%20Proxies>`__
   -  `SSL/TLS Interception Proxies <SSL-TLS-Interception-Proxies>`__
   -  `Browser Support <Browser%20Support>`__
   -  `WebSocket Compliance
      Testing <WebSocket%20Compliance%20Testing>`__
   -  `Stream Testee <Stream%20Testee>`__

Programmers
-----------

-  `Application Scenarios <Application%20Scenarios>`__
-  `Programming Guide <Programming%20Guide>`__
-  General `URI Format <URI%20Format>`__

   -  `Logging in Crossbar.io <Logging%20in%20Crossbario>`__
   -  `Error Handling <Error%20Handling>`__
   -  `Session Meta Events and
      Procedures <Session%20Metaevents%20and%20Procedures>`__
   -  `Development with External
      Devices <Development-with-External-Devices>`__

-  `WAMP Features <WAMP%20Features>`__

   -  Session

      -  `Session Meta Events and
         Procedures <Session%20Metaevents%20and%20Procedures>`__

   -  `Publish & Subscribe (PubSub) <PubSub>`__

      -  `How Subscriptions Work <How%20Subscriptions%20Work>`__
      -  `Basic Subscriptions <Basic%20Subscriptions>`__
      -  `Subscriber Black- and
         Whitelisting <Subscriber%20Black%20and%20Whitelisting>`__
      -  `Publisher Exclusion <Publisher%20Exclusion>`__
      -  `Publisher Identification <Publisher%20Identification>`__
      -  `Pattern-Based
         Subscriptions <Pattern%20Based%20Subscriptions>`__
      -  `Subscription Meta Events and
         Procedures <Subscription%20Meta%20Events%20and%20Procedures>`__
      -  `Event History <Event%20History>`__

   -  `Remote Procedure Calls <RPC>`__

      -  `How Registrations Work <How%20Registrations%20Work>`__
      -  `Basic Registrations <Basic%20Registrations>`__
      -  `Caller Identification <Caller%20Identification>`__
      -  `Progressive Call Results <Progressive%20Call%20Results>`__
      -  `Pattern-Based
         Registrations <Pattern%20Based%20Registrations>`__
      -  `Shared Registrations <Shared%20Registrations>`__
      -  `Registration Meta Events and
         Procedures <Registration%20Meta%20Events%20and%20Procedures>`__

   -  `Error Handling <Error%20Handling>`__
   -  `URI Format <URI%20Format>`__

-  Frameworks and specific Scenarios

   -  `Adding Real-Time to Django
      Applications <Adding%20Real%20Time%20to%20Django%20Applications>`__
   -  [[AngularJS Application Components]]
   -  `Database Programming with
      PostgreSQL <Database%20Programming%20with%20PostgreSQL>`__

-  Crossbar.io features

   -  `Starting and Stopping
      Crossbar.io <Starting%20and%20Stopping%20Crossbario>`__
   -  `Logging in Crossbar.io <Logging%20in%20Crossbario>`__
   -  `Configuring Crossbar.io's
      Logging <Configuring%20Crossbario%20Logging>`__

-  `Crossbar.io Demo Instance <Demo%20Instance>`__
-  `Application Templates <Application%20Templates>`__
-  `Examples <Examples>`__

More
----

-  `Compatibility Policy <Compatibility-Policy>`__
-  `Crossbar.io Code License <Crossbar-License>`__
-  `Crossbar.io Documentation License <Documentation-License>`__
-  `Contributing to the
   Project <https://github.com/crossbario/crossbar/blob/master/CONTRIBUTING.md>`__\ \*\*
-  `Contributing FAQ <Contributing%20FAQ>`__
-  `FAQ <FAQ>`__
