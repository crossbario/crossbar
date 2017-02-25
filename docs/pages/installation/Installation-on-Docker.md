title: Installation on Docker
toc: [Documentation, Installation, Installation on Docker]

# Installation on Docker

## Install Docker

To install Docker on Ubuntu from official repositories, follow [https://docs.docker.com/engine/installation/linux/ubuntu/](this]).

Once per once, do this

```console
sudo apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    make \
    software-properties-common
```

and this

```console
curl -fsSL https://apt.dockerproject.org/gpg | sudo apt-key add -

sudo add-apt-repository \
       "deb https://apt.dockerproject.org/repo/ \
       ubuntu-$(lsb_release -cs) \
       main"
```

Then, to install Docker

```console
sudo apt-get update
sudo apt-get -y install docker-engine
```

This should give you

```console
ubuntu@ip-172-31-2-14:~$ which docker
/usr/bin/docker
ubuntu@ip-172-31-2-14:~$ sudo docker version
Client:
 Version:      1.13.1
 API version:  1.26
 Go version:   go1.7.5
 Git commit:   092cba3
 Built:        Wed Feb  8 06:50:14 2017
 OS/Arch:      linux/amd64

Server:
 Version:      1.13.1
 API version:  1.26 (minimum version 1.12)
 Go version:   go1.7.5
 Git commit:   092cba3
 Built:        Wed Feb  8 06:50:14 2017
 OS/Arch:      linux/amd64
 Experimental: false
ubuntu@ip-172-31-2-14:~$
```

## Pull the Crossbar.io Docker image

To pull the latest Crossbar.io (Community) image from DockerHub:

```console
sudo docker pull crossbario/crossbar
```

To start a new Docker container with Crossbar.io

```console
sudo docker run --rm -it -p 8080:8080 --name crossbar crossbario/crossbar
```

## Start from host node directories

To start Crosssbar.io in a Docker container while providing a host directory as the node directory for the Crossbar.io node running inside the Docker container, do the following:

```console
sudo docker run \
        -v ${PWD}/crossbar:/node \
        -p 8080:8080 \
        --name crossbar \
        --rm -it crossbario/crossbar
```

Above will start Crossbar.io using the host directory

    {PWD}/crossbar

as a mountpoint for the container volume

    /node

inside.

For example, in a first terminal

```console
cd ~
git clone git@github.com:crossbario/crossbar-examples.git
cd ~/crossbar-examples/docker/disclose
make docker
```

and in a second terminal

```console
make client
```

See [here](https://github.com/crossbario/crossbar-examples/tree/master/docker/disclose).
