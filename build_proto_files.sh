#!/bin/bash

# Fail early
set -e

# the directory this script is in
BASEDIR="$(readlink -f $(dirname $0))"
THIS="$0"

cd "$BASEDIR"

# PBF binary
pbf="$BASEDIR/node_modules/pbf/bin/pbf"

input_dir="$BASEDIR/protobuf_files"
output_dir="$BASEDIR/protobuf_temp_output"
mkdir -p "$output_dir"

find "$input_dir" -iname '*.proto' -print0 | xargs -0 -n 1 sh -c "base_name=\"\$(basename \"\$1\")\"; '$pbf' \"\$1\" > \"${output_dir}/\${base_name%.proto}.js\"" --
