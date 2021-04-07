# Docker image based on Jupyter Python stack with preinstalled CrossbarFX integration
# https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html#jupyter-tensorflow-notebook

FROM jupyter/tensorflow-notebook

COPY .jupyter/jupyter_notebook_config.py /home/jovyan/.jupyter

RUN pip install -U pip && pip install aiohttp autobahn[asyncio,twisted,encryption,serialization,scram]

# RUN pip install zlmdb cfxdb

COPY .wheels /tmp/

RUN ls -la /tmp

RUN pip install --no-cache-dir \
        /tmp/zlmdb-*-py2.py3-none-any.whl \
        /tmp/cfxdb-*-py2.py3-none-any.whl \
    && pip show zlmdb cfxdb
