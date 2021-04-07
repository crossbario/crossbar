default:
	@echo "targets: build run"

build:
	docker build --rm -t my-crossbarfx-notebook .

run:
	docker run \
		-p 8888:8888 \
		-v /some/host/folder/for/work:/home/jovyan/work \
		--user $UID --group-add users \
		my-crossbarfx-notebook
