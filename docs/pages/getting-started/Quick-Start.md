[Documentation](.) > Quick Start

# Quick Start

This quick start describes how to install Crossbar.io, test the installation and create and run a sample application.


## Install Crossbar.io

> Alternative routes for this generic installation are described in [these guides for specific operating systems](Local-Installation).

You will need [Python](http://python.org) 2/3 or [PyPy](http://pypy.org/) 2 and [pip](https://pip.pypa.io/).

To install Crossbar.io with **required** dependencies:

    pip install crossbar

To install Crossbar.io with **all optional** parts as well:

    pip install crossbar[all]


## Test the Installation

When successful, the installation will have created a `crossbar` command line tool:

```console
(python279_1)oberstet@thinkpad-t430s:~$ which crossbar
/home/oberstet/python279_1/bin/crossbar
(python279_1)oberstet@thinkpad-t430s:~$ ls -la `which crossbar`
-rwxrwxr-x 1 oberstet oberstet 331 Aug 17 21:09 /home/oberstet/python279_1/bin/crossbar
```

> The path to the `crossbar` executable will depend on your environment.

You can then verify the install by running `crossbar version`, which lists the software versions of important Crossbar.io components:

```console
(python279_1)oberstet@thinkpad-t430s:~$ crossbar version
     __  __  __  __  __  __      __     __
    /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
    \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/

Crossbar.io        : 0.11.0
  Autobahn         : 0.10.5.post2
    UTF8 Validator : wsaccel-0.6.2
    XOR Masker     : wsaccel-0.6.2
    JSON Codec     : ujson-1.33
    MsgPack Codec  : msgpack-python-0.4.6
  Twisted          : 15.3.0-EPollReactor
  Python           : 2.7.9/CPython
OS                 : Linux-3.13.0-61-generic-x86_64-with-debian-jessie-sid
Machine            : x86_64
```

## Create an Application

The Crossbar.io command line tool `crossbar` can generate complete, ready-to-run application templates to get you started quickly.

To create a *Hello world!* application with a HTML5/JavaScript frontend and *Python backend*:

    crossbar init --template hello:python --appdir hello

or to create the application with a *NodeJS backend*:

    crossbar init --template hello:nodejs --appdir hello

> You will need to install AutobahnJS for Node by doing `npm install -g autobahn` and have `NODE_PATH` set so Node finds it.

To get a list of available templates:

    crossbar templates

When initializing an application template, a directory will be created with a couple of files prefilled. E.g. the Python variant of the application template will create the following files:

```text
./.crossbar/config.json
./hello/hello.py
./hello/web/autobahn.min.js
./hello/web/index.html
./hello/__init__.py
./MANIFEST.in
./README.md
./setup.py
```

Here, `./.crossbar/config.json` is a configuration file for a Crossbar.io node while the other files are for the application itself.

For further information about getting started with specific languages, see this [overview](Choose your Weapon).


## Run the Application

To start the Crossbar.io node switch to the application directory

    cd hello
    crossbar start

Then open [`http://localhost:8080/`](http://localhost:8080/) in your browser. Make sure to open the JavaScript console as well to see logging output.

What you should see logged is a message such as "Hello from Python" or "Hello from NodeJS", indicating that the JavaScript code running in the browser just successfully called a remote procedure in another WAMP application component implemented in Python or NodeJS.

You can find the backend code in `./hello/hello.py` (for the Python variant) and the frontend code in `./hello/web/index.html`.


## What now?

Go to [Command Line](Command Line) to learn about the Crossbar.io command line tool or jump into [Choose your Weapon](Choose your Weapon) to learn how to get started with your language of choice.
