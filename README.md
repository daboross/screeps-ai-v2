Screeps-v2
==========

This repository contains a snapshot of my program written for the JavaScript-based MMO game, screeps.com.

Although screeps uses JS, this repository is, as you've probably noticed, written in Python. In order to accomplish this,
I've used a tool called [transcrypt](transcrypt.com).

Transcrypt allows turning a python program pretty directly into a JavaScript program - the command I've used to do this
is in the ``./build.sh` program in this repository.

To get started with this project, you'll need to get the following programs available:
- `python-3.5`
- `pip` (often comes with python)
- `virtualenv` (install manually later, see below)
- `node.js`
- `npm` (often comes with node)
- `grunt` (install manually later, see below)

In order to install Python 3.5, pip, node.js and npm, I would recommend looking up instructions specific to your
operating system.

If you are using Windows, I would also recommend installing `git bash`. You'll need some version of bash in order to run
the deploy script.

To install virtualenv, after you have installed `pip`, use the following command:

```sh
pip install --user virtualenv
```

To install `grunt`, after you have installed `npm`, use the following commands:
```sh
npm install -g grunt-cli
```

After that, you should run the `build.sh` script of this project once to install the rest of the dependencies.

The only remaining step will be to provide your screeps credentials. To do that, put your log in email into a file
called `.screeps-email` in this project directory, and your password into a file called `.screeps-password`.

Following that, you're all set up! All you need to do now is run the `./build.sh` script whenever you want to compile
and deploy code, and it will deal with the rest of it.


##### Notes (personal):

Color scheme: #5c3732, #c2621b, #536958

Some copy/paste commands:

```
JSON.stringify(Game.market.outgoingTransactions, null, 4)
Game.rooms.W47N26.terminal.send(RESOURCE_LEMERGIUM, 5000, "W43N52", "Trading")
Game.market.calcTransactionCost(5000, "W47N26", "W43N52")
JSON.stringify(_.countBy(Game.constructionSites, 'structureType'))
for (let flag of py.flags.find_ms_flag("W49N25", py.flags.MAIN_DESTRUCT, py.flags.SUB_ROAD)) { let road = flag.pos.lookFor(LOOK_STRUCTURES); if (road.length && road[0].structureType == STRUCTURE_ROAD) { road[0].destroy()} else if (!road.length) { flag.remove() }}

Game.profiler.background()
Game.profiler.output(100);
```
