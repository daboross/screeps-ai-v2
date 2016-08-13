#!/bin/bash
# Build file for transcrypting Python files into JavaScript, and subsequently deploying to the local repository.

# Fail early
set -e

# the directory this script is in
BASEDIR="$(readlink -f $(dirname $0))"
cd "$BASEDIR"

if [[ ! -e env ]]; then
    virtualenv -p python3.5 --system-site-packages env
    "./env/bin/pip" install -r "$BASEDIR/requirements.txt"
    npm install # do this here because this means we're in a new install
fi

# Variables
TRANSCRYPT="$BASEDIR/env/bin/transcrypt"


rm -rf target/
mkdir -p target/

cd "src"
"$TRANSCRYPT" -n -b -p .none main.py
cp __javascript__/main.* ../target/
cd ../

patch -lb target/main.js js_patches/fix_string_format.patch
patch -lb target/main.js js_patches/allow_in_on_objects.patch

mkdir -p dist/
cp target/main.js dist/
cp js_files/*.js dist/

grunt screeps "$@"
