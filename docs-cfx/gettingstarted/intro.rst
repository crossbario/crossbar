Introduction
============

.. code-block:: console

    curl https://download.crossbario.com/crossbarfx/linux-amd64/crossbarfx-latest -o /tmp/crossbarfx
    chmod +x /tmp/crossbarfx
    sudo cp /tmp/crossbarfx /usr/local/bin/
    /usr/local/bin/crossbarfx version

.. code-block:: console

    CROSSBAR_FABRIC_URL=ws://localhost:9000/ws crossbarfx shell auth --yes

.. code-block:: console

    mkdir ${HOME}/master1
    docker run --rm --name crossbarfx -p 9000:9000 -t \
        -v ${HOME}/master1:/master:rw \
        -v ${HOME}/.crossbarfx/default.pub:/.crossbarfx/default.pub:ro \
        -e CROSSBAR_FABRIC_SUPERUSER=/.crossbarfx/default.pub \
        crossbario/crossbarfx:pypy-slim-amd64 master start --cbdir=/master/.crossbar


.. code-block:: console

    cd ${HOME}/master1
    CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub crossbarfx master start

.. code-block:: console

    (cpy382_1) oberstet@intel-nuci7:~/master1$ CROSSBAR_FABRIC_URL=ws://localhost:9000/ws crossbarfx shell auth --yes

    Created new local user directory: /home/oberstet/.crossbarfx
    Created new local user configuration: /home/oberstet/.crossbarfx/config.ini
    New user public key generated: /home/oberstet/.crossbarfx/default.pub
    New user private key generated (keep this safe!): /home/oberstet/.crossbarfx/default.priv
    Connection was refused by other side: 111: Connection refused.
    (cpy382_1) oberstet@intel-nuci7:~/master1$ crossbarfx master start^C
    (cpy382_1) oberstet@intel-nuci7:~/master1$ env | grep CROSS
    CROSSBAR_FABRIC_SUPERUSER=
    CROSSBAR_FABRIC_URL=
    (cpy382_1) oberstet@intel-nuci7:~/master1$ CROSSBAR_FABRIC_SUPERUSER=${HOME}/.crossbarfx/default.pub crossbarfx master start

    2020-07-01T16:04:37+0200 [Controller  19029]
    2020-07-01T16:04:37+0200 [Controller  19029]     :::::::::::::::::
    2020-07-01T16:04:37+0200 [Controller  19029]           :::::          _____                 __              _____  __
    2020-07-01T16:04:37+0200 [Controller  19029]     :::::   :   :::::   / ___/______  ___ ___ / /  ___ _____  / __/ |/_/
    2020-07-01T16:04:37+0200 [Controller  19029]     :::::::   :::::::  / /__/ __/ _ \(_-<(_-</ _ \/ _ `/ __/ / _/_>  <
    2020-07-01T16:04:37+0200 [Controller  19029]     :::::   :   :::::  \___/_/  \___/___/___/_.__/\_,_/_/   /_/ /_/|_|
    2020-07-01T16:04:37+0200 [Controller  19029]           :::::
    2020-07-01T16:04:37+0200 [Controller  19029]     :::::::::::::::::   Crossbar.io v20.6.2 [00000]
    2020-07-01T16:04:37+0200 [Controller  19029]
    2020-07-01T16:04:37+0200 [Controller  19029]     Copyright (c) 2013-2020 Crossbar.io Technologies GmbH. All rights reserved.
    2020-07-01T16:04:37+0200 [Controller  19029]
    2020-07-01T16:04:37+0200 [Controller  19029] Booting master node .. <crossbar.node.main._run_command_start>
    ...
    2020-07-01T16:04:39+0200 [Router      19039] SUPERUSER public key 7f3870073d114e5d87be22fbfe1d2bf266d246579f37fde5ac18aa1a65b53a95 loaded from /home/oberstet/.crossbarfx/default.pub
    ...
    2020-07-01T16:04:44+0200 [Controller  19029] <crossbarfx.master.node.node.FabricCenterNode.boot>::NODE_BOOT_COMPLETE


.. code-block:: console

    crossbarfx shell auth
    crossbarfx shell show status
    crossbarfx shell show license
    crossbarfx shell show version
