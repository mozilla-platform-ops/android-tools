# devicepool config generator

## overview

allocates workers to queues based on queue counts among device types (p2, g5).

## setup

```
# install poetry
# see: https://python-poetry.org/docs/#installation

poetry install
poetry shell
# if poetry is grumpy, try the following
poetry env use python3  # or python3.7
```

## running against a test config

```
make
```

## running against real config

```
# copy the original config to .original
# - the generator outputs to config.yaml, so we need to record the original checkout state
cp config.yaml config.yaml.original

./generate.py -c PATH_TO_DEVICEPOOL_CONFIG_DIR

```

The tool doesn't restart the service (yet).

## testing

```
make test
```