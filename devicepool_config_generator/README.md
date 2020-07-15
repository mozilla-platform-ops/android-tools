# devicepool config generator

## overview

allocates workers to queues based on queue counts among device types (p2, g5).

## current issues/questions

- would a single queue for all android work be simpler?
  - is there benefit to the split system?
- if p2-perf has 2000 jobs, and p2-unit has 300 very important jobs the program will currently allocate 85% to perf. p2-unit is higher priority (see assumptions) and should have a larger portion of workers.
  - config should specify which queues can donate/share their capacity. p2-unit wouldn't share. better method than using ratio and using minimums.
    - TODO: model desired behavior, then figure out how to write a configuration.

### desired behaviors

Given: 50 workers.

- 200 unit, 1000 perf: 60% unit, 40% perf?
- 200 unit, 100000000 perf: 60 unit, 40% perf
- 0 unit, 1000 perf: 90% perf, x minimum unit
- 1000 unit, 0 perf: 95% unit, x minimum perf

### assumptions

in unit queues:
- we see less abuse/accidental load?
- unit tests are more time sensitive?
  - used in gating more?

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
