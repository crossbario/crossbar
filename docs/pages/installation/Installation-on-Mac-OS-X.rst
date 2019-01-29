:orphan:

Installation on Mac OS X
========================

When installing on OS X natively, you have the choice of running on
`CPython <https://www.python.org/>`__ (the standard interpreter) or
`PyPy <http://pypy.org/>`__ (a high performance JIT compiler). Both are
good choices, but PyPy is generally much faster at run-time, while being
slower on startup.

Please start from either `Setting up CPython <#setting-up-cpython>`__ or
`Setting up PyPy <#setting-up-pypy>`__, and then continue with
`Installing Crossbar.io <#installing-crossbar.io>`__.

Other options to get Crossbar.io running on OS X:

-  using **Docker**: see `Docker on Mac OSX <https://docs.docker.com/engine/installation/mac/>`__ and then
   follow `Installation on Docker <Installation%20on%20Docker>`__
-  using `VirtualBox <https://www.virtualbox.org/>`__ : setup an
   Ubuntu Linux VM and then follow :doc:`Debian and Ubuntu Installation  <Installation-on-Linux>`.

Setting up CPython
------------------

Install pip:

::

    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    sudo python get-pip.py

Install virtualenv:

::

    sudo pip install -U virtualenv

Then create a new virtualenv:

::

    virtualenv ~/python-venv

Finally, start working in the virtual environment:

::

    cd ~/python-venv/
    . bin/activate

Continue with the step `Installing
Crossbar.io <#installing-crossbar.io>`__.

Setting up PyPy
---------------

Install Homebrew using the instructions on the `Homebrew
site <https://brew.sh/>`__.

    *Why Homebrew?* Homebrew is OS X's "missing package manager" and can
    make updating PyPy in the future much easier. It also makes sure you
    have all the dependencies without manually fetching anything.

Then install PyPy:

::

    brew install pypy

Install virtualenv:

::

    pypy -m pip install virtualenv

Create a PyPy virtualenv in the directory ``pypy-venv``:

::

    pypy -m virtualenv ~/pypy-venv

Finally, start working in the virtual environment:

::

    cd ~/pypy-venv/
    . bin/activate

Continue with the step `Installing
Crossbar.io <#installing-crossbar.io>`__.

Installing Crossbar.io
----------------------

To install Crossbar.io

::

    pip install crossbar

To check the installation:

.. code:: console

    (pypy-venv)hawkowl@hegira:~/pypy-venv> crossbar version

    Crossbar.io package versions and platform information:

    Crossbar.io                  : 0.10.2

      Autobahn|Python            : 0.10.1
        WebSocket UTF8 Validator : autobahn
        WebSocket XOR Masker     : autobahn
        WAMP JSON Codec          : stdlib
        WAMP MsgPack Codec       : msgpack-python-0.4.5
      Twisted                    : 15.0.0-KQueueReactor
      Python                     : 2.7.8-PyPy

    OS                           : Darwin-14.1.0-x86_64-i386-64bit
    Machine                      : x86_64

To update an existing Crossbar.io installation:

::

    pip install -U crossbar
