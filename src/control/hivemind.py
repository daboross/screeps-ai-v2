import math

import context
import creep_wrappers
import flags
from constants import *
from control.building import ConstructionMind
from role_base import RoleBase
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_MAX_BUILDERS = 3
_SLIGHTLY_SMALLER_THAN_MAX_INT = math.pow(2, 30)


# TODO: MiningMind
def _get_hauler_count_for_mine(flag):
    sitting = flag.memory.sitting if flag.memory.sitting else 0
    carry_per_tick = (50.0 * 5.0) / (context.room().distance_storage_to_mine(flag) * 2.1)
    room = Game.rooms[flag.pos.roomName]
    if room and (not room.controller or room.controller.reservation):
        mining_per_tick = 9.0
    else:
        mining_per_tick = 4.0
    produce_per_tick = mining_per_tick + round(sitting / 200.0)
    max_haulers = math.ceil(produce_per_tick / carry_per_tick)
    return max_haulers


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
        has_work = not not creep.getActiveBodyparts(WORK)
        biggest_energy_store = 0
        smallest_num_harvesters = _SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id_1 = None
        best_id_2 = None
        sources = creep.room.find(FIND_SOURCES)
        for source in sources:
            energy = _.sum(source.pos.findInRange(FIND_DROPPED_ENERGY, 1), 'amount') or 0
            # print("[{}] Energy at {}: {}".format(creep.room.name, source.id[-4:], energy))
            if source.id in self.targets[target_source]:
                current_harvesters = self.targets[target_source][source.id]
            else:
                current_harvesters = 0
            if current_harvesters < smallest_num_harvesters:
                smallest_num_harvesters = current_harvesters
            if energy > biggest_energy_store:
                biggest_energy_store = energy
        # print("[{}] Biggest energy store: {}".format(creep.room.name, biggest_energy_store))
        for source in sources:
            dedicated_miner_placed = not not (Memory.dedicated_miners_stationed and
                                              Memory.dedicated_miners_stationed[source.id])
            energy = _.sum(source.pos.findInRange(FIND_DROPPED_ENERGY, 1), 'amount') or 0
            if source.id in self.targets[target_source]:
                current_harvesters = self.targets[target_source][source.id]
            else:
                current_harvesters = 0
            if dedicated_miner_placed or has_work:
                if (current_harvesters <= smallest_num_harvesters) and energy + 100 > biggest_energy_store:
                    # print("[{}] Setting best_id_1: {}. {} + 100 > {}".format(
                    #     creep.room.name, source.id[-4:], energy, biggest_energy_store))
                    best_id_1 = source.id
                elif energy >= biggest_energy_store:
                    best_id_2 = source.id

        if best_id_1:
            return best_id_1
        if best_id_2:
            return best_id_2
        return None

    def _find_new_big_h_source(self, creep):
        for source in creep.room.find(FIND_SOURCES):
            source_id = source.id
            current_harvesters = self.targets[target_big_source][source_id]
            if not current_harvesters or current_harvesters < 1:
                return source_id

        return None

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
        best_id = None
        needs_refresh = False
        for site_id in context.room().building.next_priority_construction_targets():
            if site_id.startsWith("flag-"):
                max_num = _MAX_BUILDERS
            else:
                site = Game.getObjectById(site_id)
                if not site:
                    # we've built it
                    needs_refresh = True
                    continue
                max_num = min(_MAX_BUILDERS, math.ceil((site.progressTotal - site.progress) / 200))
            current_num = self.targets[target_construction][site_id]
            # TODO: this 200 should be a decided factor based off of spawn extensions
            if not current_num or current_num < max_num:
                best_id = site_id
                break
        if needs_refresh:
            context.room().building.refresh_targets()
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
        for flag in context.room().remote_mining_operations:
            flag_id = "flag-{}".format(flag.name)
            miners = self.targets[target_remote_mine_miner][flag_id]
            if not miners or miners < 1:
                distance = movement.distance_squared_room_pos(flag.pos, creep.pos)
                if distance < closest_flag:
                    closest_flag = distance
                    best_id = flag_id
                else:
                    print("[{}][{}] Flag is further than {} away... (range: {})".format(
                        creep.memory.home, creep.name, closest_flag, distance))
            else:
                print("[{}][{}] flag has {} miners already...".format(
                    creep.memory.home, creep.name, miners))

        return best_id

    def _find_new_remote_hauler_mine(self):
        best_id = None
        smallest_percentage = 1  # don't go to any rooms with 100% haulers in use.
        for flag in context.room().remote_mining_operations:
            if not flag.memory.remote_miner_targeting and not (flag.memory.sitting > 500):
                continue  # only target mines with active miners
            flag_id = "flag-{}".format(flag.name)
            haulers = self.targets[target_remote_mine_hauler][flag_id]
            hauler_percentage = haulers / _get_hauler_count_for_mine(flag)
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
        for flag in context.room().remote_mining_operations:
            # TODO: should we only target already-mined rooms?
            if Game.rooms[flag.pos.roomName]:
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
                    if not flag.memory.remote_miner_targeting:
                        distance += 10000  # Choose an already targeted mine if possible!
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
            sponsoring = {}
            for name in Object.keys(Game.rooms):
                room_mind = RoomMind(self, Game.rooms[name])
                all_rooms.append(room_mind)
                if room_mind.my:
                    my_rooms.append(room_mind)
                    if not room_mind.spawn and room_mind.sponsor_name:
                        if sponsoring[room_mind.sponsor_name]:
                            sponsoring[room_mind.sponsor_name].push(room_mind)
                        else:
                            sponsoring[room_mind.sponsor_name] = [room_mind]
                self._room_to_mind[name] = room_mind
            for sponsor_name in sponsoring.keys():
                sponsor = self.get_room(sponsor_name)
                for subsidiary in sponsoring[sponsor_name]:
                    sponsor.subsidiaries.push(subsidiary)
            self._my_rooms = my_rooms
            self._all_rooms = all_rooms
        return self._my_rooms

    def find_visible_rooms(self):
        if not self._all_rooms:
            self.find_my_rooms()
        return self._all_rooms

    def get_room(self, room_name):
        """
        Gets a visible room given its room name.
        :rtype: RoomMind
        """
        return self._room_to_mind[room_name]

    def poll_remote_mining_flags(self):
        flag_list = flags.find_flags_global(flags.REMOTE_MINE)
        room_to_flags = {}
        for flag in flag_list:
            room = self.get_room(flag.pos.roomName)
            if room and room.my:
                print("[{}] Removing remote mining flag {}, now that room is owned.".format(room.room_name, flag.name))
                flag.remove()
            else:
                sponsor = self.get_room(flag.memory.sponsor)
                if not sponsor:
                    print("[hive] Couldn't find sponsor for mining flag {}! (sponsor name set: {})".format(
                        flag.name, flag.memory.sponsor
                    ))
                    continue
                if room_to_flags[sponsor.room_name]:
                    room_to_flags[sponsor.room_name].push(flag)
                else:
                    room_to_flags[sponsor.room_name] = [flag]
        for room in self.visible_rooms:
            if room.room_name in room_to_flags:
                room._remote_mining_operations = room_to_flags[room.room_name]
            else:
                room._remote_mining_operations = []

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
                print("[{}][{}] Giving a {} a new home.".format(home.room_name, creep.name, creep.memory.role))
                creep.memory.home = home.room_name
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
                    Memory.meta.unowned_room_alerted = True
            elif not room.my:
                print("[hive] One or more creeps has {} as its home, but {} isn't owned!".format(name, name))
                if not Memory.meta.unowned_room_alerted:
                    Game.alert("[hive] One or more creeps has {} as its home, but {} isn't owned!".format(name, name))
                    Memory.meta.unowned_room_alerted = True
            else:
                room._creeps = new_creep_lists[name]

    def toString(self):
        return "HiveMind[rooms: {}]".format(JSON.stringify([room.room_name for room in self.my_rooms]))

    my_rooms = property(find_my_rooms)
    visible_rooms = property(find_visible_rooms)


profiling.profile_class(HiveMind, [
    "my_rooms",
    "visible_rooms",
])

# TODO: A lot of these should be changed for if the room has 1 or 2 sources!
_min_work_mass_big_miner = 8  # TODO: This really should be based off of spawn extensions & work mass percentage!
_extra_work_mass_per_big_miner = 10
_min_work_mass_remote_mining_operation = 25
_extra_work_mass_per_extra_remote_mining_operation = 10
_min_work_mass_for_full_storage_use = 35

_min_stored_energy_before_enabling_full_storage_use = 8000
_min_stored_energy_to_draw_from_before_refilling = 20000

# 0 is rcl 1
_rcl_to_sane_wall_hits = [100, 1000, 10 * 1000, 100 * 1000, 500 * 1000, 600 * 1000, 1000 * 1000, 10 * 1000 * 1000]


class RoomMind:
    """
    Modes to create:

    - Whether or not to use STORAGE
    - When to create Big Harvesters
    - When to set workers to TOWER FILL

    Variables to consider
    - WORK_MASS: a total count of all WORK bodyparts on worker creeps
    - CONTROLLER_LEVEL: current controller level
    - USING_STORAGE: whether or not we're using a storage
    - FULL_ROAD_COVERAGE: whether or not all paths are covered in roads in this room.
    :type hive_mind: HiveMind
    :type room: Room
    :type building: ConstructionMind
    :type subsidiaries: list[RoomMind]
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
        self.building = ConstructionMind(self)
        self.subsidiaries = []
        self._remote_mining_operations = None
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
        self._target_defender_count = None
        self._first_target_defender_count = None
        self._first_target_cleanup_count = None
        self._target_colonist_count = None
        self._target_spawn_fill_count = None
        self._max_sane_wall_hits = None
        self._spawns = None
        self.my = room.controller and room.controller.my
        self.spawn = self.spawns[0] if self.spawns and len(self.spawns) else None
        if self.mem.sponsor:
            self.sponsor_name = self.mem.sponsor
        else:
            self.sponsor_name = None

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

    def _get_remote_mining_operations(self):
        if self._remote_mining_operations is None:
            self.hive_mind.poll_remote_mining_flags()
        return self._remote_mining_operations

    remote_mining_operations = property(_get_remote_mining_operations)

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
        rt_pair = [creep.name, creep.get_replacement_time()]
        if not rt_map[role]:
            rt_map[role] = [rt_pair]
        else:
            #_.sortedIndex(array, value, [iteratee=_.identity])
            # Lodash version is 3.10.0 - this was replaced by sortedIndexBy in 4.0.0
            rt_map[role].splice(_.sortedIndex(rt_map[role], rt_pair, lambda p: p[1]), 0, rt_pair)

    def distance_storage_to_mine(self, flag):
        cache_name = "storage_distance_to_{}".format(flag.name)
        cached = self.get_cached_property(cache_name)
        if cached:
            return cached
        if self.room.storage:
            distance = movement.path_distance(self.room.storage.pos, flag.pos)
            self.store_cached_property(cache_name, distance, 150)
        else:
            distance = movement.path_distance(self.spawn.pos, flag.pos)
            self.store_cached_property(cache_name, distance, 75)
        return distance

    def recalculate_roles_alive(self):
        """
        Forcibly recalculates the current roles in the room. If everything's working correctly, this method should have
        no effect. However, it is useful to run this method frequently, for if memory becomes corrupted or a bug is
        introduced, this can ensure that everything is entirely correct.
        """
        print("[{}] Recalculating roles alive.".format(self.room_name))
        # old_rt_map = self.mem.rt_map
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

            rt_pair = (creep.name, creep.get_replacement_time())
            if not rt_map[role]:
                rt_map[role] = [rt_pair]
            else:
                #_.sortedIndex(array, value, [iteratee=_.identity])
                # Lodash version is 3.10.0 - this was replaced by sortedIndexBy in 4.0.0
                rt_map[role].splice(_.sortedIndex(rt_map[role], rt_pair, lambda p: p[1]), 0, rt_pair)
        self.mem.roles_alive = roles_alive
        self.mem.rt_map = rt_map

    def get_next_replacement_name(self, role):
        rt_map = self.rt_map
        if role in rt_map and len(rt_map[role]):
            for rt_pair in rt_map[role]:
                if rt_pair[1] > Game.time:
                    break
                name = rt_pair[0]
                if Memory.creeps[name] and not Memory.creeps[name].replacement:
                    return name

        return None

    def next_x_to_die_of_role(self, role, x=1):
        if not x:
            x = 1
        result = []
        rt_map = self._get_rt_map()
        if role in rt_map and len(rt_map[role]):
            for rt_pair in rt_map[role]:
                result.append(rt_pair[0])
                if len(result) >= x:
                    break
        return result

    def register_new_replacing_creep(self, role, replaced_name, replacing_name):
        print("[{}][{}] Registering as replacement for {} (a {}).".format(self.room_name, replacing_name, replaced_name,
                                                                          role))
        if Memory.creeps[replaced_name]:
            Memory.creeps[replaced_name].replacement = replacing_name
        else:
            print("[{}] Couldn't find creep-needing-replacement {} to register {} as the replacer to!".format(
                self.room_name, replaced_name, replacing_name
            ))

    def replacements_currently_needed_for(self, role):
        rt_map = self._get_rt_map()
        count = 0
        if role in rt_map and len(rt_map[role]):
            for creep, replacement_time in rt_map[role]:
                if (not Memory.creeps[creep] or not Memory.creeps[creep].replacement) and replacement_time <= Game.time:
                    count += 1
                    print("[{}] No one currently replacing {}, a {}!".format(self.room_name, creep, role))
        return count

    def poll_hostiles(self):
        if not Memory.hostiles:
            Memory.hostiles = []
        if not Memory.hostile_last_rooms:
            Memory.hostile_last_rooms = {}
        if Memory.meta.friends and len(Memory.meta.friends):
            targets = self.room.find(FIND_HOSTILE_CREEPS, {
                "filter": lambda c: c.owner.username not in Memory.meta.friends
            })
        else:
            targets = self.room.find(FIND_HOSTILE_CREEPS)
        for hostile in targets:
            if hostile.id not in Memory.hostiles:
                Memory.hostiles.push(hostile.id)
                Memory.hostile_last_rooms[hostile.id] = self.room_name

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
                if not Memory.dedicated_miners_stationed or not Memory.dedicated_miners_stationed[source.id]:
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
            self._full_storage_use = not not (
                (self.trying_to_get_full_storage_use and self.room.storage.store[RESOURCE_ENERGY]
                 >= _min_stored_energy_before_enabling_full_storage_use)
                or (self.room.storage and self.room.storage.store[RESOURCE_ENERGY]
                    >= _min_stored_energy_to_draw_from_before_refilling)
            )
        return self._full_storage_use

    def get_target_dedi_miner_count(self):
        """
        :rtype: int
        """
        if self._ideal_big_miner_count is None:
            if self.work_mass >= _min_work_mass_big_miner:
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
            # TODO: don't count rooms mined by other owned rooms! This is a hack.
            if self.work_mass > _min_work_mass_remote_mining_operation:
                self._target_remote_mining_operation_count = min(
                    1 + math.floor(
                        (self.work_mass - _min_work_mass_remote_mining_operation)
                        / _extra_work_mass_per_extra_remote_mining_operation
                    ),
                    len(self.remote_mining_operations)
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
            if self.get_target_remote_mining_operation_count():
                for flag in self.remote_mining_operations:
                    if flag.memory.remote_miner_targeting or flag.memory.sitting > 500:
                        total_count += _get_hauler_count_for_mine(flag)
            self._target_remote_hauler_count = total_count
        return self._target_remote_hauler_count

    def get_target_remote_reserve_count(self, first):
        """
        :rtype: int
        """
        if (self._first_target_remote_reserve_count if first else self._target_remote_reserve_count) is None:
            mining_op_count = self.get_target_remote_mining_operation_count()
            if mining_op_count:
                rooms_mining_in = set()
                rooms_under_1000 = set()
                rooms_under_4000 = set()
                for flag in self.remote_mining_operations:
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
            else:
                self._first_target_remote_reserve_count = 0
                self._target_remote_reserve_count = 0
        return self._first_target_remote_reserve_count if first else self._target_remote_reserve_count

    def get_target_local_hauler_count(self):
        """
        :rtype: int
        """
        # TODO: Merge local hauler and spawn fill roles!
        if self._target_local_hauler_count is None:
            if self.trying_to_get_full_storage_use:
                # TODO: 2 here should ideally be replaced with a calculation taking in path distance from each source to
                # the storage and hauler capacity.
                total_count = math.ceil(self.get_target_dedi_miner_count() * 1.5)
                for source in self.sources:
                    energy = _.sum(source.pos.findInRange(FIND_DROPPED_ENERGY, 1), 'amount')
                    total_count += energy / 200.0
                self._target_local_hauler_count = math.floor(total_count)

            else:
                self._target_local_hauler_count = 0
        return self._target_local_hauler_count

    def get_target_link_manager_count(self):
        """
        :rtype: int
        """
        if self._target_link_managers is None:
            if len(self.room.find(FIND_STRUCTURES, {"filter": {"structureType": STRUCTURE_LINK}})) >= 2 \
                    and self.trying_to_get_full_storage_use:
                self._target_link_managers = 1
            else:
                self._target_link_managers = 0
        return self._target_link_managers

    def get_target_cleanup_count(self, first=False):
        """
        :rtype: int
        """
        if (self._first_target_cleanup_count if first else self._target_cleanup_count) is None:
            if self.full_storage_use:

                # TODO: merge filter and generic.Cleanup's filter (the same code) together somehow.
                piles = self.room.find(FIND_DROPPED_RESOURCES, {
                    "filter": lambda s: len(
                        _.filter(s.pos.lookFor(LOOK_CREEPS), lambda c: c.memory and c.memory.stationary is True)) == 0
                })
                total_energy = 0
                for pile in piles:
                    total_energy += pile.amount
                if first:
                    self._first_target_cleanup_count = int(math.ceil(total_energy / 1000.0))
                else:
                    # TODO: replacing Math.round with round() once transcrypt fixes that.
                    self._target_cleanup_count = int(min(round(total_energy / 500.0), 1))
            else:
                self._target_cleanup_count = 0

        return self._first_target_cleanup_count if first else self._target_cleanup_count

    def get_target_defender_count(self, first):
        """
        :rtype: int
        """
        if (self._first_target_defender_count if first else self._target_defender_count) is None:
            hostile_count = 0
            hostiles_per_room = {}
            if Memory.hostiles:
                for id in Memory.hostiles:
                    if hostiles_per_room[Memory.hostile_last_rooms[id]]:
                        hostiles_per_room[Memory.hostile_last_rooms[id]] += 1
                    else:
                        hostiles_per_room[Memory.hostile_last_rooms[id]] = 1
            for name in hostiles_per_room.keys():
                # TODO: make a system for each remote mining room to have a base room!
                # Currently, we just spawn defenders for all non-owned rooms, and for this room if it doesn't have
                # any towers. We don't check remote rooms if first is true.
                room = self.hive_mind.get_room(name)
                # TODO: store and find if there are any HEALers, and if there aren't only use towers.
                # TODO: Much more sophisticated attack code needed!
                # TODO: determine if the room is a mining op of ours or not!
                if not room or (room.room_name == self.room_name or (not first and not room.my)):
                    hostile_count += hostiles_per_room[name]
            if first:
                self._first_target_defender_count = hostile_count
            else:
                self._target_defender_count = hostile_count
        return (self._first_target_defender_count if first else self._target_defender_count)

    def get_first_target_cleanup_count(self):
        """
        :rtype: int
        """
        return self.get_target_cleanup_count(True)

    def get_target_colonist_count(self):
        if not self._target_colonist_count:
            needed = 0
            for room in self.subsidiaries:
                needed += max(0, 3 - _.sum(room.role_counts))
            self._target_colonist_count = needed
        return self._target_colonist_count

    def get_target_spawn_fill_backup_count(self):
        # TODO: 7 should be a constant.
        if self.full_storage_use or self.are_all_big_miners_placed or self.work_mass > 8:
            return 1
        else:
            return 2 + len(self.sources)

    def get_target_spawn_fill_count(self):
        if self._target_spawn_fill_count is None:
            spawn_fill_backup = self.role_count(role_spawn_fill_backup)
            tower_fill = self.role_count(role_tower_fill)
            regular_count = max(0, 2 + len(self.sources) - tower_fill - spawn_fill_backup)
            if self.trying_to_get_full_storage_use:
                self._target_spawn_fill_count = regular_count
            else:
                extra_count = 0
                for source in self.sources:
                    energy = _.sum(source.pos.findInRange(FIND_DROPPED_ENERGY, 1), 'amount')
                    extra_count += energy / 200.0
                self._trying_to_get_full_storage_use = regular_count + extra_count
        return self._target_spawn_fill_count

    def get_target_builder_count(self):
        return 2 + 2 * len(self.sources)

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
            [role_spawn_fill_backup, self.get_target_spawn_fill_backup_count],
            [role_defender, lambda: self.get_target_defender_count(True)],
            [role_link_manager, self.get_target_link_manager_count],
            [role_cleanup, self.get_first_target_cleanup_count],
            [role_dedi_miner, self.get_target_dedi_miner_count],
            [role_tower_fill, lambda: tower_fillers],
            [role_cleanup, self.get_target_cleanup_count],
            [role_spawn_fill, self.get_target_spawn_fill_count],
            [role_local_hauler, self.get_target_local_hauler_count],
            [role_upgrader, lambda: 1],
        ]
        for role, get_ideal in requirements:
            if self.role_count(role) - self.replacements_currently_needed_for(role) < get_ideal():
                return role

    def _next_probably_local_role(self):
        roles = [
            [role_builder, self.get_target_builder_count],
        ]
        for role, ideal in roles:
            if self.role_count(role) - self.replacements_currently_needed_for(role) < ideal():
                return role

    def _next_remote_mining_role(self):
        remote_operation_reqs = [
            [role_defender, self.get_target_defender_count],
            # Be sure we're reserving all the current rooms we're mining before we start mining a new room!
            # get_target_remote_reserve_count takes into account only rooms with miners *currently* mining them.
            [role_remote_mining_reserve, lambda: self.get_target_remote_reserve_count(True)],
            [role_remote_hauler, self.get_target_remote_hauler_count],
            [role_remote_miner, self.get_target_remote_mining_operation_count],
            [role_remote_mining_reserve, self.get_target_remote_reserve_count],
            [role_colonist, self.get_target_colonist_count],
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
    "mem",
    "role_counts",
    "room_name",
    "position",
    "sources",
    "spawns",
    "creeps",
    "work_mass",
    "next_role",
    "remote_mining_operations",
    "rt_map",
    "are_all_big_miners_placed",
    "trying_to_get_full_storage_use",
    "full_storage_use",
    "max_sane_wall_hits",
])
