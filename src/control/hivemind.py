import math

import creep_wrappers
import flags
import spawning
from constants import *
from control import live_creep_utils
from control.building import ConstructionMind
from control.links import LinkingMind
from control.minerals import MineralMind
from control.mining import MiningMind
from control.pathdef import HoneyTrails
from role_base import RoleBase
from roles import military
from tools import profiling
from utilities import consistency
from utilities import movement
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def fit_num_sections(needed, maximum, extra_initial=0, min_split=1):
    if maximum <= 1:
        return maximum

    num = min_split
    trying = Infinity
    while trying > maximum:
        trying = math.ceil(needed / num - extra_initial)
        num += 1
    return trying


def parse_xy_arguments(pos, optional_y):
    """
    Parses x/optional_y arguments into x, y, and roomName
    :param pos: The first argument
    :param optional_y: The second argument
    :return: (x, y, room_name)
    :rtype: (int, int, str)
    """
    if optional_y is not None and optional_y is not undefined:
        return pos, optional_y, None
    else:
        if pos.pos:
            return pos.pos.x, pos.pos.y, pos.pos.roomName
        else:
            return pos.x, pos.y, pos.roomName


class HiveMind:
    """
    :type target_mind: control.targets.TargetMind
    :type my_rooms: list[RoomMind]
    :type visible_rooms: list[RoomMind]
    """

    def __init__(self, target_mind):
        self.target_mind = target_mind
        self.honey = HoneyTrails(self)
        self._my_rooms = None
        self._all_rooms = None
        self._remote_mining_flags = None
        self._room_to_mind = {}

    def find_my_rooms(self):
        """
        :rtype: list[RoomMind]
        """
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
                sponsor = self._room_to_mind[sponsor_name]
                if sponsor:
                    for subsidiary in sponsoring[sponsor_name]:
                        sponsor.subsidiaries.push(subsidiary)
            self._my_rooms = my_rooms
            self._all_rooms = _.sortBy(all_rooms, 'room_name')
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
        if not self._all_rooms:
            self.find_visible_rooms()
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
                if not flag.memory.active:
                    continue
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
        current_room = self.get_room(current_room_name)
        if current_room and current_room.my:
            return current_room

        mining_flags = flags.find_flags(current_room_name, flags.REMOTE_MINE)
        for flag in mining_flags:
            return self.get_room(flag.memory.sponsor)
        current_pos = movement.parse_room_to_xy(current_room_name)
        if not current_pos:
            print("[{}] Couldn't parse room name!".format(current_room_name))
            return None
        closest_squared_distance = Infinity
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
                    Game.notify("[hive] One or more creeps has {} as its home, but {} isn't even visible!".format(
                        name, name))
                    Memory.meta.unowned_room_alerted = True
            elif not room.my:
                print("[hive] One or more creeps has {} as its home, but {} isn't owned!".format(name, name))
                if not Memory.meta.unowned_room_alerted:
                    Game.notify("[hive] One or more creeps has {} as its home, but {} isn't owned!".format(name, name))
                    Memory.meta.unowned_room_alerted = True
            else:
                room._creeps = new_creep_lists[name]

    def toString(self):
        return "HiveMind[rooms: {}]".format(JSON.stringify([room.room_name for room in self.my_rooms]))

    my_rooms = property(find_my_rooms)
    visible_rooms = property(find_visible_rooms)


profiling.profile_whitelist(HiveMind, [
    "poll_remote_mining_flags",
    "poll_all_creeps",
])

# TODO: A lot of these should be changed for if the room has 1 or 2 sources!
_min_work_mass_big_miner = 8  # TODO: This really should be based off of spawn extensions & work mass percentage!
_extra_work_mass_per_big_miner = 10

_min_total_pause_remote_mining = 950000
_min_energy_pause_remote_mining = 150000
_max_total_resume_remote_mining = 700000
_max_energy_resume_remote_mining = 50000
_min_work_mass_per_source_for_full_storage_use = 15

_min_energy_enable_full_storage_use = 10000
_max_energy_disable_full_storage_use = 5000
_energy_to_resume_upgrading = 14000
_energy_to_pause_upgrading = 8000
_energy_to_pause_building = 14000
_energy_to_resume_building = 28000
_min_stored_energy_to_draw_from_before_refilling = 20000

# 0 is rcl 1
_rcl_to_sane_wall_hits = [100, 1000, 10 * 1000, 100 * 1000, 400 * 1000, 600 * 1000, 1000 * 1000, 10 * 1000 * 1000]
_rcl_to_min_wall_hits = [100, 1000, 5 * 1000, 50 * 1000, 200 * 1000, 500 * 1000, 800 * 1000, 1000 * 1000]


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
    :type links: LinkingMind
    :type mining: MiningMind
    :type subsidiaries: list[RoomMind]
    :type sources: list[Source]
    :type creeps: list[Creep]
    :type work_mass: int
    :type are_all_big_miners_placed: bool
    :type trying_to_get_full_storage_use: bool
    :type full_storage_use: bool
    :type max_sane_wall_hits: int
    :type min_sane_wall_hits: int
    """

    def __init__(self, hive_mind, room):
        self.hive_mind = hive_mind
        self.room = room
        self.my = room.controller and room.controller.my
        if self.my:
            self.building = ConstructionMind(self)
            self.links = LinkingMind(self)
            self.mining = MiningMind(self)
            self.minerals = MineralMind(self)
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
        self._target_remote_hauler_carry_mass = None
        self._first_target_remote_reserve_count = None
        self._target_remote_reserve_count = None
        self._target_local_hauler_carry_mass = None
        self._target_link_managers = None
        self._target_cleanup_mass = None
        self._target_defender_count = None
        self._first_simple_target_defender_count = None
        self._first_target_cleanup_mass = None
        self._target_colonist_work_mass = None
        self._target_mineral_steal_mass = None
        self._target_simple_claim_count = None
        self._target_room_reserve_count = None
        self._target_spawn_fill_mass = None
        self._target_td_healer_count = None
        self._target_td_goader_count = None
        self._target_simple_dismantler_count = None
        self._target_remote_hauler_count = None
        self._total_needed_spawn_fill_mass = None
        self._builder_use_first_only = False
        self._max_sane_wall_hits = None
        self._conducting_siege = None
        self._spawns = None
        # source keeper rooms are hostile
        self.hostile = not room.controller or (room.controller.owner and not room.controller.my)
        if room.controller and room.controller.owner and not room.controller.my:
            if not Memory.enemy_rooms:
                Memory.enemy_rooms = []
            if room.name not in Memory.enemy_rooms:
                Memory.enemy_rooms.push(room.name)
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
            if self.mem.cache[name].ttl_after_use:
                self.mem.cache[name].last_used = Game.time
            return self.mem.cache[name].value
        else:
            return None

    def store_cached_property(self, name, value, ttl, use_ttl=None):
        if not self.mem.cache:
            self.mem.cache = {}
        self.mem.cache[name] = {"value": value, "dead_at": Game.time + ttl}
        if use_ttl:
            self.mem.cache[name].ttl_after_use = use_ttl
            self.mem.cache[name].last_used = Game.time

    def store_cached_property_at(self, name, value, dead_at):
        if not self.mem.cache:
            self.mem.cache = {}
        self.mem.cache[name] = {"value": value, "dead_at": dead_at}

    def find(self, parameter):
        cache = volatile_cache.mem(self.room_name)
        if cache.has(parameter):
            return cache.get(parameter)
        else:
            # this is patched in here because we pretty much never want to find hostile creeps besides like this:
            if parameter == FIND_HOSTILE_CREEPS and len(Memory.meta.friends):
                result = self.room.find(FIND_HOSTILE_CREEPS, {
                    "filter": lambda c: c.owner.username not in Memory.meta.friends
                })
            elif parameter == PYFIND_REPAIRABLE_ROADS:
                result = _.filter(self.find(FIND_STRUCTURES),
                                  lambda s:
                                  (
                                      (s.structureType == STRUCTURE_ROAD
                                       and not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_ROAD))
                                      or (s.structureType == STRUCTURE_CONTAINER and
                                          not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_CONTAINER))
                                  ) and s.hits < s.hitsMax)
            elif parameter == PYFIND_BUILDABLE_ROADS:
                result = _.filter(self.find(FIND_MY_CONSTRUCTION_SITES),
                                  lambda s:
                                  (
                                      s.structureType == STRUCTURE_ROAD
                                      and not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                                  ) or (
                                      s.structureType == STRUCTURE_CONTAINER
                                      and not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_CONTAINER))
                                  )
            else:
                result = self.room.find(parameter)
            cache.set(parameter, result)
            return result

    def find_at(self, find_type, pos, optional_y=None):
        """
        Looks for something at a position, and caches the result for this tick.

        This is meant as a drop-in replacement for pos.lookFor() or room.lookForAt().
        :param find_type: thing to look for, one of the FIND_* constants
        :type find_type: str
        :param pos: The position to look for at, or the x value of a position
        :type pos: int | RoomPosition
        :param optional_y: The y value of the position. If this is specified, `pos` is treated as the x value, not as a
                           whole position
        :type optional_y: int | None
        :return: A list of results
        :rtype: list[RoomObject]
        """
        x, y, room_name = parse_xy_arguments(pos, optional_y)
        if room_name is not None and room_name != self.room_name:
            room = self.hive_mind.get_room(room_name)
            if room:
                return room.find_at(find_type, x, y)
            else:
                return []
        raw_find_results = self.find(find_type)
        found = []
        if len(raw_find_results):
            for element in raw_find_results:
                if element.pos.x == x and element.pos.y == y:
                    found.append(element)
        return found

    def find_in_range(self, find_type, find_range, pos, optional_y=None):
        """
        Looks for something near a position, and caches the result for this tick.

        This is meant as a drop-in replacement for pos.findInRange().

        Note that this performs a search using "rectangular range", or everything whose x and y are within range of the center
         x and y, while the default findInRange() function uses a circular range, where the positions are compared using actual
         distance.

        :param find_type: thing to look for, one of the FIND_* constants
        :type find_type: str
        :param find_range: the integer range to look within
        :type find_range: int
        :param pos: The position to look for at, or the x value of a position
        :type pos: int | RoomPosition
        :param optional_y: The y value of the position. If this is specified, `pos` is treated as the x value, not as a whole position
        :type optional_y: int | None
        :return: A list of results
        :rtype: list[RoomObject]
        """
        x, y, room_name = parse_xy_arguments(pos, optional_y)
        if room_name is not None and room_name != self.room_name:
            room = self.hive_mind.get_room(pos.roomName)
            if room:
                return room.find_in_range(find_type, find_range, x, y)
            else:
                return []
        raw_find_results = self.find(find_type)
        found = []
        if len(raw_find_results):
            for element in raw_find_results:
                if abs(element.pos.x - x) <= find_range and abs(element.pos.y - y) <= find_range:
                    found.append(element)
        return found

    def find_closest_by_range(self, find_type, pos, lodash_filter=None):
        """
        Looks for something in this room closest the the given position, and caches the result for this tick.

        This is meant as a drop-in replacement for pos.findClosestByRange()

        :param find_type: thing to look for, one of the FIND_* constants
        :type find_type: str
        :param pos: The position to look for at
        :type pos: RoomPosition
        :param lodash_filter: Optional lodash filter object to apply to the results before checking distance.
        :type lodash_filter: dict | callable
        :return: A single result
        :rtype: RoomObject
        """
        if pos.pos:
            pos = pos.pos
        raw_find_results = self.find(find_type)
        if lodash_filter:
            raw_find_results = _.filter(raw_find_results, lodash_filter)
        if not len(raw_find_results):
            return None
        closest_distance = Infinity
        closest_element = None
        for element in raw_find_results:
            distance = movement.distance_squared_room_pos(pos, element.pos)
            if distance < closest_distance:
                closest_element = element
                closest_distance = distance
        return closest_element

    def _get_role_counts(self):
        if not self.mem.roles_alive:
            self.recalculate_roles_alive()
        return self.mem.roles_alive

    role_counts = property(_get_role_counts)

    def _get_work_mass(self):
        if not self.mem.roles_work:
            self.recalculate_roles_alive()
        return self.mem.roles_work

    work_mass_map = property(_get_work_mass)

    def _get_carry_mass(self):
        if not self.mem.roles_carry:
            self.recalculate_roles_alive()
        return self.mem.roles_carry

    carry_mass_map = property(_get_carry_mass)

    def _get_remote_mining_operations(self):
        if self._remote_mining_operations is None:
            self.hive_mind.poll_remote_mining_flags()
        return self._remote_mining_operations

    possible_remote_mining_operations = property(_get_remote_mining_operations)

    def paving(self):
        paving = self.get_cached_property("paving_here")
        if paving is None:
            if self.my:
                # TODO: 2 maybe should be a constant?
                paving = self.full_storage_use and self.get_max_mining_op_count() >= 1 \
                         and len(self.mining.available_mines) >= 1
            else:
                paving = False
                for flag in flags.find_flags(self, flags.REMOTE_MINE):
                    if flag.memory.sponsor and flag.memory.remote_miner_targeting:
                        # if we're a remote mine and our sponsor is paving, let's also pave.
                        sponsor = self.hive_mind.get_room(flag.memory.sponsor)
                        if sponsor and sponsor.paving():
                            paving = True
                            break
            self.store_cached_property("paving_here", paving, 200)

        return self.get_cached_property("paving_here")

    def all_paved(self):
        paved = self.get_cached_property("completely_paved")
        if paved is not None:
            return paved

        paved = True
        unreachable_rooms = False
        if not _.find(self.find(FIND_STRUCTURES), {"structureType": STRUCTURE_ROAD}):
            paved = False  # no roads
        elif len(self.find(PYFIND_BUILDABLE_ROADS)) > len(_.filter(self.find(FIND_STRUCTURES),
                                                                   {"structureType": STRUCTURE_ROAD})):
            paved = False  # still paving
        elif self.my:
            for flag in self.mining.active_mines:
                room = self.hive_mind.get_room(flag.pos.roomName)
                if room:
                    if not room.all_paved():
                        paved = False
                        break
                else:
                    unreachable_rooms = True  # Cache for less time
        # TODO: better remote mine-specific paving detection, so we can disable this shortcut
        if not paved and self.paving():
            paved = True
        if paved:
            if unreachable_rooms:
                self.store_cached_property("completely_paved", paved, 50)
            else:
                self.store_cached_property("completely_paved", paved, 200)
        else:

            self.store_cached_property("completely_paved", paved, 20)
        return paved

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

    def carry_mass_of(self, role):
        mass = self.carry_mass_map[role]
        if mass:
            return mass
        else:
            return 0

    def work_mass_of(self, role):
        mass = self.work_mass_map[role]
        if mass:
            return mass
        else:
            return 0

    def register_to_role(self, creep):
        """
        Registers the creep's role and time till replacement in permanent memory. Should only be called once per creep.
        """
        if not isinstance(creep, RoleBase):
            creep = creep_wrappers.wrap_creep(self.hive_mind, self.hive_mind.target_mind, self, creep)
        role = creep.memory.role
        if role in self.role_counts:
            self.role_counts[role] += 1
        else:
            self.role_counts[role] = 1
        if role in self.carry_mass_map:
            self.carry_mass_map[role] += spawning.carry_count(creep)
        else:
            self.carry_mass_map[role] = spawning.carry_count(creep)
        if role in self.work_mass_map:
            self.work_mass_map[role] += spawning.work_count(creep)
        else:
            self.work_mass_map[role] = spawning.work_count(creep)
        rt_map = self._get_rt_map()
        rt_pair = [creep.name, creep.get_replacement_time()]
        if not rt_map[role]:
            rt_map[role] = [rt_pair]
        else:
            # _.sortedIndex(array, value, [iteratee=_.identity])
            # Lodash version is 3.10.0 - this was replaced by sortedIndexBy in 4.0.0
            rt_map[role].splice(_.sortedIndex(rt_map[role], rt_pair, lambda p: p[1]), 0, rt_pair)

    def recalculate_roles_alive(self):
        """
        Forcibly recalculates the current roles in the room. If everything's working correctly, this method should have
        no effect. However, it is useful to run this method frequently, for if memory becomes corrupted or a bug is
        introduced, this can ensure that everything is entirely correct.
        """
        # print("[{}] Recalculating roles alive.".format(self.room_name))
        # old_rt_map = self.mem.rt_map
        roles_alive = {}
        roles_work = {}  # TODO: better system for storing these
        roles_carry = {}
        rt_map = {}

        for creep in self.creeps:
            role = creep.memory.role
            if not role:
                continue
            if role not in roles_alive:
                roles_alive[role] = 1
            else:
                roles_alive[role] += 1
            if role not in roles_work:
                roles_work[role] = spawning.work_count(creep)
            else:
                roles_work[role] += spawning.work_count(creep)
            if role not in roles_carry:
                roles_carry[role] = spawning.carry_count(creep)
            else:
                roles_carry[role] += spawning.carry_count(creep)

            if creep.spawning or creep.memory.role == role_temporary_replacing:
                continue  # don't add rt_pairs for spawning creeps
            creep = creep_wrappers.wrap_creep(self.hive_mind, self.hive_mind.target_mind, self, creep)

            rt_pair = (creep.name, creep.get_replacement_time())
            if not rt_map[role]:
                rt_map[role] = [rt_pair]
            else:
                # _.sortedIndex(array, value, [iteratee=_.identity])
                # Lodash version is 3.10.0 - this was replaced by sortedIndexBy in 4.0.0
                rt_map[role].splice(_.sortedIndex(rt_map[role], rt_pair, lambda p: p[1]), 0, rt_pair)
        self.mem.roles_alive = roles_alive
        self.mem.roles_work = roles_work
        self.mem.roles_carry = roles_carry
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
        key = "next_{}_to_die_{}".format(x, role)
        result = self.get_cached_property(key)
        if result:
            return result
        result = []
        rt_map = self._get_rt_map()
        if role in rt_map and len(rt_map[role]):
            for rt_pair in rt_map[role]:
                result.append(rt_pair[0])
                if len(result) >= x:
                    break
        self.store_cached_property_at(key, result, self.mem.meta.clear_next)
        return result

    def extra_creeps_with_carry_in_role(self, role, target_carry_mass):
        """
        Gets a list of extra creep names who are in the given role, given that the target is target_carry_mass
        :param role: The role
        :param target_carry_mass: The desired carry mass
        :return: Creeps who should be switched to a different role
        :type role: str
        :type target_carry_mass: int
        :rtype: list[str]
        """
        key = "ecc_{}".format(role)
        result = self.get_cached_property(key)
        if result:
            return result
        current = self.carry_mass_of(role)
        left_to_remove = current - target_carry_mass
        result = []
        if left_to_remove < 0:
            return result
        rt_map = self._get_rt_map()
        if role in rt_map:
            for name, rt in rt_map[role]:
                if name not in Game.creeps:
                    continue
                carry = spawning.carry_count(Game.creeps[name])
                if carry > left_to_remove:
                    # We don't want to go below the target, but there might be a smaller creep we can remove?
                    continue
                left_to_remove -= carry
                result.append(name)
        if self.mem.meta.clear_next - Game.time < 19:
            self.store_cached_property_at(key, result, self.mem.meta.clear_next)
        else:
            self.store_cached_property(key, result, 19)
        return result

    def extra_creeps_with_work_in_role(self, role, target_work_mass):
        """
        Gets a list of extra creep names who are in the given role, given that the target is target_work_mass
        :param role: The role
        :param target_work_mass: The desired work mass
        :return: Creeps who should be switched to a different role
        :type role: str
        :type target_work_mass: int
        :rtype: list[str]
        """
        key = "ecw_{}".format(role)
        result = self.get_cached_property(key)
        if result:
            return result
        current = self.work_mass_of(role)
        left_to_remove = current - target_work_mass
        result = []
        if left_to_remove < 0:
            return result
        rt_map = self._get_rt_map()
        if role in rt_map:
            for name, rt in rt_map[role]:
                if name not in Game.creeps:
                    continue
                work = spawning.work_count(Game.creeps[name])
                if work > left_to_remove:
                    # We don't want to go below the target, but there might be a smaller creep we can remove?
                    continue
                left_to_remove -= work
                result.append(name)
        if self.mem.meta.clear_next - Game.time < 19:
            self.store_cached_property_at(key, result, self.mem.meta.clear_next)
        else:
            self.store_cached_property(key, result, 19)
        return result

    def register_new_replacing_creep(self, replaced_name, replacing_name):
        # print("[{}][{}] Registering as replacement for {} (a {}).".format(self.room_name, replacing_name,
        #                                                                   replaced_name, role))
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
                if Game.creeps[creep] and not Memory.creeps[creep].replacement and replacement_time <= Game.time:
                    count += 1
        return count

    def count_noneol_creeps_targeting(self, target_type, target_id):
        """
        Gets the number of non-end-of-life creeps with the specified target_id as their target_type target in
        TargetMind.
        :param target_type: The type of the target to search for
        :param target_id: The target ID to search for
        :return: The number of creeps targeting the given target for which creep.replacement_time() <= Game.time
        """
        # TODO: eventually, restructure memory so this becomes one of the most efficient operations:
        # Memory is currently saved so as to make replacements_currently_needed_for() an efficient operation.
        # It's currently called more than this function, but more spawning code should eventually switch to using
        # this one.
        count = 0
        targeters = self.hive_mind.target_mind.creeps_now_targeting(target_type, target_id)
        for name in targeters:
            creep = Game.creeps[name]
            if creep and Game.time < live_creep_utils.replacement_time(creep):
                count += 1
        return count

    def carry_mass_of_replacements_currently_needed_for(self, role):
        mass = 0
        rt_map = self._get_rt_map()
        if role in rt_map and len(rt_map[role]):
            for creep, replacement_time in rt_map[role]:
                if Game.creeps[creep] and not Memory.creeps[creep].replacement and replacement_time <= Game.time:
                    mass += spawning.carry_count(Game.creeps[creep])
                else:
                    break  # this is sorted
        return mass

    def work_mass_of_replacements_currently_needed_for(self, role):
        mass = 0
        rt_map = self._get_rt_map()
        if role in rt_map and len(rt_map[role]):
            for creep, replacement_time in rt_map[role]:
                if Game.creeps[creep] and not Memory.creeps[creep].replacement and replacement_time <= Game.time:
                    mass += spawning.work_count(Game.creeps[creep])
                else:
                    break  # this is sorted
        return mass

    def precreep_tick_actions(self):
        time = Game.time
        meta = self.mem.meta
        if not meta:
            meta = {"clear_next": 0, "reset_spawn_on": 0}
            self.mem.meta = meta

        if time > meta.clear_next:
            # print("[{}] Clearing memory".format(self.room_name))
            consistency.clear_memory(self)
            self.recalculate_roles_alive()
            # Recalculate spawning - either because a creep death just triggered our clearing memory, or we haven't
            # recalculated in the last 500 ticks.
            # TODO: do we really need to recalculate every 500 ticks? even though it really isn't expensive
            self.reset_planned_role()
            del meta.clear_now
            # print("[{}] Next clear in {} ticks.".format(self.room_name, meta.clear_next - Game.time))

        # reset_spawn_on is set to the tick after the next creep's TTR expires in consistency.clear_memory()
        if time > meta.reset_spawn_on:
            self.reset_planned_role()
            meta.reset_spawn_on = meta.clear_next + 1

        # TODO: this will make both rooms do it at the same time, but this is better than checking every time memory is
        # cleared! Actually, it's quite cheap.
        if Game.time % 10 == 0:
            self.reassign_roles()

    def reassign_roles(self):
        return consistency.reassign_room_roles(self)

    def poll_hostiles(self):
        if not Memory.hostiles:
            Memory.hostiles = []
        if not Memory.hostile_last_rooms:
            Memory.hostile_last_rooms = {}
        if not Memory.hostile_last_positions:
            Memory.hostile_last_positions = {}

        sk_room = False
        if self.hostile:
            if self.room.controller:
                return  # don't find hostile creeps in other players rooms... that's like, not a great plan...
            else:
                sk_room = True

        remove = None
        for hostile_id, hostile_room, pos, owner, dead_at in Memory.hostiles:
            if (hostile_room == self.room_name and not Game.getObjectById(hostile_id)) \
                    or (not dead_at or Game.time > dead_at):
                if remove:
                    remove.append(hostile_id)
                else:
                    remove = [hostile_id]
        if remove:
            for hostile_id in remove:
                military.delete_target(hostile_id)
        new_hostiles = False
        targets = self.find(FIND_HOSTILE_CREEPS)
        for hostile in targets:
            if sk_room and hostile.owner.username != INVADER_USERNAME and \
                    (hostile.owner.username == SK_USERNAME or
                         (hostile.getActiveBodyparts(ATTACK) == 0 and hostile.getActiveBodyparts(RANGED_ATTACK) == 0)):
                continue
            # TODO: overhaul hostile info storage
            hostile_list = _.find(Memory.hostiles, lambda t: t[0] == hostile.id and t[1] == self.room_name)
            if hostile_list:
                hostile_list[2] = hostile.pos  # this is the only thing which would update
            else:
                Memory.hostiles.push([hostile.id, self.room_name, hostile.pos, hostile.owner.username,
                                      Game.time + hostile.ticksToLive + 1])
                Memory.hostile_last_rooms[hostile.id] = self.room_name
                new_hostiles = True
            Memory.hostile_last_positions[hostile.id] = hostile.pos
        if new_hostiles:
            if self.my:
                self.reset_planned_role()
            else:
                mining_flags = flags.find_flags(self, flags.REMOTE_MINE)
                for flag in mining_flags:
                    room = self.hive_mind.get_room(flag.memory.sponsor)
                    if room:
                        room.reset_planned_role()

    def get_name(self):
        return self.room.name

    def get_position(self):
        if self._position is None:
            self._position = movement.parse_room_to_xy(self.room.name)
        return self._position

    def get_sources(self):
        if self._sources is None:
            self._sources = self.find(FIND_SOURCES)
        return self._sources

    def get_spawns(self):
        if self._spawns is None:
            self._spawns = self.find(FIND_MY_SPAWNS)
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
            self._trying_to_get_full_storage_use = self.are_all_big_miners_placed and self.room.storage \
                                                   and (self.work_mass >=
                                                        _min_work_mass_per_source_for_full_storage_use
                                                        * len(self.sources)
                                                        or self.room.storage.store[RESOURCE_ENERGY]
                                                        >= _min_stored_energy_to_draw_from_before_refilling)
        return self._trying_to_get_full_storage_use

    def get_full_storage_use(self):
        """
        :rtype: bool
        """
        if self._full_storage_use is None:
            if self.room.storage and (self.room.storage.store[RESOURCE_ENERGY]
                                          >= _min_stored_energy_to_draw_from_before_refilling or
                                          (not self.spawn and self.room.storage.store[RESOURCE_ENERGY] > 0)):
                self._full_storage_use = True
                self.mem.full_storage_use = True
            else:
                if self.trying_to_get_full_storage_use:
                    if self.mem.full_storage_use and self.room.storage.store[RESOURCE_ENERGY] \
                            <= _max_energy_disable_full_storage_use:
                        print("[{}] Disabling full storage use.".format(self.room_name))
                        self.mem.full_storage_use = False
                    if not self.mem.full_storage_use and self.room.storage.store[RESOURCE_ENERGY] \
                            > _min_energy_enable_full_storage_use:
                        print("[{}] Enabling full storage use.".format(self.room_name))
                        self.mem.full_storage_use = True
                    self._full_storage_use = self.mem.full_storage_use
                else:
                    self._full_storage_use = False
        return self._full_storage_use

    def mining_ops_paused(self):
        if not self.full_storage_use:
            return False
        if self.mem.focusing_home and _.sum(self.room.storage.store) < _max_total_resume_remote_mining \
                or self.room.storage.store.energy < _max_energy_resume_remote_mining:
            self.mem.focusing_home = False
        if not self.mem.focusing_home and _.sum(self.room.storage.store) > _min_total_pause_remote_mining \
                and self.room.storage.store.energy > _min_energy_pause_remote_mining:
            self.mem.focusing_home = True
        return not not self.mem.focusing_home

    def upgrading_paused(self):
        if self.room.controller.level < 4 or not self.room.storage or self.room.storage.storeCapacity <= 0:
            return False
        # TODO: constant here and below in upgrader_work_mass
        if self.conducting_siege() and self.room.storage.store.energy < 700000:
            return True  # Don't upgrade while we're taking someone down.
        if self.mem.upgrading_paused and self.room.storage.store.energy > _energy_to_resume_upgrading:
            self.mem.upgrading_paused = False
        if not self.mem.upgrading_paused and self.room.storage.store.energy < _energy_to_pause_upgrading:
            self.mem.upgrading_paused = True
        return not not self.mem.upgrading_paused

    def building_paused(self):
        if self.room.controller.level < 4 or not self.room.storage or self.room.storage.storeCapacity <= 0:
            return False
        if self.conducting_siege():
            return True  # Don't build while we're taking someone down.
        if self.mem.building_paused and self.room.storage.store.energy > _energy_to_resume_building:
            self.mem.building_paused = False
        if not self.mem.building_paused and self.room.storage.store.energy < _energy_to_pause_building:
            self.mem.building_paused = True
        if self.mem.building_paused:
            # this is somewhat expensive, so do this calculation last
            # If building is paused and we have fewer spawns/extensions than spawn/extension build sites, don't pause
            # building!
            return self.spawn and (len(_.filter(self.find(FIND_MY_STRUCTURES),
                                                lambda s: s.structureType == STRUCTURE_SPAWN or
                                                          s.structureType == STRUCTURE_EXTENSION))
                                   > len(_.filter(self.find(FIND_MY_CONSTRUCTION_SITES),
                                                  lambda s: s.structureType == STRUCTURE_SPAWN or
                                                            s.structureType == STRUCTURE_EXTENSION)))
        else:
            return False

    def _any_closest_to_me(self, flag_type):
        return _.find(
            flags.find_flags_global(flag_type),
            lambda f: self.hive_mind.get_closest_owned_room(f.pos.roomName).room_name == self.room_name
        )

    def conducting_siege(self):
        if self._conducting_siege is None:
            self._conducting_siege = Game.cpu.bucket > 4200 and not not (
                self._any_closest_to_me(flags.ATTACK_DISMANTLE)
                or (
                    (self._any_closest_to_me(flags.TD_D_GOAD) or self._any_closest_to_me(flags.ATTACK_POWER_BANK))
                    and self._any_closest_to_me(flags.TD_H_H_STOP)
                    and self._any_closest_to_me(flags.TD_H_D_STOP)
                )
            )
        return self._conducting_siege

    def get_max_mining_op_count(self):
        if not self.my:
            print("[{}] WARNING: get_max_mining_op_count called for non-owned room!".format(self.room_name))
            return 0
        spawning_energy = self.room.energyCapacityAvailable
        sources = len(self.sources)
        rcl = self.room.controller.level

        if sources <= 1:
            min_wm = 25
            extra_wm = 10
            min_energy = 550  # rcl 2, fully built
            min_rcl = 2
            extra_rcl = 0
            if rcl < 7:
                max_via_rcl2 = 3
            elif rcl == 7:
                max_via_rcl2 = 4
            else:
                max_via_rcl2 = 2
        else:
            min_wm = 40  # Around all roles built needed for an rcl 3 room!
            extra_wm = 10
            min_energy = 800  # rcl 3, fully built
            min_rcl = 3
            extra_rcl = 1
            if rcl < 7:
                max_via_rcl2 = 2
            elif rcl == 7:
                max_via_rcl2 = 3
            else:
                max_via_rcl2 = 1

        if self.work_mass < min_wm:
            max_via_wm = 0
        else:
            max_via_wm = math.floor((self.work_mass - min_wm) / extra_wm) + 1
        if spawning_energy < min_energy:
            max_via_energy = 0
        else:
            max_via_energy = Infinity
        if rcl < min_rcl:
            max_via_rcl = 0
        else:
            max_via_rcl = math.floor((rcl - min_rcl) / extra_rcl) + 1

        return min(max_via_wm, max_via_energy, max_via_rcl, max_via_rcl2)

    def get_max_local_miner_count(self):
        spawning_energy = self.room.energyCapacityAvailable
        sources = len(self.sources)

        min_energy = 550  # rcl 2, fully built
        if sources <= 1:
            min_wm = 7
            extra_wm = 10
        else:
            min_wm = 15
            extra_wm = 10

        if self.full_storage_use:  # Just make them anyways, it'll be fine - we have stored energy.
            max_via_wm = Infinity
        elif self.work_mass < min_wm:
            max_via_wm = 0
        else:
            max_via_wm = math.floor((self.work_mass - min_wm) / extra_wm) + 1
        if spawning_energy < min_energy:
            max_via_energy = 0
        else:
            max_via_energy = Infinity
        return min(max_via_wm, max_via_energy)

    def get_max_sane_wall_hits(self):
        """
        :rtype: int
        """
        return _rcl_to_sane_wall_hits[self.room.controller.level - 1]  # 1-to-0-based index

    def get_min_sane_wall_hits(self):
        return _rcl_to_min_wall_hits[self.room.controller.level - 1]  # 1-to-0 based index

    def get_target_local_miner_count(self):
        """
        :rtype: int
        """
        if self._ideal_big_miner_count is None:
            miner_count = self.get_max_local_miner_count()
            if miner_count > 0:
                self._ideal_big_miner_count = min(len(self.sources), miner_count)
            else:
                self._ideal_big_miner_count = 0
        return self._ideal_big_miner_count

    def get_target_local_hauler_mass(self):
        """
        :rtype: int
        """
        # TODO: Merge local and remote hauler spawning!
        if self._target_local_hauler_carry_mass is None:
            if self.trying_to_get_full_storage_use:
                carry_max_6 = max(3, min(6, spawning.max_sections_of(self, creep_base_hauler)))
                total_mass = math.ceil(self.get_target_local_miner_count() * 2 * carry_max_6)
                for source in self.sources:
                    energy = _.sum(self.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount')
                    total_mass += energy / 200.0
                self._target_local_hauler_carry_mass = math.floor(total_mass)
            else:
                self._target_local_hauler_carry_mass = 0
        return self._target_local_hauler_carry_mass

    def get_target_link_manager_count(self):
        """
        :rtype: int
        """
        if self._target_link_managers is None:
            links = 0
            for s in self.find(FIND_STRUCTURES):
                if s.structureType == STRUCTURE_LINK:
                    links += 1
            if links >= 2 and self.trying_to_get_full_storage_use:
                self._target_link_managers = 1
            else:
                self._target_link_managers = 0
        return self._target_link_managers

    def get_target_cleanup_mass(self):
        """
        :rtype: int
        """
        return 0

    def get_target_simple_defender_count(self, first=False):
        """
        :rtype: int
        """
        if (self._first_simple_target_defender_count if first else self._target_defender_count) is None:
            hostile_count = 0
            room_mine_to_protect = {}
            if Memory.hostiles:
                for hostile_id, hostile_room, hostile_pos, hostile_owner in Memory.hostiles:
                    if hostile_owner == INVADER_USERNAME:  # TODO: ranged defenders to go against player attackers!
                        if hostile_room not in room_mine_to_protect:
                            room = self.hive_mind.get_room(hostile_room)
                            closest_owned_room = self.hive_mind.get_closest_owned_room(hostile_room)
                            if (not first or (room and hostile_room == self.room_name)) \
                                    and closest_owned_room.room_name == self.room_name \
                                    and (hostile_room != self.room_name or self.mem.alert_for > 20):
                                room_mine_to_protect[hostile_room] = True
                            else:
                                room_mine_to_protect[hostile_room] = False
                        if room_mine_to_protect[hostile_room]:
                            hostile_count += 1
            if first:
                self._first_simple_target_defender_count = hostile_count
            else:
                self._target_defender_count = hostile_count
        return self._first_simple_target_defender_count if first else self._target_defender_count

    def get_target_colonist_work_mass(self):
        worker_mass = spawning.max_sections_of(self, creep_base_worker)
        hauler_mass = spawning.max_sections_of(self, creep_base_half_move_hauler)
        if not self._target_colonist_work_mass:
            needed = 0
            mineral_steal = 0
            for room in self.subsidiaries:
                room_work_mass = 0
                for role in Object.keys(room.work_mass_map):
                    room_work_mass += room.work_mass_map[role] \
                                      - room.work_mass_of_replacements_currently_needed_for(role)
                needed += max(0, worker_mass * 3 - room_work_mass)
                if room.room.storage and _.sum(room.room.storage.store) > room.room.storage.store.energy \
                        and room.room.storage.storeCapacity <= 0:
                    mineral_steal += hauler_mass
            self._target_colonist_work_mass = needed
            self._target_mineral_steal_mass = mineral_steal
        return self._target_colonist_work_mass

    def get_target_mineral_steal_mass(self):
        if not self._target_mineral_steal_mass:
            self.get_target_colonist_work_mass()
        return self._target_mineral_steal_mass

    def get_target_spawn_fill_backup_work_mass(self):
        work_max_5 = max(3, min(5, spawning.max_sections_of(self, creep_base_worker)))
        # TODO: 7 should be a constant.
        if self.full_storage_use or self.are_all_big_miners_placed or self.work_mass > 8:
            if self.full_storage_use and (self.are_all_big_miners_placed or self.work_mass > 25):
                return 0
            else:
                return 1 * work_max_5
        else:
            return (2 + len(self.sources)) * work_max_5

    def get_target_spawn_fill_mass(self):
        if self._target_spawn_fill_mass is None:
            if self.get_target_local_miner_count():
                # spawn_fill_backup = self.carry_mass_of(role_spawn_fill_backup)
                tower_fill = self.carry_mass_of(role_tower_fill)
                # Enough so that it takes only 4 trips for each creep to fill all extensions.
                total_mass = math.ceil(self.get_target_total_spawn_fill_mass())
                # Spawn fill backup used to be here, but they now completely shift to builders once all spawn fill have been created.
                regular_count = max(0, total_mass - tower_fill)
                if self.trying_to_get_full_storage_use or self.full_storage_use:
                    self._target_spawn_fill_mass = regular_count
                else:
                    extra_count = 0
                    for source in self.sources:
                        energy = _.sum(self.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount')
                        extra_count += energy / 200.0
                    self._target_spawn_fill_mass = math.ceil(regular_count + extra_count)
            else:
                self._target_spawn_fill_mass = 0
        return self._target_spawn_fill_mass

    def get_target_total_spawn_fill_mass(self):
        if self._total_needed_spawn_fill_mass is None:
            if self.get_target_local_miner_count():
                self._total_needed_spawn_fill_mass = math.pow(self.room.energyCapacityAvailable / 50.0 * 200, 0.3)
            else:
                self._total_needed_spawn_fill_mass = 0
        return self._total_needed_spawn_fill_mass

    def get_target_builder_work_mass(self):
        no_repair_above = self.max_sane_wall_hits * 0.8

        def not_road(id):
            thing = Game.getObjectById(id)
            return thing is not None and thing.structureType != STRUCTURE_ROAD

        def is_relatively_decayed(id):
            thing = Game.getObjectById(id)
            return thing is not None and thing.hits <= thing.hitsMax * 0.6 and thing.hits <= no_repair_above

        worker_size = max(3, min(8, spawning.max_sections_of(self, creep_base_worker)))
        if not self.building_paused():
            total = _.sum(self.building.next_priority_construction_targets(), not_road) \
                    + _.sum(self.building.next_priority_repair_targets(), is_relatively_decayed)
            if total > 0:
                if total < 4:
                    return worker_size
                elif total < 12:
                    return 2 * worker_size
                else:
                    return 3 * worker_size
            else:
                total = _.sum(self.building.next_priority_big_repair_targets(), is_relatively_decayed)
                if total > 0:
                    return worker_size
        return 0

    def get_target_upgrader_work_mass(self):
        base = self.get_variable_base(role_upgrader)
        if base is creep_base_full_upgrader:
            worker_size = max(2, spawning.max_sections_of(self, base)) * 2
        else:
            worker_size = max(1, spawning.max_sections_of(self, base))

        if self.upgrading_paused():
            wm = 1
        elif self.mining_ops_paused():
            wm = worker_size * 4
        else:
            wm = min(self.room.controller.level, worker_size)
        if self.full_storage_use:
            if Memory.hyper_upgrade:
                extra = min(_.sum(self.room.storage.store) - 100000, self.room.storage.store.energy - 50000)
            else:
                extra = min(_.sum(self.room.storage.store) - 700000, self.room.storage.store.energy - 150000)
            if extra > 0:
                if Memory.hyper_upgrade:
                    wm += math.ceil(extra / 1000)
                else:
                    wm += math.floor(extra / 2000)
                if extra >= 200000:
                    wm += math.ceil((extra - 200000) / 400)
                    print("[{}] Spawning more emergency upgraders! Target work mass: {} (worker_size: {})"
                          .format(self.room_name, wm, worker_size))

        return min(wm, worker_size * 6)

    def get_target_tower_fill_mass(self):
        if not self.get_target_spawn_fill_mass():
            return 0
        mass = 0
        for s in self.find(FIND_STRUCTURES):
            if s.structureType == STRUCTURE_TOWER:
                # TODO: cache max_parts_on? called a ton in this method and other get_target_*_mass methods.
                # but we probably shouldn't since it's mostly a hack to emulate spawning 5-section creeps anyways?
                mass += max(1, min(5, spawning.max_sections_of(self, creep_base_hauler))) * 0.75
        return math.ceil(mass)

    def get_target_simple_claim_count(self):
        if self._target_simple_claim_count is None:
            count = 0
            for flag in flags.find_flags_global(flags.CLAIM_LATER):
                room = self.hive_mind.get_room(flag.pos.roomName)
                if not room or (not room.my and not room.room.controller.owner):
                    if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name != self.room_name:
                        # there's a closer room, let's not claim here.
                        continue
                    count += 1
            self._target_simple_claim_count = count
        return self._target_simple_claim_count

    def get_target_room_reserve_count(self):
        if self._target_room_reserve_count is None:
            count = 0
            if self.room.energyCapacityAvailable >= 650:
                for flag in flags.find_flags_global(flags.RESERVE_NOW):
                    room_name = flag.pos.roomName
                    room = Game.rooms[room_name]
                    if not room or (room.controller and not room.controller.my and not room.controller.owner):
                        # TODO: save in memory and predict the time length this room is reserved, and only send out a
                        # reserve creep for <3000 ticks reserved.
                        if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name != self.room_name:
                            # there's a closer room, let's not claim here.
                            continue
                        count += 1
            self._target_room_reserve_count = count
            # claimable!
        return self._target_room_reserve_count

    def get_next_spawn_fill_body_size(self):
        # Enough so that it takes only 2 trips for each creep to fill all extensions.
        total_mass = self.room.energyCapacityAvailable / 50 / 2
        return fit_num_sections(total_mass, spawning.max_sections_of(self, creep_base_hauler))

    def _next_needed_local_mining_role(self):
        requirements = [
            [role_spawn_fill_backup, self.get_target_spawn_fill_backup_work_mass, False, True],
            [role_defender, lambda: self.get_target_simple_defender_count(True)],
            [role_link_manager, self.get_target_link_manager_count],
            [role_cleanup, self.get_target_cleanup_mass, True],
            [role_dedi_miner, self.get_target_local_miner_count],
            [role_tower_fill, self.get_target_tower_fill_mass, True],
            [role_spawn_fill, self.get_target_spawn_fill_mass, True],
            [role_upgrader, lambda: self.get_target_upgrader_work_mass() if self.mining_ops_paused() else None,
             False, True],
            [role_local_hauler, self.get_target_local_hauler_mass, True],
        ]
        role_needed = None
        for role, get_ideal, count_carry, count_work in requirements:
            if count_carry:
                if self.carry_mass_of(role) - self.carry_mass_of_replacements_currently_needed_for(role) < get_ideal():
                    role_needed = role
                    break
            elif count_work:
                if self.work_mass_of(role) - self.work_mass_of_replacements_currently_needed_for(role) < get_ideal():
                    role_needed = role
                    break
            else:
                if self.role_count(role) - self.replacements_currently_needed_for(role) < get_ideal():
                    role_needed = role
                    break

        if role_needed:
            # TODO: this is all mostly a conversion of the old system to the new.
            # Ideally we'd be creating a more complete package with the above (at least for replacement name)
            return {
                "role": role_needed,
                "base": self.get_variable_base(role_needed),
                "replacing": self.get_next_replacement_name(role_needed),
                "num_sections": self.get_max_sections_for_role(role_needed),
            }
        else:
            return None

    def _next_needed_local_role(self):
        requirements = [
            [role_upgrader, self.get_target_upgrader_work_mass, False, True],
            [role_simple_claim, self.get_target_simple_claim_count],
            [role_room_reserve, self.get_target_room_reserve_count],
            # TODO: a "first" argument to this which checks energy, then do another one at the end of remote.
            [role_colonist, self.get_target_colonist_work_mass, False, True],
            [role_mineral_steal, self.get_target_mineral_steal_mass, True],
            [role_mineral_hauler, self.minerals.get_target_mineral_hauler_count],
            [role_mineral_miner, self.minerals.get_target_mineral_miner_count],
            [role_builder, self.get_target_builder_work_mass, False, True],
            [role_defender, self.get_target_simple_defender_count],
        ]
        role_needed = None
        for role, get_ideal, count_carry, count_work in requirements:
            if count_carry:
                if self.carry_mass_of(role) - self.carry_mass_of_replacements_currently_needed_for(role) < get_ideal():
                    role_needed = role
                    break
            elif count_work:
                if self.work_mass_of(role) - self.work_mass_of_replacements_currently_needed_for(role) < get_ideal():
                    role_needed = role
                    break
            else:
                if self.role_count(role) - self.replacements_currently_needed_for(role) < get_ideal():
                    role_needed = role
                    break

        if role_needed:
            # TODO: this is all mostly a conversion of the old system to the new.
            # Ideally we'd be creating a more complete package with the above (at least for replacement name)
            return {
                "role": role_needed,
                "base": self.get_variable_base(role_needed),
                "replacing": self.get_next_replacement_name(role_needed),
                "num_sections": self.get_max_sections_for_role(role_needed),
            }
        else:
            return None

    def get_max_sections_for_role(self, role):
        max_mass = {
            role_spawn_fill_backup:
                self.get_target_spawn_fill_backup_work_mass,
            role_link_manager:
                lambda: min(self.get_target_link_manager_count() * 8,
                            spawning.max_sections_of(self, creep_base_hauler)),
            role_dedi_miner:
            # Have a maximum of 3 move for local miners
                lambda: min(3, spawning.max_sections_of(self, creep_base_3000miner)),
            role_cleanup:
                lambda: math.ceil(max(self.get_target_cleanup_mass(),
                                      min(10, spawning.max_sections_of(self, creep_base_hauler)))),
            role_spawn_fill:
                lambda: fit_num_sections(self.get_target_total_spawn_fill_mass(),
                                         spawning.max_sections_of(self, creep_base_hauler), 0, 2),
            role_tower_fill:
            # Tower fillers are basically specialized spawn fillers.
                lambda: fit_num_sections(self.get_target_total_spawn_fill_mass(),
                                         spawning.max_sections_of(self, creep_base_hauler), 0, 2),
            role_local_hauler:
                lambda: fit_num_sections(math.ceil(self.get_target_local_hauler_mass() / len(self.sources)),
                                         spawning.max_sections_of(self, creep_base_hauler)),
            role_upgrader:
                lambda: min(self.get_target_upgrader_work_mass(),
                            spawning.max_sections_of(self, self.get_variable_base(role_upgrader))),
            role_defender:
                lambda: self.get_target_simple_defender_count() *
                        min(6, spawning.max_sections_of(self, creep_base_defender)),
            role_simple_claim:
                lambda: 1,
            role_room_reserve:
                lambda: min(2, spawning.max_sections_of(self, creep_base_reserving)),
            role_colonist:
                lambda: min(10, spawning.max_sections_of(self, creep_base_worker)),
            role_builder: lambda: max(3, min(8, spawning.max_sections_of(self, creep_base_worker))),
            role_mineral_miner:
                lambda: 4,  # TODO: bigger miner/haulers maybe if we get resource prioritization?
            role_mineral_hauler:  # TODO: Make this depend on distance from terminal to mineral + miner size
                lambda: spawning.max_sections_of(self, creep_base_hauler),
            role_td_goad:
                lambda: spawning.max_sections_of(self, creep_base_goader),
            role_td_healer:
                lambda: spawning.max_sections_of(self, creep_base_half_move_healer),
            role_simple_dismantle:
                lambda: spawning.max_sections_of(self, creep_base_dismantler),
        }
        if role in max_mass:
            return max_mass[role]()
        else:
            print("[{}] Can't find max section function for role {}!".format(self.room_name, role))
            return Infinity

    def get_variable_base(self, role):
        if role == role_remote_hauler:
            if self.all_paved():
                return creep_base_work_half_move_hauler
            elif self.paving():
                return creep_base_work_full_move_hauler
            else:
                return creep_base_hauler
        elif role == role_upgrader:
            if _.find(self.find_in_range(FIND_MY_STRUCTURES, 4, self.room.controller.pos),
                      lambda s: s.structureType == STRUCTURE_LINK or s.structureType == STRUCTURE_STORAGE):
                return creep_base_full_upgrader
            else:
                return creep_base_worker
        else:
            return role_bases[role]

    def _next_cheap_military_role(self):
        for flag in flags.find_flags_global(flags.SCOUT):
            if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name:
                flag_id = "flag-{}".format(flag.name)
                noneol_targeting_count = self.count_noneol_creeps_targeting(target_single_flag, flag_id)
                if noneol_targeting_count < 1:
                    print("[{}] ---------".format(self.room_name))
                    print('[{}] Spawning new scout, targeting {}.'.format(self.room_name, flag))
                    print("[{}] ---------".format(self.room_name))
                    return {
                        "role": role_scout,
                        "base": creep_base_scout,
                        "num_sections": 1,
                        "targets": [
                            [target_single_flag, flag_id],
                        ]
                    }
        return None

    def flags_without_target(self, flag_type):
        result = []  # TODO: yield
        for flag in flags.find_flags_global(flag_type):
            if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name:
                flag_id = "flag-{}".format(flag.name)
                noneol_targeting_count = self.count_noneol_creeps_targeting(target_single_flag, flag_id)
                if noneol_targeting_count < 1:
                    result.append(flag)
        return result

    def get_spawn_for_flag(self, role, half_move_base, full_move_base, flag):
        if movement.distance_squared_room_pos(self.spawn, flag) > math.pow(200, 2):
            base = full_move_base
        else:
            base = half_move_base
        return {
            "role": role,
            "base": base,
            "num_sections": spawning.max_sections_of(self, base),
            "targets": [
                [target_single_flag, "flag-{}".format(flag.name)],
            ]
        }

    def spawn_one_creep_per_flag(self, flag_type, role, half_move_base, full_move_base):
        for flag in self.flags_without_target(flag_type):
            return self.get_spawn_for_flag(role, half_move_base, full_move_base, flag)
        return None

    def _next_tower_breaker_role(self):
        if not self.conducting_siege():
            return None
        role_obj = self.spawn_one_creep_per_flag(flags.TD_H_H_STOP, role_td_healer, creep_base_half_move_healer,
                                                 creep_base_full_move_healer)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(flags.TD_D_GOAD, role_td_goad, creep_base_goader,
                                                 creep_base_full_move_goader)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(flags.ATTACK_DISMANTLE, role_simple_dismantle, creep_base_dismantler,
                                                 creep_base_full_move_dismantler)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(flags.ATTACK_POWER_BANK, role_power_attack, creep_base_power_attack,
                                                 creep_base_full_move_power_attack)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(flags.ATTACK_POWER_BANK, role_power_attack, creep_base_power_attack,
                                                 creep_base_full_move_power_attack)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(flags.REAP_POWER_BANK, role_power_cleanup, creep_base_half_move_hauler,
                                                 creep_base_hauler)
        if role_obj:
            return role_obj
        # for flag in flags.find_flags_global(flags.REAP_POWER_BANK):
        #     if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name:
        #         # TODO: don't duplicate in TargetMind
        #         room = self.hive_mind.get_room(flag.pos.roomName)
        #         if not room:
        #             continue
        #         bank = room.find_at(FIND_STRUCTURES, flag.pos)[0]
        #         if bank and bank.hits < bank.hitsMax * 0.1:
        #             return self.get_spawn_for_flag(role_power_cleanup, creep_base_half_move_hauler,
        #                                            creep_base_hauler, flag)

        return None

    def reset_planned_role(self):
        del self.mem.next_role

    def plan_next_role(self):
        if not self.my:
            return None
        funcs_to_try = [
            self._next_needed_local_mining_role,
            self._next_cheap_military_role,
            lambda: self.mining.next_remote_mining_role(self.get_max_mining_op_count()),
            self._next_tower_breaker_role,
            self._next_needed_local_role,
        ]
        next_role = None
        for func in funcs_to_try:
            next_role = func()
            if next_role:
                maximum = spawning.max_sections_of(self, next_role.base)
                if next_role.num_sections is not None and next_role.num_sections > maximum:
                    print("[{}] Function decided on {} sections for {} (a {}), which is more than the allowed {}."
                          .format(self.room_name, next_role.num_sections, next_role.base, next_role.role, maximum))
                    next_role.num_sections = maximum
                break
        if next_role:
            if next_role.replacing is None:
                del next_role.replacing
            self.mem.next_role = next_role
        else:
            print("[{}] All creep targets reached!".format(self.room_name))
            self.mem.next_role = None

    def get_next_role(self):
        if self.mem.next_role is undefined:
            self.plan_next_role()
        return self.mem.next_role

    def toString(self):
        return "RoomMind[room_name: {}, my: {}, using_storage: {}, conducting_siege: {}]".format(
            self.room_name, self.my, self.full_storage_use, self.conducting_siege())

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
    min_sane_wall_hits = property(get_min_sane_wall_hits)


profiling.profile_whitelist(RoomMind, [
    "recalculate_roles_alive",
    "precreep_tick_actions",
    "poll_hostiles",
    "plan_next_role",
    "find",
    "find_at",
    "find_in_range",
    "find_closest_by_range",
])
