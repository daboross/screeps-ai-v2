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
delete Memory.cache.path_W47N27_15_6_W47N26_21_2
py.get_room("W47N27").honey.find_path(new RoomPosition(15, 6, "W47N27"), new RoomPosition(21, 2, "W47N26"))
JSON.stringify(PathFinder.search(new RoomPosition(15, 6, "W47N27"), {pos: new RoomPosition(21, 2, "W47N26"), range: 1}), 4, 4)
JSON.stringify(Memory.hostiles, 3, 3)
for (let key in Memory.cache) { Memory.cache[key].d = Game.time + Math.random() * 50 }
for (let key in Memory.cache) { if (key.indexOf("W46N28") != -1) { delete Memory.cache[key] } }
for (let site of Game.rooms.W45N28.find(FIND_MY_CONSTRUCTION_SITES)) { site.remove() };
for (let key in Memory.cache) { if (key.indexOf("W45N28") != -1) { delete Memory.cache[key] } }
for (let room of py.context.hive().visible_rooms) { delete room.mem.cache.paving_here }
for (let room of py.context.hive().visible_rooms) { room.building.next_priority_destruct_targets(); room.building.refresh_destruction_targets(); }
Memory.hyper_upgrade = true; for (let room of py.context.hive().my_rooms) { room.reset_planned_role() }
for (let flag of py.flags.find_flags_ms_global(py.flags.MAIN_DESTRUCT, py.flags.SUB_ROAD)) {  flag.remove() }
Memory.rooms.W46N28.empty_to = "W49N25"
delete Memory.rooms.W47N26.cache.placed_mining_roads
for (let creep of _.values(Game.creeps)) { if (creep.memory.role == py.constants.role_colonist) { console.log(creep.name + ": "+ creep.pos); }}
for (let s of Game.rooms.W48N29.find(FIND_STRUCTURES)) { if (s.structureType == STRUCTURE_WALL && !s.pos.lookFor(LOOK_FLAGS).length && Game.cpu.getUsed() < 200) { s.pos.cfms(py.flags.MAIN_BUILD, py.flags.SUB_WALL); } }
```
