#!/usr/bin/env bash

set -e

input_file="android_hw_gw_execution_flow.dot"
output_prefix="android_hw_gw_execution_flow"

# cleanup
# rm *.png *.svg

# generate
dot -Tsvg $input_file -o $output_prefix.svg
dot -Tpng $input_file -o $output_prefix.png
