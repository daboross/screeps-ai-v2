#!/bin/bash
# Build file for transcrypting Python files into JavaScript, and subsequently deploying to the local repository.

# Fail early
set -e

# Variables
TRANSCRYPT="$HOME/Projects/Python/Environments/screeps/bin/transcrypt"

rm -rf target/
mkdir -p target/

cd "src"
"$TRANSCRYPT" -n -b -p .none -e 6 main.py
cp __javascript__/main.* ../target/
cd ../

# Use perl here rather than sed in order to do multi-line regex matching
# This is a workaround for some sort of error caused by the Screeps environment - I think it's loading the code multiple times without clearing the main namespace or something, and thus defineProperty() fails with "already exists".
# This if statement will fix that, but this is a hacky way of adding it - maybe I can get a patch format in the future?
perl -0777 -pi -e 's/(Object.defineProperty [(]String.prototype, (:?.+|\n){48})/if (!String.prototype.format) {$1}/g' target/main.js

cp target/main.js js_files/

rsync -ahP js_files/ ~/.config/Screeps/scripts/screeps.com/v2/
