This project contains the jawampa template for [crossbar.io](http://crossbar.io)
================================================================================

**Prerequisites:**
- JDK >= 6
- Maven
- jawampa in the matching version

**jawampa** can be installed into the local maven repository in the following
way:
~~~~
git clone https://github.com/Matthias247/jawampa.git
cd jawampa
git checkout 0.1
mvn install
~~~~

The example/template application can then be compiled and started in the
following way (starting in the examples root directory):
~~~~
mvn compile
mvn exec:java -Dexec.mainClass="ws.wamp.jawampa.CrossbarExample" -Dexec.args="ws://localhost:8080/ws realm1"
~~~~

Starting the template requires 2 commandline arguments
- The URL of the router
- The realm to join on the router

Alternative:
- Import the template application as a maven project into your IDE
- Setup a launch configuration for `ws.wamp.jawampa.CrossbarExample` and
  and the commandline arguments there.
- Run the application from inside your IDE.
