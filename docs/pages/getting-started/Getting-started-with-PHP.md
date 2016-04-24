[Documentation](.) > [Choose your Weapon](Choose your Weapon) > Getting started with PHP

# Getting started with PHP

In this recipe we will use Crossbar.io to generate an application template for a [WAMP](http://wamp.ws/) application written in [PHP](http://php.net/) using [Thruway](https://github.com/voryx/Thruway), an open-source WAMP implementation for PHP. The generated application includes a JavaScript frontend to run in a browser.

The frontend and backend components will talk with each other using all four main interactions available in WAMP:

1. call a remote procedure
2. register a procedure for remote calling
3. publish an event to a topic
4. subscribe to a topic to receive events

We will run the whole application with Crossbar.io serving as a WAMP router, static Web server and PHP/Thruway application component host.

## Prerequisites

Install [PHP](http://www.php.net/) and [Composer](https://getcomposer.org/):

    sudo apt-get install -y php5-cli php5-json curl
    curl -s http://getcomposer.org/installer | php
    sudo mv composer.phar /usr/local/bin/composer

# Create an example application

To create a new Crossbar.io node and generate a [PHP](http://www.php.net/) / [Thruway](https://github.com/voryx/Thruway) based "Hello world!" example application:

    crossbar init --template hello:php --appdir $HOME/hello

This will initialize a new node and application under `$HOME/hello` using the application template `hello:php`.

> To get a list of available templates, use `crossbar templates`.

You should see the application template being initialized:

```console
oberstet@ubuntu1404:~$ crossbar init --template hello:php --appdir $HOME/hello
Crossbar.io application directory '/home/oberstet/hello' created
Initializing application template 'hello:php' in directory '/home/oberstet/hello'
Creating directory /home/oberstet/hello/.crossbar
Creating directory /home/oberstet/hello/web
Creating file      /home/oberstet/hello/README.md
Creating file      /home/oberstet/hello/client.php
Creating file      /home/oberstet/hello/Makefile
Creating file      /home/oberstet/hello/.gitignore
Creating file      /home/oberstet/hello/.crossbar/config.json
Creating file      /home/oberstet/hello/web/index.html
Creating file      /home/oberstet/hello/web/autobahn.min.js
Application template initialized

Now install dependencies for the PHP/Thruway client by entering 'make install', start Crossbar using 'crossbar start' and open http://localhost:8080 in your browser.
```

## Install example dependencies

The dependencies for the PHP example need to be *installed* (once):

    cd $HOME/hello
    make install

## Start the node

Start your new Crossbar.io node using:

    cd $HOME/hello
    crossbar start

You should see the node starting:

```console
oberstet@ubuntu1404:~/hello$ crossbar start
2014-06-25 15:34:23+0200 [Controller  28900] Log opened.
2014-06-25 15:34:23+0200 [Controller  28900] ============================== Crossbar.io ==============================

2014-06-25 15:34:23+0200 [Controller  28900] Crossbar.io 0.9.6 starting
2014-06-25 15:34:23+0200 [Controller  28900] Running on CPython using EPollReactor reactor
2014-06-25 15:34:23+0200 [Controller  28900] Starting from node directory /home/oberstet/hello/.crossbar
2014-06-25 15:34:23+0200 [Controller  28900] Starting from local configuration '/home/oberstet/hello/.crossbar/config.json'
2014-06-25 15:34:23+0200 [Controller  28900] No WAMPlets detected in enviroment.
2014-06-25 15:34:23+0200 [Controller  28900] Starting Router with ID 'worker1' ..
2014-06-25 15:34:23+0200 [Router      28909] Log opened.
2014-06-25 15:34:24+0200 [Router      28909] Running under CPython using EPollReactor reactor
2014-06-25 15:34:24+0200 [Router      28909] Entering event loop ..
2014-06-25 15:34:24+0200 [Controller  28900] Router with ID 'worker1' and PID 28909 started
2014-06-25 15:34:24+0200 [Router      28909] Monkey-patched MIME table (0 of 551 entries)
2014-06-25 15:34:24+0200 [Router      28909] Site starting on 8080
2014-06-25 15:34:24+0200 [Controller  28900] Router 'worker1': transport 'transport1' started
2014-06-25 15:34:24+0200 [Controller  28900] Starting Guest with ID 'worker2' ..
2014-06-25 15:34:24+0200 [Controller  28900] GuestWorkerClientProtocol.connectionMade
2014-06-25 15:34:24+0200 [Controller  28900] Guest with ID 'worker2' and PID 28912 started
2014-06-25 15:34:24+0200 [Controller  28900] Guest 'worker2': started
2014-06-25 15:34:24+0200 [Guest       28912] Starting Transport
2014-06-25 15:34:24+0200 [Guest       28912] Pawl has connected
2014-06-25 15:34:24+0200 [Guest       28912] Received: [2,440447902995220,{"authrole":"anonymous","authmethod":"anonymous","authprovider":"anonymous","roles":{"broker":{"features":{"publisher_identification":true,"publisher_exclusion":true,"subscriber_blackwhite_listing":true}},"dealer":{"features":{"progressive_call_results":true,"caller_identification":true}}},"authid":"anonymous"}]
2014-06-25 15:34:24+0200 [Guest       28912] Received: [33,1471889554668967,8790061651978363]
2014-06-25 15:34:24+0200 [Guest       28912] Received: [17,1471889554670221,2585505197144630]
2014-06-25 15:34:24+0200 [Guest       28912] Publish Acknowledged!
2014-06-25 15:34:24+0200 [Guest       28912] Received: [65,1471889554673262,8658327088018463]
2014-06-25 15:34:24+0200 [Guest       28912] Received: [68,4406464655528414,8658327088018463,{},[2,3)
2014-06-25 15:34:24+0200 [Guest       28912] Received: [50,1471889554675782,{},[5)
2014-06-25 15:34:24+0200 [Guest       28912] Result: 5
...
```

The Crossbar example configuration has started a WAMP router and a guest worker running the PHP/Thruway based application component. It also runs a Web server for serving static Web content.


## Open the frontend

Open [`http://localhost:8080/`](http://localhost:8080/) (or wherever Crossbar runs) in your browser. When you watch the browser's JavaScript console, you should see

![Hello from PHP](/static/img/docs/shots/hello_php.png)

Hooray! That means: it works;)

You have just called a PHP procedure from JavaScript running in the browser. The call was transferred via WAMP, and routed by Crossbar.io between the application front- and backend components.

## Hacking the code

All the PHP backend code is in the file `client.php`. All the JavaScript frontend code is in `web/index.html`.

## Useful links

The [Thruway project site](https://github.com/voryx/Thruway) provides some documentation on Thruway in its [wiki](https://github.com/voryx/Thruway/wiki).

[Minion](https://github.com/Vinelab/minion) is a project which builds on Thruway and provides a simplified interface for getting clients up and running.

The [Crossbar HTTP Publisher Bundle](https://github.com/facile-it/crossbar-http-publisher-bundle) provides a neat wrapper for submitting PubSub events via a [Crossbar HTTP Publisher](HTTP Bridge Publisher).