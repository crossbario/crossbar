title: Installation on Ubuntu Snappy
toc: [Documentation, Installation, Installation on Ubuntu Snappy]

# Installation on Ubuntu Snappy

[Ubuntu Snappy](http://www.ubuntu.com/cloud/tools/snappy) is a new kind of server operating system that uses a transactional updating scheme for applications.

**Crossbar.io publishes an official binary package for Ubuntu Snappy.**

> Note: Ubuntu Snappy is a specialised version of regular Ubuntu. If you are using regular Ubuntu, please read [Installation on Ubuntu and Debian](Installation on Ubuntu and Debian) for installation instructions.


## Installing

On your Ubuntu Snappy server, run:

    sudo snappy install crossbar.crossbar

> The crossbar.crossbar name is because it is the Crossbar.io package published by the Crossbar.io project.

This will download and install Crossbar.io.

You can check the version installed by running:

```console
(amd64)ubuntu@ubuntu-core-stable-2:~$ sudo snappy list
Name          Date       Version Developer
ubuntu-core   2015-04-23 2       ubuntu
crossbar      2015-05-06 0.10.4  crossbar
generic-amd64 2015-04-23 1.1
```

To verify the installation:

```console
(amd64)ubuntu@ubuntu-core-stable-2:~$ crossbar.crossbar version
(
Crossbar.io package versions and platform information:

Crossbar.io                  : 0.10.4

  Autobahn|Python            : 0.10.3
    WebSocket UTF8 Validator : ?
    WebSocket XOR Masker     : ?
    WAMP JSON Codec          : stdlib
    WAMP MsgPack Codec       : msgpack-python-0.4.6
  Twisted                    : 15.1.0-EPollReactor
  Python                     : 2.7.8-PyPy

OS                           : Linux-3.19.0-15-generic-x86_64-with-glibc2.2.5
Machine                      : x86_64
```

## Running

Because of Ubuntu Snappy's tightened security, Snappy apps can only write to certain parts of the filesystem.
After you run it for the first time (for example, running the version check above), Snappy creates app directories.

Here is an example of creating a sample configuration and running Crossbar on Snappy:

```console
(amd64)ubuntu@ubuntu-core-stable-2:~$ cd apps/crossbar.crossbar/0.10.4/
(amd64)ubuntu@ubuntu-core-stable-2:~/apps/crossbar.crossbar/0.10.4$ crossbar.crossbar init
Initializing application template 'default' in directory '/home/ubuntu/apps/crossbar.crossbar/0.10.4'
Using template from '/apps/crossbar.crossbar/0.10.4/site-packages/crossbar/templates/default'
Creating directory /home/ubuntu/apps/crossbar.crossbar/0.10.4/.crossbar
Creating file      /home/ubuntu/apps/crossbar.crossbar/0.10.4/.crossbar/config.json
Application template initialized

To start your node, run 'crossbar start --cbdir /home/ubuntu/apps/crossbar.crossbar/0.10.4/.crossbar'

(amd64)ubuntu@ubuntu-core-stable-2:~/apps/crossbar.crossbar/0.10.4$ crossbar.crossbar start
2015-05-07 03:46:56+0000 [Controller   1740] Log opened.
2015-05-07 03:46:56+0000 [Controller   1740] ==================== Crossbar.io ====================

2015-05-07 03:46:56+0000 [Controller   1740] Crossbar.io 0.10.4 starting
2015-05-07 03:46:56+0000 [Controller   1740] Running on PyPy using EPollReactor reactor
2015-05-07 03:46:56+0000 [Controller   1740] Starting from node directory /home/ubuntu/apps/crossbar.crossbar/0.10.4/.crossbar
2015-05-07 03:46:57+0000 [Controller   1740] Starting from local configuration '/home/ubuntu/apps/crossbar.crossbar/0.10.4/.crossbar/config.json'
```
