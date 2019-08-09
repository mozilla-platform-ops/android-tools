#!/usr/bin/env bash

set -e

# input_file="android_hw_gw_execution_flow.dot"
# output_prefix="android_hw_gw_execution_flow"

# cleanup
# rm *.png *.svg

# generate
for file in $(ls *.dot)
do
  basename=$(basename -s .dot $file)
  set -x
  dot -Tsvg $basename.dot -o $basename.svg
  dot -Tpng $basename.dot -o $basename.png
  set +x
done