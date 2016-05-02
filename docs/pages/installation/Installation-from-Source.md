title: Installation from Source
toc: [Documentation, Installation, Local Installation, Installation from Source]

# Installation from Source

Here is how to build Python or PyPy and Crossbar.io from sources.

This is a reliable, quick way of installation that does not require superuser rights, can install to any location (such as your home directory) and does not depend on system Python packages.

> Note: This recipe was tested on a completely fresh install of [Ubuntu](http://www.ubuntu.com/) [14.04 LTS 64-bit Server](http://www.ubuntu.com/download/server) running as a [Oracle VirtualBox](https://www.virtualbox.org/) virtual machine.

## Prepare

After a fresh install of Linux (we use Ubuntu 14.04 LTS 64-bit Server), first update your system (recommended):

    sudo apt-get update
    sudo apt-get -y dist-upgrade

and reboot. Then install the prerequisites:

    sudo apt-get -y install build-essential libssl-dev libffi-dev \
       libreadline-dev libbz2-dev libsqlite3-dev libncurses5-dev

> Note: These packages really should be installed system-wide, whereas the Python and Crossbar.io we build and install in an arbitrary (non-system) location.

Now continue to build for:

 1. [CPython](#cpython) or
 2. [PyPy](#pypy)


## CPython

After the [prepare-step](#prepare), build Python from vanilla sources and install it to your home directory:

    cd $HOME
    wget https://www.python.org/ftp/python/2.7.8/Python-2.7.8.tar.xz
    tar xvf Python-2.7.8.tar.xz
    cd Python-2.7.8
    ./configure --prefix=$HOME/python278
    make
    make install

Install [Pip](https://pypi.python.org/pypi/pip):

    wget https://bootstrap.pypa.io/get-pip.py
    ~/python278/bin/python get-pip.py

Now, to install Crossbar from [PyPi](https://pypi.python.org/pypi/crossbar):

    ~/python278/bin/pip install crossbar

**or** install Crossbar directly from [GitHub](https://github.com/crossbario/crossbar):

    cd $HOME
    git clone git@github.com:crossbario/crossbar.git
    cd crossbar/crossbar
    git tag -l
    git checkout v0.9.4
    ~/python278/bin/pip install -e .[all]

> Generally, you should only use *tagged* versions from the source tree. The *head* of *master* and/or other branches than *master* might be broken or incomplete.

Check the Crossbar installation:

```console
$v~/python278/bin/crossbar version
Crossbar.io software versions:

Crossbar.io     : 0.9.6-2
Autobahn        : 0.8.10
Twisted         : 13.2.0-IOCPReactor
Python          : 2.7.5
UTF8 Validator  : autobahn
XOR Masker      : autobahn
```

If everything went fine, add the following to your `$HOME/.profile`:

```shell
export PATH=${HOME}/python278/bin:${PATH}
```

## PyPy

After the [prepare-step](#prepare), install PyPy to your home directory:

    cd $HOME
    wget https://bitbucket.org/pypy/pypy/downloads/pypy-2.3-linux64.tar.bz2
    tar xvjf pypy-2.3-linux64.tar.bz2

Install [Pip](https://pypi.python.org/pypi/pip):

    wget https://bootstrap.pypa.io/get-pip.py
    ~/pypy-2.3-linux64/bin/pypy get-pip.py

Now, to install Crossbar from [PyPi](https://pypi.python.org/pypi/crossbar):

    ~/pypy-2.3-linux64/bin/pip install crossbar

**or** install Crossbar directly from [GitHub](https://github.com/crossbario/crossbar):

    cd $HOME
    git clone git@github.com:crossbario/crossbar.git
    cd crossbar/crossbar
    git tag -l
    git checkout v0.9.4
    ~/pypy-2.3-linux64/bin/pip install -e .[all]

> Generally, you should only use *tagged* versions from the source tree. The *head* of *master* and/or other branches than *master* might be broken or incomplete.

Check the Crossbar installation:

```console
$ ~/pypy-2.3-linux64/bin/crossbar version
Crossbar.io software versions:

Crossbar.io     : 0.9.6-2
Autobahn        : 0.8.10
Twisted         : 13.2.0-IOCPReactor
Python          : 2.7.5
UTF8 Validator  : autobahn
XOR Masker      : autobahn
```

If everything went fine, add the following to your `$HOME/.profile`:

```shell
export PATH=${HOME}/pypy-2.3-linux64/bin:${PATH}
```

## Updating from the Repository

Once you've installed Crossbar.io, you can **update to the newest release version** at any time by doing

    pip install -U crossbar

If you want to **update to the most current development version** (e.g. for testing), you can do so from the git repository.

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
    pip install --upgrade -e .[all]

> On Windows, this will most likely  require installing the [Microsoft Visual C++ Compiler for Python 2.7](http://www.microsoft.com/en-us/download/details.aspx?id=44266).

## Installation Logs

Here is a complete installation log from Crossbar.io on **Python 3.**4

```console
(python342_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$ make install
pip install --upgrade -e .[all]
You are using pip version 6.0.6, however version 7.1.2 is available.
You should consider upgrading via the 'pip install --upgrade pip' command.
Obtaining file:///home/oberstet/scm/crossbar/crossbar
Requirement already up-to-date: click>=4.1 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: setuptools>=18.1 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: zope.interface>=3.6.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: twisted>=15.3.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: autobahn[twisted]>=0.10.5 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: netaddr>=0.7.15 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pytrie>=0.2 in /home/oberstet/python342_1/lib/python3.4/site-packages/PyTrie-0.2-py3.4.egg (from crossbar==0.11.0)
Requirement already up-to-date: jinja2>=2.8 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: mistune>=0.7 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pygments>=2.0.2 in /home/oberstet/python342_1/lib/python3.4/site-packages/Pygments-2.0.2-py3.4.egg (from crossbar==0.11.0)
Requirement already up-to-date: pyyaml>=3.11 in /home/oberstet/python342_1/lib/python3.4/site-packages/PyYAML-3.11-py3.4-linux-x86_64.egg (from crossbar==0.11.0)
Requirement already up-to-date: shutilwhich>=1.1.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: treq>=15.0.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: psutil>=3.1.1 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: setproctitle>=1.1.9 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyinotify>=0.9.6 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: lmdb>=0.87 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyasn1>=0.1.8 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pycrypto>=2.6.1 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: msgpack-python>=0.4.6 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: cryptography>=0.9.3 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyOpenSSL>=0.15.1 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyasn1-modules>=0.0.7 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: service-identity>=14.0.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: wsaccel>=0.6.2 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: ujson>=1.33 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: colorama>=0.3.3 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: mock>=1.3.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: six>=1.6.1 in /home/oberstet/python342_1/lib/python3.4/site-packages (from autobahn[twisted]>=0.10.5->crossbar==0.11.0)
Requirement already up-to-date: txaio>=1.0.2 in /home/oberstet/python342_1/lib/python3.4/site-packages (from autobahn[twisted]>=0.10.5->crossbar==0.11.0)
Requirement already up-to-date: MarkupSafe in /home/oberstet/python342_1/lib/python3.4/site-packages/MarkupSafe-0.23-py3.4-linux-x86_64.egg (from jinja2>=2.8->crossbar==0.11.0)
Requirement already up-to-date: requests in /home/oberstet/python342_1/lib/python3.4/site-packages (from treq>=15.0.0->crossbar==0.11.0)
Requirement already up-to-date: idna>=2.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from cryptography>=0.9.3->crossbar==0.11.0)
Requirement already up-to-date: cffi>=1.1.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from cryptography>=0.9.3->crossbar==0.11.0)
Requirement already up-to-date: characteristic>=14.0.0 in /home/oberstet/python342_1/lib/python3.4/site-packages (from service-identity>=14.0.0->crossbar==0.11.0)
Requirement already up-to-date: pbr>=0.11 in /home/oberstet/python342_1/lib/python3.4/site-packages (from mock>=1.3.0->crossbar==0.11.0)
Requirement already up-to-date: pycparser in /home/oberstet/python342_1/lib/python3.4/site-packages (from cffi>=1.1.0->cryptography>=0.9.3->crossbar==0.11.0)
Installing collected packages: crossbar
  Running setup.py develop for crossbar
    Creating /home/oberstet/python342_1/lib/python3.4/site-packages/crossbar.egg-link (link to .)
    crossbar 0.11.0 is already the active version in easy-install.pth
    Installing crossbar script to /home/oberstet/python342_1/bin
    Installed /home/oberstet/scm/crossbar/crossbar
Successfully installed crossbar-0.11.0
(python342_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$ which crossbar
/home/oberstet/python342_1/bin/crossbar
(python342_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$ crossbar version
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
  Python           : 3.4.2/CPython
OS                 : Linux-3.13.0-62-generic-x86_64-with-debian-jessie-sid
Machine            : x86_64

(python342_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$
```

And here is an installation log for Crossbar.io on **Python 2.7**:

```console
(python279_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$ make install
pip install --upgrade -e .[all]
You are using pip version 7.1.0, however version 7.1.2 is available.
You should consider upgrading via the 'pip install --upgrade pip' command.
Obtaining file:///home/oberstet/scm/crossbar/crossbar
Requirement already up-to-date: click>=4.1 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: setuptools>=18.1 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: zope.interface>=3.6.0 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: twisted>=15.3.0 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: autobahn[twisted]>=0.10.5 in /home/oberstet/scm/autobahn/AutobahnPython (from crossbar==0.11.0)
Requirement already up-to-date: netaddr>=0.7.15 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pytrie>=0.2 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: jinja2>=2.8 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: mistune>=0.7 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pygments>=2.0.2 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyyaml>=3.11 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: shutilwhich>=1.1.0 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: treq>=15.0.0 in /home/oberstet/python279_1/lib/python2.7/site-packages/treq-15.0.0-py2.7.egg (from crossbar==0.11.0)
Requirement already up-to-date: psutil>=3.1.1 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: setproctitle>=1.1.9 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyinotify>=0.9.6 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: lmdb>=0.87 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyasn1>=0.1.8 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pycrypto>=2.6.1 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: msgpack-python>=0.4.6 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: cryptography>=0.9.3 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyOpenSSL>=0.15.1 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: pyasn1-modules>=0.0.7 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: service-identity>=14.0.0 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: wsaccel>=0.6.2 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: ujson>=1.33 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: colorama>=0.3.3 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: mock>=1.3.0 in /home/oberstet/python279_1/lib/python2.7/site-packages (from crossbar==0.11.0)
Requirement already up-to-date: six>=1.6.1 in /home/oberstet/python279_1/lib/python2.7/site-packages (from autobahn[twisted]>=0.10.5->crossbar==0.11.0)
Requirement already up-to-date: txaio>=1.0.3 in /home/oberstet/python279_1/lib/python2.7/site-packages (from autobahn[twisted]>=0.10.5->crossbar==0.11.0)
Requirement already up-to-date: MarkupSafe in /home/oberstet/python279_1/lib/python2.7/site-packages (from jinja2>=2.8->crossbar==0.11.0)
Requirement already up-to-date: requests in /home/oberstet/python279_1/lib/python2.7/site-packages (from treq>=15.0.0->crossbar==0.11.0)
Requirement already up-to-date: idna>=2.0 in /home/oberstet/python279_1/lib/python2.7/site-packages (from cryptography>=0.9.3->crossbar==0.11.0)
Requirement already up-to-date: enum34 in /home/oberstet/python279_1/lib/python2.7/site-packages (from cryptography>=0.9.3->crossbar==0.11.0)
Requirement already up-to-date: ipaddress in /home/oberstet/python279_1/lib/python2.7/site-packages (from cryptography>=0.9.3->crossbar==0.11.0)
Requirement already up-to-date: cffi>=1.1.0 in /home/oberstet/python279_1/lib/python2.7/site-packages (from cryptography>=0.9.3->crossbar==0.11.0)
Requirement already up-to-date: characteristic>=14.0.0 in /home/oberstet/python279_1/lib/python2.7/site-packages (from service-identity>=14.0.0->crossbar==0.11.0)
Requirement already up-to-date: funcsigs in /home/oberstet/python279_1/lib/python2.7/site-packages (from mock>=1.3.0->crossbar==0.11.0)
Requirement already up-to-date: pbr>=0.11 in /home/oberstet/python279_1/lib/python2.7/site-packages (from mock>=1.3.0->crossbar==0.11.0)
Requirement already up-to-date: pycparser in /home/oberstet/python279_1/lib/python2.7/site-packages (from cffi>=1.1.0->cryptography>=0.9.3->crossbar==0.11.0)
Installing collected packages: crossbar
  Running setup.py develop for crossbar
Successfully installed crossbar-0.11.0
(python279_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$ which crossbar
/home/oberstet/python279_1/bin/crossbar
(python279_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$ crossbar version
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
OS                 : Linux-3.13.0-62-generic-x86_64-with-debian-jessie-sid
Machine            : x86_64

(python279_1)oberstet@thinkpad-t430s:~/scm/crossbar/crossbar$
```

## Next

Ready to go? Then [choose your language or device of choice](Choose your Weapon).