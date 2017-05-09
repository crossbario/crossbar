title: Getting Started
toc: [Documentation, Getting Started]

# Getting Started with Crossbar.io

This guide shows you how to start the Crossbar.io router and some basic application components using Docker containers.

This the quickest way to get the necessary components for developing WAMP applications using Crossbar.io up and running, and to get a feel for how things work.

The Docker containers are kept in sync with the latest Crossbar.io and Autobahn (our WAMP client libraries) releases.

> Docker is **not necessary** to run Crossbar.io, or to develop WAMP applications. We cover alternative ways of getting there in this documentation, and we provide links for these at the end of this guide.

## A basic WAMP Application

We provide four types of Docker containers:

* Crossbar.io router
* Autobahn|Python
* Autobahn|JS
* Autobahn|CPP

The Autobahn containers each run a WAMP component with identical functionality, and the Crossbar.io router serves the JavaScript component for running in the browser.

The component is there to illustrate how to connect to Crossbar.io as well as the interactions which WAMP provides.

Specifically, each component:

* **Subscribes** to a topic (`com.example.oncounter`)
* **Publishes** to the same topic
* **Registers** a procedure (`com.example.add2`)
* **Calls** this procedure

These interactions already work with a single component. The component receives events based on its own publishes and calls the procedure on itself.

When running multiple components:

* Each component receives events based on the pulishes of all components (including itself).
* Procedures on components are called round-robin-style, i.e. the router has an ordered list of registrations and calls these sequentially.

You can mix components of different languages, and run as many components as you want.

Check the log output in the terminals to see what is happening and how things change when you spin up or shut down containers

> Our example uses the Docker images we publish. These are available in a wide range of flavors (base system size, processor architecture). For an overview of available images, as well as for a look what happens inside these, see the [crossbar-docker GitHub repo](https://github.com/crossbario/crossbar-docker).

> The Docker containers as well as the Autobahn libaries are liberally licensed, so you can use them and modify them in your own projects as you like (including commercial ones). Crossbar.io is under the AGPL, which is unproblematic when you use it as-is (again: including in commercial projects).


## How to start

> An alternative for running Crossbar.io without Docker is **installation into a dedicated Python**, see [our instructions](/docs/Installation/). 

You need Docker installed ([Docker installation instructions](https://docs.docker.com/engine/installation/)).

Our make files require that Docker can be run as non-root user - which can be done like so

```console
sudo usermod -aG docker <username>
```

where `username` is the name of the user you're logged in as.

Clone the [Crossbar.io Starter Template Repository](https://github.com/crossbario/crossbar-starter):

```console
git clone https://github.com/crossbario/crossbar-starter.git
```

On first start of each container type, the Docker image is pulled. This is cached so that subsequent starts are fast. (Updates to an image are automatically pulled.)

### Crossbar.io

The Crossbar.io container is required in order for any of the other containers to work properly.

Then start a new Crossbar.io node from the starter template in a container:

```console
cd crossbar-starter/crossbar
make start
```
This should give you output like this:

[![asciicast](https://asciinema.org/a/6ufqm00z2xmdb3xdnrrzf4es7.png)](https://asciinema.org/a/6ufqm00z2xmdb3xdnrrzf4es7)

Now open you browser at [http://localhost:8080](http://localhost:8080).

This displays a WAMP component running in the browser. Open as many pages as you like, try this across different browsers and devices. Check out the log output (toggle developer tools using `F12` in most browsers) how this changes with multiple components running.


### Autobahn|JS

To start an Autobahn|JS component running on NodeJS and connecting to the Crossbar.io node we started with the Crossbar docker container:

```console
cd crossbar-starter/autobahn-js
make start
```

This should give you output like this:

[![asciicast](https://asciinema.org/a/5bd3oco61umd4to8qxfixzbh4.png)](https://asciinema.org/a/5bd3oco61umd4to8qxfixzbh4)

> This uses the latest [autobahn-js](https://hub.docker.com/r/crossbario/autobahn-js/) Docker image for x86 architecture, which is build from [this Docker file](https://github.com/crossbario/crossbar-docker/blob/master/autobahn-js/x86_64/Dockerfile.alpine).     
You can start the container on ARM (v7) and ARM64 with `make start_armhf` and `make start_aarch64` respectively.

### Autobahn|Python

Here is how to start an Autobahn|Python component connecting to the Crossbar.io node we started with the Crossbar docker container:

```console
cd crossbar-starter/autobahn-python
make start
```

This should give you output like this:

[![asciicast](https://asciinema.org/a/a4d35xf82ylibi0jqwfje56b0.png)](https://asciinema.org/a/a4d35xf82ylibi0jqwfje56b0)

> This uses the latest [autobahn-python](https://hub.docker.com/r/crossbario/autobahn-python/) Docker image for x86 architecture, which is build from [this Docker file](https://github.com/crossbario/crossbar-docker/blob/master/autobahn-python/x86_64/Dockerfile.cpy3-alpine).     
You can start the container on ARM (v7) and ARM64 with `make start_armhf` and `start_aarch64` respectively.     

> Autobahn|Python components can be written using either Python 2.7 or >=3.5. They can use  the Twisted framework or, for Python >=3.5, the integrated asyncio. There are images to cover all of these variations. The default image is for Python 3 and supports both variants, but only the code using Twisted is run (you can change this in `app/run`).


### Autobahn|CPP

Here is how to start an Autobahn|CPP component connecting to the Crossbar.io node of above:

```console
cd crossbar-starter/autobahn-cpp
make build
make start
```

This should give you output like this:

[![asciicast](https://asciinema.org/a/aqpejunlkxbk8o4iuaz1lm9x8.png)](https://asciinema.org/a/aqpejunlkxbk8o4iuaz1lm9x8)

> This uses the latest [autobahn-python](https://hub.docker.com/r/crossbario/autobahn-cpp/) Docker image for x86 architecture, which is build from [this Docker file](https://github.com/crossbario/crossbar-docker/blob/master/autobahn-cpp/x86_64/Dockerfile.gcc).     
You can start the container on ARM (v7) and ARM64 with `make build_armhf` & `make start_armhf` and `start_aarch64` & `make start_aarch64` respectively.


### Modifying Things

The containers as-is are there to demonstrate principles.

To develop your own applications, you need to modify the code they run as well as the Crossbar.io config.

The application components are in the `app` directory of each of the subdiretories (and, in the `crossbar` directory, in the `web` directory).

The Crossbar.io configuration file is in the `.crossbar` subdirectory.

## Further Materials

* [installation of Crossbar.io](/docs/Installation)
* [basic concepts of WAMP and Crossbar.io](/docs/Basic-Concepts)
* [development involving external devices](/docs/Development-with-External-Devices)
* [creating Docker images from your components](/docs/Creating-Docker-Images)
* [an overview of available WAMP client libraries](/about/Supported-Languages/)
* [the full documentation](/docs/Table-of-Contents/)
