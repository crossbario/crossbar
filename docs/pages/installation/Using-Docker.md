title: Using Docker
toc: [Documentation, Installation, Using Docker]

# Using Docker

With [Docker](https://www.docker.com/) you can run Crossbar.io and WAMP application components or microservices without dependencies on or interference with your base system. This makes things easier by reducing the number of things which can go wrong.

We provide ready-to-go Docker images on [Docker Hub](https://hub.docker.com/r/crossbario/) for

* [Crossbar.io Docker Images](https://hub.docker.com/r/crossbario/crossbar/tags/)
* [AutobahnPython Docker Images](https://hub.docker.com/r/crossbario/autobahn-python/tags/)
* [AutobahnJS Docker Images](https://hub.docker.com/r/crossbario/autobahn-js/tags/)
* [AutobahnCpp Docker Images](https://hub.docker.com/r/crossbario/autobahn-cpp/tags/)

For an overview of all Docker images, more technical details and sources, please see the [Git repository](https://github.com/crossbario/crossbar-docker).


## Install Docker

First, [install Docker](https://docs.docker.com/engine/installation/). Here is what works on Ubuntu/Debian

```console
sudo apt-get update
sudo apt-get install curl
curl -fsSL https://get.docker.com/ | sh
sudo usermod -aG docker oberstet
```


## Using the Crossbar.io Docker Image

Get the image from [here](https://hub.docker.com/r/crossbario/crossbar/tags/) by running

    docker pull crossbario/crossbar

and start the image

    docker run -it -p 8080:8080 crossbario/crossbar

> If you haven't pulled the image previously, then this will also do the pull.

This will start a container with a Crossbar.io node with the default configuration. To check things are running, point your browser to `http://localhost:8080`. This should show a custom `404` page.

### Notes on Image Size

We have taken care to keep the image sizes low. As of this writing, the Crossbar.io image is at 80-110 MB download size. Size is relative here, though:

* The base image which Crossbar.io uses only needs to be downloaded once on the machine you're using Docker on. After that this initial download is used by all Docker images based on the same base image.
* Similarly, since containers use an overlay file system over the base image, additional containers only take up space on disk based on the differences to the root system.


## Using the Autobahn Docker Images

We provide additional Docker images for the [Autobahn WAMP client libraries](http://crossbar.io/autobahn/). These images are set up to automatically connect Autobahn to the above Crossbar.io Docker image.


### AutobahnJS

[Start](#using-the-crossbar.io-docker-image) the Crossbar.io image in a first terminal. In a second terminal, type

    docker run -it crossbario/autobahn-js \
        node client.js ws://192.168.1.100:8080/ws realm1

> Here, you will need to replace the IP address `192.168.1.100` with that of your box (and it needs to be one visible from within the container - NOT `127.0.0.1`).

You should see log messages of the Autobahn component successfully connecting and then disconnecting again.


### AutobahnPython

[Start](#using-the-crossbar.io-docker-image) the Crossbar.io image in a first terminal. In a second terminal, type

    docker run -it crossbario/autobahn-python:cpy2 \
        python client.py --url ws://192.168.1.100:8080/ws --realm realm1

> Here, you will need to replace the IP address `192.168.1.100` with that of your box (and it needs to be one visible from within the container - NOT `127.0.0.1`).

You should see log messages of the Autobahn component successfully connecting and then disconnecting again.
