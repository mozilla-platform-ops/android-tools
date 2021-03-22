# worker health tools

Tools to ensure Taskcluster workers are not idle and performing well (success rate).

## fitness.py

Provide a report on a provisioner and worker-type.

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

Helps identify Bitbar workers that are configured in a TC queue that has pending jobs, but aren't reporting for work. Utilizes a mozilla-bitbar-devicepool configuration file to detect workers that haven't worked in more than 24 hours.

If a queue doesn't have work, we can't verify they're functioning (via the currently used method).

```
./missing_workers.sh -h
```

## slack_alert

Sends scheduled slack message about problem hosts.

## influx_logger

Logs worker health metrics to influx.
