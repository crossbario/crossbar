[Documentation](.) > [Administration](Administration) > The Command Line

# The Command Line

Crossbar.io comes as a command line tool `crossbar` which works identical across all supported platforms.

* [Quick Reference](#quick-reference)
* [Getting Help](#getting-help)
* [Initializing a Node](#initializing-a-node)
* [Starting and Stopping a Node](#starting-and-stopping-a-node)

## Quick Reference

Here is a quick reference of all commands available in the Crossbar.io CLI:

Command | Description
--- | ---
`crossbar --help` | Get help
`crossbar <command> --help` | Get help on `command` (see below)
`crossbar version` | Print Crossbar.io version
`crossbar init` | Initializes a new Crossbar.io node from an application template
`crossbar start` | Starts a Crossbar.io node
`crossbar stop` | Stops a Crossbar.io node
`crossbar restart` | Restarts a Crossbar.io node
`crossbar status` | Check if a Crossbar.io node is running
`crossbar convert` | Converts a Crossbar.io node configuration file from JSON to YAML and vice-versa

---

## Getting Help

To get help, type `crossbar --help`:

```console
(python279_1)oberstet@thinkpad-t430s:~/mynode1$ crossbar --help
usage: crossbar [-h] [--reactor {select,poll,epoll,kqueue,iocp}]
                {version,init,templates,start,stop,restart,status,check,convert}
                ...

Crossbar.io - Polyglot application router - http://crossbar.io

optional arguments:
  -h, --help            show this help message and exit
  --reactor {select,poll,epoll,kqueue,iocp}
                        Explicit Twisted reactor selection

commands:
  {version,init,templates,start,stop,restart,status,check,convert}
                        Crossbar.io command to run
    version             Print software versions.
    init                Initialize a new Crossbar.io node.
    templates           List templates available for initializing a new
                        Crossbar.io node.
    start               Start a Crossbar.io node.
    stop                Stop a Crossbar.io node.
    restart             Restart a Crossbar.io node.
    status              Checks whether a Crossbar.io node is running.
    check               Check a Crossbar.io node`s local configuration file.
    convert             Convert a Crossbar.io node`s local configuration file
                        from JSON to YAML or vice versa.
```

The `crossbar` tool has multiple subcommands, and you can get help on those also, e.g. `crossbar init --help`:

```console
(python279_1)oberstet@thinkpad-t430s:~/mynode1$ crossbar init --help
usage: crossbar init [-h] [--template TEMPLATE] [--appdir APPDIR]

optional arguments:
  -h, --help           show this help message and exit
  --template TEMPLATE  Template for initialization
  --appdir APPDIR      Application base directory where to create app and node
                       from template.
```

---

## Initializing a Node

Crossbar.io runs from a node directory. The node directory, usually `.crossbar`, contains a node configuration file `.crossbar/config.json` and other data such as log files. It is for internal use, and you should not add or modify files other than the `config.json`.

You can initialize a new node by doing:

```console
(python279_1)oberstet@thinkpad-t430s:~/mynode1$ crossbar init --template default
Initializing application template 'default' in directory '/home/oberstet/mynode1'
Using template from '/home/oberstet/python279_1/lib/python2.7/site-packages/crossbar-0.11.0-py2.7.egg/crossbar/templates/default'
Creating directory /home/oberstet/mynode1/.crossbar
Creating file      /home/oberstet/mynode1/.crossbar/config.json
Application template initialized

To start your node, run 'crossbar start --cbdir /home/oberstet/mynode1/.crossbar'
```

In this example, `/home/oberstet/mynode/.crossbar` is the Crossbar.io **node directory**.

The initialization above was done using the default template. Node templates are a quick and easy way of creating a new node. There are additional templates besides the basic default one. Some of these create working sample application for a specific language.

You can list the available templates by running `crossbar templates`:

```console
(python279_1)oberstet@thinkpad-t430s:~/mynode1$ crossbar templates

Available Crossbar.io node templates:

  default          A WAMP router speaking WebSocket plus a static Web server.
  hello:python     A minimal Python WAMP application hosted in a router and a HTML5 client.
  hello:nodejs     A minimal NodeJS WAMP application hosted in a router and a HTML5 client.
  hello:browser    A minimal JavaAScript WAMP application with two components running in the browser.
  hello:cpp        A minimal C++11/AutobahnCpp WAMP application hosted in a router and a HTML5 client.
  hello:csharp     A minimal C#/WampSharp WAMP application hosted in a router and a HTML5 client.
  hello:erlang     A minimal Erlang/Erwa WAMP application hosted in a router and a HTML5 client.
  hello:php        A minimal PHP/Thruway WAMP application hosted in a router and a HTML5 client.
  hello:java       A minimal Java/jawampa WAMP application hosted in a router and a HTML5 client.
  hello:tessel     A minimal JavaScript/wamp-tessel WAMP application running on a Tessel and with a HTML5 client.
```

---

## Starting and Stopping a Node

To **start** your Crossbar.io node:

```console
(python279_1)oberstet@thinkpad-t430s:~/mynode1$ crossbar start
2015-08-30T19:25:45+0200 [Controller   9187]      __  __  __  __  __  __      __     __
2015-08-30T19:25:45+0200 [Controller   9187]     /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
2015-08-30T19:25:45+0200 [Controller   9187]     \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/
2015-08-30T19:25:45+0200 [Controller   9187]
2015-08-30T19:25:45+0200 [Controller   9187]     Version: 0.11.0
2015-08-30T19:25:45+0200 [Controller   9187]
2015-08-30T19:25:45+0200 [Controller   9187] Starting from node directory /home/oberstet/mynode1/.crossbar
2015-08-30T19:25:45+0200 [Controller   9187] Loading node configuration file '/home/oberstet/mynode1/.crossbar/config.json'
2015-08-30T19:25:45+0200 [Controller   9187] Entering reactor event loop...
2015-08-30T19:25:45+0200 [Controller   9187] Joined realm 'crossbar' on node management router
2015-08-30T19:25:45+0200 [Controller   9187] No WAMPlets detected in enviroment.
2015-08-30T19:25:45+0200 [Controller   9187] Starting Router with ID 'worker1'...
2015-08-30T19:25:46+0200 [Router       9192] Worker running under CPython-EPollReactor
2015-08-30T19:25:46+0200 [Controller   9187] Router with ID 'worker1' and PID 9192 started
2015-08-30T19:25:46+0200 [Controller   9187] Router 'worker1': realm 'realm1' (named 'realm1') started
2015-08-30T19:25:46+0200 [Controller   9187] Router 'worker1': role 'role1' (named 'anonymous') started on realm 'realm1'
2015-08-30T19:25:46+0200 [Router       9192] Site starting on 8080
2015-08-30T19:25:46+0200 [Controller   9187] Router 'worker1': transport 'transport1' started
...
```

In this case, Crossbar.io has automatically detected the node directory by its canonical name `.crossbar` and used the configuration `.crossbar/config.json`.

You can set a different node directory via the command line option `--cbdir` or via an environment variable `CROSSBAR_DIR`.

Open **http://localhost:8080** in your browser. You should see a 404 page rendered by Crossbar.io. Which means: it works!

![Crossbar.io 404 page](/static/img/docs/shots/crossbar_404.png)

To **stop** your Crossbar.io node, just hit CTRL-C:

```console
^C2015-08-30T19:27:11+0200 [Controller   9187] Received SIGINT, shutting down.
2015-08-30T19:27:11+0200 [Controller   9187] sending TERM to subprocess 9192
2015-08-30T19:27:11+0200 [Controller   9187] waiting for 9192 to exit...
2015-08-30T19:27:11+0200 [Router       9192] Received SIGTERM, shutting down.
2015-08-30T19:27:11+0200 [Router       9192] Connection to node controller lost.
2015-08-30T19:27:11+0200 [Router       9192] Lost connection to '<pipe>': Connection lost
2015-08-30T19:27:11+0200 [Router       9192] No more controller connection; shutting down.
2015-08-30T19:27:11+0200 [Router       9192] (TCP Port 8080 Closed)
2015-08-30T19:27:11+0200 [Controller   9187] Process connection gone: A process has ended with a probable error condition: process ended with exit code 1.
2015-08-30T19:27:11+0200 [Controller   9187] Lost connection to 'process 9192': process ended with exit code 1
2015-08-30T19:27:11+0200 [Controller   9187] Node worker worker1 ended (0 workers left)
2015-08-30T19:27:11+0200 [Controller   9187] Node shutting down ..
2015-08-30T19:27:11+0200 [Controller   9187] Shutting down node...
2015-08-30T19:27:11+0200 [Controller   9187] Main loop terminated.
(python279_1)oberstet@thinkpad-t430s:~/mynode1$
```

---
