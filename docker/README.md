# Crossbar.io for Docker

Crossbar.io for Docker is available from the official Dockerhub repository for currently 3 CPU architectures:

* [amd64](https://hub.docker.com/r/crossbario/crossbar/tags/)
* [armhf](https://hub.docker.com/r/crossbario/crossbar-armhf/tags/)
* [aarch64](https://hub.docker.com/r/crossbario/crossbar-aarch64/tags/)

The repository here contains the tooling we use to build those images. If you are only _using_ this stuff, then you should be fine with:

**amd64** (eg your usual server):

```console
docker pull crossbario/crossbar
```

**armhf** (eg for the RaspberryPi):

```console
docker pull crossbario/crossbar-armhf
```

**aarch64** (eg on Cavium Thunder X):

```console
docker pull crossbario/crossbar-aarch64
```

## Requirements

### OS

Building is only tested on Ubuntu 16.04 LTS on x86-64. If you use something else, you are on your own.

### Qemu

You will need Qemu since we are cross building images for `armhf` and `aarch64` on an `amd64` host:

```console
make qemu_deps
```

### AutobahnJS

The images here include an example Crossbar.io node directory [./node](./node), and within this directory, there is a copy of AutobahnJS.

To update the files here, you need a current `autobahn-js-built` repo as a sibling to this repository, and then do:

```console
make autobahn
```


## Building

Set the Crossbar.io (Community) version you are building for:

```console
export CROSSBAR_VERSION='17.3.1'
```

Start the build:

```console
make build_community
```

Check Crossbar.io versions by running the images:

```console
make version_community
```


## Images

Here is a current (2017/04/17) table of all Docker images we support for Crossbar.io:

Crossbar.io Edition | Architecture | Base OS | Python | Base Image | Dockerfile | Image Tag
---|---|---|---|---|---|---
Community | amd64 | Alpine | CPy3 | `python:3-alpine` | [Dockerfile.amd64-community-cpy3](Dockerfile.amd64-community-cpy3) | `crossbario/crossbar:community-cpy3`
Community | armhf | Debian/Jessie | CPy3 | `armhf/python:3.6` | [Dockerfile.armhf-community-cpy3](Dockerfile.armhf-community-cpy3) | `crossbario/crossbar-armhf:community-cpy3`
Community | aarch64 | Debian/Jessie | CPy3 | `aarch64/python:3.6` | [Dockerfile.aarch64-community-cpy3](Dockerfile.aarch64-community-cpy3) | `crossbario/crossbar-aarch64:community-cpy3`
Community | amd64 | Debian/jessie | PyPy3 | `debian:jessie` | [Dockerfile.amd64-community-pypy3](Dockerfile.amd64-community-pypy3) | `crossbario/crossbar:community-pypy3`


## Limitations

### PyPy3 on armhf/aarch64 flavors

We currently don't have images for PyPy3 on `armhf` or `aarch64`, because:

* PyPy does not yet support `aarch64`, see [here](https://bitbucket.org/pypy/pypy/issues/2331/armv8-aarch64-or-aarch32-support).
* PyPy does not yet have automated builders for PyPy3 on `arm64`, see [here](https://bitbucket.org/pypy/pypy/issues/2540/missing-pypy3-armhf-builder)

Once above issues are fixed, we will have these images (already listed here for showing the naming system):

Crossbar.io Edition | Architecture | Base OS | Python | Base Image | Dockerfile | Image Tag
---|---|---|---|---|---|---
Community | armhf | Debian/Jessie | PyPy3 | `armhf/debian` | [Dockerfile.armhf-community-cpy3](Dockerfile.armhf-community-cpy3) | `crossbario/crossbar-armhf:community-cpy3`
Community | aarch64 | Debian/Jessie | PyPy3 | `aarch64/debian` | [Dockerfile.aarch64-community-cpy3](Dockerfile.aarch64-community-cpy3) | `crossbario/crossbar-aarch64:community-cpy3

### Alpine on armhf/aarch64

We currently use Debian as the base image on armhf/aarch64 because there is some weirdo issue with libsodium on [musl](https://www.musl-libc.org/), the C run-time library used by Alpine.

During the libsodium build, a test case fails for [sodium_utils3.c](https://github.com/jedisct1/libsodium/blob/master/test/default/sodium_utils3.c):

```
FAIL: sodium_utils3
```

See [here](https://gist.github.com/oberstet/4b0f34b6765aa12ceee723def1f91e20#file-gistfile1-txt-L823).

There also is a warning:

```
qemu: Unsupported syscall: 384
```

See [here](https://gist.github.com/oberstet/4b0f34b6765aa12ceee723def1f91e20#file-gistfile1-txt-L77). However, it seem [this can be ignored](https://docs.resin.io/troubleshooting/troubleshooting/#unsupported-syscall-384-from-qemu-on-builder).

Above issue needs to be further analyzed:

```
See test/default/test-suite.log
Please report to https://github.com/jedisct1/libsodium/issues
```

### Crossbar.io Fabric

Images for Crossbar.io Fabric will follow soonish!



## Qemu crossbuilding

The following are some general notes on cross building Docker images using Qemu.

References:

* http://blog.ubergarm.com/run-arm-docker-images-on-x86_64-hosts/

armhf images:

* https://hub.docker.com/r/armhf/debian/tags/
* https://hub.docker.com/r/armhf/python/tags/

aarch64 images:

* https://hub.docker.com/r/aarch64/debian/tags/
* https://hub.docker.com/r/aarch64/python/tags/

Install the stuff

```console
sudo apt-get update && apt-get install -y --no-install-recommends \
        qemu-user-static \
        binfmt-support
sudo update-binfmts --enable qemu-arm
sudo update-binfmts --display qemu-arm
```

Test the baby:

```console
qemu-arm-static -version
curl -O http://ubergarm.com/dre/hello-world-arm
chmod a+x hello-world-arm
file hello-world-arm
qemu-arm-static hello-world-arm
./hello-world-arm
```

### Testing

#### Debian/armhf

```console
sudo docker pull armhf/debian:jessie
sudo docker run --rm -it -v /usr/bin/qemu-arm-static:/usr/bin/qemu-arm-static armhf/debian:jessie uname -a
```

should give you

```console
Linux 1300319df2a8 4.4.0-72-generic #93-Ubuntu SMP Fri Mar 31 14:07:41 UTC 2017 armv7l GNU/Linux
```

#### CPython3/armhf

```console
sudo docker pull armhf/python:3.6
sudo docker run --rm -it -v /usr/bin/qemu-arm-static:/usr/bin/qemu-arm-static armhf/python:3.6 python -V
```

should give you

```console
Python 3.6.1
```

#### Debian/aarch64


```console
sudo docker pull aarch64/debian:jessie
sudo docker run --rm -it -v /usr/bin/qemu-aarch64-static:/usr/bin/qemu-aarch64-static aarch64/debian:jessie uname -a
```

should give you

```console
Linux 10834da604c6 4.4.0-72-generic #93-Ubuntu SMP Fri Mar 31 14:07:41 UTC 2017 aarch64 GNU/Linux
```

#### CPython3/aarch64

```console
sudo docker pull aarch64/python:3.6
sudo docker run --rm -it -v /usr/bin/qemu-aarch64-static:/usr/bin/qemu-aarch64-static aarch64/python:3.6 python -V
```

should give you

```console
Python 3.6.1
```
