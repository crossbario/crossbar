[Documentation](.) > [Choose your Weapon](Choose your Weapon) > Getting started with Java

# Getting started with Java

In this recipe we will use Crossbar.io to generate a [WAMP](http://wamp.ws/) application written in Java and using [jawampa](https://github.com/Matthias247/jawampa), an open-source WAMP implementation.

The generated application consists of a [Java/jawampa backend](https://github.com/crossbario/crossbar/blob/master/crossbar/templates/hello/java/src/main/java/ws/wamp/jawampa/CrossbarExample.java) and a [JavaScript/AutobahnJS frontend](https://github.com/crossbario/crossbar/blob/master/crossbar/templates/hello/java/web/index.html) to run in a browser.

The frontend and backend components will talk with each other using all four main interactions available in WAMP:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

We will run the whole application with Crossbar.io serving as a WAMP router, static Web server and jawampa application component host.

## Prerequisites

You will need:

* Java JDK >= 6
* [Apache Maven](http://maven.apache.org/)
* [jawampa](https://github.com/Matthias247/jawampa)

To install JDK and Maven on Ubuntu:

    sudo apt-get install -y default-jdk maven

To install jawampa:

    cd /tmp
    git clone https://github.com/Matthias247/jawampa.git
    cd jawampa
    git checkout 0.1
    mvn install

## Initialize the application template

To instantiate the demo application template, run the following from an arbitrary directory (like `$HOME/mynode1`):

    crossbar init --template hello:java

You should see log output like the following:

```console
oberstet@ubuntu1404:~/mynode1$ crossbar init --template hello:java
Initializing application template 'hello:java' in directory '/home/oberstet/mynode1'
Using template from '/home/oberstet/python278/lib/python2.7/site-packages/crossbar-0.9.9-py2.7.egg/crossbar/templates/hello/java'
Creating directory /home/oberstet/mynode1/.crossbar
Creating directory /home/oberstet/mynode1/web
Creating directory /home/oberstet/mynode1/src
Creating file      /home/oberstet/mynode1/.gitignore
Creating file      /home/oberstet/mynode1/pom.xml
Creating file      /home/oberstet/mynode1/README.md
Creating file      /home/oberstet/mynode1/.crossbar/config.json
Creating file      /home/oberstet/mynode1/web/index.html
Creating file      /home/oberstet/mynode1/web/autobahn.min.js
Creating directory /home/oberstet/mynode1/src/main
Creating directory /home/oberstet/mynode1/src/main/java
Creating directory /home/oberstet/mynode1/src/main/java/ws
Creating directory /home/oberstet/mynode1/src/main/java/ws/wamp
Creating directory /home/oberstet/mynode1/src/main/java/ws/wamp/jawampa
Creating file      /home/oberstet/mynode1/src/main/java/ws/wamp/jawampa/CrossbarExample.java
Application template initialized

Please follow the README.md to build the Java component first, then start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.

oberstet@ubuntu1404:~/mynode1$
```

## Build the jawampa application component

    mvn dependency:copy-dependencies
    mvn compile

You should see log output like the following:

```console
oberstet@ubuntu1404:~/mynode1$ mvn dependency:copy-dependencies
[INFO] Scanning for projects...
[INFO]
[INFO] ------------------------------------------------------------------------
[INFO] Building crossbar_template 0.0.1-SNAPSHOT
[INFO] ------------------------------------------------------------------------
[INFO]
[INFO] --- maven-dependency-plugin:2.1:copy-dependencies (default-cli) @ crossbar_template ---
[INFO] Copying jackson-annotations-2.4.0.jar to /home/oberstet/mynode1/target/dependency/jackson-annotations-2.4.0.jar
[INFO] Copying jackson-core-2.4.2.jar to /home/oberstet/mynode1/target/dependency/jackson-core-2.4.2.jar
[INFO] Copying jackson-databind-2.4.2.jar to /home/oberstet/mynode1/target/dependency/jackson-databind-2.4.2.jar
[INFO] Copying rxjava-core-0.20.4.jar to /home/oberstet/mynode1/target/dependency/rxjava-core-0.20.4.jar
[INFO] Copying netty-buffer-4.0.23.Final.jar to /home/oberstet/mynode1/target/dependency/netty-buffer-4.0.23.Final.jar
[INFO] Copying netty-codec-4.0.23.Final.jar to /home/oberstet/mynode1/target/dependency/netty-codec-4.0.23.Final.jar
[INFO] Copying netty-codec-http-4.0.23.Final.jar to /home/oberstet/mynode1/target/dependency/netty-codec-http-4.0.23.Final.jar
[INFO] Copying netty-common-4.0.23.Final.jar to /home/oberstet/mynode1/target/dependency/netty-common-4.0.23.Final.jar
[INFO] Copying netty-handler-4.0.23.Final.jar to /home/oberstet/mynode1/target/dependency/netty-handler-4.0.23.Final.jar
[INFO] Copying netty-transport-4.0.23.Final.jar to /home/oberstet/mynode1/target/dependency/netty-transport-4.0.23.Final.jar
[INFO] Copying jawampa-0.1.0.jar to /home/oberstet/mynode1/target/dependency/jawampa-0.1.0.jar
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
[INFO] Total time: 3.032s
[INFO] Finished at: Thu Oct 30 22:29:13 CET 2014
[INFO] Final Memory: 11M/92M
[INFO] ------------------------------------------------------------------------
oberstet@ubuntu1404:~/mynode1$ mvn compile
[INFO] Scanning for projects...
[INFO]
[INFO] ------------------------------------------------------------------------
[INFO] Building crossbar_template 0.0.1-SNAPSHOT
[INFO] ------------------------------------------------------------------------
[INFO]
[INFO] --- maven-resources-plugin:2.3:resources (default-resources) @ crossbar_template ---
[WARNING] Using platform encoding (UTF-8 actually) to copy filtered resources, i.e. build is platform dependent!
[INFO] skip non existing resourceDirectory /home/oberstet/mynode1/src/main/resources
[INFO]
[INFO] --- maven-compiler-plugin:3.1:compile (default-compile) @ crossbar_template ---
[INFO] Changes detected - recompiling the module!
[WARNING] File encoding has not been set, using platform encoding UTF-8, i.e. build is platform dependent!
[INFO] Compiling 1 source file to /home/oberstet/mynode1/target/classes
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
[INFO] Total time: 4.530s
[INFO] Finished at: Thu Oct 30 22:29:20 CET 2014
[INFO] Final Memory: 15M/92M
[INFO] ------------------------------------------------------------------------
oberstet@ubuntu1404:~/mynode1$
```

## Start the Crossbar.io node

Now start the Crossbar.io node:

    crossbar start

You should see the node and the jawampa WAMP application component starting:

```console
oberstet@ubuntu1404:~/mynode1$ crossbar start
2014-10-30 22:30:10+0100 [Controller  26720] Log opened.
2014-10-30 22:30:10+0100 [Controller  26720] ============================== Crossbar.io ==============================

2014-10-30 22:30:10+0100 [Controller  26720] Crossbar.io 0.9.9 starting
2014-10-30 22:30:11+0100 [Controller  26720] Running on CPython using EPollReactor reactor
2014-10-30 22:30:11+0100 [Controller  26720] Starting from node directory /home/oberstet/mynode1/.crossbar
2014-10-30 22:30:11+0100 [Controller  26720] Starting from local configuration '/home/oberstet/mynode1/.crossbar/config.json'
2014-10-30 22:30:11+0100 [Controller  26720] No WAMPlets detected in enviroment.
2014-10-30 22:30:11+0100 [Controller  26720] Starting Router with ID 'worker1' ..
2014-10-30 22:30:11+0100 [Controller  26720] Entering reactor event loop ...
2014-10-30 22:30:11+0100 [Router      26729] Log opened.
2014-10-30 22:30:12+0100 [Router      26729] Running under CPython using EPollReactor reactor
2014-10-30 22:30:12+0100 [Router      26729] Entering event loop ..
2014-10-30 22:30:12+0100 [Controller  26720] Router with ID 'worker1' and PID 26729 started
2014-10-30 22:30:12+0100 [Controller  26720] Router 'worker1': realm 'realm1' started
2014-10-30 22:30:12+0100 [Controller  26720] Router 'worker1': role 'role1' started on realm 'realm1'
2014-10-30 22:30:12+0100 [Router      26729] Site starting on 8080
2014-10-30 22:30:12+0100 [Controller  26720] Router 'worker1': transport 'transport1' started
2014-10-30 22:30:12+0100 [Controller  26720] Starting Guest with ID 'worker2' ..
2014-10-30 22:30:12+0100 [Controller  26720] GuestWorkerClientProtocol.connectionMade
2014-10-30 22:30:12+0100 [Controller  26720] Guest with ID 'worker2' and PID 26732 started
2014-10-30 22:30:12+0100 [Controller  26720] Guest 'worker2': started
2014-10-30 22:30:13+0100 [Guest       26732] Session status changed to Disconnected
2014-10-30 22:30:13+0100 [Guest       26732] Session status changed to Connecting
2014-10-30 22:30:14+0100 [Guest       26732] Session status changed to Connected
...
```

Now open your browser at [http://127.0.0.1:8080](http://127.0.0.1:8080) and watch the JavaScript console output.

![Hello from Java](/static/img/docs/getting_started_with_java_01.png)
