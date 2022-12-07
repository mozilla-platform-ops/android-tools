# devicepool scripts

- `devicepool_bootstrap.sh`: used on first run for a host
  - calls `devicepool_update.sh`
- `devicepool_update.sh`: used on all runs after
- `devicepool_diff.sh`: used to verify configs are correct/identical

## other scripts

These are called by the main scripts mentioned above.

- `distribute_bitbar_env.sh`: sends out the bitbar env file to /etc/bitbar/bitbar_env
- `distribute_bitbar_files.sh`: sends out files that live in ~bitbar/mozilla-bitbar-devicepool/files

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
