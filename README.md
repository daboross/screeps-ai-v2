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
Game.market.createOrder(ORDER_SELL, RESOURCE_HYDROGEN, x, 20000, "W49N25")
for (let name of Object.keys(Memory.rooms)) { if (!(name in Game.rooms) || !Game.rooms[name].controller || !Game.rooms[name].controller.my) { let mem = Memory.rooms[name]; delete mem.market; if (mem.cache && _.isEmpty(mem.cache)) { delete mem.cache; }; if (_.isEmpty(mem)) { delete Memory.rooms[name]; }}}
JSON.stringify(Game.market.orders, null, 4)
py.get_room("W49N25").minerals.fill_order('')
for (let road of Game.rooms.E7N58.find(FIND_STRUCTURES)) { if (road.structureType == STRUCTURE_ROAD) { road.pos.cfms(py.flags.MAIN_DESTRUCT, py.flags.SUB_ROAD);} }
for (let creep of py.get_room("E9N47").creeps) { if (creep.memory.role == "builder") { py.context.targets().untarget_all(creep) } }
_(py.get_room("E9N47").building.next_priority_repair_targets()).map(Game.getObjectById).filter().map('hits').value()
JSON.stringify(_(py.get_room("E9N47").building.next_priority_repair_targets()).map(Game.getObjectById).filter().map(x => _.map(x.pos.lookFor(LOOK_STRUCTURES), 'structureType')).value(), null, 4)
```

Planned market deals:

py.get_room("W49N25").minerals.fulfill_market_order('E9N11', 'H', 6000, '57d90b4f65b00f5b2259578f')
py.get_room("W49N25").minerals.fulfill_market_order('W60N30', 'H', 100000, 57d8fc7fc1dd100c7b45a4d8')
py.get_room("W49N25").minerals.fulfill_market_order('W50N30', 'Z', 50000, '57da38e4d950275f71ffbd64');
py.get_room("W49N25").minerals.fulfill_market_order('W50N20', 'H', 100 * 1000, '57da2c006de15d752b0684d4');
py.get_room("W49N25").minerals.fulfill_market_order('E24S21', 'H', 6500, '57da2bacc35ad09c28417c3d');
py.get_room("W49N25").minerals.fulfill_market_order('W28S13', 'H', 27082, '57ddd8a09f7906ce03b5d3e1')
py.get_room("W49N25").minerals.fulfill_market_order('W40N40', 'H', 284380, '57e4232ab62fb4be21b2a15f')
_(py.get_room("E17N55").creeps).filter(c => c.memory.role == 'builder').forEach(c => py.context.targets()._register_new_targeter("extra_repair_site", c.name, "57fdce57218402fd6c166f03") || _.set(Memory.creeps[c.name], 'la','b'))
TODO: creep 'setting_up' memory variable which is set on spawn or on replacing or on autoactions move

Game.market.createOrder(ORDER_BUY, "XKHO2", 23, 3000, "E15N52")

py.context.targets()._register_new_targeter("rampart_def", "2366", "57fe2bc3985c67b3701c90c5")
_(py.get_room("E17N55").creeps).filter(c => c.memory.role == 'builder').forEach(c => py.context.targets()._register_new_targeter("extra_repair_site", c.name, "57fdce57218402fd6c166f03") || _.set(Memory.creeps[c.name], 'la','b'))
Memory.rooms.E17N55.cache.building_targets = []; Memory.rooms.E17N55.non_wall_construction_targets = [];
_(py.get_room("E17N55").building.next_priority_repair_targets()).map(Game.getObjectById).filter().map(s => `${s.hits}:${s.structureType}`).value()
for (let room of py.hive().my_rooms) { console.log(`${room.room_name}: def: ${!!room.mem.prepping_defenses}, pause: ${!!room.mem.pause}`) }
_(py.hive().my_rooms).filter('room.terminal').map(x => `\nRoom ${x.roomName} has ${' and '.join(_(x.minerals.get_total_room_resource_counts).map(v, r => `${v} ${r}`))}.`
_(py.hive().my_rooms).filter('room.terminal').map(x => `\nRoom ${x.room_name} has ${x.minerals.get_total_room_resource_counts()['XLHO2'] || 0} XLHO2 and ${x.minerals.get_total_room_resource_counts()['XKHO2'] || 0} XKHO2`).value()
JSON.stringify(_.countBy(py.flags.find_flags_global(py.flags.ATTACK_POWER_BANK), 'pos.roomName'))

py.get_room("E11N34").minerals.fill_order('5828da30dcfc6b7f21ea02d7')
py.get_room("E11N34").minerals.fill_order('5828a31d6a473c1f6cea64af')
py.get_room("E11N34").minerals.fill_order('5828b5dc5d912caa0137185e')
