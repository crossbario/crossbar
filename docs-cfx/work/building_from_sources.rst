Building from Sources
=====================

This recipe describes building Crossbar.io *from sources*, on a completely
fresh **Ubuntu 18.04 Server**.

The recipe is intended *for Crossbar.io developers hacking on Crossbar.io code itself*
and currently requires access to company internal, private Git repositories.

Prepare OS
----------

Update the system and reboot:

.. code-block:: console

    sudo apt update
    sudo apt -y dist-upgrade
    sudo reboot

Install distro packages required for a from source build:

.. code-block:: console

    sudo apt-get -y install expect build-essential libssl-dev libffi-dev libunwind-dev \
    libreadline-dev zlib1g-dev libbz2-dev libsqlite3-dev libncurses5-dev libsnappy-dev \
    libenchant-dev rng-tools

Build Python
------------

The following builds CPython 3.8.2 from vanilla upstream sources:

.. code-block:: console

    cd ~
    wget https://www.python.org/ftp/python/3.8.2/Python-3.8.2.tar.xz
    tar xvf Python-3.8.2.tar.xz
    cd Python-3.8.2
    ./configure --prefix=$HOME/cpy382 --enable-shared
    make -j4
    make install
    cd ..

Now run:

.. code-block:: console

    sudo sh -c 'echo ${HOME}/cpy382/lib > /etc/ld.so.conf.d/cpy382.conf'
    sudo ldconfig
    export LD_LIBRARY_PATH=${HOME}/cpy382/lib

Create a fresh virtualenv:

.. code-block:: console

    ~/cpy382/bin/python3 -m venv ~/cpy382_1
    source ~/cpy382_1/bin/activate
    which python
    python -V

Install Docker
--------------

The following installs Docker (community edition) from upstream:

.. code-block:: console

    sudo apt-get -y install \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg-agent \
        software-properties-common

and

.. code-block:: console

    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

and

.. code-block:: console

    sudo add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    stable"

    sudo apt-get update
    sudo apt-get -y install docker-ce docker-ce-cli containerd.io

    which docker
    docker --version
    sudo docker run hello-world

Install Docker Compose into the active Python virtualenv:

.. code-block:: console

    pip install docker-compose
    docker-compose --version

Install NodeJS
--------------

The following installs NodeJS from upstream:

.. code-block:: console

    cd ~
    wget https://nodejs.org/dist/v12.14.1/node-v12.14.1-linux-x64.tar.xz
    tar xvf node-v12.14.1-linux-x64.tar.xz
    export PATH=${HOME}/node-v12.14.1-linux-x64/bin:${PATH}
    which node
    node --version

Build CrossbarFX from Sources
-----------------------------

**Clone** all our source code Git repositories for CrossbarFX:

.. code-block:: console

    cd ~
    mkdir -p ~/scm/crossbario
    cd ~/scm/crossbario
    git clone git@github.com:crossbario/txaio.git
    git clone git@github.com:crossbario/autobahn-python.git
    git clone git@github.com:crossbario/zlmdb.git
    git clone git@github.com:crossbario/cfxdb.git
    git clone git@github.com:crossbario/crossbar.git
    git clone git@github.com:crossbario/crossbarfx.git
    git clone git@github.com:crossbario/xbr-protocol.git
    cd ~

To **pull** status in all cloned Git repositories:

.. code-block:: console

    cd ~/scm/crossbario/txaio && git pull
    cd ~/scm/crossbario/autobahn-python && git pull
    cd ~/scm/crossbario/zlmdb && git pull
    cd ~/scm/crossbario/cfxdb && git pull
    cd ~/scm/crossbario/crossbar && git pull
    cd ~/scm/crossbario/crossbarfx && git pull
    cd ~/scm/crossbario/xbr-protocol && git pull
    cd ~

To follow upstream:

.. code-block:: console

    cd ~/scm/crossbario/txaio && git checkout master && git fetch --all && git merge upstream/master && git push
    cd ~/scm/crossbario/autobahn-python && git checkout master && git fetch --all && git merge upstream/master && git push
    cd ~/scm/crossbario/zlmdb && git checkout master && git fetch --all && git merge upstream/master && git push
    cd ~/scm/crossbario/cfxdb && git checkout master && git fetch --all && git merge upstream/master && git push
    cd ~/scm/crossbario/crossbar && git checkout master && git fetch --all && git merge upstream/master && git push
    cd ~/scm/crossbario/crossbarfx && git checkout master && git fetch --all && git merge upstream/master && git push
    cd ~/scm/crossbario/xbr-protocol && git checkout master && git fetch --all && git merge upstream/master && git push
    cd ~

To get the **status** in all cloned Git repositories:

.. code-block:: console

    cd ~/scm/crossbario/txaio && git status
    cd ~/scm/crossbario/autobahn-python && git status
    cd ~/scm/crossbario/zlmdb && git status
    cd ~/scm/crossbario/cfxdb && git status
    cd ~/scm/crossbario/crossbar && git status
    cd ~/scm/crossbario/crossbarfx && git status
    cd ~/scm/crossbario/xbr-protocol && git status
    cd ~

**Activate the virtualenv created above, build and install everything from sources**:

.. code-block:: console

    source ~/cpy382_1/bin/activate
    cd ~/scm/crossbario/txaio && pip install -e .
    cd ~/scm/crossbario/autobahn-python && pip install -e .[all]
    cd ~/scm/crossbario/zlmdb && pip install -e .
    cd ~/scm/crossbario/cfxdb && pip install -e .
    cd ~/scm/crossbario/crossbar && pip install -e .
    cd ~/scm/crossbario/crossbarfx && pip install -e .
    cd ~

Check the installed versions of packages:

.. code-block:: console

    pip show txaio
    pip show autobahn-python
    pip show zlmdb
    pip show cfxdb
    pip show crossbar
    pip show crossbarfx

Check the built CrossbarFX CLI and versions:

.. code-block:: console

    cd ~
    source ~/cpy382_1/bin/activate
    which crossbarfx
    crossbarfx version

.. code-block:: console

    (cpy382_1) ubuntu@ip-172-31-45-110:~$ crossbarfx version


        :::::::::::::::::
              :::::          _____                 __              _____  _______
        :::::   :   :::::   / ___/______  ___ ___ / /  ___ _____  / __/ |/_/ ___/
        :::::::   :::::::  / /__/ __/ _ \(_-<(_-</ _ \/ _ `/ __/ / _/_>  </ /__
        :::::   :   :::::  \___/_/  \___/___/___/_.__/\_,_/_/   /_/ /_/|_|\___/
              :::::
        :::::::::::::::::   Crossbar.io Fabric XBR Center v20.1.2 [00000]

        Copyright (c) 2013-2020 Crossbar.io Technologies GmbH. All rights reserved.

    Crossbar.io        : 20.1.2
    txaio            : 20.1.1
    Autobahn         : 20.1.3
        UTF8 Validator : wsaccel-0.6.2
        XOR Masker     : wsaccel-0.6.2
        JSON Codec     : stdlib
        MsgPack Codec  : msgpack-0.6.2
        CBOR Codec     : cbor-1.0.0
        UBJSON Codec   : ubjson-0.14.0
        FlatBuffers    : flatbuffers-1.11
    Twisted          : 19.10.0-EPollReactor
    LMDB             : 0.98/lmdb-0.9.22
    Python           : 3.8.2/CPython
    CrossbarFX         : 20.1.2
    NumPy            : 1.15.4
    zLMDB            : 20.1.1
    Frozen executable  : no
    Operating system   : Linux-4.15.0-1058-aws-x86_64-with-glibc2.2.5
    Host machine       : x86_64
    Release key        : RWTg6NK33a/KXvRvBD3AxRN6P+jyCQbTaELF2rzMa5h0ao+i0Te3I3K4

------

System Integration
------------------

Set system hostname and domain (see `here <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/set-hostname.html>`__):

.. code-block:: console

    sudo hostnamectl set-hostname planet.xbr.network

Allow the currently logged in user to use Docker without becoming root:

.. code-block:: console

    sudo groupadd docker
    sudo usermod -aG docker $USER

Allow CrossbarFX to listen on TCP/IP ports <1024:

.. code-block:: console

    sudo setcap cap_net_bind_service=+ep /home/ubuntu/cpy382_1/bin/crossbarfx
    sudo setcap cap_net_bind_service=+ep /home/ubuntu/cpy382/bin/python3.8

Add XBR configuration to user environment (``${HOME}/.profile``):

.. code-block:: console

    export XBR_DEBUG_TOKEN_ADDR=0xCfEB869F69431e42cdB54A4F4f105C19C080A601
    export XBR_DEBUG_NETWORK_ADDR=0xC89Ce4735882C9F0f0FE26686c53074E09B0D550
    export XBR_DEBUG_MARKET_ADDR=0xD833215cBcc3f914bD1C9ece3EE7BF8B14f841bb
    export XBR_DEBUG_CATALOG_ADDR=0x9561C133DD8580860B6b7E504bC5Aa500f0f06a7
    export XBR_DEBUG_CHANNEL_ADDR=0xe982E462b094850F12AF94d21D470e21bE9D0E9C


SSH
---

To allow agent forwarding (both receiving and outgoing to anywhere .. be careful!):

.. code-block:: console

    sudo sh -c "echo 'ForwardAgent yes' >> /etc/ssh/ssh_config"
    sudo sh -c "echo 'AllowAgentForwarding yes' >> /etc/ssh/sshd_config"


TLS
---

To install `Lego <https://go-acme.github.io/lego/>`__ from `upstream release <https://github.com/go-acme/lego/releases>`__:

.. code-block:: console

    wget https://github.com/go-acme/lego/releases/download/v3.5.0/lego_v3.5.0_linux_amd64.tar.gz
    tar xvf lego_v3.5.0_linux_amd64.tar.gz
    sudo cp ./lego /usr/local/bin/lego


Network Tuning
--------------

Linux TCP networking is tuned as in the following. This (or similar) is
*required*, since we are really pushing the system.

Add the following to the end of ``/etc/sysctl.conf`` and do
``sysctl -p``:

::

    net.core.somaxconn = 8192
    net.ipv4.tcp_max_orphans = 8192
    net.ipv4.tcp_max_syn_backlog = 8192
    net.core.netdev_max_backlog = 262144

    net.ipv4.ip_local_port_range = 1024 65535

    #net.ipv4.tcp_low_latency = 1
    #net.ipv4.tcp_window_scaling = 0
    #net.ipv4.tcp_syncookies = 0

    fs.file-max = 16777216
    fs.pipe-max-size = 134217728

Further system level tuning:

Modify ``/etc/security/limits.conf`` for the following

::

    # wildcard does not work for root, but for all other users
    *               soft     nofile           1048576
    *               hard     nofile           1048576
    # settings should also apply to root
    root            soft     nofile           1048576
    root            hard     nofile           1048576

and add the following line

::

    session required pam_limits.so

to both of these files at the end:

::

    /etc/pam.d/common-session
    /etc/pam.d/common-session-noninteractive

Reboot (or at least I don't know how to make it immediate without
reboot).

Check that you actually got large (``1048576``) FD limit:

::

    ulimit -n

Probably also check that above ``sysctl`` settings actually are in place
(``sysctl -a | grep ..`` or such). I am paranoid.