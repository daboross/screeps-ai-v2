import math

import creep_utils
import flags
import profiling
from constants import *
from screeps_constants import *

__pragma__('noalias', 'name')

_MAX_BUILDERS = 3
_SLIGHTLY_SMALLER_THAN_MAX_INT = math.pow(2, 30)


class TargetMind:
    def __init__(self):
        if not Memory.targets:
            Memory.targets = {
                "targets_used": {},
                "targeters_using": {},
            }
        self.mem = Memory.targets
        if not self.mem.targets_used:
            self.mem.targets_used = {}
        if not self.mem.targeters_using:
            self.mem.targeters_using = {}
        self.targets = self.mem.targets_used
        self.targeters = self.mem.targeters_using
        self.find_functions = {
            target_source: self._find_new_source,
            target_big_source: self._find_new_big_h_source,
            target_construction: self._find_new_construction_site,
            target_repair: self._find_new_repair_site,
            target_big_repair: self._find_new_big_repair_site,
            target_harvester_deposit: self._find_new_harvester_deposit_site,
            target_tower_fill: self._find_new_tower,
            target_remote_mine_miner: self._find_new_remote_miner_mine,
            target_remote_mine_hauler: self._find_new_remote_hauler_mine,
            target_remote_reserve: self._find_new_reservable_controller,
            target_source_local_hauler: self._find_new_local_hauler_mine,
            target_closest_deposit_site: self._find_closest_deposit_site,
        }

    def _register_new_targeter(self, type, targeter_id, target_id):
        if not self.targeters[targeter_id]:
            self.targeters[targeter_id] = {
                type: target_id
            }
        elif not self.targeters[targeter_id][type]:
            self.targeters[targeter_id][type] = target_id
        else:
            old_target_id = self.targeters[targeter_id][type]
            self.targeters[targeter_id][type] = target_id
            if old_target_id == target_id:
                return  # everything beyond here would be redundant
            self.targets[type][old_target_id] -= 1
            if len(self.targets[type][old_target_id]) <= 0:
                del self.targets[type][old_target_id]

        if not self.targets[type]:
            self.targets[type] = {
                target_id: 1
            }
        elif not self.targets[type][target_id]:
            self.targets[type][target_id] = 1
        else:
            self.targets[type][target_id] += 1

    def _unregister_targeter(self, type, targeter_id):
        existing_target = self._get_existing_target_id(type, targeter_id)
        if existing_target:
            self.targets[type][existing_target] -= 1
            if self.targets[type][existing_target] <= 0:
                del self.targets[type][existing_target]
            del self.targeters[targeter_id][type]
            if len(self.targeters[targeter_id]) == 0:
                del self.targeters[targeter_id]

    def _unregister_all(self, targeter_id):
        if self.targeters[targeter_id]:
            for type in Object.keys(self.targeters[targeter_id]):
                target = self.targeters[targeter_id][type]
                self.targets[type][target] -= 1
                if self.targets[type][target] <= 0:
                    del self.targets[type][target]
        del self.targeters[targeter_id]

    def _find_new_target(self, type, creep, extra_var):
        if not self.targets[type]:
            self.targets[type] = {}
        func = self.find_functions[type]
        if func:
            return func(creep, extra_var)
        else:
            raise Error("Couldn't find find_function for '{}'!".format(type))

    def _get_existing_target_id(self, type, targeter_id):
        if self.targeters[targeter_id]:
            return self.targeters[targeter_id][type]
        return None

    def _get_new_target_id(self, type, targeter_id, creep, extra_var):
        existing_target = self._get_existing_target_id(type, targeter_id)
        if existing_target:
            return existing_target
        new_target = self._find_new_target(type, creep, extra_var)
        if not new_target:
            return None
        self._register_new_targeter(type, targeter_id, new_target)
        return new_target

    def get_new_target(self, creep, type, extra_var=None, second_time=False):
        target_id = self._get_new_target_id(type, creep.name, creep, extra_var)
        if not target_id:
            return None
        if target_id.startswith("flag-"):
            target = Game.flags[target_id[5:]]
        else:
            target = Game.getObjectById(target_id)
        if not target:
            self._unregister_targeter(type, creep.name)
            if not second_time:
                return self.get_new_target(creep, type, extra_var, True)
        return target

    def _get_existing_target_from_name(self, name, type):
        """Exists to give an interface for when creeps die. TODO: make a full method."""
        target_id = self._get_existing_target_id(type, name)
        if not target_id:
            return None
        if target_id.startswith("flag-"):
            target = Game.flags[target_id[5:]]
        else:
            target = Game.getObjectById(target_id)
        if not target:
            self._unregister_targeter(type, name)
        return target

    def get_existing_target(self, creep, type):
        return self._get_existing_target_from_name(creep.name, type)

    def untarget(self, creep, type):
        self._unregister_targeter(type, creep.name)

    def untarget_all(self, creep):
        self._unregister_all(creep.name)

    def _find_new_source(self, creep):
        smallest_num_harvesters = 8000
        best_id = None
        closest_distance = _SLIGHTLY_SMALLER_THAN_MAX_INT
        for source in creep.room.find(FIND_SOURCES):
            source_id = source.id
            current_harvesters = self.targets[target_source][source_id]
            if not current_harvesters:
                return source_id
            elif current_harvesters <= smallest_num_harvesters + 1:
                range = creep_utils.distance_squared_room_pos(source.pos, creep.pos)
                if range < closest_distance or current_harvesters <= smallest_num_harvesters - 1:
                    best_id = source_id
                    closest_distance = range
                    smallest_num_harvesters = current_harvesters

        return best_id

    def _find_new_big_h_source(self, creep):
        for source in creep.room.find(FIND_SOURCES):
            source_id = source.id
            current_harvesters = self.targets[target_big_source][source_id]
            if not current_harvesters or current_harvesters < 1:
                return source_id

        return None

    def _find_new_local_hauler_mine(self, creep):
        smallest_num_haulers = _SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id = None
        for source in creep.room.find(FIND_SOURCES):
            source_id = source.id
            current_harvesters = self.targets[target_source_local_hauler][source_id]
            if not current_harvesters:
                return source_id
            elif current_harvesters < smallest_num_haulers:
                best_id = source_id
                smallest_num_haulers = current_harvesters

        return best_id

    def _find_new_harvester_deposit_site(self, creep):
        closest_distance = _SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if (structure.structureType == STRUCTURE_EXTENSION or structure.structureType == STRUCTURE_SPAWN) \
                    and structure.energy < structure.energyCapacity and structure.my:
                source_id = structure.id
                current_num = self.targets[target_harvester_deposit][source_id]
                # TODO: "1" should be a lot bigger if we have smaller creeps and no extensions.
                if not current_num or current_num < 1:
                    range = creep_utils.distance_squared_room_pos(structure.pos, creep.pos)
                    if range < closest_distance:
                        closest_distance = range
                        best_id = source_id

        return best_id

    def _find_new_construction_site(self, creep):
        closest_distance = _SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id = None
        for site in creep.room.find(FIND_CONSTRUCTION_SITES):
            site_id = site.id
            current_num = self.targets[target_construction][site_id]
            # TODO: this 200 should be a decided factor based off of spawn extensions
            if not current_num or current_num < \
                    min(_MAX_BUILDERS, math.ceil((site.progressTotal - site.progress) / 200)):
                range = creep_utils.distance_squared_room_pos(site.pos, creep.pos)
                if range < closest_distance:
                    closest_distance = range
                    best_id = site_id
        return best_id

    def _find_new_repair_site(self, creep, max_hits):
        closest_distance = _SLIGHTLY_SMALLER_THAN_MAX_INT
        smallest_num_builders = _SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if structure.my != False and structure.hits < structure.hitsMax * 0.9 \
                    and (structure.hits < max_hits or not max_hits):
                struct_id = structure.id
                current_num = self.targets[target_repair][struct_id]
                # TODO: this 200 should be a decided factor based off of spawn extensions
                if not current_num or current_num < \
                        min(_MAX_BUILDERS, math.ceil((min(max_hits, structure.hitsMax * 0.9) - structure.hits) / 200)) \
                        or current_num <= smallest_num_builders + 1:
                    range = creep_utils.distance_squared_room_pos(structure.pos, creep.pos)
                    if range < closest_distance:
                        smallest_num_builders = current_num
                        closest_distance = range
                        best_id = struct_id

        return best_id

    def _find_new_big_repair_site(self, creep, max_hits):
        closest_distance = _SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if structure.my != False and structure.hits < structure.hitsMax * 0.9 \
                    and (structure.hits < max_hits or not max_hits):
                struct_id = structure.id
                current_num = self.targets[target_big_repair][struct_id]
                if not current_num or current_num < 1:
                    range = creep_utils.distance_squared_room_pos(structure.pos, creep.pos)
                    if range < closest_distance:
                        closest_distance = range
                        best_id = struct_id

        return best_id

    def _find_new_tower(self, creep):
        most_lacking = 0
        best_id = None
        for tower_id in Memory.tower.towers:
            tower = Game.getObjectById(tower_id)
            if tower.room != creep.room:
                continue
            if tower.energyCapacity - tower.energy > most_lacking:
                most_lacking = tower.energyCapacity - tower.energy
                best_id = tower_id

        return best_id

    def _find_new_remote_miner_mine(self, creep):
        best_id = None
        closest_flag = _SLIGHTLY_SMALLER_THAN_MAX_INT
        for flag in flags.get_global_flags(flags.REMOTE_MINE):
            flag_id = "flag-{}".format(flag.name)
            miners = self.targets[target_remote_mine_miner][flag_id]
            if not miners or miners < 1:
                range = creep_utils.distance_squared_room_pos(flag.pos, creep.pos)
                if range < closest_flag:
                    closest_flag = range
                    best_id = flag_id
                else:
                    print("[{}] Flag is further than {} away... (range: {})".format(creep.name, closest_flag, range))
            else:
                print("[{}] flag has {} miners already...".format(creep.name, miners))

        return best_id

    def _find_new_remote_hauler_mine(self, creep):
        best_id = None
        smallest_percentage = 1  # don't go to any rooms with 100% haulers in use.
        for flag in flags.get_global_flags(flags.REMOTE_MINE):
            if not flag.memory.remote_miner_targeting:
                continue  # only target mines with active miners
            flag_id = "flag-{}".format(flag.name)
            haulers = self.targets[target_remote_mine_hauler][flag_id]
            # TODO: cache this result here.
            max_haulers = math.ceil(math.sqrt(creep_utils.distance_squared_room_pos(
                Game.rooms[creep.memory.home].storage.pos, flag.pos)
            ) / 13)
            hauler_percentage = haulers / max_haulers
            if not haulers or hauler_percentage < smallest_percentage:
                smallest_percentage = hauler_percentage
                best_id = flag_id

        return best_id

    def _find_closest_deposit_site(self, creep):
        # Called once per creep in the entire lifetime
        target = creep.pos.findClosestByPath(FIND_STRUCTURES, {
            "filter": lambda s: s.structureType == STRUCTURE_LINK or s.structureType == STRUCTURE_STORAGE
        })
        if target:
            return target.id
        else:
            return None

    def _find_new_reservable_controller(self, creep):
        best_id = None
        closest_room = _SLIGHTLY_SMALLER_THAN_MAX_INT
        # TODO: this really needs to be some kind of thing merged into RoomMind!
        max_reservable = 1 if Game.rooms[creep.memory.home].energyCapacityAvailable < 1300 else 2
        for flag in flags.get_global_flags(flags.REMOTE_MINE):
            if flag.memory.remote_miner_targeting and Game.rooms[flag.pos.roomName]:
                # must have a remote miner targeting, and be a room we have a view into.
                controller = Game.rooms[flag.pos.roomName].controller
                current_reservers = self.targets[target_remote_reserve][controller.id]
                if current_reservers >= max_reservable:  # TODO: should this be a constant, or is 2 a good small number?
                    continue  # max is 2
                if controller.my or (controller.reservation
                                     and controller.reservation.username != creep.owner.username):
                    continue
                # Dispatch logic is to send 2 reservers to controllers with ticksToEnd < 4000, and 1 reserver to all
                # others.
                if not controller.reservation or controller.reservation.ticksToEnd < 4000 or current_reservers < 1:
                    # Ok, it's a controller we can reserve
                    controller_id = controller.id
                    range = creep_utils.distance_squared_room_pos(controller.pos, creep.pos)
                    if range < closest_room:
                        closest_room = range
                        best_id = controller_id

        return best_id


profiling.profile_class(TargetMind)


class HiveMind:
    """
    :type target_mind: TargetMind
    :type my_rooms: list[RoomMind]
    :type visible_rooms: list[RoomMind]
    """

    def __init__(self, target_mind):
        self.target_mind = target_mind
        self._my_rooms = None
        self._all_rooms = None
        self._room_to_mind = {}

    def find_my_rooms(self):
        if not self._my_rooms:
            my_rooms = []
            all_rooms = []
            for name in Object.keys(Game.rooms):
                room_mind = RoomMind(self, Game.rooms[name])
                all_rooms.append(room_mind)
                if room_mind.my:
                    my_rooms.append(room_mind)
                self._room_to_mind[name] = room_mind
            self._my_rooms = my_rooms
            self._all_rooms = all_rooms
        return self._my_rooms

    def find_visible_rooms(self):
        if not self._all_rooms:
            self.find_my_rooms()
        return self._all_rooms

    def get_room(self, room_name):
        return self._room_to_mind[room_name]

    def get_remote_mining_flags(self):
        if not self._remote_mining_flags:
            self._remote_mining_flags = flags.get_global_flags(flags.REMOTE_MINE)
            altered = False
            for flag in self._remote_mining_flags:
                if Game.rooms[flag.roomName] and Game.rooms[flag.roomName].controller \
                        and Game.rooms[flag.roomName].controller.my:
                    print("[room: {}] Removing remote mining flag, now that room is owned.".format(flag.roomName))
                    flag.remove()
                    altered = True
            if altered:
                self._remote_mining_flags = flags.get_global_flags(flags.REMOTE_MINE, True)
        return self._remote_mining_flags

    def get_closest_owned_room(self, current_room_name):
        current_pos = creep_utils.parse_room_to_xy(current_room_name)
        if not current_pos:
            print("[room: {}] Couldn't parse room name!".format(current_room_name))
            return None
        closest_squared_distance = _SLIGHTLY_SMALLER_THAN_MAX_INT
        closest_room = None
        for room in self.my_rooms:
            if not room.my:
                continue
            distance = creep_utils.squared_distance(current_pos, room.position)
            if distance < closest_squared_distance:
                closest_squared_distance = distance
                closest_room = room
        return closest_room

    def poll_hostiles(self):
        for room in self.visible_rooms:
            room.poll_hostiles()

    def poll_all_creeps(self):
        new_creep_lists = {}
        for name in Game.creeps:
            creep = Game.creeps[name]
            home = creep.memory.home
            if not creep.memory.home:
                home = self.get_closest_owned_room(creep.pos.roomName)
                creep.memory.home = home
            if home in new_creep_lists:
                new_creep_lists[home].append(creep)
            else:
                new_creep_lists[home] = [creep]
        for name in new_creep_lists:
            room = self.get_room(name)
            if not room:
                print("[hive] One or more creeps has {} as its home, but {} isn't even visible!".format(name, name))
                if not Memory.meta.unowned_room_alerted:
                    Game.alert("[hive] One or more creeps has {} as its home, but {} isn't even visible!".format(
                        name, name))
            elif not room.my:
                print("[hive] One or more creeps has {} as its home, but {} isn't owned!".format(name, name))
                if not Memory.meta.unowned_room_alerted:
                    Game.alert("[hive] One or more creeps has {} as its home, but {} isn't owned!".format(name, name))
            else:
                room._creeps = new_creep_lists[name]

    my_rooms = property(find_my_rooms)
    visible_rooms = property(find_visible_rooms)
    remote_mining_flags = property(get_remote_mining_flags)


profiling.profile_class(HiveMind, ["my_rooms", "visible_rooms", "remote_mining_flags"])

_min_work_mass_big_miner = 15
_extra_work_mass_per_big_miner = 10
_min_work_mass_remote_mining_operation = 50
_extra_work_mass_per_extra_remote_mining_operation = 15
_min_work_mass_for_full_storage_use = 35

_min_stored_energy_before_enabling_full_storage_use = 8000

# 0 is rcl 1
_rcl_to_sane_wall_hits = [100, 5000, 10000, 100000, 500000, 1000000, 5000000, 10000000]


class RoomMind:
    """
    Modes to create:

    - Whether or not to use STORAGE
    - When to create Big Harvesters
    - When to set workers to TOWER FILL

    Variables to consider
    - WORK_MASS: a total count of all WORK bodyparts on worker creeps
    - BIG_HARVESTERS_PLACED: where big harvesters exist
    - TIME_TO_REPLACE_BIG_HARVESTER: We need to count how long till the next big harvester dies plus how long it should
                                     take for the new big harvester to move from spawn to the big harvester's location
    :type hive_mind: HiveMind
    :type room: Room
    :type sources: list[Source]
    :type creeps: list[Creep]
    :type work_mass: int
    :type are_all_big_miners_placed: bool
    :type trying_to_get_full_storage_use: bool
    :type full_storage_use: bool
    :type target_big_harvester_count: int
    :type target_remote_miner_count: int
    :type target_remote_hauler_count: int
    :type target_remote_reserve_count: int
    :type target_local_hauler_count: int
    :type max_sane_wall_hits: int
    """

    def __init__(self, hive_mind, room):
        self.hive_mind = hive_mind
        self.room = room
        spawns = room.find(FIND_STRUCTURES, {"filter": {"structureType": STRUCTURE_SPAWN}})
        self.my = room.controller and room.controller.my and len(spawns)
        self.spawn = spawns[0]
        self._sources = None
        self._creeps = None
        self._work_mass = None
        self._position = None
        self._ideal_big_miner_count = None
        self._all_big_miners_placed = None
        self._trying_to_get_full_storage_use = None
        self._full_storage_use = None
        self._target_remote_mining_operation_count = None
        self._target_remote_hauler_count = None
        self._target_remote_reserve_count = None
        self._target_local_hauler_count = None
        self._target_link_managers = None
        self._max_sane_wall_hits = None
        self._spawn = None

    def poll_hostiles(self):
        if not Memory.hostiles:
            Memory.hostiles = []
        if Memory.meta.friends and len(Memory.meta.friends):
            targets = self.room.find(FIND_HOSTILE_CREEPS, {
                "filter": lambda c: c.owner.username not in Memory.meta.friends
            })
        else:
            targets = self.room.find(FIND_HOSTILE_CREEPS)
        for hostile in targets:
            if hostile.id not in Memory.hostiles:
                Memory.hostiles.push(hostile.id)

    def get_name(self):
        return self.room.name

    def get_position(self):
        if self._position is None:
            self._position = creep_utils.parse_room_to_xy(self.room.name)
        return self._position

    def get_sources(self):
        if self._sources is None:
            self._sources = self.room.find(FIND_SOURCES)
        return self._sources

    def get_creeps(self):
        if self._creeps is None:
            creeps = []
            for name in Object.keys(Game.creeps):
                creep = Game.creeps[name]
                if creep.memory.home == self.room_name:
                    creeps.append(creep)
            self._creeps = creeps
        return self._creeps

    def get_work_mass(self):
        if self._work_mass is None:
            mass = 0
            for creep in self.get_creeps():
                for part in creep.body:
                    # TODO: better measure for local haulers!
                    if part.type == WORK or part.type == CARRY:
                        mass += 1
            self._work_mass = math.floor(mass / 2)
        return self._work_mass

    def get_if_all_big_miners_are_placed(self):
        if self._all_big_miners_placed is None:
            all_placed = True
            for source in self.sources:
                if not Memory.big_harvesters_placed[source.id]:
                    all_placed = False
                    break
            self._all_big_miners_placed = all_placed
        return self._all_big_miners_placed

    def get_trying_to_get_full_storage_use(self):
        if self._trying_to_get_full_storage_use is None:
            self._trying_to_get_full_storage_use = self.work_mass >= _min_work_mass_for_full_storage_use \
                                                   and self.are_all_big_miners_placed \
                                                   and self.room.storage
        return self._trying_to_get_full_storage_use

    def get_full_storage_use(self):
        if self._full_storage_use is None:
            self._full_storage_use = self.trying_to_get_full_storage_use and \
                                     self.room.storage.store[RESOURCE_ENERGY] \
                                     >= _min_stored_energy_before_enabling_full_storage_use
        return self._full_storage_use

    def get_target_big_harvester_count(self):
        if self._ideal_big_miner_count is None:
            if self.work_mass > _min_work_mass_big_miner:
                self._ideal_big_miner_count = min(
                    len(self.sources),
                    1 + math.floor((self.work_mass - _min_work_mass_big_miner) /
                                   _extra_work_mass_per_big_miner)
                )
            else:
                self._ideal_big_miner_count = 0
        return self._ideal_big_miner_count

    def get_target_remote_mining_operation_count(self):
        if self._target_remote_mining_operation_count is None:
            if self.work_mass > _min_work_mass_remote_mining_operation:
                self._target_remote_mining_operation_count = min(
                    1 + math.floor(
                        (self.work_mass - _min_work_mass_remote_mining_operation)
                        / _extra_work_mass_per_extra_remote_mining_operation
                    ),
                    len(self.hive_mind.remote_mining_flags)
                )
            else:
                self._target_remote_mining_operation_count = 0
        return self._target_remote_mining_operation_count

    def get_target_remote_hauler_count(self):
        if self._target_remote_hauler_count is None:
            # TODO: this assumes that walking distance ~= exact range, and that remote miners go to storage, not the closest link.
            # After we get some code to calculate walking distances based off of a path (is it just number of entries?), we should
            # fix this, AND CACHE IT IN MEMORY! (as it will use paths)
            total_count = 0
            for flag in flags.get_global_flags(flags.REMOTE_MINE):
                if flag.memory.remote_miner_targeting:
                    amount = math.ceil(
                        math.sqrt(creep_utils.distance_squared_room_pos(self.room.storage.pos, flag.pos)) / 13
                    )
                    total_count += amount
            self._target_remote_hauler_count = total_count
        return self._target_remote_hauler_count

    def get_target_remote_reserve_count(self):
        if self._target_remote_reserve_count is None:
            mining_op_count = self.target_remote_miner_count
            rooms_mining_in = set()
            rooms_under_4000 = set()
            for flag in flags.get_global_flags(flags.REMOTE_MINE):
                # TODO: Should we really be using *existing* miners to determine *target* reservers?
                # We might want to instead calculate the exact planned operations, but that would require range
                # calculations.
                room = Game.rooms[flag.pos.roomName]
                if flag.memory.remote_miner_targeting and room:
                    controller = room.controller
                    # TODO: hardcoded username here
                    if controller and (not controller.reservation or controller.reservation.username == "daboross"):
                        if mining_op_count <= 0:
                            break  # let's only process the right number of mining operations
                        mining_op_count -= 1
                        rooms_mining_in.add(flag.pos.roomName)
                        if not controller.reservation or controller.reservation.ticksToEnd < 4000:
                            if self.room.energyCapacityAvailable < 1300:
                                # if energy capacity is at least 1300, the reserve creeps we're making are going to have
                                # 2 reserve already!
                                # TODO: this class and spawning logic really need to be merged a bit.
                                rooms_under_4000.add(flag.pos.roomName)
            # Send 2 per room for rooms < 4000, 1 per room otherwise.
            self._target_remote_reserve_count = len(rooms_mining_in) + len(rooms_under_4000)
        return self._target_remote_reserve_count

    def get_target_local_hauler_count(self):
        if self._target_local_hauler_count is None:
            if self.trying_to_get_full_storage_use:
                # TODO: 2 here should ideally be replaced with a calculation taking in path distance from each source to
                # the storage and hauler capacity.
                self._target_local_hauler_count = self.target_big_harvester_count * 2
            else:
                self._target_local_hauler_count = 0
        return self._target_local_hauler_count

    def get_target_link_manager_count(self):
        if self._target_link_managers is None:
            if len(self.room.find(FIND_STRUCTURES, {"filter": {"structureType": STRUCTURE_LINK}})) >= 2 \
                    and self.room.storage:
                self._target_link_managers = 1
            else:
                self._target_link_managers = 0
        return self._target_link_managers

    def get_max_sane_wall_hits(self):
        if self._max_sane_wall_hits is None:
            self._max_sane_wall_hits = _rcl_to_sane_wall_hits[self.room.controller.level - 1]  # 1-to-0-based index
        return self._max_sane_wall_hits

    room_name = property(get_name)
    position = property(get_position)
    sources = property(get_sources)
    creeps = property(get_creeps)
    work_mass = property(get_work_mass)
    are_all_big_miners_placed = property(get_if_all_big_miners_are_placed)
    trying_to_get_full_storage_use = property(get_trying_to_get_full_storage_use)
    full_storage_use = property(get_full_storage_use)
    target_big_harvester_count = property(get_target_big_harvester_count)
    target_remote_miner_count = property(get_target_remote_mining_operation_count)
    target_remote_hauler_count = property(get_target_remote_hauler_count)
    target_remote_reserve_count = property(get_target_remote_reserve_count)
    target_local_hauler_count = property(get_target_local_hauler_count)
    target_link_manager_count = property(get_target_link_manager_count)
    max_sane_wall_hits = property(get_max_sane_wall_hits)


profiling.profile_class(RoomMind, [
    "room_name",
    "position",
    "sources",
    "creeps",
    "work_mass",
    "are_all_big_miners_placed",
    "trying_to_get_full_storage_use",
    "full_storage_use",
    "target_big_harvester_count",
    "target_remote_miner_count",
    "target_remote_hauler_count",
    "target_remote_reserve_count",
    "target_link_manager_count",
    "max_sane_wall_hits",
])
