#!/usr/bin/env bash
  
set -e

# find all executables in directory, and run with --help
# we expect them to return with code 0, or there's an issue

if [[ "$OSTYPE" == "linux-gnu" ]]; then
        # ...
        find_cmd="find . -executable -type f"
elif [[ "$OSTYPE" == "darwin"* ]]; then
        # Mac OSX
        find_cmd="find . -perm +111 -type f"
else
      echo "unknown os. talk to developer!"
      exit 1
fi

$find_cmd | grep -v test_help | xargs -n 1 -t -I FILE pipenv run FILE --help

echo ""
echo "SUCCESS"
