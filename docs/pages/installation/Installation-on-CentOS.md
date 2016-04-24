[Documentation](.) > [Installation](Installation) > [Local Installation](Local Installation) > Installation on CentOS

# Installation on CentOS

There are two methods of installing Crossbar.io on CentOS -- from the official binary distribution (recommended), or from source.

## Installing the Official Distribution

Crossbar.io hosts official binary packages for **CentOS 7** (RHEL should be fine also).

> If this is not the CentOS version you are using, please install from source as mentioned below.

First, install the repo's GPG key:

    sudo rpm --import "http://pool.sks-keyservers.net/pks/lookup?op=get&search=0x5FC6281FD58C6920"

Then add the repo to your sources:

    sudo sh -c "echo '[crossbar]
    name = Crossbar
    baseurl = http://package.crossbar.io/centos/7/
    enabled = 1
    gpgcheck = 1' > /etc/yum.repos.d/crossbar.repo"

Install Crossbar:

    sudo yum install crossbar

You can then test the installation by printing out the versions of the Crossbar components.

    /opt/crossbar/bin/crossbar version

**You're done!**

Ready for more? Then [choose your language or device of choice](Choose your Weapon).


## Installing from Source

Install the requirements:

    sudo yum install libffi-devel
    sudo pip install virtualenv

Then create a new virtualenv:

    virtualenv python-venv

> *Why virtualenv?* Virtualenv, as the name suggests, creates a "virtual environment" for your Python packages. This means that you can have newer versions of packages that might already be on your system, without worrying about breaking any applications that might require previous versions.

Finally, start working in the virtual environment:

    cd python-venv/
    . bin/activate


### Installing Crossbar.io

To install Crossbar.io with minimal (required) dependencies:

    pip install crossbar

To install Crossbar.io with all additional (optional) dependencies:

    pip install crossbar[all]

To check the installation:

    crossbar version

To update an existing Crossbar.io installation:

    pip install -U crossbar

You can then invoke Crossbar without activating the virtualenv by running `~/python-venv/bin/crossbar`.


## Next

Ready to go? Then [choose your language or device of choice](Choose your Weapon).
