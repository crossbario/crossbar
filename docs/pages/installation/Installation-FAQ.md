title: Installation FAQ
toc: [Documentation, Installation, Installation FAQ]

# Installation FAQ

## Python runtime

### What is PyPy?

[Python](https://www.python.org/) is a programming language that has multiple *implementations*. The original and default implementation is usually called *CPython*, since it is written in C.

Other implementations include:

* [PyPy](http://pypy.org/)
* [Jython](http://www.jython.org/)
* [IronPython](http://ironpython.net/)

Now, PyPy is a Python implementation specifically geared towards *high performance*.

Different from CPython, PyPy is not an interpreter, but compiling Python bytecode to native machine code - transparently and on the fly. It is a [JIT compiler](http://en.wikipedia.org/wiki/Just-in-time_compilation).

Also, PyPy [has](http://morepypy.blogspot.de/2013/10/incremental-garbage-collector-in-pypy.html) a powerful and *incremental garbage collector*. A [garbage collector](http://en.wikipedia.org/wiki/Garbage_collection_%28computer_science%29) is responsible for managing memory in a dynamic language such as Python.

### Should I run on CPython or PyPy?

Short answer: Using CPython is easier and quicker. If you don't need the highest possible performance, stick with CPython.

Running on PyPy will give you a *lot* more performance than CPython though. Of course there are some downsides as well:

* longer startup time compared to CPython (since the JIT compiler will need to do more initial work)
* it takes some time (seconds to minutes) until Crossbar.io reaches maximum performance (since the JIT compiler needs to warm up on the code hot-paths)
* it might have higher memory consumption than CPython

## How large is Crossbar.io?

**Short answer**

* 258 kB as a download
* 81 MB as a virtualenv
* 187 MB as a binary package
* 398 MB as a Docker container

**Long answer**

Crossbar.io itself is a download of less than 1 MB. However, Crossbar.io depends on a lot of other libraries and packages. It reuses proven solutions wherever possible. For this reason, when actually installing Crossbar.io, the footprint will be significantly larger than the download size of Crossbar.io suggests.

Here is what you get installing Crossbar.io into a fresh Python 3 virtualenv:

```console
oberstet@thinkpad-t430s:~$ ./python351/bin/virtualenv ~/python351_3
Using base prefix '/home/oberstet/python351'
New python executable in /home/oberstet/python351_3/bin/python3.5
Also creating executable in /home/oberstet/python351_3/bin/python
Installing setuptools, pip, wheel...done.
oberstet@thinkpad-t430s:~$ du -hs ~/python351_3/
23M /home/oberstet/python351_3/
(python351_3) oberstet@thinkpad-t430s:~$ pip install crossbar[all]
Collecting crossbar[all]
Downloading crossbar-0.13.0.tar.gz (254kB)
...
Successfully built crossbar autobahn cryptography txaio
Installing collected packages: click, zope.interface, twisted, six, txaio, autobahn, netaddr, pytrie, MarkupSafe, jinja2, mistune, pygments, pyyaml, shutilwhich, sdnotify, psutil, lmdb, msgpack-python, cbor, idna, pyasn1, pycparser, cffi, cryptography, pyOpenSSL, pyasn1-modules, attrs, service-identity, pynacl, requests, treq, setproctitle, pyinotify, wsaccel, ujson, pep8, pyflakes, mccabe, flake8, colorama, pbr, mock, pycrypto, crossbar
Successfully installed MarkupSafe-0.23 attrs-15.2.0 autobahn-0.13.0 cbor-1.0.0 cffi-1.5.2 click-6.4 colorama-0.3.7 crossbar-0.13.0 cryptography-1.3.1 flake8-2.5.4 idna-2.1 jinja2-2.8 lmdb-0.89 mccabe-0.4.0 mistune-0.7.2 mock-1.3.0 msgpack-python-0.4.7 netaddr-0.7.18 pbr-1.8.1 pep8-1.7.0 psutil-4.1.0 pyOpenSSL-16.0.0 pyasn1-0.1.9 pyasn1-modules-0.0.8 pycparser-2.14 pycrypto-2.6.1 pyflakes-1.0.0 pygments-2.1.3 pyinotify-0.9.6 pynacl-1.0.1 pytrie-0.2 pyyaml-3.11 requests-2.9.1 sdnotify-0.3.0 service-identity-16.0.0 setproctitle-1.1.9 shutilwhich-1.1.0 six-1.10.0 treq-15.1.0 twisted-16.0.0 txaio-2.2.2 ujson-1.35 wsaccel-0.6.2 zope.interface-4.1.3
You are using pip version 8.0.2, however version 8.1.1 is available.
You should consider upgrading via the 'pip install --upgrade pip' command.
(python351_3) oberstet@thinkpad-t430s:~$ du -hs ~/python351_3/
81M /home/oberstet/python351_3/
(python351_3) oberstet@thinkpad-t430s:~$

That is **81 MB** installed size, compared to **254kB** download size for Crossbar.io alone.

Now, the virtualenv doesn't include the whole Python itself. Here is the Python underlying the above virtualenv:

```
oberstet@thinkpad-t430s:~$ du -hs python351
178M    python351
```

Now, when you install Crossbar.io from our binary packages (recommended), you get:


```console
oberstet@thinkpad-t430s:~$ sudo apt-get install crossbar
Paketlisten werden gelesen... Fertig
Abhaengigkeitsbaum wird aufgebaut.
Statusinformationen werden eingelesen.... Fertig
crossbar ist schon die neueste Version.
Die folgenden Pakete wurden automatisch installiert und werden nicht mehr benoetigt:
  libksba8 libpth20 pinentry-gtk2
Verwenden Sie apt-get autoremove, um sie zu entfernen.
0 aktualisiert, 0 neu installiert, 0 zu entfernen und 8 nicht aktualisiert.
oberstet@thinkpad-t430s:~$ /opt/crossbar/bin/crossbar version
Automatically choosing optimal Twisted reactor
Running on Linux and optimal reactor (epoll) was installed.
     __  __  __  __  __  __      __     __
    /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
    \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/

 Crossbar.io        : 0.13.0
   Autobahn         : 0.13.0 (with JSON, MessagePack, CBOR)
   Twisted          : 16.0.0-EPollReactor
   LMDB             : 0.89/lmdb-0.9.18
   Python           : 2.7.10/PyPy-5.0.0
 OS                 : Linux-3.13.0-83-generic-x86_64-with-debian-jessie-sid
 Machine            : x86_64

oberstet@thinkpad-t430s:~$ du -hs /opt/crossbar/
187M    /opt/crossbar/
oberstet@thinkpad-t430s:~$
```

That's slightly larger, which is expected, since the binary package is fully self-contained, and it also runs PyPy (which is itself slightly larger than CPython). But **187 MB**.

However, again, this doesn't contain the OS, only everything Python and above. So, here is what you get using OS containers, with the Crossbar.io for Docker image:


```console
oberstet@thinkpad-t430s:~$ sudo docker images
REPOSITORY                   TAG                 IMAGE ID            CREATED             SIZE
crossbario/autobahn-python   pypy2               9a88814a94ac        2 hours ago         766.4 MB
crossbario/autobahn-python   cpy2                f8fca54bbe88        3 hours ago         726.3 MB
crossbario/autobahn-python   cpy3                d8a61e17d280        3 hours ago         730.4 MB
crossbario/autobahn-js       latest              a72b7ea6d885        3 hours ago         724.4 MB
crossbario/crossbar          latest              7b5c8eb01260        6 hours ago         398.2 MB
python                       3                   70c16d34e4c8        2 days ago          689.6 MB
python                       2                   e4a554df875e        2 days ago          676.8 MB
pypy                         2                   d45ac503524a        2 days ago          725 MB
ubuntu                       latest              97434d46f197        8 days ago          188 MB
oberstet@thinkpad-t430s:~$
```

So Crossbar.io is **398 MB** when Dockerized.
