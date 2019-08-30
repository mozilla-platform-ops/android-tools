# devicepool scripts

devicepool_bootstrap.sh: used on first run for a host
devicepool_update.sh: used on all runs after

## required setup

- install btq
  - `pip3 install git+https://github.com/aerickson/btq.git@master`

## TODO

- refactor
  - main scripts
    - devicepool_bootstrap
    - devicepool_maintain
  - pull things out
    - devicepool_converge
    - devicepool_credentials
    - devicepool_update_repos
