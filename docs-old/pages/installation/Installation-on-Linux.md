title: Installation on Linux
toc: [Documentation, Installation, Installation on Linux]

# Installation on Linux

We provide Docker containers for Crossbar.io, which we suggest as the easiest way of getting started.

If you don't want to use this option, then here's how to install Crossbar.io from sources on any generic Linux.

This is a reliable, quick way of installation that does not require superuser rights, can install to any location (such as your home directory) and does not depend on system Python packages.

> Note: This recipe was tested on a completely fresh install of [Ubuntu](http://www.ubuntu.com/) [14.04 LTS 64-bit Server](http://www.ubuntu.com/download/server) running as a [Oracle VirtualBox](https://www.virtualbox.org/) virtual machine.

## Prepare

### Debian

After a fresh install of Ubuntu 16.04 LTS 64-bit Server, first make sure your system packages are fully up to date:

    sudo apt-get update
    sudo apt-get -y dist-upgrade

Then install the prerequisites:

    sudo apt-get -y install build-essential libssl-dev libffi-dev \
       libreadline-dev libbz2-dev libsqlite3-dev libncurses5-dev

### CentOS 7

After a fresh install of CentOS 7 64bit, first make sure your system packages are fully up to date:

    sudo yum update

Then install the prerequisites:

    yum install gcc gcc-c++ make openssl-devel libffi-devel

Now continue to build for:

 1. [CPython](#install-for-cpython) or
 2. [PyPy](#install-for-pypy)

> Crossbar.io can be run using regular Python (CPython) or PyPy, a Just-in-Time-Compiler for Python. The latter speeds up the Python code, so that Crossbar.io is more performant (lower latencies, higher possible throughput). On the downside, Crossbar. io running on PyPy requires more memory, takes longer to start up, and the speed increases require some period of operation (the JIT-compiler needs some data about actual program execution to work with).

> The instructions here are for Python 2.7, but Crossbar.io runs on Python >=3.5 as well. PyPy support for Python 3.5 may be incomplete, so for PyPy and for the time being, it's best to use Python 2.7.

## Install for CPython

After the [prepare-step](#prepare), build Python from vanilla sources and install it to your home directory:

    cd $HOME
    wget https://www.python.org/ftp/python/2.7.13/Python-2.7.13.tar.xz
    tar xvf Python-2.7.13.tar.xz
    cd Python-2.7.13
    ./configure --prefix=$HOME/python2713
    make
    make install

()

Install [Pip](https://pypi.python.org/pypi/pip) and make sure it is the latest version:

    ~/python2713/bin/python -m ensurepip
    ~/python2713/bin/python -m pip install -U pip

Install Crossbar and its dependencies from [PyPI](https://pypi.python.org/pypi/crossbar):

    ~/python2713/bin/pip install crossbar

Check the Crossbar installation:

```console
$ ~/python2713/bin/crossbar version
     __  __  __  __  __  __      __     __
    /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
    \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/

 Crossbar.io        : 0.13.2
   Autobahn         : 0.14.0 (with JSON, MessagePack, CBOR)
   Twisted          : 16.1.1-EPollReactor
   LMDB             : 0.89/lmdb-0.9.18
   Python           : 2.7.11/CPython
 OS                 : Linux-4.4.0-22-generic-x86_64-with-debian-stretch-sid
 Machine            : x86_64

```

If everything went fine, add the following to your `$HOME/.profile`:

```shell
export PATH=${HOME}/python2713/bin:${PATH}
```

## Install for PyPy

After the [prepare-step](#prepare), install PyPy to your home directory:

    cd $HOME
    wget https://bitbucket.org/pypy/pypy/downloads/pypy-5.1.1-linux64.tar.bz2
    tar xvjf pypy-5.1.1-linux64.tar.bz2

Install [Pip](https://pypi.python.org/pypi/pip) and make sure it is the latest version:

    ~/pypy-5.1.1-linux64/bin/pypy -m ensurepip
    ~/pypy-5.1.1-linux64/bin/pypy -m pip install -U pip

Now, to install Crossbar from [PyPI](https://pypi.python.org/pypi/crossbar):

    ~/pypy-5.1.1-linux64/bin/pip install crossbar

Check the Crossbar installation:

```console
$ ~/pypy-5.1.1-linux64/bin/crossbar version
     __  __  __  __  __  __      __     __
    /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
    \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/

 Crossbar.io        : 0.13.2
   Autobahn         : 0.14.0 (with JSON, MessagePack, CBOR)
   Twisted          : 16.1.1-EPollReactor
   LMDB             : 0.89/lmdb-0.9.18
   Python           : 2.7.10/PyPy-5.1.1
 OS                 : Linux-4.4.0-22-generic-x86_64-with-debian-stretch-sid
 Machine            : x86_64

```

If everything went fine, add the following to your `$HOME/.profile`:

```shell
export PATH=${HOME}/pypy-5.1.1-linux64/bin:${PATH}
```

## Updating to newest release

Once you've installed Crossbar.io, you can update to the newest release version at any time by doing

    pip install -U crossbar


## Updating to current develepment version

If you want to update to the most current development version (e.g. for testing), you can do so from the git repository.

### Cloning the repo

> Note: The Amazon EC2 or Microsoft Azure images we provide already have the git repository cloned.*

You need to have [git](http://git-scm.com/) installed.

Then clone the repository into a directory `crossbar` in your current directory. If you're not registered on GitHub you can clone the repository by doing

    git clone https://github.com/crossbario/crossbar.git

else we suggest using SSH

    git clone git@github.com:crossbario/crossbar.git

If you want to name the directory differently, just add that directory name at the end, e.g.

### Pulling changes

Unless you've just cloned the repository, you need to update it before installing. In a shell, in the repository directory, do

    git pull

## Update Crossbar.io

Then you can update your Crossbar.io installation by doing

    cd crossbar
    pip install --upgrade -e .

> On Windows, this will most likely require installing the [Microsoft Visual C++ Compiler for Python 2.7](http://www.microsoft.com/en-us/download/details.aspx?id=44266).
