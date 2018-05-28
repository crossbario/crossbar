title: Creating Docker Images
toc: [Documentation, Programming Guide, Creating Docker Images]

# Creating Docker Images

The Docker containers we recommend using for getting started (see [Getting Started](/docs/Getting-Started)) as a default gets its configuration, app code to run and instructions what to run from the respective repository in the starter repository.

You may want to package all of this into a new Docker image, so that you can distribute everything necessary for deployment in one image.

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
