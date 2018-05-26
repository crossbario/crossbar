title: Installation on Docker
toc: [Documentation, Installation, Installation on Docker]

# Installation on Docker

## Install Docker

To install Docker follow the instructions at the [Docker Web site](https://docs.docker.com/engine/installation/) for your OS. For instructions below, we assume a Linux system.

## Pull the Crossbar.io Docker image

To pull the latest Crossbar.io (Community) image from DockerHub:

```console
sudo docker pull crossbario/crossbar
```

To start a new Docker container with Crossbar.io

```console
sudo docker run --rm -it -p 8080:8080 --name crossbar crossbario/crossbar
```

If things are working, this logs the startup of Crossbar.io within the container, e.g. (first few lines only listed here)

```console
2017-04-06T14:19:31+0000 [Controller      1] New node key pair generated!
2017-04-06T14:19:31+0000 [Controller      1] File permissions on node private key fixed!
2017-04-06T14:19:31+0000 [Controller      1]      __  __  __  __  __  __      __     __
2017-04-06T14:19:31+0000 [Controller      1]     /  `|__)/  \/__`/__`|__) /\ |__)  |/  \
2017-04-06T14:19:31+0000 [Controller      1]     \__,|  \\__/.__/.__/|__)/~~\|  \. |\__/
2017-04-06T14:19:31+0000 [Controller      1]                                         
2017-04-06T14:19:31+0000 [Controller      1] Version:     Crossbar.io COMMUNITY 17.3.1
```

If you navigate a browser to `http://localhost:8080` you should also see a Crossbar.io status page.

This uses the default configuration file stored in the Docker container.

To use you own configuration and data (e.g. for workers, to be served as Web content), you can either

* start with a node directory from your host system, or
* create a new image with the node directory embedded.

Usually the former will be used during development and the latter for deployments.

## Start with node directory from host

With this method, you provide a directory to use as the node directory on starting the Docker container.

Crossbar.io then uses this as the location to look for its configuration, for worker code or for Web content to serve.

E.g. when you do the following

```console
sudo docker run \
        -v ${PWD}/crossbar:/node \
        -p 8080:8080 \
        --name crossbar \
        --rm -it crossbario/crossbar
```

Crossbar.io will start using the host directory

    {PWD}/crossbar

as a mountpoint for the container volume

    /node

inside.

The Crossbar.io running inside the Docker container expects a Crossbar.io node application directory residing on the volume `/node`.

Put differently, the Crossbar.io inside Docker will start

    crossbar start --cbdir /node/.crossbar

For an example of this in action, see e.g. the [Docker Publisher and Caller Disclosure example](https://github.com/crossbario/crossbar-examples/tree/master/docker/disclose).

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
