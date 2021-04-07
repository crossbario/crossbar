# Docker image based on Jupyter Python stack with preinstalled CrossbarFX integration
# https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html#jupyter-tensorflow-notebook

FROM jupyter/tensorflow-notebook

RUN pip install -U pip && pip install autobahn[asyncio] zlmdb
