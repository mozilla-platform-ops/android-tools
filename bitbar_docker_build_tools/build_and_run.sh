#!/usr/bin/env bash

set -e
#set -x

. ./common.sh

./cleanup.sh

# see if polipo is up
status=0
nc -v -z localhost 8123 || status=$?

if [ "$status" == 0 ] ; then
	# polipo is running
	echo "* using proxy"
	echo ""

	proxy_host=host.docker.internal
	export http_proxy="http://localhost:8123"
	export https_proxy="http://localhost:8123"

	docker build --build-arg http_proxy=http://$proxy_host:8123 \
		--build-arg https_proxy=http://$proxy_host:8123 \
		-t test-docker .
else
	# polipo is not running
	echo "* not using proxy"
	echo ""

	docker build -t "$DOCKER_IMAGE_NAME" .
fi

docker create --name "$DOCKER_IMAGE_NAME" "$DOCKER_IMAGE_NAME"

./open_shell.sh
