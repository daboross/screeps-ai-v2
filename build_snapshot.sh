#!/bin/bash
# Build file for transpiling Python files into JavaScript, and subsequently deploying to the screeps server.

# Fail early
set -e

# the directory this script is in
BASEDIR="$(readlink -f "$(dirname $0)")"
cd "$BASEDIR"

if [[ ! -e env ]]; then
    virtualenv -p python3.5 --system-site-packages env
    "./env/bin/pip" install -r "$BASEDIR/requirements.txt"
    npm install # do this here because this means we're in a new install
fi

# Transcrypt binary
TRANSCRYPT="$BASEDIR/env/bin/transcrypt"
# Final distribution directory
DIST_DIR="$BASEDIR/dist"
# Source javascript files directory
JS_DIR="$BASEDIR/js_files"
# Python source directory
SRC_DIR="$BASEDIR/src"

cd "$SRC_DIR"
"$TRANSCRYPT" -n -b -p .none main.py
cd "$BASEDIR"

rm -r "$DIST_DIR/"
mkdir -p "$DIST_DIR/"
cp "$SRC_DIR/__javascript__/main.js" "$DIST_DIR/"
cp "$JS_DIR/"*.js "$DIST_DIR/"

cat "$DIST_DIR/customizations.js" "$DIST_DIR/main.js" | sed  -e 's/[[:space:]]*$//' -e 's/'"$(printf '\t')"'/    /g' > "$BASEDIR/snapshot_main.js"