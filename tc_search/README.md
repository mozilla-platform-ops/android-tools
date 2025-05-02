# tc_search

Searches Taskcluster provisionerIds and workerTypes for a string.

## usage

### setup

```bash
# install poetry
# - left to user to decide how

# install dependencies
poetry install
. ./.venv/bin/activate
```

### v2

```bash
# finding out how many win moonshots vs
./tc_search_v2.py | grep win | grep nuc | wc -l

./tc_search_v2.py | grep win | grep ms | wc -l
```

### v1

```bash
# show help
./tc_search.py -h

# search for provisioners and worker types mentioning 'bitbar'
./tc_search.py bitbar

# list all provisioners and worker types
./tc_search.py
```
