# worker health tools

Tools to ensure Taskcluster workers are not idle and performing well (success rate).

### setup

For all tools, run in the pipenv.

```
# one-time setup
# install pipenv
pipenv install

# for every use
pipenv shell
# run command
```

### overview

## fitness.py

Shows each worker's success rate and varios concerning conditions like, consecutive failures, lack of work.

Provides a report on a provisioner and worker-type.

Not specific to Bitbar (works on all taskcluster provisioners).

![fitness.py](images/fitness_py_example.png)

```
./fitness.py -h

# to report on all worker types under a provisioner
./fitness.py -p PROVISIONER
# for a specific worker-type in the provisioner
./fitness.py -p PROVISIONER WORKER-TYPE
```

## missing_workers

For static hardware pools (like moonshots, macs, and bitbar), alert if a worker hasn't worked in more than a day (they disappear from TC output in 24 hours).

If a queue doesn't have work, we can't verify they're functioning (via the currently used method - TC doesn't show static worker status unless working (I think)).

```
./missing_workers.py -h
```

## slack_alert

Sends scheduled slack message about problem hosts.

```
./slack_alert.py -h
```

## influx_logger

Logs worker health metrics to influx.

```
./influx_logger.py -h
```
