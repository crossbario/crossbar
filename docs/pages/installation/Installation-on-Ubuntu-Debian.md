title: Installation on Ubuntu and Debian
toc: [Documentation, Installation, Installation on Ubuntu and Debian]

# Installation on Ubuntu and Debian

There are two methods of installing Crossbar.io on Ubuntu and Debian

* [Installing the Binary Packages](#installing-the-official-distribution) **(recommended for Ubuntu)**, or
* [Installing from Source](#installing-from-source)

## Installing the Binary Packages

The binary packages bundle everything needed and provide a fully self-contained, optimized Crossbar.io installation.

Crossbar.io currently hosts official binary packages for **Ubuntu 14.04 LTS** and **Ubuntu 16.04 LTS** on **x86-64**. If this is not OS or architecture you are using, please follow the [Installing from Source](#installing-from-source).

### Add Repository Signing Key

First install our package repository's GPG signing key:

    sudo apt-key adv --keyserver hkps.pool.sks-keyservers.net --recv D58C6920

This only needs to be done once.

> If you are behind a coporate firewall, above command might fail or just hang. Please see [here](http://support.gpgtools.org/kb/faq/cant-reach-key-server-are-you-behind-a-company-firewall) and try with `--keyserver hkp://hkps.pool.sks-keyservers.net:80` in above.

### Add Package Repository

Then add our repo to your machine's apt sources.

For **Ubuntu 14.04 ("Trusty")**:

    sudo sh -c "echo 'deb http://package.crossbar.io/ubuntu trusty main' \
        > /etc/apt/sources.list.d/crossbar.list"

For **Ubuntu 16.04 ("Xenial")**:

    sudo sh -c "echo 'deb http://package.crossbar.io/ubuntu xenial main' \
        > /etc/apt/sources.list.d/crossbar.list"

Again, this only needs to be done once.

### Install the Package

Now update your packages and install Crossbar.io:

    sudo apt-get update
    sudo apt-get install crossbar

The package is installed under `/opt/crossbar`. You can test the installation by running `crossbar version`:

```console
oberstet@office-corei7:~$ /opt/crossbar/bin/crossbar version
     __  __  __  __  __  __      __     __
    /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
    \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/

 Crossbar.io        : 0.13.2
   Autobahn         : 0.13.1 (with JSON, MessagePack, CBOR)
   Twisted          : 16.1.1-EPollReactor
   LMDB             : 0.89/lmdb-0.9.18
   Python           : 2.7.10/PyPy-5.0.1
 OS                 : Linux-4.4.0-22-generic-x86_64-with-debian-stretch-sid
 Machine            : x86_64
```

**Hooray! Installation is complete.**

### Update the Package

To update Crossbar.io later

    sudo apt-get update
    sudo apt-get install --upgrade crossbar


## Installing from Source

When installing from source, you have the choice of running on CPython (the standard Python interpreter) or PyPy (a high performance Python JIT compiler). Both are good choices, but running on PyPy is generally way faster.

This guide will install Crossbar.io in a [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/). **Installing in a virtualenv is highly recommended**.

> Why virtualenv? A virtualenv, as the name suggests, creates a "virtual environment" for your Python packages. This means that you can have newer versions of packages that might already be on your system, without worrying about breaking any applications that might require previous versions.


### Update your system

Update your system, to make sure you have the latest packages:

    sudo apt-get update
    sudo apt-get dist-upgrade

Continue with [Setup for CPython](#setup-for-cpython) or [Setup for PyPy](#setup-for-pypy).


### Setup for CPython

First, install the requirements:

    sudo apt-get install build-essential \
        libssl-dev libffi-dev python-dev python-pip

Then create a new virtualenv:

    virtualenv ~/python-venv

Finally, start working in the virtual environment:

    cd ~/python-venv/
    . bin/activate

Debian ships a very old pip so you must upgrade it in the virtualenv before proceeding:

    pip install --upgrade pip setuptools

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

You can then test the installation by printing out the versions of the Crossbar components.

    crossbar version

To update an existing Crossbar.io installation:

    pip install -U crossbar

From now on, you invoke Crossbar without activating the virtualenv by running `~/pypy-venv/bin/crossbar` or `~/python-venv/bin/crossbar`, depending on which Python interpreter you are using.

**You're done!**
