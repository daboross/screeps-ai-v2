#!/bin/bash
source "$HOME/Projects/Python/Environments/screeps/bin/activate"
cd "src" &&
transcrypt -n -b -p .none main.py &&
# Use perl here rather than sed in order to do multi-line regex matching
# This is a workaround for some sort of error caused by the Screeps environment - I think it's loading the code multiple times without clearing the main namespace or something, and thus defineProperty() fails with "already exists".
# This if statement will fix that, but this is a hacky way of adding it - maybe I can get a patch format in the future?
perl -0777 -pi -e 's/(Object.defineProperty [(]String.prototype, (:?.+|\n){48})/if (!String.prototype.format) {$1}/g' __javascript__/main.js &&
cp __javascript__/main.js ~/.config/Screeps/scripts/screeps.com/v2/main.js
true
