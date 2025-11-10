build_amd:
    docker build --platform linux/amd64 -f Dockerfile.working -t europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:latest -t europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:23.1.2 .

build:
    docker build -f Dockerfile.working -t europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:latest -t europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:23.1.2 .

push:
    docker push europe-docker.pkg.dev/record-1283/eu.gcr.io/crossbar:23.1.2

rollout: build_amd build push
