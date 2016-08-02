#!/bin/bash
# Build file for transcrypting Python files into JavaScript, and subsequently deploying to the local repository.

# Fail early
set -e

# Variables
TRANSCRYPT="$HOME/Projects/Python/Environments/screeps/bin/transcrypt"

rm -rf target/
mkdir -p target/

cd "src"
"$TRANSCRYPT" -n -b -p .none main.py
cp __javascript__/main.* ../target/
cd ../

patch target/main.js js_patches/fix_string_format.patch
patch target/main.js js_patches/allow_in_on_objects.patch

cp target/main.js js_files/

rsync -ahP js_files/ ~/.config/Screeps/scripts/screeps.com/v2/
