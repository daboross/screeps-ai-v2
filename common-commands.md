screeps-v2 common commands
==========================

Here are some tasks, and how to accomplish them via the console interface.

If you are just using the in game console, and like using terminals, I would recommend installing screeps-pyconsole to connect.
It is a python3 application which uses websockets to connect to the server. Soon I should be offering instillation via pip, but for now you'll
need to clone the repository manually. If you already have the dependencies for screeps-v2 set up though, it doesn't require anything
else. See https://github.com/daboross/screeps-pyconsole.

```
# Count construction sites:
JSON.stringify(_.countBy(Game.constructionSites, 'structureType'))
JSON.stringify(_.countBy(Game.constructionSites, 'pos.roomName'))

# Start the profiler
py.records.start()

# Output profiler results
py.records.output()

# Reset the profiler data
py.records.reset()
py.records.start()

# Clear all path caches to/from the room 'W15S15'
py.cc('W15S15')

# Get tons of data on all currently known hostiles
JSON.stringify(Memory.hostiles, 3, 3)

# Expire everything soon
for (let key in Memory.cache) { Memory.cache[key].d = Game.time + Math.random() * 100; }

# Remove construction sites in W15S15
Game.rooms.W15S15.find(FIND_MY_CONSTRUCTION_SITES).forEach(site => site.remove());

# Enable 'hyper upgrade' status
Memory.hyper_upgrade = true; for (let room of py.context.hive().my_rooms) { room.reset_planned_role() }

# Display the location of all creeps of a certain role
_(Game.creeps).filter('role', py.constants.role_colonist).forEach(console.log(creep.name + ": " + creep.pos))

# Mark existing structures with building flags (with CPU limiter included)
for (let s of Game.rooms.W48N29.find(FIND_STRUCTURES)) { if (s.structureType == STRUCTURE_WALL && !s.pos.lookFor(LOOK_FLAGS).length && Game.cpu.getUsed() < 200) { s.pos.cfms(py.flags.MAIN_BUILD, py.flags.SUB_WALL); } }

# Tell 'W15S15' to empty all resources into 'W25S25'
Memory.rooms.W15S15.empty_to = "W25S25"

# Clear accidentally created values from some room memories
for (let name of Object.keys(Memory.rooms)) { if (!(name in Game.rooms) || !Game.rooms[name].controller || !Game.rooms[name].controller.my) { let mem = Memory.rooms[name]; delete mem.market; if (mem.cache && _.isEmpty(mem.cache)) { delete mem.cache; }; if (_.isEmpty(mem)) { delete Memory.rooms[name]; }}}

# "Complete refresh" to clear old memory values and old creep memories which don't have a room associated with them
py.consistency.complete_refresh()

# Force 'W15S15''s builders to re-target
for (let creep of py.get_room("W15S15").creeps) { if (creep.memory.role == "builder") { py.context.targets().untarget_all(creep) } }

# Check on the building priority of 'W15S15' to ensure it is correct
_(py.get_room("W15S15").building.next_priority_repair_targets()).map(Game.getObjectById).filter().map('hits').value()
JSON.stringify(_(py.get_room("W15S15").building.next_priority_repair_targets()).map(Game.getObjectById).filter().map(x => _.map(x.pos.lookFor(LOOK_STRUCTURES), 'structureType')).value(), null, 4)
_(py.get_room("W15S15").building.next_priority_repair_targets()).map(Game.getObjectById).filter().map(s => `${s.hits}:${s.structureType}`).value()


# Make 'W15S15' re-place remote mining roads
py.get_room('W15S15').building.re_place_remote_mining_roads()

# Example of debugging pathfinding
py.get_room("W47N27").honey.find_path(new RoomPosition(15, 6, "W47N27"), new RoomPosition(21, 2, "W47N26"))
JSON.stringify(PathFinder.search(new RoomPosition(15, 6, "W47N27"), {pos: new RoomPosition(21, 2, "W47N26"), range: 1}), 4, 4)

# Urgent reassignment of all builders in a room to a specific target
_(py.get_room("E17N55").creeps).filter(c => c.memory.role == 'builder').forEach(c => py.context.targets().manually_register(c, 12, "57fdce57218402fd6c166f03") || _.set(Memory.creeps[c.name], 'la','b'))

# Remove flags we don't need anymore
for (let flag of py.flags.find_flags_ms_global(py.flags.MAIN_DESTRUCT, py.flags.SUB_ROAD)) {  flag.remove() }

# Tell exactly where a specific type of flag is located
JSON.stringify(_.countBy(py.flags.find_flags_global(py.flags.ATTACK_POWER_BANK), 'pos.roomName'))

# Manually re-route wall defender
py.context.targets().manually_register({name: "2366"}, 40, "57fe2bc3985c67b3701c90c5")

# Manually turn all creeps to a certain role (unadvisable usually)
Game.rooms.E56N21.find(FIND_MY_CREEPS).forEach(c => c.memory.role = py.constants.role_builder)

# Check on status of owned rooms
for (let room of py.hive().my_rooms) { console.log(`${room.name}: def: ${!!room.mem.prepping_defenses}, pause: ${!!room.mem.pause}`) }

# Get RCL and minimum wall hits for each owned room
_(py.hive().my_rooms).map(x => [x, _(x.find(FIND_STRUCTURES)).filter(s => s.structureType == STRUCTURE_WALL || s.structureType == STRUCTURE_RAMPART).min('hits')]).map(t => [t[0], t[1] == Infinity ? 0 : t[1].hits]).sortBy(t => t[1]).map(t => `${t[0].name}: ${t[0].rcl}, ${t[1] / 1000000}M`).join('\n')

# Get transactions heading towards a specific room
_(Game.market.incomingTransactions).filter(x => x.resourceType == RESOURCE_ENERGY && x.to == 'W47S45').map(x => `${x.from} -> ${x.to}: ${x.amount / 1000}k`.value().join('\n')

# Get recent transactions:
JSON.stringify(Game.market.outgoingTransactions, null, 4)

# Check on market orders
JSON.stringify(Game.market.orders, null, 4)

# Get an overview of all mineral counts and existing orders
py.hive().mineral_report()

# Create a sell order
Game.market.createOrder(ORDER_SELL, RESOURCE_HYDROGEN, 1.0, 20000, "W49N25")

# Create a buy order
Game.market.createOrder(ORDER_BUY, "XKHO2", 23, 3000, "E15N52")

# Example of asking a room to fill an existing market buy order
# Overly specific:
py.get_room("W49N25").minerals.fulfill_market_order('E9N11', 'H', 6000, '57d90b4f65b00f5b2259578f')
# "Just fill it" version:
py.get_room("E11N34").minerals.fill_order('5828b5dc5d912caa0137185e')

# Cancel all orders being filled
_(py.hive().my_rooms).filter(room => room.minerals && !room.minerals.has_no_terminal_or_storage()).forEach(function (room) { delete room.minerals.mem.fulfilling; })

# Force a room's builders to only consider repairing until the next cache refresh
Memory.rooms.E17N55.cache.building_targets = []; Memory.rooms.E17N55.non_wall_construction_targets = [];

# Get furthest distance between owned rooms
_(py.hive().my_rooms).map(r => _(py.hive().my_rooms).map(r2 => Game.map.getRoomLinearDistance(r.name, r2.name)).max()).max()
```

