WHEELS=${PWD}/jupyter/.wheels
CROSSBAR_ROOT=${HOME}/scm/crossbario/crossbarfx


default:
	@echo "targets: run_crossbar run_crossbar_dev build_notebook run_notebook"


clean_wheels:
	-rm -f $(WHEELS)/*
	ls -la $(WHEELS)

build_wheels:
	CROSSBAR_ROOT=$(CROSSBAR_ROOT) pip wheel --no-cache-dir --no-deps --wheel-dir=$(WHEELS) \
		../../../zlmdb \
		../../cfxdb
	ls -la $(WHEELS)


clean_db:
	-rm -rf ./crossbar/.testdb/


analyze:
	python analyze.py


run_crossbar_host:
	crossbarfx edge start \
		--cbdir=${PWD}/crossbar/.crossbar \
		--loglevel=info

run_crossbar_exe:
	~/crossbarfx-linux-amd64-20181028-fc87e59 edge start \
		--cbdir=${PWD}/crossbar/.crossbar \
		--loglevel=info

run_crossbar:
	docker run -it --rm \
		-p 8080:8080 \
		-v ${PWD}/crossbar:/node \
		--name crossbar \
		crossbario/crossbarfx

run_crossbar_pypy3:
	docker run -it --rm \
		-p 8080:8080 \
		-v ${PWD}/crossbar:/node \
		--name crossbar \
		crossbario/crossbarfx:pypy3


version_crossbar_host:
	crossbarfx edge version

version_crossbar:
	docker run -it --rm \
		--entrypoint=/usr/local/bin/crossbarfx \
		crossbario/crossbarfx \
		edge version

version_crossbar_pypy3:
	docker run -it --rm \
		--entrypoint=/usr/local/bin/crossbarfx \
		crossbario/crossbarfx:pypy3 \
		edge version


run_notebook_host:
	jupyter notebook \
		--config=${PWD}/jupyter/jupyter_notebook_config.py \
		--notebook-dir=${PWD}/jupyter/notebooks

run_notebook:
	docker run \
		--net=host \
		-v ${PWD}/jupyter/notebooks:/work/notebooks \
		-v ${PWD}/crossbar/.testdb:/work/testdb \
		crossbario/crossbarfx-notebook


build_notebook: build_wheels build_notebook_cpy build_notebook_pypy

build_notebook_cpy:
	docker build \
		-t crossbario/crossbarfx-notebook:cpy \
		-f jupyter/Dockerfile.cpy jupyter

build_notebook_pypy:
	docker build \
		-t crossbario/crossbarfx-notebook \
		-t crossbario/crossbarfx-notebook:latest \
		-t crossbario/crossbarfx-notebook:pypy \
		-f jupyter/Dockerfile.pypy jupyter


publish_notebook: publish_notebook_cpy publish_notebook_pypy

publish_notebook_cpy:
	docker push crossbario/crossbarfx-notebook:cpy

publish_notebook_pypy:
	docker push crossbario/crossbarfx-notebook
	docker push crossbario/crossbarfx-notebook:latest
	docker push crossbario/crossbarfx-notebook:pypy

