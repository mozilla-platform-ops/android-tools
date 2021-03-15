# tc_search

Searches Taskcluster provisionerIds and workerTypes for a string.

## usage

```
# install dependencies
pip3 install poetry
poetry shell

# show help
./tc_search.py -h

# search for provisioners and worker types mentioning 'bitbar'
./tc_search.py bitbar

# list all provisioners and worker types
./tc_search.py
```
