# last_started_alert

Send a pagerduty alert if there are jobs in the monitored TC queues and there are no 'start' events in the devicepool logs. See code for exact logic.

Designed to run on the devicepool servers.

## setup

```
venv -p python3 virtualenv
./venv/bin/pip install -r requirements.txt
```

## usage

### alert mode

```
PAGERDUTY_TOKEN=<SERVICE_TOKEN> venv/bin/python ./last_started_alert.py

```

### debugg / test mode

```
venv/bin/python ./last_started_alert.py -v
```
