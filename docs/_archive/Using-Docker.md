title: Using Docker
toc: [Documentation, Installation, Using Docker]

# Creating Docker Images

It's easy to try out Crossbar.io using our Docker images - see [Getting Starte](/docs/Getting-Started).

This article describes how to create a Docker image from a component you've devleoped using one of our Docker images.

For an overview of all Docker images, more technical details and sources, please see the [Git repository](https://github.com/crossbario/crossbar-docker).


### Notes on Image Size

We have taken care to keep the image sizes low. As of this writing, the Crossbar.io image is at 80-110 MB download size. Size is relative here, though:

* The base image which Crossbar.io uses only needs to be downloaded once on the machine you're using Docker on. After that this initial download is used by all Docker images based on the same base image.
* Similarly, since containers use an overlay file system over the base image, additional containers only take up space on disk based on the differences to the root system.



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
