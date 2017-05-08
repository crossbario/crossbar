title: Installation on RaspberryPi
toc: [Documentation, Installation, Installation on RaspberryPi]

# Installation on the RaspberryPi

This recipe will guide you through installing Crossbar.io on the Pi. After this, you will be able to

* run the Crossbar.io WAMP router on the Pi, as well as
* run WAMP application components on the Pi written in Python using [AutobahnPython](http://autobahn.ws/python/), which connect to a WAMP router - either on the Pi or on a different machine.

## Install Rasbian

The recipe was tested with a complete fresh install of everything, beginning from the operating system. We will use [Raspbian](https://www.raspberrypi.org/downloads/raspbian/) as the operating system on the Pi. If you already have Raspbian running, you can skip this step.

To install Raspbian on your Pi, follow the [NOOBS installation guide](http://www.raspberrypi.org/help/noobs-setup/).

The only adjustments I made during installation were:

1. Activate *SSH daemon*, which allows to log into the Pi remotely via SSH.
2. *Expand Filesystem*, which ensure all of the SD card capacity is available.
3. Activate *Turbo mode*, which allows the CPU clock to scale from 700MHz to 1GHz during load. **Note that you will need a power supply that can supply sufficient current for this to work stable.**

> Note: you can check the current clock rate at which the Pi runs by doing `sudo cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq`


## Enlarge Root Partition

The Raspbian images will create a root filesystem of only 2GB size, independent of the capacity of the actual SD card used. The is very small and you can't install a lot of additional stuff.

To enlarge the root partition to the full size of the SD card, you can [use raspi-config](http://elinux.org/RPi_raspi-config#expand_rootfs_-_Expand_root_partition_to_fill_SD_card):

    sudo raspi-config

and choose **Expand Filesystem**.


## Update the OS

It is recommended to update the OS and installed software. Log into your Pi and do

    sudo apt-get update
    sudo apt-get -y dist-upgrade

## Install prerequisites

To install the necessary prerequisites on the Pi, do

    sudo apt-get install -y build-essential libssl-dev libffi-dev python-dev

Then install the latest version of [Pip](https://pip.pypa.io/en/latest/), a Python package manager:

    wget https://bootstrap.pypa.io/get-pip.py
    sudo python get-pip.py

## Install Crossbar.io

If you want to run Crossbar.io itself on the Pi, you need to install it on the Pi - obviously;)

Simply do

    sudo pip install crossbar

(This may take a while since some dependencies compile.)

To test the installation, do the following (be patient, startup can take 10-20s):

```console
pi@raspberrypi ~ $ crossbar version

Crossbar.io package versions and platform information:

Crossbar.io                  : 0.10.4

  Autobahn|Python            : 0.10.3
    WebSocket UTF8 Validator : wsaccel-0.6.2
    WebSocket XOR Masker     : wsaccel-0.6.2
    WAMP JSON Codec          : ujson-1.33
    WAMP MsgPack Codec       : msgpack-python-0.4.6
  Twisted                    : 15.1.0-EPollReactor
  Python                     : 2.7.3-CPython

OS                           : Linux-3.18.7+-armv6l-with-debian-7.8
Machine                      : armv6l
```
