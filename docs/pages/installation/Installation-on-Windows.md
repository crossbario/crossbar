title: Installation on Windows
toc: [Documentation, Installation, Installation on Windows]

# Installation on Windows

Crossbar.io is a Python application, with a few additional dependencies. Since Windows does not have a builtin package management for applications, installing Crossbar.io requires installing some of these dependencies manually.

There are two possibilities to install Crossbar.io:

* [Installation using the PyPi] (Python Package Index) - quick install of the latest release version
* [Installation from Source](#installation-from-source) - building everything (but Python) from sources

## Basic Installation

### Installing the Dependencies

Crossbar.io is a Python application. In addition to Python, setup requires the PyWin32 additions, `pip` (a Python package manager) and the Microsoft Visual C++ compiler for Python 2.7.

1. Download and install [Python for Windows 2.7.x](https://www.python.org/downloads/windows/) - **32-bit** even on 64-bit systems (strongly recommended)
2. Add `C:\Python27\` and `C:\Python27\Scripts` to your `PATH` ('Control Panel' - 'System' - 'Change Settings' - 'Advanced' - 'Environment Variables' - 'Path' is part of the system variables)
3. Download and install [PyWin32](http://sourceforge.net/projects/pywin32/files/pywin32/) - 32-bit version for Python 2.7 - 'win32'
4. If you're on any Python version previous to 2.7.9, you need to install `pip`. Download the [`get-pip` script](https://bootstrap.pypa.io/get-pip.py) and run this (works from Windows Explorer or the download dialog of your browser).
5. Download and install the [Microsoft Visual C++ compiler for Python 2.7](http://www.microsoft.com/en-us/download/details.aspx?id=44266)

### Installing Crossbar.io

Now you can install Crossbar.io by opening a command shell and doing

    pip install crossbar

This installs Crossbar.io from the [Python Package Index](https://pypi.python.org/pypi).

To verify that the installation was successful, in the shell do

    crossbar version

which should output something like:

```console
C:\Users\IEUser>crossbar version
     __  __  __  __  __  __      __     __
    /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
    \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/

 Crossbar.io        : 0.13.0
   Autobahn         : 0.13.1 (with JSON, MessagePack, CBOR)
   Twisted          : 16.1.1-IOCPReactor
   LMDB             : 0.89/lmdb-0.9.18
   Python           : 2.7.11/CPython
 OS                 : Windows-7-6.1.7601-SP1
 Machine            : x86
```

## Installation from Source

Recently, Microsoft has published a compiler package specifically for building Python binary extensions on Windows which simplifies matters a lot.

1. Download and install the [compiler package](http://www.microsoft.com/en-us/download/details.aspx?id=44266).
2. Open "Visual C++ 2008 32-bit Command Prompt" from the "Microsoft Visual C++ Compiler Package for Python 2.7" program folder
3. Change to the `crossbar/crossbar` directory and type `pip install -e .[all]`

## Running Crossbar.io from the Git shell

Git shell on Windows no longer shows any logging output for Crossbar.io if this is started regularly (`crossbar start`).

To get logging output, do

    winpty crossbar start

(The above only applies to Git shell - not the regular Windows command shell and Powershell.)
