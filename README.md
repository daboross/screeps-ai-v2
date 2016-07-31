Screeps-v2
==========

This repository contains a snapshot of my program written for the JavaScript-based MMO game, screeps.com.

Although screeps uses JS, this repository is, as you've probably noticed, written in Python. In order to accomplish this,
I've used a tool called [transcrypt](transcrypt.com).

Transcrypt allows turning a python program pretty directly into a JavaScript program - the command I've used to do this
is in the ``./build.sh` program in this repository.

If you do choose to try this script/program, I would recommend first making a virtualenv for screeps
(be sure to use Python 3.5), installing transcrypt with pip, and editing the `build.sh` script to
match your directory structure, rather than mine.

Due to the competitive nature of the game, I've decided to not release any of my scripts after today's date, 2016-07-31.
This repository is a snapshot from that date, and can serve as a based for your program if you want - however, I have
designed a lot of it to my personal development preferences, and part of the fun of Screeps is designing your own script.

I chose this date because it's one where my script does completely function, but has a few large architecture things
which definitely should be changed going into the future, including the creep-spawning system. The code goes up to
doing remote mining, but does not manage claiming any other rooms, or finding any remote mining or building targets
itself. Some of the things are in place to manage multiple rooms, but also some code definitely assumes that we only
own one room.

If you do take some ideas from this repository, that's awesome, but at some point I would definitely recommend rewriting
the core framework of the repository, and only taking the usage of transcrypt, and maybe a design few ideas.
