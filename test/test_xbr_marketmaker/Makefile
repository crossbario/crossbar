.PHONY: crossbar example_provider jupyter ganache

CROSSBAR=crossbarfx edge

default:
	docker-compose up --build

clean_db:
	rm -f ${PWD}/crossbar/.testdb/*
	# rm -f ./crossbar/.crossbar/key.*

check_db:
	du -hs crossbar/.testdb/
	ls -la crossbar/.testdb/

run_crossbar:
	$(CROSSBAR) start --cbdir=${PWD}/crossbar/.crossbar

run_example_provider:
	python provider/provider.py

run_example_consumer:
	python consumer/consumer.py

run_jupyter:
	jupyter notebook \
		--config=${PWD}/jupyter/.jupyter/jupyter_notebook_config.py \
		--notebook-dir=${PWD}/jupyter/notebooks

run_ganache:
	docker run -it --rm --user 1000 --net=host --volume=/tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=unix:0 --entrypoint=/bin/sh ganache /run.sh

# https://stackoverflow.com/a/49021109
# docker run -d --rm --device /dev/fuse --cap-add SYS_ADMIN --security-opt apparmor:unconfined <image_id/name> 
# docker run -it --rm --cap-drop=all --net=host --volume=/tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=unix:0 ganache

clean_ganache:
	-sudo rm -rf ./ganache/.data/*

build_ganache:
	docker build -t ganache -f ganache/Dockerfile ganache
