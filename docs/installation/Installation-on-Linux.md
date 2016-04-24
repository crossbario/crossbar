[Documentation](.) > [Installation](Installation) > [Local Installation](Local Installation) > Installation on Linux

# Installation on Linux

The following provides installation instructions that should work on most Linux distributions.

> We provide more specific and polished installation instructions plus official binary packages for [Ubuntu 14.04 LTS](Installation-on-Ubuntu) and [CentOS 7/RHEL](Installation-on-CentOS). Please follow those if you are using one of these systems.

## Requirements

Your system will need OpenSSL, libffi, and a working build chain.
On a Debian (or Debian-derived) system, the requirements can be installed by:

    sudo apt-get install build-essential libssl-dev libffi-dev \
        libreadline-dev libbz2-dev libsqlite3-dev libncurses5-dev

Or for RedHat and derivatives:

    sudo yum install python-devel "@Development tools" libffi-devel openssl-devel

Then download and install a portable PyPy binary:

    cd $HOME
    wget https://bitbucket.org/squeaky/portable-pypy/downloads/pypy-2.5-linux_x86_64-portable.tar.bz2
    tar xvjf pypy-2.5-linux_x86_64-portable.tar.bz2

Install pip:

    wget https://bootstrap.pypa.io/get-pip.py
    ~/pypy-2.5-linux_x86_64-portable/bin/pypy get-pip.py

## Installing Crossbar

This PyPy is a entirely self contained Python distribution.
Any packages installed inside it are local only to that PyPy installation, without having to worry about conflicting Python packages installed from your distribution.

Install Crossbar inside the PyPy distribution:

    ~/pypy-2.5-linux_x86_64-portable/bin/pip install crossbar

Then check the Crossbar installation to make sure it installed correctly

```console
$ ~/pypy-2.5-linux_x86_64-portable/bin/crossbar version
Crossbar.io package versions and platform information:

Crossbar.io                  : 0.10.2

  Autobahn|Python            : 0.10.1
    WebSocket UTF8 Validator : autobahn
    WebSocket XOR Masker     : autobahn
    WAMP JSON Codec          : stdlib
    WAMP MsgPack Codec       : msgpack-python-0.4.5
  Twisted                    : 15.0.0-EPollReactor
  Python                     : 2.7.8-PyPy

OS                           : Linux-3.10.0-123.el7.x86_64-x86_64-with-centos-7.0.1406-Core
Machine                      : x86_64
```

## Next

Ready to go? Then [choose your language or device of choice](Choose your Weapon).
