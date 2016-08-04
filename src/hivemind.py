import math

import context
import creep_wrappers
import flags
from constants import *
from role_base import RoleBase
from tools import profiling
from utils import movement
from utils.screeps_constants import *

__pragma__('noalias', 'name')

_MAX_BUILDERS = 3
_SLIGHTLY_SMALLER_THAN_MAX_INT = math.pow(2, 30)


class TargetMind:
    def __init__(self):
        if not Memory.targets:
            Memory.targets = {
                "targets_used": {},
                "targeters_using": {},
                "last_clear": Game.time,
            }
        self.mem = Memory.targets
        if not self.mem.targets_used:
            self.mem.targets_used = {}
        if not self.mem.targeters_using:
            self.mem.targeters_using = {}
        if (self.mem.last_clear or 0) + 500 < Game.time:
            self._reregister_all()
            self.mem.last_clear = Game.time
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

    def __get_targets(self):
        return self.mem.targets_used

    def __set_targets(self, value):
        self.mem.targets_used = value

    def __get_targeters(self):
        return self.mem.targeters_using

    def __set_targeters(self, value):
        self.mem.targeters_using = value

    targets = property(__get_targets, __set_targets)
    targeters = property(__get_targeters, __set_targeters)

    def _register_new_targeter(self, ttype, targeter_id, target_id):
        if targeter_id not in self.targeters:
            self.targeters[targeter_id] = {
                ttype: target_id
            }
        elif ttype not in self.targeters[targeter_id]:
            self.targeters[targeter_id][ttype] = target_id
        else:
            old_target_id = self.targeters[targeter_id][ttype]
            self.targeters[targeter_id][ttype] = target_id
            if old_target_id == target_id:
                return  # everything beyond here would be redundant
            self.targets[ttype][old_target_id] -= 1
            if len(self.targets[ttype][old_target_id]) <= 0:
                del self.targets[ttype][old_target_id]

        if ttype not in self.targets:
            self.targets[ttype] = {
                target_id: 1,
            }
        elif not self.targets[ttype][target_id]:
            self.targets[ttype][target_id] = 1
        else:
            self.targets[ttype][target_id] += 1

    def _reregister_all(self):
        new_targets = {}
        for targeter_id in Object.keys(self.targeters):
            for ttype in Object.keys(self.targeters[targeter_id]):
                target_id = self.targeters[targeter_id][ttype]
                if ttype in new_targets:
                    if target_id in new_targets[ttype]:
                        new_targets[ttype][target_id] += 1
                    else:
                        new_targets[ttype][target_id] = 1
                else:
                    new_targets[ttype] = {target_id: 1}
        self.targets = new_targets

    def _unregister_targeter(self, ttype, targeter_id):
        existing_target = self._get_existing_target_id(ttype, targeter_id)
        if existing_target:
            if self.targets[ttype] and self.targets[ttype][existing_target]:
                self.targets[ttype][existing_target] -= 1
                if self.targets[ttype][existing_target] <= 0:
                    del self.targets[ttype][existing_target]
            del self.targeters[targeter_id][ttype]
            if len(self.targeters[targeter_id]) == 0:
                del self.targeters[targeter_id]

    def _unregister_all(self, targeter_id):
        if self.targeters[targeter_id]:
            for ttype in Object.keys(self.targeters[targeter_id]):
                if ttype in self.targets:
                    target = self.targeters[targeter_id][ttype]
                    if target in self.targets[ttype]:
                        self.targets[ttype][target] -= 1
                        if self.targets[ttype][target] <= 0:
                            del self.targets[ttype][target]
        del self.targeters[targeter_id]

    def _move_targets(self, old_targeter_id, new_targeter_id):
        if self.targeters[old_targeter_id]:
            self.targeters[new_targeter_id] = self.targeters[old_targeter_id]
            del self.targeters[old_targeter_id]

    def _find_new_target(self, ttype, creep, extra_var):
        if not self.targets[ttype]:
            self.targets[ttype] = {}
        func = self.find_functions[ttype]
        if func:
            return func(creep, extra_var)
        else:
            raise Error("Couldn't find find_function for '{}'!".format(ttype))

    def _get_existing_target_id(self, ttype, targeter_id):
        if self.targeters[targeter_id]:
            return self.targeters[targeter_id][ttype]
        return None

    def _get_new_target_id(self, ttype, targeter_id, creep, extra_var):
        existing_target = self._get_existing_target_id(ttype, targeter_id)
        if existing_target:
            return existing_target
        new_target = self._find_new_target(ttype, creep, extra_var)
        if not new_target:
            return None
        self._register_new_targeter(ttype, targeter_id, new_target)
        return new_target

    def get_new_target(self, creep, ttype, extra_var=None, second_time=False):
        target_id = self._get_new_target_id(ttype, creep.name, creep, extra_var)
        if not target_id:
            return None
        if target_id.startswith("flag-"):
            target = Game.flags[target_id[5:]]
        else:
            target = Game.getObjectById(target_id)
        if not target:
            self._unregister_targeter(ttype, creep.name)
            if not second_time:
                return self.get_new_target(creep, ttype, extra_var, True)
        return target

    def _get_existing_target_from_name(self, name, ttype):
        """Exists to give an interface for when creeps die. TODO: make a full method."""
        target_id = self._get_existing_target_id(ttype, name)
        if not target_id:
            return None
        if target_id.startswith("flag-"):
            target = Game.flags[target_id[5:]]
        else:
            target = Game.getObjectById(target_id)
        if not target:
            self._unregister_targeter(ttype, name)
        return target

    def get_existing_target(self, creep, ttype):
        return self._get_existing_target_from_name(creep.name, ttype)

    def untarget(self, creep, ttype):
        self._unregister_targeter(ttype, creep.name)

    def untarget_all(self, creep):
        self._unregister_all(creep.name)

    def assume_identity(self, old_name, new_name):
        self._move_targets(old_name, new_name)

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
                distance = movement.distance_squared_room_pos(source.pos, creep.pos)
                if distance < closest_distance or current_harvesters <= smallest_num_harvesters - 1:
                    best_id = source_id
                    closest_distance = distance
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
                if not current_num or current_num < math.ceil(structure.energyCapacity / creep.carryCapacity):
                    distance = movement.distance_squared_room_pos(structure.pos, creep.pos)
                    if distance < closest_distance:
                        closest_distance = distance
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
                distance = movement.distance_squared_room_pos(site.pos, creep.pos)
                if distance < closest_distance:
                    closest_distance = distance
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
                    distance = movement.distance_squared_room_pos(structure.pos, creep.pos)
                    if distance < closest_distance:
                        smallest_num_builders = current_num
                        closest_distance = distance
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
                    distance = movement.distance_squared_room_pos(structure.pos, creep.pos)
                    if distance < closest_distance:
                        closest_distance = distance
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
                distance = movement.distance_squared_room_pos(flag.pos, creep.pos)
                if distance < closest_flag:
                    closest_flag = distance
                    best_id = flag_id
                else:
                    print("[{}] Flag is further than {} away... (range: {})".format(creep.name, closest_flag, distance))
            else:
                print("[{}] flag has {} miners already...".format(creep.name, miners))

        return best_id

    def _find_new_remote_hauler_mine(self):
        best_id = None
        smallest_percentage = 1  # don't go to any rooms with 100% haulers in use.
        for flag in flags.get_global_flags(flags.REMOTE_MINE):
            if not flag.memory.remote_miner_targeting:
                continue  # only target mines with active miners
            flag_id = "flag-{}".format(flag.name)
            haulers = self.targets[target_remote_mine_hauler][flag_id]
            # TODO: cache this result here, and merge with get_target_remote_hauler_count in RoomMind
            sitting = flag.memory.sitting if flag.memory.sitting else 0
            carry_per_tick = (50.0 * 5.0) / (context.room().distance_storage_to_mine(flag) * 2.0)
            produce_per_tick = 9.0 + (sitting / 500.0)
            max_haulers = math.ceil(produce_per_tick / carry_per_tick) + 1.0
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
        max_reservable = 2 if Game.rooms[creep.memory.home].energyCapacityAvailable < 1300 else 1
        for flag in flags.get_global_flags(flags.REMOTE_MINE):
            # TODO: Figure out why this isn't working.
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
                    distance = movement.distance_squared_room_pos(controller.pos, creep.pos)
                    if distance < closest_room:
                        closest_room = distance
                        best_id = controller_id

        return best_id


profiling.profile_class(TargetMind, ["targets", "targeters"])


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
        self._remote_mining_flags = None
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
                    print("[{}] Removing remote mining flag, now that room is owned.".format(flag.roomName))
                    flag.remove()
                    altered = True
            if altered:
                self._remote_mining_flags = flags.get_global_flags(flags.REMOTE_MINE, True)
        return self._remote_mining_flags

    def get_closest_owned_room(self, current_room_name):
        current_pos = movement.parse_room_to_xy(current_room_name)
        if not current_pos:
            print("[{}] Couldn't parse room name!".format(current_room_name))
            return None
        closest_squared_distance = _SLIGHTLY_SMALLER_THAN_MAX_INT
        closest_room = None
        for room in self.my_rooms:
            if not room.my:
                continue
            distance = movement.squared_distance(current_pos, room.position)
            if distance < closest_squared_distance:
                closest_squared_distance = distance
                closest_room = room
        return closest_room

    def poll_hostiles(self):
        for room in self.visible_rooms:
            room.poll_hostiles()

    def poll_all_creeps(self):
        new_creep_lists = {}
        for name in Object.keys(Game.creeps):
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
_min_stored_energy_to_draw_from_before_refilling = 20000

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
    :type max_sane_wall_hits: int
    """

    def __init__(self, hive_mind, room):
        self.hive_mind = hive_mind
        self.room = room
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
        self._first_target_remote_reserve_count = None
        self._target_remote_reserve_count = None
        self._target_local_hauler_count = None
        self._target_link_managers = None
        self._target_cleanup_count = None
        self._first_target_cleanup_count = None
        self._max_sane_wall_hits = None
        self._spawns = None
        self.my = room.controller and room.controller.my and len(self.spawns)
        self.spawn = self.spawns[0] if self.spawns else None

    def _get_mem(self):
        return self.room.memory

    mem = property(_get_mem)

    def get_cached_property(self, name):
        if not self.mem.cache:
            self.mem.cache = {}
        if name in self.mem.cache and self.mem.cache[name].dead_at > Game.time:
            return self.mem.cache[name].value
        else:
            return None

    def store_cached_property(self, name, value, ttl):
        if not self.mem.cache:
            self.mem.cache = {}
        self.mem.cache[name] = {"value": value, "dead_at": Game.time + ttl}

    def _get_role_counts(self):
        if not self.mem.roles_alive:
            self.recalculate_roles_alive()
        return self.mem.roles_alive

    role_counts = property(_get_role_counts)

    def _get_rt_map(self):
        if not self.mem.rt_map:
            self.recalculate_roles_alive()
        return self.mem.rt_map

    def role_count(self, role):
        count = self.role_counts[role]
        if count:
            return count
        else:
            return 0

    def register_to_role(self, creep):
        """
        Registers the creep's role and time till replacement in permanent memory. Should only be called once per creep.
        """
        if not isinstance(creep, RoleBase):
            creep = creep_wrappers.wrap_creep(creep)
        role = creep.memory.role
        if self.role_counts[role]:
            self.role_counts[role] += 1
        else:
            self.role_counts[role] = 1
        rt_map = self._get_rt_map()
        rt_pair = (creep.name, creep.get_replacement_time(), None)
        if not rt_map[role]:
            rt_map[role] = [rt_pair]
        else:
            #_.sortedIndex(array, value, [iteratee=_.identity])
            # Lodash version is 3.10.0 - this was replaced by sortedIndexBy in 4.0.0
            rt_map[role].splice(_.sortedIndex(rt_map[role], rt_pair, lambda p: p[1]), 0, rt_pair)

    def distance_storage_to_mine(self, flag):
        if not self.room.storage:
            return Infinity
        cache_name = "storage_distance_to_{}".format(flag.name)
        cached = self.get_cached_property(cache_name)
        if cached:
            return cached
        distance = movement.path_distance(self.room.storage.pos, flag.pos)
        self.store_cached_property(cache_name, distance, 150)
        return distance

    def recalculate_roles_alive(self):
        """
        Forcibly recalculates the current roles in the room. If everything's working correctly, this method should have
        no effect. However, it is useful to run this method frequently, for if memory becomes corrupted or a bug is
        introduced, this can ensure that everything is entirely correct.
        """
        old_rt_map = self.mem.rt_map
        roles_alive = {}
        rt_map = {}

        for creep in self.creeps:
            role = creep.memory.role
            if not role:
                continue
            if not roles_alive[role]:
                roles_alive[role] = 1
            else:
                roles_alive[role] += 1
            if creep.spawning or creep.memory.role == role_temporary_replacing:
                continue  # don't add rt_pairs for spawning creeps
            creep = creep_wrappers.wrap_creep(creep)
            rt_pair = (creep.name, creep.get_replacement_time(), None)
            if not rt_map[role]:
                rt_map[role] = [rt_pair]
            else:
                #_.sortedIndex(array, value, [iteratee=_.identity])
                # Lodash version is 3.10.0 - this was replaced by sortedIndexBy in 4.0.0
                rt_map[role].splice(_.sortedIndex(rt_map[role], rt_pair, lambda p: p[1]), 0, rt_pair)
        self.mem.roles_alive = roles_alive
        for role in rt_map.keys():  # ensure we keep existing replacing creeps.
            if role in old_rt_map:
                for rt_pair in rt_map[role].keys():
                    for second_pair in self.mem.rt_map[role]:
                        if second_pair[0] == rt_pair[0]:
                            rt_pair[2] = second_pair[2]
                            print("[{}][recalculate_roles_alive] Found matching rt_pair: Setting {}[2] to {}[2]".format(
                                self.room_name, JSON.stringify(rt_pair), JSON.stringify(second_pair)
                            ))
                            break
                    else:
                        if rt_pair[1] <= Game.time:
                            print("[{}][recalculate_roles_alive] Didn't find matching rt_pair for {} in old rt_map"
                                .format(
                                self.room_name, JSON.stringify(rt_pair)
                            ))
            else:
                print("[{}][recalculate_roles_alive] role {} in new rt_map, but not old rt_map".format(
                    self.room_name, role
                ))
        self.mem.rt_map = rt_map

    def get_next_replacement_name(self, role):
        # return None  # TODO: fix the system and remove this
        rt_map = self.rt_map
        if role in rt_map and len(rt_map[role]):
            index = 0
            while index < len(rt_map[role]) and rt_map[role][index][1] <= Game.time:
                # the third object is the name of the creep currently vying to replace
                if not Game.creeps[rt_map[role][index][2]]:
                    return rt_map[role][index][0]
                index += 1

        return None

    def next_to_die_of_role(self, role):
        rt_map = self.rt_map
        if role in rt_map and len(rt_map[role]):
            return rt_map[role][0][0]

    def register_new_replacing_creep(self, role, replaced_name, replacing_name):
        print("[{}] Registering as replacement for {} (a {}).".format(replacing_name, replaced_name, role))
        rt_map = self._get_rt_map()
        found = False
        if role in rt_map and len(rt_map[role]):
            # TODO: this is somewhat duplicated in get_next_replacement_name
            index = 0
            while index < len(rt_map[role]) and rt_map[role][index][1] <= Game.time:
                # the third object is the name of the creep currently vying to replace
                if rt_map[role][index][0] == replaced_name:
                    rt_map[role][index][2] = replacing_name
                    found = True
                index += 1
        if not found:
            print("[{}] Couldn't find creep-needing-replacement {} to register {} as the replacer to!".format(
                self.room_name, replaced_name, replacing_name
            ))

    def replacements_currently_needed_for(self, role):
        # return 0  # TODO: fix the system and remove this
        rt_map = self._get_rt_map()
        count = 0
        if role in rt_map and len(rt_map[role]):
            for creep, replacement_time, existing_replacer in rt_map[role]:
                if not existing_replacer and replacement_time <= Game.time:
                    count += 1
                    print("[{}] No one currently replacing {}, a {}!".format(self.room_name, creep, role))
        return count

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
            self._position = movement.parse_room_to_xy(self.room.name)
        return self._position

    def get_sources(self):
        if self._sources is None:
            self._sources = self.room.find(FIND_SOURCES)
        return self._sources

    def get_spawns(self):
        if self._spawns is None:
            self._spawns = self.room.find(FIND_MY_SPAWNS)
        return self._spawns

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
        """
        :rtype: bool
        """
        if self._all_big_miners_placed is None:
            all_placed = True
            for source in self.sources:
                if not Memory.big_harvesters_placed[source.id]:
                    all_placed = False
                    break
            self._all_big_miners_placed = all_placed
        return self._all_big_miners_placed

    def get_trying_to_get_full_storage_use(self):
        """
        :rtype: bool
        """
        if self._trying_to_get_full_storage_use is None:
            self._trying_to_get_full_storage_use = self.work_mass >= _min_work_mass_for_full_storage_use \
                                                   and self.are_all_big_miners_placed \
                                                   and self.room.storage
        return self._trying_to_get_full_storage_use

    def get_full_storage_use(self):
        """
        :rtype: bool
        """
        if self._full_storage_use is None:
            self._full_storage_use = (self.trying_to_get_full_storage_use and
                                      self.room.storage.store[RESOURCE_ENERGY]
                                      >= _min_stored_energy_before_enabling_full_storage_use) \
                                     or (self.room.storage and self.room.storage.store[RESOURCE_ENERGY]
                                         >= _min_stored_energy_to_draw_from_before_refilling)
        return self._full_storage_use

    def get_target_big_harvester_count(self):
        """
        :rtype: int
        """
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
        """
        :rtype: int
        """
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
        """
        :rtype: int
        """
        if self._target_remote_hauler_count is None:
            total_count = 0
            for flag in flags.get_global_flags(flags.REMOTE_MINE):
                if flag.memory.remote_miner_targeting:
                    # TODO: merge this with the _find_new_remote_hauler_mine method of TargetMind
                    # TODO: why is 3 neccessary here?
                    sitting = flag.memory.sitting if flag.memory.sitting else 0
                    carry_per_tick = (50.0 * 5.0) / (context.room().distance_storage_to_mine(flag) * 1.5)
                    produce_per_tick = 9.0 + (sitting / 500.0)
                    max_haulers = math.ceil(produce_per_tick / carry_per_tick) + 1.0
                    total_count += max_haulers
            self._target_remote_hauler_count = total_count
        return self._target_remote_hauler_count

    def get_target_remote_reserve_count(self, first):
        """
        :rtype: int
        """
        if (self._first_target_remote_reserve_count if first else self._target_remote_reserve_count) is None:
            mining_op_count = self.get_target_remote_mining_operation_count()
            rooms_mining_in = set()
            rooms_under_1000 = set()
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
                        if not controller.reservation or controller.reservation.ticksToEnd < 1000:
                            rooms_under_1000.add(flag.pos.roomName)
                        if not controller.reservation or controller.reservation.ticksToEnd < 4000:
                            if self.room.energyCapacityAvailable < 1300:
                                # if energy capacity is at least 1300, the reserve creeps we're making are going to have
                                # 2 reserve already!
                                # TODO: this class and spawning logic really need to be merged a bit.
                                rooms_under_4000.add(flag.pos.roomName)

            if first:
                self._first_target_remote_reserve_count = len(rooms_under_1000) + len(rooms_under_4000)
            else:
                # Send 2 per room for rooms < 4000, 1 per room otherwise.
                self._target_remote_reserve_count = len(rooms_mining_in) + len(rooms_under_4000)
        return self._first_target_remote_reserve_count if first else self._target_remote_reserve_count

    def get_target_local_hauler_count(self):
        """
        :rtype: int
        """
        if self._target_local_hauler_count is None:
            if self.trying_to_get_full_storage_use:
                # TODO: 2 here should ideally be replaced with a calculation taking in path distance from each source to
                # the storage and hauler capacity.
                self._target_local_hauler_count = self.get_target_big_harvester_count() * 2
            else:
                self._target_local_hauler_count = 0
        return self._target_local_hauler_count

    def get_target_link_manager_count(self):
        """
        :rtype: int
        """
        if self._target_link_managers is None:
            if len(self.room.find(FIND_STRUCTURES, {"filter": {"structureType": STRUCTURE_LINK}})) >= 2 \
                    and self.room.storage:
                self._target_link_managers = 1
            else:
                self._target_link_managers = 0
        return self._target_link_managers

    def get_target_cleanup_count(self, first=False):
        """
        :rtype: int
        """
        if (self._first_target_cleanup_count if first else self._target_cleanup_count) is None:
            # TODO: merge filter and generic.Cleanup's filter (the same code) together somehow.
            piles = self.room.find(FIND_DROPPED_RESOURCES, {
                "filter": lambda s: len(
                    _.filter(s.pos.lookFor(LOOK_CREEPS), lambda c: c.memory.stationary is True)) == 0
            })
            total_energy = 0
            for pile in piles:
                total_energy += pile.amount
            if first:
                self._first_target_cleanup_count = int(math.ceil(total_energy / 1000.0))
            else:
                # TODO: replacing Math.round with round() once transcrypt fixes that.
                self._target_cleanup_count = int(min(round(total_energy / 500.0), 1))

        return self._first_target_cleanup_count if first else self._target_cleanup_count

    def get_first_target_cleanup_count(self):
        """
        :rtype: int
        """
        return self.get_target_cleanup_count(True)

    def get_max_sane_wall_hits(self):
        """
        :rtype: int
        """
        if self._max_sane_wall_hits is None:
            self._max_sane_wall_hits = _rcl_to_sane_wall_hits[self.room.controller.level - 1]  # 1-to-0-based index
        return self._max_sane_wall_hits

    def _next_needed_local_role(self):
        tower_fillers = len(self.room.find(FIND_STRUCTURES, {"filter": {"structureType": STRUCTURE_TOWER}}))
        requirements = [
            [role_spawn_fill_backup, lambda: 2],
            [role_link_manager, self.get_target_link_manager_count],
            [role_cleanup, self.get_first_target_cleanup_count],
            [role_dedi_miner, self.get_target_big_harvester_count],
            [role_cleanup, self.get_target_cleanup_count],
            [role_tower_fill, lambda: tower_fillers],
            [role_spawn_fill, lambda: 5 - tower_fillers],
            [role_local_hauler, self.get_target_local_hauler_count],
            [role_upgrader, lambda: 1],
        ]
        for role, get_ideal in requirements:
            if self.role_count(role) - self.replacements_currently_needed_for(role) < get_ideal():
                return role

    def _next_probably_local_role(self):
        roles = [
            [role_upgrader, 2],
            [role_builder, 6],
        ]
        for role, ideal in roles:
            if self.role_count(role) - self.replacements_currently_needed_for(role) < ideal:
                return role

    def _next_remote_mining_role(self):
        remote_operation_reqs = [
            [role_defender, lambda: len(Memory.hostiles)],
            # Be sure we're reserving all the current rooms we're mining before we start mining a new room!
            # get_target_remote_reserve_count takes into account only rooms with miners *currently* mining them.
            [role_remote_mining_reserve, lambda: self.get_target_remote_reserve_count(True)],
            [role_remote_hauler, self.get_target_remote_hauler_count],
            [role_remote_mining_reserve, self.get_target_remote_reserve_count],
            [role_remote_miner, self.get_target_remote_mining_operation_count],
        ]
        for role, get_ideal in remote_operation_reqs:
            if self.role_count(role) - self.replacements_currently_needed_for(role) < get_ideal():
                return role

    def reset_planned_role(self):
        del self.mem.next_role

    def plan_next_role(self):
        next_role = self._next_needed_local_role()
        if not next_role:
            next_role = self._next_remote_mining_role()
            if not next_role:
                next_role = self._next_probably_local_role()
        if next_role:
            print("[{}] Next role to spawn: {}".format(self.room_name, next_role))
            self.mem.next_role = next_role
        else:
            print("[{}] Everything's good!".format(self.room_name))
            # set to false specifically to avoid "is None" check in get_next_role()
            self.mem.next_role = None

    def get_next_role(self):
        if self.mem.next_role is undefined:
            self.plan_next_role()
        return self.mem.next_role

    def toString(self):
        return "RoomMind[room_name: {}, roles: {}, my: {}, using_storage: {}]".format(
            self.room_name, self.mem.role_counts if self.mem.role_counts else "undefined", self.my,
            self.full_storage_use)

    room_name = property(get_name)
    position = property(get_position)
    sources = property(get_sources)
    spawns = property(get_spawns)
    creeps = property(get_creeps)
    work_mass = property(get_work_mass)
    next_role = property(get_next_role)
    rt_map = property(_get_rt_map)
    are_all_big_miners_placed = property(get_if_all_big_miners_are_placed)
    trying_to_get_full_storage_use = property(get_trying_to_get_full_storage_use)
    full_storage_use = property(get_full_storage_use)
    max_sane_wall_hits = property(get_max_sane_wall_hits)


profiling.profile_class(RoomMind, [
    "room_name",
    "position",
    "sources",
    "spawns",
    "creeps",
    "work_mass",
    "role_counts",
    "next_role",
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
