#!/usr/bin/env bash

set -e

mkdir -p /tmp/cache/polipo
polipo2 -c polipo.conf
