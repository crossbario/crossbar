title: Installation on Docker
toc: [Documentation, Installation, Local Installation, Installation on Docker]

# Crossbar.io and Autobahn Docker Images

With Docker you can run Crossbar.io (and application components) without any interdependencies or interference with your base system. This makes things easier by reducing the number of things which can go wrong.

We provide images on the [Docker Hub](https://hub.docker.com/r/crossbario/)**.

This offers Docker images with [Crossbar.io](https://hub.docker.com/r/crossbario/crossbar/tags/) as well as with [Autobahn|Python](https://hub.docker.com/r/crossbario/autobahn-python/tags/), [Autobahn|JS](https://hub.docker.com/r/crossbario/autobahn-js/tags/) and [Autobahn|Cpp](https://hub.docker.com/r/crossbario/autobahn-cpp/tags/).

For an overview of all Docker images and more technical details, see the [GitHub repository](https://github.com/crossbario/crossbar-docker).


## Usage

Installation:

```console
sudo docker pull crossbario/crossbar
```

To run:

```console
sudo docker run -it -p 8080:8080 crossbario/crossbar
```

(If you haven't pulled the image previously, then this will also do the pull.)

This will start a container with a Crossbar.io node with the default configuration. To check things are running, point your browser to http://localhost:8080. This should show a custom 404 page.


## WAMP Components in Docker Containers

We provide additional Docker images for the Auboahn|JS and Autobahn|Python WAMP client libraries.
These are set up to connect to the above Crossbar.io Docker image.

### AutobahnJS

In a second terminal, type

```console
sudo docker run -it crossbario/autobahn-js node client.js ws://192.168.1.100:8080/ws realm1
```

Here, you will need to replace the IP address `192.168.1.100` with that of your box (and it needs to be one visible from within the container - NOT `127.0.0.1`).

This should log the fact that the component connected and disconnected without errors.

### AutobahnPython

In another terminal, type

```console
sudo docker run -it crossbario/autobahn-python:cpy2 python client.py --url ws://192.168.1.100:8080/ws --realm realm1
```

Again, replace the IP address according to your network setup.

This just logs the fact that it connected and disconnected without errors.


## Image Sizes

We have taken care to keep the image sizes low. As of this writing, the Crossbar.io image is at 111 MB download size. Size is relative here, though:

* The base image which Crossbar.io uses only needs to be downloaded once on the machine you're using Docker on. After that this initial download is used by all Docker images based on the same base image.

* Similarly, since containers use an overlay file system over the base image, additional containers only take up space on disk based on the differences to the root system.


## Next

Ready to go? Then [choose your language or device of choice](Choose your Weapon).