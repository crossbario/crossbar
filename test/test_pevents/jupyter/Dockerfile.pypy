##
## CrossbarFX Data Workbench
##

FROM buildpack-deps:bionic

MAINTAINER The Crossbar.io Project <support@crossbario.com>

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1

##### (1) first install pypy3 (copied from https://github.com/docker-library/pypy/blob/master/3/Dockerfile)

# ensure local pypy is preferred over distribution pypy
ENV PATH /usr/local/bin:$PATH

# http://bugs.python.org/issue19846
# > At the moment, setting "LANG=C" on a Linux system *fundamentally breaks Python 3*, and that's not OK.
ENV LANG C.UTF-8

# runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
		tcl \
		tk \
	&& rm -rf /var/lib/apt/lists/*

ENV PYPY_VERSION 6.0.0

# if this is called "PIP_VERSION", pip explodes with "ValueError: invalid truth value '<VERSION>'"
ENV PYTHON_PIP_VERSION 18.1

RUN set -ex; \
	\
# this "case" statement is generated via "update.sh"
	dpkgArch="$(dpkg --print-architecture)"; \
	case "${dpkgArch##*-}" in \
# amd64
		amd64) pypyArch='linux64'; sha256='4cfffa292b9ef34bb6ba39cdbaa196c5c5cbbc5aa3faaa157cf45d7e34027048' ;; \
# arm32v5
		armel) pypyArch='linux-armel'; sha256='6a6888a55192f58594838b8b3d2e7daaad43d3bf4293afab3dd8987d0bbd1124' ;; \
# i386
		i386) pypyArch='linux32'; sha256='b04eeee5160e6cb5f8962de80f077ea1dc7be34e77d74bf075519c23603f5ff9' ;; \
		*) echo >&2 "error: current architecture ($dpkgArch) does not have a corresponding PyPy $PYPY_VERSION binary release"; exit 1 ;; \
	esac; \
	\
	wget -O pypy.tar.bz2 "https://bitbucket.org/pypy/pypy/downloads/pypy3-v${PYPY_VERSION}-${pypyArch}.tar.bz2"; \
	echo "$sha256 *pypy.tar.bz2" | sha256sum -c; \
	tar -xjC /usr/local --strip-components=1 -f pypy.tar.bz2; \
	find /usr/local/lib-python -depth -type d -a \( -name test -o -name tests \) -exec rm -rf '{}' +; \
	rm pypy.tar.bz2; \
	\
	pypy3 --version

RUN set -ex; \
	\
	wget -O get-pip.py 'https://bootstrap.pypa.io/get-pip.py'; \
	\
	pypy3 get-pip.py \
		--disable-pip-version-check \
		--no-cache-dir \
		"pip==$PYTHON_PIP_VERSION" \
	; \
	pip --version; \
	\
	rm -f get-pip.py

##### (2) now install a jupyter based analytics environment

# https://docs.scipy.org/doc/scipy/reference/building/linux.html#debian-ubuntu
# https://jupyterlab.readthedocs.io/en/stable/
# https://github.com/jupyterhub/jupyterhub


RUN    apt-get update \
    && apt-get install -y --no-install-recommends \
               lsb-release \
               ca-certificates \
               apt-transport-https \
               curl \
               wget \
               expat \
               build-essential \
               libssl-dev \
               libsnappy-dev \
               gcc gfortran python-dev libopenblas-dev liblapack-dev cython

RUN wget -O /usr/share/keyrings/red-data-tools-keyring.gpg https://packages.red-data-tools.org/$(lsb_release --id --short | tr 'A-Z' 'a-z')/red-data-tools-keyring.gpg
COPY red-data-tools.list /etc/apt/sources.list.d/

RUN apt-get update && \
    apt-get install -y --no-install-recommends libhdf5-dev libarrow-dev libparquet-dev

RUN pip install -U pip && \
    pip install numpy pandas matplotlib scipy jupyter 

# the following installs all packages from
#
#    * https://github.com/jupyter/docker-stacks/blob/master/scipy-notebook/Dockerfile
#    * https://github.com/jupyter/docker-stacks/blob/master/minimal-notebook/Dockerfile
#    * https://github.com/jupyter/docker-stacks/blob/master/base-notebook/Dockerfile
#
# without the packages already installed further above.
#
# FIXME (failing currently): hdf5 numba
#
RUN pip install ipywidgets numexpr h5py seaborn scikit-learn scikit-image sympy \
                patsy statsmodels cloudpickle dill bokeh sqlalchemy vincent \
                beautifulsoup4 protobuf xlrd

# ML stuff, from https://github.com/jupyter/docker-stacks/blob/master/tensorflow-notebook/Dockerfile
#
# FIXME: tensorflow keras pyro
RUN apt-get update && apt-get install -y cmake

RUN pip install keras
#RUN pip install pyarrow
#RUN pip install pytorch

## our own stuff

RUN pip install -U pip && \
    pip install aiohttp autobahn[asyncio,twisted,encryption,serialization,scram]

# RUN pip install zlmdb cfxdb

COPY .wheels /tmp/

RUN ls -la /tmp

RUN pip install --no-cache-dir \
        /tmp/zlmdb-*-py2.py3-none-any.whl \
        /tmp/cfxdb-*-py2.py3-none-any.whl \
    && pip show zlmdb cfxdb

#USER 1000

ENV HOME /work
VOLUME /work
WORKDIR /work

#RUN mkdir -p /work/.jupyter
#COPY jupyter_notebook_config.py /work/.jupyter

CMD ["jupyter", "notebook", "--allow-root", "--no-browser", "--notebook-dir", "/work/notebooks", "--config", "/work/.jupyter/jupyter_notebook_config.py"]
