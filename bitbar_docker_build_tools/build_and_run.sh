#!/usr/bin/env bash

set -e
set -x

./cleanup.sh

proxy_host=host.docker.internal
export http_proxy="http://localhost:8123"
export https_proxy="http://localhost:8123"

docker build --build-arg http_proxy=http://$proxy_host:8123 \
	--build-arg https_proxy=http://$proxy_host:8123 \
	-t test-docker .

#docker build -t test-docker .
docker create --name test-docker test-docker

./open_shell.sh

# sleep 5
# docker logs test-docker
