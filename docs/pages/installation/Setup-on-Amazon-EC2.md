title: Setup on Amazon EC2
toc: [Documentation, Installation, Setup on Amazon EC2]

# Setup on Amazon EC2

We provide a **Crossbar.io on Amazon EC2 Virtual Machine Image** as a Community AMI to make setup on [Amazon EC2](http://aws.amazon.com/ec2/) as simple as possible. The image has Crossbar.io running on [Ubuntu Server 14.04 LTS](https://insights.ubuntu.com/2014/04/17/whats-new-in-ubuntu-server-14-04-lts/).

If you want to install Crossbar.io from scratch, or run it on a different OS, see the [instructions for installation](Home#Installation).

## Create an Instance

1. Press 'Launch Instance'
2. Select 'Community AMIs' in the list of AMI sources on the left.
3. Search for 'crossbar' using the search box.
4. Select the found AMI.
5. In the setup, when configuring the security group, it makes sense to add a 'Custom TCP Rule' for the 'Port Range' '8080' since the application templates that come with Crossbar are served on this port.

> There are AMIs for all regions, so this should work no matter where you want to run you EC2 instance.


## SSH into the instance

Now connect to the machine via SSH software of your choice.

* The IP or domain name are listed in the instance information
* The user name is 'ubuntu'.

Once you've logged into the machine, you can set up Crossbar.io. One place to start is by using the [application templates](Application Templates). For example, to set up the hello:browser demo and run it, do

    crossbar init --template hello:browser --appdir hello_browser
    cd hello_browser
    crossbar start

You can then access the demo from any (modern) browser at the IP of your machine at port 8080.


## Updating Crossbar.io

Since Crossbar.io is under active development, the version of Crossbar installed in the image will often lag behind.

There are two ways of updating Crossbar.io:


### Update to latest release

You can udpate to the latest release version using `pip` (a Python package manager). Simply do

    pip install -U crossbar[all]


### Update to trunk

To get the most current development version of Crossbar.io, you can update from the GitHub repository. Git is already installed and the repository is cloned into `crossbar`.

To update do

    git pull
    cd crossbar
    pip install --upgrade -e .[all]
