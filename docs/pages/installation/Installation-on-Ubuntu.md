title: Installation on Ubuntu
toc: [Documentation, Installation, Local Installation, Installation on Ubuntu]

# Installation on Ubuntu

There are two methods of installing Crossbar.io on Ubuntu

* [from the official distribution](#installing-the-official-distribution) (recommended), or
* [from source](#installing-from-source)

## Installing the Official Distribution

Crossbar.io hosts official binary packages for **Ubuntu 14.04 LTS**.

> If this is not the version of Ubuntu you are using, please install from source as mentioned below.

First, install the repo's GPG key:

    sudo apt-key adv --keyserver hkps.pool.sks-keyservers.net --recv D58C6920

> If you are behind a coporate firewall, above command might fail or just hang. Please see [here](http://support.gpgtools.org/kb/faq/cant-reach-key-server-are-you-behind-a-company-firewall) and try with `--keyserver hkp://hkps.pool.sks-keyservers.net:80` in above.

Then add the repo to your server's apt sources:

    sudo sh -c "echo 'deb http://package.crossbar.io/ubuntu trusty main' \
        > /etc/apt/sources.list.d/crossbar.list"

Update your package sources:

    sudo apt-get update

Install Crossbar.io:

    sudo apt-get install crossbar

You can then test the installation by printing out the versions of the Crossbar components.

    /opt/crossbar/bin/crossbar version

**You're done!**

Ready for more? Then [choose your language or device of choice](Choose your Weapon).

---

## Installing from Source

When installing from source, you have the choice of installing on CPython (the standard interpreter) or PyPy (a high performance interpreter).
Both are good choices, but PyPy is generally faster (at the cost of a little extra RAM).

This guide will install Crossbar.io in a [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/).

> *Why virtualenv?* Virtualenv, as the name suggests, creates a "virtual environment" for your Python packages. This means that you can have newer versions of packages that might already be on your system, without worrying about breaking any applications that might require previous versions.


### Update your system

Update your system, to make sure you have the latest packages:

    sudo apt-get update
    sudo apt-get dist-upgrade

Continue with [Setup for CPython](#setup-for-cpython) or [Setup for PyPy](#setup-for-pypy).


### Setup for CPython

First, install the requirements:

    sudo apt-get install build-essential libssl-dev libffi-dev python-dev python-pip

Then create a new virtualenv:

    virtualenv ~/python-venv

Finally, start working in the virtual environment:

    cd ~/python-venv/
    . bin/activate

Continue with the step [Installing Crossbar.io](#installing-crossbar.io).


### Setup for PyPy

Add the PyPy PPA:

    sudo apt-add-repository ppa:pypy/ubuntu/ppa
    sudo apt-get update

Install [PyPy](http://pypy.org/), pip, and build requirements:

    sudo apt-get install build-essential libssl-dev python-pip pypy pypy-dev

Then install virtualenv through pip:

    sudo pip install virtualenv

Create a PyPy virtualenv in the directory `pypy-venv`:

    virtualenv --python=pypy ~/pypy-venv

Finally, start working in the virtual environment:

    cd ~/pypy-venv/
    . bin/activate

Continue with the step [Installing Crossbar.io](#installing-crossbar.io).


### Installing Crossbar.io

To install Crossbar.io

    pip install crossbar

To check the installation:

```console
(pypy-venv)hawkowl@ubuntu-14-10:~/pypy-venv$ crossbar version

Crossbar.io package versions and platform information:

Crossbar.io                  : 0.10.1

  Autobahn|Python            : 0.9.5
    WebSocket UTF8 Validator : autobahn
    WebSocket XOR Masker     : autobahn
    WAMP JSON Codec          : stdlib
    WAMP MsgPack Codec       : msgpack-python-0.4.5
  Twisted                    : 15.0.0-EPollReactor
  Python                     : 2.7.8-PyPy

OS                           : Linux-3.16.0-30-generic-x86_64-with-Ubuntu-14.10-utopic
Machine                      : x86_64
```

To update an existing Crossbar.io installation:

    pip install -U crossbar

You can then invoke Crossbar without activating the virtualenv by running `~/pypy-venv/bin/crossbar` or `~/python-venv/bin/crossbar`, depending on which Python interpreter you are using.

---

## Next

Ready to go? Then [choose your language or device of choice](Choose your Weapon).