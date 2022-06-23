:orphan:

Automatic Startup and Restart
=============================

For running Crossbar.io in production, you might want to:

-  automatically start Crossbar.io at system boot as a daemon
   (background service)
-  automatically restart Crossbar.io if it exits (either deliberately,
   or by accident)

There are different approaches and tools to accomplish above under
Unix-like operating systems:

-  `systemd <#systemd>`__: recommended for **Ubuntu >= 15.04**
-  `upstart <#upstart>`__: recommended for **Ubuntu 14.04 LTS**
-  `daemontools <#daemontools>`__: recommended for **FreeBSD**

systemd
-------

Crossbar supports systemd notify mechanism. Normally systemd just starts the process and assumes that's enough, but in the case of Crossbar and a client Autobahn application this isn't good enough, at least not on all systems.
Simple service type is still supported.

Create a systemd service file ``/etc/systemd/system/crossbar.service``

::

    [Unit]
    Description=Crossbar.io
    After=network.target

    [Service]
    Type=notify
    User=ubuntu
    Group=ubuntu
    StandardInput=null
    StandardOutput=journal
    StandardError=journal
    Environment="MYVAR1=foobar"
    ExecStart=/opt/crossbar/bin/crossbar start --cbdir=/home/ubuntu/mynode1/.crossbar
    ExecStop=/opt/crossbar/bin/crossbar stop --cbdir=/home/ubuntu/mynode1/.crossbar
    Restart=on-abort

    [Install]
    WantedBy=multi-user.target

    Adjust the path to the Crossbar.io executable
    ``/opt/crossbar/bin/crossbar`` and your Crossbar.io node directory
    ``/home/ubuntu/mynode1/.crossbar`` in above.

Then do:

.. code:: console

    sudo systemctl daemon-reload

To make Crossbar.io start automatically at boot time:

.. code:: console

    sudo systemctl enable crossbar.service

To start, stop, restart and get status for Crossbar.io:

.. code:: console

    sudo systemctl start crossbar
    sudo systemctl stop crossbar
    sudo systemctl restart crossbar
    sudo systemctl status crossbar

To get log output:

.. code:: console

    journalctl -f -u crossbar

--------------

upstart
-------

Create an upstart job file ``/etc/init/crossbar.conf``

::

    description "Crossbar.io"

    start on runlevel [2345]
    stop on runlevel [!2345]

    respawn
    respawn limit 20 5

    setuid ubuntu
    setgid ubuntu

    env MYVAR1=foobar

    exec /opt/crossbar/bin/crossbar start --cbdir=/home/ubuntu/mynode1/.crossbar

    Adjust the path to the Crossbar.io executable
    ``/opt/crossbar/bin/crossbar`` and your Crossbar.io node directory
    ``/home/ubuntu/mynode1/.crossbar`` in above.

Then do

.. code:: console

    sudo initctl reload-configuration

To start, stop, restart and get status for Crossbar.io:

.. code:: console

    sudo start crossbar
    sudo stop crossbar
    sudo restart crossbar
    sudo status crossbar

To get log output:

.. code:: console

    sudo tail -f /var/log/upstart/crossbar.log

--------------

daemontools
-----------

The following describes how to monitor and restart Crossbar.io
automatically using `Daemontools <http://cr.yp.to/daemontools.html>`__.
**Daemontools** is a simple, effective, highly secure tool create by
`Dan Bernstein <https://en.wikipedia.org/wiki/Daniel_J._Bernstein>`__
(aka "djb").

    Note: There is also `runit <http://smarden.org/runit/>`__, which is
    a Daemontools clone that some people
    `prefer <https://www.sanityinc.com/articles/init-scripts-considered-harmful/>`__.

Installation
~~~~~~~~~~~~

To install Daemontools on Debian based systems (Ubuntu et al):

::

    sudo apt-get install csh daemontools daemontools-run

This will install a couple of tools including

::

    /usr/bin/svc
    /usr/bin/svstat
    /usr/bin/svscanboot
    /usr/bin/setuidgid

Configuration
~~~~~~~~~~~~~

Create a Daemontools service directory for Crossbar.io:

::

    sudo mkdir /etc/service/crossbar

Create a service run script

::

    sudo vi /etc/service/crossbar/run

with the following content:

::

    #!/bin/sh

    exec /usr/bin/setuidgid ubuntu \
       /home/ubuntu/pypy-2.2.1-linux64/bin/crossbar start \
       --cbdir /home/ubuntu/cbdemo/.crossbar \
       --logdir /home/ubuntu/cbdemo/.crossbar/log

Above assumes:

-  you are using PyPy under the specified path
-  you want to run Crossbar.io under the dedicated Unix user ``ubuntu``
   (which fits for a Amazon EC2 Ubuntu Server AMI)
-  you have a Crossbar.io node created in the specified node directory
-  you want Crossbar.io log to the specified subdirectory within the
   node directory

Make the run script executable:

::

    sudo chmod +x /etc/service/crossbar/run

To make Daemontools start automatically at system boot:

::

    sudo vi /etc/rc.local

and add the following to the end of that file:

::

    /bin/csh -cf '/usr/bin/svscanboot &'

    exit 0

Reboot your system and check the Crossbar.io has been started:

::

    ubuntu@ip-10-229-126-122:~$ sudo svstat /etc/service/crossbar
    /etc/service/crossbar: up (pid 1006) 91391 seconds

Administration
~~~~~~~~~~~~~~

To stop Crossbar.io:

::

    sudo svc -d /etc/service/crossbar

To (manually) start again:

::

    sudo svc -u /etc/service/crossbar

To restart:

::

    sudo svc -t /etc/service/crossbar

To check status:

::

    sudo svstat /etc/service/crossbar

By default - if given ``--logdir`` option - Crossbar.io will create
daily rotated log files in the directory specified:

::

    ubuntu@ip-10-229-126-122:~$ ls -la /home/ubuntu/cbdemo/.crossbar/log
    total 28
    drwxr-xr-x 2 ubuntu ubuntu  4096 Mar 18 04:15 .
    drwxrwxr-x 3 ubuntu ubuntu  4096 Mar 17 16:14 ..
    -rw-r--r-- 1 ubuntu ubuntu  2737 Mar 18 08:13 node.log
    -rw-r--r-- 1 ubuntu ubuntu 13915 Mar 17 16:14 node.log.2014_3_17

To watch the log file:

::

    tail -f /home/ubuntu/cbdemo/.crossbar/log/node.log

