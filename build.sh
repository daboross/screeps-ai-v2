#!/bin/bash
source "$HOME/Projects/Python/Environments/screeps/bin/activate"
transcrypt -n -b -p .none src/main.py &&
cp __javascript__/main.js ~/.config/Screeps/scripts/screeps.com/v2/main.js
