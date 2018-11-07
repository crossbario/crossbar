:orphan:


Development with External Devices
=================================

Applications may comprise components which need to run on external
devices, e.g. one that contains special hardware. As an example, an IoT
application may include a component which uses a Raspberry Pi to attach
sensors.

Here you don't want to have to edit files on the external device via
SSH, but rather use your established editor etc. on your development
machine.

A way to get there is to mount a working directory from your development
machine on the external device.

We show you two ways of achieving this.

The instructions here assume that both machines run a form of
Linux/\*nix.

You need to be able to ssh into the external device.

For the first method, additionally your development machine has to have
an SSH daemon running and port 22 open for SSH. It's cleaner than the
second method, and it's possible that it can be adapted to work on
Windows.

The second method works without the SSH daemon on your development
machine, and does not require any open ports on there either.

Method 1
--------

On the external device, **sshfs** is required, which you can install by
developing

.. code:: console

    sudo apt-get install sshfs

You need to know the IP of your development machine, which is part of
what is listed when you do

.. code:: console

    ifconfig

This can list several devices, e.g. for Docker and virtualization
sulutions. Usually the address in the ``192.`` network is the correct
one.

Now, in the SSH session with the external machine, mount your working
directory:

.. code:: console

    sudo sshfs -o allow_other your_dev_machine_username@192.168.55.138:/home/your_dev_machine_username/source_dir ~/remote_dir

This mounts a source directory in your home directory to the mount point
you choose on your external device.

Now you can do code edits in your favorite editor on your development
machine and all you need to do via the SSH connection is launch the
component on the external device.

Method 2
--------

Create a mountpoint on the Pi

.. code:: console

    mkdir -p iotcookbook

and then mount your local working copy *on* your Pi *from* your
notebook:

.. code:: console

    dpipe /usr/lib/openssh/sftp-server = ssh pi@192.168.1.111 \
        sshfs :${HOME}/iotcookbook /home/pi/iotcookbook -o slave &

    The ``dpipe`` command comes as part of the `vde2
    package <https://packages.debian.org/search?keywords=vde2>`__, which
    can be installed with ``sudo apt-get install -y vde2``.
