#!/usr/bin/env bash

set -e
# set -x

. ./common.sh

#FORCE_CLEAN=1

# TODO: ignore output, but don't hide problems with execution

docker container rm "$DOCKER_IMAGE_NAME" 2>/dev/null || true
# docker images prune || true
# docker container prune -f || true

# from https://stackoverflow.com/questions/32723111/how-to-remove-old-and-unused-docker-images
# TODO: only run this when we need to (docker is out of disk...)

# TODO: this doesn't work, run `docker system df`

# if less than 40 GB
a=$(df -k "$PWD" | awk '/[0-9]%/{print $(NF-5)}')
echo "free disk space in kb: $a"
if (( a < 55000000 )) || [ -n "$FORCE_CLEAN" ] ; then
	echo "performing deep clean..."
	docker rm "$(docker ps -qa --no-trunc --filter 'status=exited')" 2> /dev/null || true
	docker rmi "$(docker images --filter "dangling=true" -q --no-trunc)" 2>/dev/null || true
else
	echo "not performing deep clean."
fi
