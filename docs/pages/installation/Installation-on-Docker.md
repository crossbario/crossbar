title: Installation on Docker
toc: [Documentation, Installation, Installation on Docker]

# Installation on Docker

## Install Docker

To install Docker on Ubuntu from official repositories, follow [[https://docs.docker.com/engine/installation/linux/ubuntu/]].

Once per host, do the following to add the Docker upstream Ubuntu/Debian repository

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

## Start with node directory from host

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

The Crossbar.io running inside the Docker container expects a Crossbar.io node application directory residing on the volume `/node`.

Put differently, the Crossbar.io inside Docker will start

    crossbar start --cbdir /node/.crossbar

For example, in a first terminal

```console
cd ~
git clone git@github.com:crossbario/crossbar-examples.git
cd ~/crossbar-examples/docker/disclose
sudo docker run \
    -v ${PWD}/crossbar:/node \
    -p 8080:8080 \
    --name crossbar \
    --rm -it crossbario/crossbar
```

and in a second terminal

```console
sudo docker run \
    -v ${PWD}/client:/root --link crossbar \
    --rm -it crossbario/autobahn-python:cpy3-alpine \
    python /root/client.py --url ws://crossbar:8080/ws --realm realm1
```

This should give you the output as [here](https://github.com/crossbario/crossbar-examples/tree/master/docker/disclose).


## Create new image with node directory embedded

Say you have a Crossbar.io node directory with configuration, embedded backend components and static Web assets:

```console
ubuntu@ip-172-31-2-14:~/crossbar-examples/docker/disclose$ ls -la crossbar/
total 20
drwxrwxr-x 3 ubuntu ubuntu 4096 Feb 25 22:00 .
drwxrwxr-x 4 ubuntu ubuntu 4096 Feb 25 22:14 ..
-rw-rw-r-- 1 ubuntu ubuntu  151 Feb 25 21:25 backend.py
drwxrwxr-x 2 ubuntu ubuntu 4096 Feb 25 22:00 .crossbar
-rw-rw-r-- 1 ubuntu ubuntu 3076 Feb 25 21:04 index.html
ubuntu@ip-172-31-2-14:~/crossbar-examples/docker/disclose$ ls -la crossbar/.crossbar/
total 12
drwxrwxr-x 2 ubuntu ubuntu 4096 Feb 25 22:00 .
drwxrwxr-x 3 ubuntu ubuntu 4096 Feb 25 22:00 ..
-rw-rw-r-- 1 ubuntu ubuntu 1571 Feb 25 21:24 config.json
```

To bundle that into a Docker image, create a new `Dockerfile`:

```
FROM crossbario/crossbar

# copy over our own node directory from the host into the image
# set user "root" before copy and change owner afterwards
USER root
COPY ./crossbar /mynode
RUN chown -R crossbar:crossbar /mynode

ENTRYPOINT ["crossbar", "start", "--cbdir", "/mynode/.crossbar"]
```

Then do

```console
sudo docker build -t myimage -f Dockerfile .
```

To start the image:

```console
sudo docker run --rm -it -p 8080:8080 myimage
```


## systemd

To start a Crossbar.io Docker container via systemd, following the instructions from [here](https://docs.docker.com/engine/admin/host_integration/#/systemd), create a new systemd service unit file for Crossbar.io (`sudo vim /etc/systemd/system/crossbar.service`)

**First, create a container**:

```console
cd ~/crossbar-examples/docker/disclose
sudo docker create \
    -v /home/ubuntu/crossbar-examples/docker/disclose/crossbar:/node \
    -p 8080:8080 \
    --name crossbar \
    crossbario/crossbar
```

**Second, create a Crossbar.io systemd service unit**:

```
[Unit]
Description=Crossbar.io
Requires=docker.service
After=docker.service

[Service]
Restart=always
StandardInput=null
StandardOutput=journal
StandardError=journal
Environment="MYVAR1=foobar"
ExecStart=/usr/bin/docker start -a crossbar
ExecStop=/usr/bin/docker stop -t 2 crossbar

[Install]
WantedBy=default.target
```

**Third, reload systemd and start the service**g:

```console
sudo systemctl daemon-reload
sudo systemctl enable crossbar
sudo systemctl start crossbar
sudo systemctl status crossbar
sudo journalctl -f -u crossbar
```

Above will make Crossbar.io start automatically at system boot time, and also start it immediately.

In the running system, you will see this process hierarchy (`sudo systemctl status`):

```console
● ip-172-31-2-14
    State: running
     Jobs: 0 queued
   Failed: 0 units
    Since: Sat 2017-02-25 22:58:48 UTC; 1min 15s ago
   CGroup: /
           ├─docker
           │ └─955d5a34ebf1a701e9efab2ed8442948b2a7c4699a434276574ae05a392f5c5d
           │   ├─1500 crossbar-controller
           │   └─1545 crossbar-worker [router]
...
```

That is, Crossbar.io is actually started not directly by systemd, but by the Docker background daemon.

This can also be seen in the logs, where the log lines are all prefixed by "docker":

```console
ubuntu@ip-172-31-2-14:~$ journalctl -f -u crossbar
-- Logs begin at Sat 2017-02-25 22:58:48 UTC. --
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Router         15] Realm 'realm1' started
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Controller      1] Router 'worker-001': realm 'realm-001' (named 'realm1') started
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Router         15] role role-001 on realm realm-001 started
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Controller      1] Router 'worker-001': role 'role-001' (named 'anonymous') started on realm 'realm-001'
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Router         15] started component: backend.Backend id=3096306263440467
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Router         15] connected!
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Controller      1] Router 'worker-001': component 'component-001' started
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Router         15] Site starting on 8080
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Controller      1] Router 'worker-001': transport 'transport-001' started
Feb 25 22:58:55 ip-172-31-2-14 docker[1406]: 2017-02-25T22:58:55+0000 [Controller      1] Node configuration applied successfully!
...
```
