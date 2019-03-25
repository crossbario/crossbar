FROM arm32v7/python:3-slim

COPY .qemu/qemu-arm-static /usr/bin/qemu-arm-static

MAINTAINER The Crossbar.io Project <support@crossbario.com>

# Metadata
ARG CROSSBAR_VERSION
ARG BUILD_DATE
ARG CROSSBAR_VCS_REF

# Metadata labeling
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="Crossbar.io Starter Template" \
      org.label-schema.description="Quickstart template for application development with Crossbar.io" \
      org.label-schema.url="http://crossbar.io" \
      org.label-schema.vcs-ref=$CROSSBAR_VCS_REF \
      org.label-schema.vcs-url="https://github.com/crossbario/crossbar" \
      org.label-schema.vendor="The Crossbar.io Project" \
      org.label-schema.version=$CROSSBAR_VERSION \
      org.label-schema.schema-version="1.0"

# Application home
ENV HOME /node
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

# install dependencies and Crossbar.io
RUN    apt-get update \
    && apt-get install -y --no-install-recommends \
               ca-certificates \
               expat \
               build-essential \
               libssl-dev \
               libffi-dev \
               libunwind-dev \
               libsnappy-dev \
               libbz2-dev \
    # install Crossbar.io from PyPI. rgd pip: https://github.com/pypa/pip/issues/6158 and https://github.com/pypa/pip/issues/6197
    && pip install --no-cache-dir --upgrade "pip<19" \
    && pip install --no-cache-dir crossbar>=${CROSSBAR_VERSION} \
    # minimize image
    # && apt-get remove -y build-essential \
    && rm -rf ~/.cache \
    && rm -rf /var/lib/apt/lists/*

# install manually, as environment markers don't work when installing crossbar from pypi
RUN pip install --no-cache-dir "wsaccel>=0.6.2" "vmprof>=0.4.12"

# test if everything installed properly
RUN crossbar version

# add our user and group
RUN adduser --system --group --uid 242 --home /node crossbar

# initialize a Crossbar.io node
COPY ./.node/ /node/
RUN chown -R crossbar:crossbar /node

# make /node a volume to allow external configuration
VOLUME /node

# set the Crossbar.io node directory as working directory
WORKDIR /node

# run under this user, and expose default port
USER crossbar
EXPOSE 8080 8000

# entrypoint for the Docker image is the Crossbar.io executable
ENTRYPOINT ["crossbar", "start", "--cbdir", "/node/.crossbar"]
