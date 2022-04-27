# quarantine_tools

Tools for quarantining taskcluster workers.

## usage

```bash
# quarantine
./tc_quarantine.py -q -p talos1804 1,10,100

# lift quarantine
./tc_quarantine.py -l -p talos1804 2,4,6,8

# get quarantined
./tc_quarantine.py -g -p talos1804

```
