import math

import creep_wrappers
import flags
import spawning
from constants import *
from control.building import ConstructionMind
from control.links import LinkingMind
from control.pathdef import HoneyTrails, CachedTrails
from role_base import RoleBase
from roles import military
from tools import profiling
from utilities import consistency
from utilities import movement
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_MAX_BUILDERS = 3

SLIGHTLY_SMALLER_THAN_MAX_INT = math.pow(2, 30)


# TODO: MiningMind
def get_carry_mass_for_remote_mine(home, flag):
    sitting = flag.memory.sitting if flag.memory.sitting else 0
    # each carry can carry 50 energy.
    carry_per_tick = 50.0 / (home.distance_storage_to_mine(flag) * 2.1)
    room = Game.rooms[flag.pos.roomName]
    if room and (not room.controller or room.controller.reservation):
        mining_per_tick = 10.0
    else:
        mining_per_tick = 5.0
    produce_per_tick = mining_per_tick + round(sitting / 200.0)
    extra_small_hauler_mass = min(5, spawning.max_sections_of(home, creep_base_hauler))
    target_mass = math.ceil(produce_per_tick / carry_per_tick) + extra_small_hauler_mass
    if not isFinite(target_mass):
        print("[{}][mining_carry_mass] ERROR: Non-finite number of haulers determined for remote mine {}!"
              " sitting: {}, cpt: {}, mpt: {}, ppt: {}, extra: {}, tm: {}".format(
            home.room_name, flag.name, sitting, carry_per_tick, mining_per_tick, produce_per_tick,
            extra_small_hauler_mass, target_mass))
        target_mass = extra_small_hauler_mass * 5

    return target_mass


class HiveMind:
    """
    :type target_mind: TargetMind
    :type my_rooms: list[RoomMind]
    :type visible_rooms: list[RoomMind]
    """

    def __init__(self, target_mind):
        self.target_mind = target_mind
        self._honey = None
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

    def get_honey(self):
        """
        :rtype: CachedTrails
        """
        if not self._honey:
            self._honey = CachedTrails(self)
        return self._honey

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
        closest_squared_distance = SLIGHTLY_SMALLER_THAN_MAX_INT
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
    honey = property(get_honey)
    visible_rooms = property(find_visible_rooms)


profiling.profile_whitelist(HiveMind, [
    "poll_remote_mining_flags",
    "poll_all_creeps",
])

# TODO: A lot of these should be changed for if the room has 1 or 2 sources!
_min_work_mass_big_miner = 8  # TODO: This really should be based off of spawn extensions & work mass percentage!
_extra_work_mass_per_big_miner = 10

_min_energy_pause_remote_mining = 950000
_max_energy_resume_remote_mining = 700000
_min_work_mass_per_source_for_full_storage_use = 15

_min_energy_enable_full_storage_use = 10000
_max_energy_disable_full_storage_use = 5000
_energy_to_resume_upgrading = 14000
_energy_to_pause_upgrading = 8000
_min_stored_energy_to_draw_from_before_refilling = 20000

# 0 is rcl 1
_rcl_to_sane_wall_hits = [100, 1000, 10 * 1000, 100 * 1000, 400 * 1000, 600 * 1000, 1000 * 1000, 10 * 1000 * 1000]
_rcl_to_min_wall_hits = [100, 1000, 5 * 1000, 50 * 1000, 200 * 1000, 500 * 1000, 8 * 1000, 1000 * 1000]


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
    :type honey: HoneyTrails
    :type links: LinkingMind
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
        self.building = ConstructionMind(self)
        self.honey = HoneyTrails(self)
        self.links = LinkingMind(self)
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
        self._target_colonist_count = None
        self._target_simple_claim_count = None
        self._target_room_reserve_count = None
        self._target_spawn_fill_count = None
        self._target_td_healer_count = None
        self._target_td_goader_count = None
        self._target_simple_dismantler_count = None
        self._target_remote_hauler_count = None
        self._max_sane_wall_hits = None
        self._spawns = None
        self.my = room.controller and room.controller.my
        # source keeper rooms are hostile
        self.hostile = not room.controller or (room.controller.owner and not room.controller.my)
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
        if parameter in cache:
            return cache[parameter]
        else:
            # this is patched in here because we pretty much never want to find hostile creeps besides like this:
            if parameter == FIND_HOSTILE_CREEPS and len(Memory.meta.friends):
                result = self.room.find(FIND_HOSTILE_CREEPS, {
                    "filter": lambda c: c.owner.username not in Memory.meta.friends
                })
            elif parameter == PYFIND_REPAIRABLE_ROADS:
                result = _.filter(self.find(FIND_STRUCTURES),
                                  lambda s: s.structureType == STRUCTURE_ROAD and s.hits < s.hitsMax
                                            and not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_ROAD))
            elif parameter == PYFIND_BUILDABLE_ROADS:
                result = _.filter(self.find(FIND_MY_CONSTRUCTION_SITES),
                                  lambda s: s.structureType == STRUCTURE_ROAD
                                            and not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_ROAD))
            else:
                result = self.room.find(parameter)
            cache[parameter] = result
            return result

    def find_at(self, find_type, pos, optional_y=None):
        """
        Looks for something at a position, and caches the result for this tick.

        This is meant as a drop-in replacement for pos.lookFor() or room.lookForAt().
        :param find_type: thing to look for, one of the FIND_* constants
        :type find_type: str
        :param pos: The position to look for at, or the x value of a position
        :type pos: int | RoomPosition
        :param optional_y: The y value of the position. If this is specified, `pos` is treated as the x value, not as a whole position
        :type optional_y: int
        :return: A list of results
        :rtype: list[RoomObject]
        """
        if optional_y:
            x = pos
            y = optional_y
        else:
            x = pos.x
            y = pos.y
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
        :type optional_y: int
        :return: A list of results
        :rtype: list[RoomObject]
        """
        if optional_y:
            x = pos
            y = optional_y
        else:
            x = pos.x
            y = pos.y
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
        raw_find_results = self.find(find_type)
        if lodash_filter:
            raw_find_results = _.filter(raw_find_results, lodash_filter)
        if not len(raw_find_results):
            return None
        closest_distance = math.pow(2, 30)
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

    remote_mining_operations = property(_get_remote_mining_operations)

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

    def paving(self):
        paving = self.get_cached_property("paving_here")
        if paving is None:
            if self.my:
                # TODO: 2 maybe should be a constant?
                paving = self.full_storage_use and len(self.remote_mining_operations) > 2
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
        elif len(self.find(PYFIND_BUILDABLE_ROADS)):
            paved = False  # still paving
        else:
            for flag in self.remote_mining_operations:
                room = self.hive_mind.get_room(flag.pos.roomName)
                if room:
                    if not room.all_paved():
                        paved = False
                        break
                else:
                    unreachable_rooms = True  # Cache for less time
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
            creep = creep_wrappers.wrap_creep(creep)
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
            #_.sortedIndex(array, value, [iteratee=_.identity])
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
            creep = creep_wrappers.wrap_creep(creep)

            rt_pair = (creep.name, creep.get_replacement_time())
            if not rt_map[role]:
                rt_map[role] = [rt_pair]
            else:
                #_.sortedIndex(array, value, [iteratee=_.identity])
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
        if result: return result
        current = self.carry_mass_of(role)
        left_to_remove = current - target_carry_mass
        result = []
        if left_to_remove < 0:
            return result
        rt_map = self._get_rt_map()
        if role in rt_map:
            for name, rt in rt_map[role]:
                if name not in Memory.creeps:
                    continue
                carry = Memory.creeps[name].carry  # TODO: this should always be set, but what if it isn't?
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
        key = "ecc_{}".format(role)
        result = self.get_cached_property(key)
        if result: return result
        current = self.work_mass_of(role)
        left_to_remove = current - target_work_mass
        result = []
        if left_to_remove < 0:
            return result
        rt_map = self._get_rt_map()
        if role in rt_map:
            for name, rt in rt_map[role]:
                if name not in Memory.creeps:
                    continue
                work = Memory.creeps[name].work  # TODO: this should always be set, but what if it isn't?
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

    def register_new_replacing_creep(self, role, replaced_name, replacing_name):
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

    def carry_mass_of_replacements_currently_needed_for(self, role):
        mass = 0
        rt_map = self._get_rt_map()
        if role in rt_map and len(rt_map[role]):
            for creep, replacement_time in rt_map[role]:
                if Game.creeps[creep] and not Memory.creeps[creep].replacement and replacement_time <= Game.time:
                    mass += spawning.carry_count(Game.creeps[creep])
        return mass

    def work_mass_of_replacements_currently_needed_for(self, role):
        mass = 0
        rt_map = self._get_rt_map()
        if role in rt_map and len(rt_map[role]):
            for creep, replacement_time in rt_map[role]:
                if Game.creeps[creep] and not Memory.creeps[creep].replacement and replacement_time <= Game.time:
                    mass += spawning.work_count(Game.creeps[creep])
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

        if self.hostile:
            return  # don't find hostile creeps in other players rooms... that's like, not a great plan...

        remove = None
        for hostile_id, hostile_room, pos, owner in Memory.hostiles:
            if hostile_room == self.room_name and not Game.getObjectById(hostile_id):
                if remove:
                    remove.append(hostile_id)
                else:
                    remove = [hostile_id]
        if remove:
            for hostile_id in remove:
                military.delete_target(hostile_id)
        targets = self.find(FIND_HOSTILE_CREEPS)
        for hostile in targets:
            # TODO: overhaul hostile info storage
            hostile_list = _.find(Memory.hostiles, lambda t: t[0] == hostile.id and t[1] == self.room_name)
            if hostile_list:
                hostile_list[2] = hostile.pos  # this is the only thing which would update
            else:
                Memory.hostiles.push([hostile.id, self.room_name, hostile.pos, hostile.owner.username])
                Memory.hostile_last_rooms[hostile.id] = self.room_name
            Memory.hostile_last_positions[hostile.id] = hostile.pos

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

    def get_target_terminal_energy(self):
        if not self.room.terminal:
            return 0
        target = self.mem.target_terminal_energy
        if not target:
            return 0
        if self.room.terminal.store.energy >= target:
            del self.mem.target_terminal_energy
            return 0
        return target

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
            self._trying_to_get_full_storage_use = self.work_mass >= _min_work_mass_per_source_for_full_storage_use \
                                                                     * len(self.sources) \
                                                   and self.are_all_big_miners_placed \
                                                   and self.room.storage
        return self._trying_to_get_full_storage_use

    def get_full_storage_use(self):
        """
        :rtype: bool
        """
        if self._full_storage_use is None:
            if self.room.storage and self.room.storage.store[RESOURCE_ENERGY] \
                    >= _min_stored_energy_to_draw_from_before_refilling:
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
        if self.mem.focusing_home and self.room.storage.store.energy < _max_energy_resume_remote_mining:
            self.mem.focusing_home = False
        if not self.mem.focusing_home and self.room.storage.store.energy > _min_energy_pause_remote_mining:
            self.mem.focusing_home = True
        return not not self.mem.focusing_home

    def upgrading_paused(self):
        if self.room.controller.level < 4:
            return False
        if self.get_target_td_healer_count() > 0:
            return True  # Don't upgrade while we're taking someone down.
        if self.mem.upgrading_paused and self.room.storage.store.energy > _energy_to_resume_upgrading:
            self.mem.upgrading_paused = False
        if not self.mem.upgrading_paused and self.room.storage.store.energy < _energy_to_pause_upgrading:
            self.mem.upgrading_paused = True
        return not not self.mem.upgrading_paused

    def get_max_mining_op_count(self):
        spawning_energy = self.room.energyCapacityAvailable
        sources = len(self.sources)
        rcl = self.room.controller.level

        if sources <= 1:
            min_wm = 25
            extra_wm = 10
            min_energy = 550  # rcl 2, fully built
            min_rcl = 2
            extra_rcl = 0
        else:
            min_wm = 40  # Around all roles built needed for an rcl 3 room!
            extra_wm = 30
            min_energy = 800  # rcl 3, fully built
            min_rcl = 3
            extra_rcl = 1

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
        return min(max_via_wm, max_via_energy, max_via_rcl)

    def get_max_local_miner_count(self):
        if self.room.storage:
            self.energy = self.room.storage.store.energy
        else:
            self.energy = 0
        spawning_energy = self.room.energyCapacityAvailable
        sources = len(self.sources)

        min_energy = 550  # rcl 2, fully built
        if sources <= 1:
            min_wm = 7
            extra_wm = 10
        else:
            min_wm = 15
            extra_wm = 10

        if self.work_mass < min_wm:
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
        if self._max_sane_wall_hits is None:
            self._max_sane_wall_hits = _rcl_to_sane_wall_hits[self.room.controller.level - 1]  # 1-to-0-based index
        return self._max_sane_wall_hits

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

    def get_target_remote_miner_count(self):
        """
        :rtype: int
        """
        if self._target_remote_mining_operation_count is None:
            max_via_state = self.get_max_mining_op_count()
            if max_via_state > 0 and not self.mining_ops_paused():
                max_via_plan = len(self.remote_mining_operations)

                if self.carry_mass_of(role_remote_hauler) >= self.get_target_remote_hauler_mass():
                    max_via_haulers = self.role_count(role_remote_miner) + 2
                else:
                    max_via_haulers = self.role_count(role_remote_miner)

                self._target_remote_mining_operation_count = min(max_via_state, max_via_plan, max_via_haulers)
            else:
                self._target_remote_mining_operation_count = 0
        return self._target_remote_mining_operation_count

    def get_target_remote_hauler_mass(self):
        """
        :rtype: int
        """
        if self._target_remote_hauler_carry_mass is None:
            needed_ops = 0
            biggest_op_mass_needed = 0  # TODO: this should be eventually replaced with spawning hauler specific to the mine.
            if self.get_max_mining_op_count():
                for flag in self.remote_mining_operations:
                    if flag.memory.remote_miner_targeting or flag.memory.sitting > 500:
                        needed_ops += 1
                    mass_for_op = get_carry_mass_for_remote_mine(self, flag)
                    if mass_for_op > biggest_op_mass_needed:
                        biggest_op_mass_needed = mass_for_op
            self._target_remote_hauler_carry_mass = needed_ops * biggest_op_mass_needed
            self._target_remote_hauler_count = needed_ops
        return self._target_remote_hauler_carry_mass

    def get_target_remote_hauler_count(self):
        """
        :rtype int
        """
        if self._target_remote_hauler_count is None:
            self.get_target_remote_hauler_mass()
        return self._target_remote_hauler_count

    def get_target_remote_reserve_count(self, first):
        """
        :rtype: int
        """
        if (self._first_target_remote_reserve_count if first else self._target_remote_reserve_count) is None:
            mining_op_count = self.get_target_remote_miner_count()
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

    def get_target_local_hauler_mass(self):
        """
        :rtype: int
        """
        # TODO: dynamically spawn creeps with less mass!
        # TODO: Merge local hauler and spawn fill roles!
        if self._target_local_hauler_carry_mass is None:
            if self.trying_to_get_full_storage_use:
                # TODO: "max_parts_on" is essentially trying to duplicate behavior prior to fully-dynamic creep bodies
                # Previously, we grew bodies dynamically and maxed out at 5 carry per creep.
                # TODO: this should be replaced with a calculation taking in path distance from each source to
                # the storage and hauler capacity.
                carry_max_5 = min(5, spawning.max_sections_of(self, creep_base_hauler))
                total_mass = math.ceil(self.get_target_local_miner_count() * 1.5 * carry_max_5)
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
        # TODO: dynamically spawn creeps with less mass!
        if self._target_cleanup_mass is None:
            # if self.full_storage_use:
            #     # TODO: merge filter and generic.Cleanup's filter (the same code) together somehow.
            #     piles = self.room.find(FIND_DROPPED_RESOURCES, {
            #         "filter": lambda s: len(
            #             _.filter(s.pos.lookFor(LOOK_CREEPS), lambda c: c.memory and c.memory.stationary is True)) == 0
            #     })
            #     total_energy = 0
            #     for pile in piles:
            #         total_energy += pile.amount
            #     self._target_cleanup_mass = math.floor(total_energy / 200.0)
            # else:
            self._target_cleanup_mass = 0

        return self._target_cleanup_mass

    def get_target_simple_defender_count(self, first=False):
        """
        :rtype: int
        """
        if (self._first_simple_target_defender_count if first else self._target_defender_count) is None:
            hostile_count = 0
            room_mine_to_protect = {}
            if Memory.hostiles:
                for hostile_id, hostile_room, hostile_pos, hostile_owner in Memory.hostiles:
                    if hostile_owner == "Invader":  # TODO: ranged defenders to go against player attackers!
                        if hostile_room not in room_mine_to_protect:
                            room = self.hive_mind.get_room(hostile_room)
                            closest_owned_room = self.hive_mind.get_closest_owned_room(hostile_room)
                            if (not first or (room and room.room_name == self.room_name)) \
                                    and closest_owned_room.room_name == self.room_name:
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
        work_max_10 = min(10, spawning.max_sections_of(self, creep_base_worker))
        if not self._target_colonist_count:
            needed = 0
            for room in self.subsidiaries:
                needed += max(0, 3 - _.sum(room.role_counts))
            self._target_colonist_count = needed * work_max_10
        return self._target_colonist_count

    def get_target_spawn_fill_backup_work_mass(self):
        work_max_5 = min(5, spawning.max_sections_of(self, creep_base_worker))
        # TODO: 7 should be a constant.
        if self.full_storage_use or self.are_all_big_miners_placed or self.work_mass > 8:
            if self.full_storage_use and (self.are_all_big_miners_placed or self.work_mass > 25):
                return 0
            else:
                return 1 * work_max_5
        else:
            return (2 + len(self.sources)) * work_max_5

    def get_target_spawn_fill_mass(self):
        if self._target_spawn_fill_count is None:
            spawn_fill_backup = self.carry_mass_of(role_spawn_fill_backup)
            tower_fill = self.carry_mass_of(role_tower_fill)
            if self.room_name == "W46N28":
                # TODO: Make it possible to scale things based off of "input energy" or hauler count of mined sources.
                # more are needed because there are no links and storage is a long way from spawn.
                total_needed = 3 + len(self.sources) + len(_.filter(
                    self.remote_mining_operations, lambda flag: not not flag.memory.remote_miner_targeting))
                # print("[{}] Activating special spawn fill target count. TODO: remove".format(self.room_name))
                max_mass_per_creep = spawning.max_sections_of(self, creep_base_hauler)
                total_mass = min(5, max_mass_per_creep) * total_needed
            else:
                total_mass = min(5 * spawning.max_sections_of(self, creep_base_hauler),
                                 3 * self.room.controller.level * len(self.sources))
            regular_count = max(0, total_mass - tower_fill - spawn_fill_backup)
            if self.trying_to_get_full_storage_use:
                self._target_spawn_fill_count = regular_count
            else:
                extra_count = 0
                for source in self.sources:
                    energy = _.sum(self.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount')
                    extra_count += energy / 200.0
                self._target_spawn_fill_count = regular_count + extra_count
        return self._target_spawn_fill_count

    def get_target_builder_work_mass(self, first=False, last=False):
        def is_relatively_decayed(id):
            thing = Game.getObjectById(id)
            return thing is not None and thing.structureType != STRUCTURE_ROAD \
                   and thing.hits > min(thing.hitsMax, self.max_sane_wall_hits) * 0.85

        # TODO: this is a hack to get correct workmasses (this is called twice)
        if self._builder_use_first_only:
            if last:
                self._builder_use_first_only = False
            else:
                first = True
        elif first:
            self._builder_use_first_only = True
        if self.upgrading_paused() and not len(self.building.next_priority_construction_targets()):
            return 0
        elif self.mining_ops_paused():
            # TODO: this is emulating pre-dynamic-creep-body generation behavior of capping work mass per creep to
            # 5 work per creep.
            return 4 + 2 * len(self.sources) * min(5, spawning.max_sections_of(self, creep_base_worker))
        elif first:
            if len(self.building.next_priority_construction_targets()):
                if len(self.sources) >= 2:
                    return 1.5 * len(self.sources) * min(8, spawning.max_sections_of(self, creep_base_worker))
                else:
                    return min(8, spawning.max_sections_of(self, creep_base_worker))
            elif _.find(self.building.next_priority_repair_targets(), is_relatively_decayed) \
                    or _.find(self.building.next_priority_big_repair_targets(), is_relatively_decayed):
                return len(self.sources) * min(8, spawning.max_sections_of(self, creep_base_worker))
            else:
                return 0
        else:
            if len(self.building.next_priority_construction_targets()) \
                    or _.find(self.building.next_priority_repair_targets(), is_relatively_decayed) \
                    or _.find(self.building.next_priority_big_repair_targets(), is_relatively_decayed):
                return 2 * len(self.sources) * min(8, spawning.max_sections_of(self, creep_base_worker))

    def get_target_upgrader_work_mass(self):
        if self.upgrading_paused():
            wm = 1
        elif self.mining_ops_paused():
            wm = spawning.max_sections_of(self, creep_base_worker) * 4
        else:
            wm = min(2 + self.room.controller.level, spawning.max_sections_of(self, creep_base_worker))
        if self.full_storage_use and self.room.storage.store.energy > 700000:
            wm += math.floor((self.room.storage.store.energy - 700000) / 2000)
        return wm

    def get_target_tower_fill_mass(self):
        mass = 0
        for s in self.find(FIND_STRUCTURES):
            if s.structureType == STRUCTURE_TOWER:
                # TODO: cache max_parts_on? called a ton in this method and other get_target_*_mass methods.
                # but we probably shouldn't since it's mostly a hack to emulate spawning 5-section creeps anyways?
                mass += min(5, spawning.max_sections_of(self, creep_base_hauler)) * 0.75
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

    def get_target_mineral_miner_count(self):
        # TODO: cache this
        # TODO: this should also depend on work mass
        minerals = self.find(FIND_MINERALS)
        if _.sum(minerals, 'mineralAmount') > 0 and _.find(self.find(FIND_MY_STRUCTURES),
                                                           {'structureType': STRUCTURE_EXTRACTOR}):
            return 1
        else:
            return 0

    def get_target_mineral_hauler_count(self):
        if self.get_target_mineral_miner_count():
            return self.role_count(role_mineral_miner) * 2
        elif self.get_target_terminal_energy():  # this method returns 0 once the terminal has reached it's target
            # this is really a hack, and should be changed soon!
            return 1
        else:
            return 0

    def get_new_remote_hauler_num_sections(self):
        if self.all_paved():
            biggest_mass = spawning.max_sections_of(self, creep_base_work_half_move_hauler)
        elif self.paving():
            biggest_mass = spawning.max_sections_of(self, creep_base_work_full_move_hauler)
        else:
            biggest_mass = spawning.max_sections_of(self, creep_base_hauler)
        needed = self.get_target_remote_hauler_mass() / self.get_target_remote_hauler_count()
        if needed > biggest_mass:
            if math.ceil(needed / 2) > biggest_mass:
                if math.ceil(needed / 3) > biggest_mass:
                    if math.ceil(needed / 4) > biggest_mass:
                        return biggest_mass
                    else:
                        return math.ceil(needed / 4)
                else:
                    return math.ceil(needed / 3)
            else:
                return math.ceil(needed / 2)
        else:
            return needed

    def get_target_td_healer_count(self):
        if self._target_td_healer_count is None:
            if not self.full_storage_use or not self.get_target_td_goader_count():
                return 0
            count = 0
            for flag in flags.find_flags_global(flags.TD_H_H_STOP):
                if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name:
                    count += 1
            self._target_td_healer_count = count
        return self._target_td_healer_count

    def get_target_td_goader_count(self):
        if self._target_td_goader_count is None:
            if not self.full_storage_use:
                return 0
            count = 0
            for flag in flags.find_flags_global(flags.TD_D_GOAD):
                if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name:
                    count += 1
            self._target_td_goader_count = count
        return self._target_td_goader_count

    def get_target_simple_dismantler_count(self):
        if self._target_simple_dismantler_count is None:
            if not self.full_storage_use:
                return 0
            count = 0
            for flag in flags.find_flags_global(flags.ATTACK_DISMANTLE):
                if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name:
                    count += 1
            self._target_simple_dismantler_count = count
        return self._target_simple_dismantler_count

    def _next_needed_local_role(self):
        requirements = [
            [role_spawn_fill_backup, self.get_target_spawn_fill_backup_work_mass, False, True],
            [role_defender, lambda: self.get_target_simple_defender_count(True)],
            [role_link_manager, self.get_target_link_manager_count],
            [role_cleanup, self.get_target_cleanup_mass, True],
            [role_dedi_miner, self.get_target_local_miner_count],
            [role_tower_fill, self.get_target_tower_fill_mass, True],
            [role_spawn_fill, self.get_target_spawn_fill_mass, True],
            [role_local_hauler, self.get_target_local_hauler_mass, True],
            [role_mineral_hauler, self.get_target_mineral_hauler_count],
            [role_upgrader, self.get_target_upgrader_work_mass, False, True],
            [role_simple_claim, self.get_target_simple_claim_count],
            [role_room_reserve, self.get_target_room_reserve_count],
            # TODO: a "first" argument to this which checks energy, then do another one at the end of remote.
            [role_colonist, self.get_target_colonist_work_mass],
            [role_mineral_miner, self.get_target_mineral_miner_count],
            [role_builder, lambda: self.get_target_builder_work_mass(True), False, True]
        ]
        for role, get_ideal, count_carry, count_work in requirements:
            if count_carry:
                if self.carry_mass_of(role) - self.carry_mass_of_replacements_currently_needed_for(role) < get_ideal():
                    return role
            elif count_work:
                if self.work_mass_of(role) - self.work_mass_of_replacements_currently_needed_for(role) < get_ideal():
                    return role
            else:
                if self.role_count(role) - self.replacements_currently_needed_for(role) < get_ideal():
                    return role

    def _next_probably_local_role(self):
        roles = [
            # Extra args as a hack to ensure that the correct workmass is returned from
            # get_max_sections_for_role() when we only want the first builder work mass.
            [role_builder, lambda: self.get_target_builder_work_mass(False, True)],
        ]
        for role, ideal in roles:
            # TODO: this code is a mess!
            if self.work_mass_of(role) - self.work_mass_of_replacements_currently_needed_for(role) < ideal():
                return role

    def _next_remote_mining_role(self):
        remote_operation_reqs = [
            [role_defender, self.get_target_simple_defender_count],
            [role_td_healer, self.get_target_td_healer_count],
            [role_td_goad, self.get_target_td_goader_count],
            [role_simple_dismantle, self.get_target_simple_dismantler_count],
            # Be sure we're reserving all the current rooms we're mining before we start mining a new room!
            # get_target_remote_reserve_count takes into account only rooms with miners *currently* mining them.
            [role_remote_mining_reserve, lambda: self.get_target_remote_reserve_count(True)],
            [role_remote_miner, self.get_target_remote_miner_count],
            [role_remote_hauler, self.get_target_remote_hauler_mass, True],
            [role_remote_mining_reserve, self.get_target_remote_reserve_count],
        ]
        for role, get_ideal, count_carry, count_work in remote_operation_reqs:
            if count_carry:
                if self.carry_mass_of(role) - self.carry_mass_of_replacements_currently_needed_for(role) < get_ideal():
                    return role
            elif count_work:
                if self.work_mass_of(role) - self.work_mass_of_replacements_currently_needed_for(role) < get_ideal():
                    return role
            else:
                if self.role_count(role) - self.replacements_currently_needed_for(role) < get_ideal():
                    return role

    def get_max_sections_for_role(self, role):
        max_mass = {
            role_spawn_fill_backup:
                self.get_target_spawn_fill_backup_work_mass,
            role_link_manager:
                lambda: min(self.get_target_link_manager_count() * 8,
                            spawning.max_sections_of(self, creep_base_hauler)),
            role_dedi_miner:
                lambda: None,  # non-dynamic completely
            role_cleanup:
                lambda: math.ceil(max(self.get_target_cleanup_mass(),
                                      min(10, spawning.max_sections_of(self, creep_base_hauler)))),
            role_spawn_fill:
                lambda: math.ceil(self.get_target_spawn_fill_mass() / 2),
            role_tower_fill:
            # Tower fillers are basically specialized spawn fillers.
                lambda: max(self.get_target_tower_fill_mass(), math.ceil(self.get_target_spawn_fill_mass() / 2)),
            role_local_hauler:
                lambda: math.ceil(self.get_target_local_hauler_mass() / len(self.sources)),
            role_upgrader:
                self.get_target_upgrader_work_mass,
            role_defender:
                lambda: self.get_target_simple_defender_count() * min(6, spawning.max_sections_of(self,
                                                                                                  creep_base_defender)),
            role_remote_hauler:
                self.get_new_remote_hauler_num_sections,
            role_remote_miner:
                lambda: min(5, spawning.max_sections_of(self, creep_base_full_miner)),
            role_remote_mining_reserve:
                lambda: min(2, spawning.max_sections_of(self, creep_base_reserving)),
            role_simple_claim:
                lambda: 1,
            role_room_reserve:
                lambda: min(5, spawning.max_sections_of(self, creep_base_reserving)),
            role_colonist:
                lambda: min(10, spawning.max_sections_of(self, creep_base_worker)),
            role_builder:
                lambda: self.get_target_builder_work_mass(),
            role_mineral_miner:
                lambda: None,  # fully dynamic
            role_mineral_hauler:  # TODO: Make this depend on distance from terminal to mineral
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
            if self.paving():
                if self.all_paved():
                    return creep_base_work_half_move_hauler
                else:
                    return creep_base_work_full_move_hauler
            else:
                return creep_base_hauler
        else:
            return role_bases[role]

    def reset_planned_role(self):
        del self.mem.next_role

    def plan_next_role(self):
        next_role = self._next_needed_local_role()
        if not next_role:
            next_role = self._next_remote_mining_role()
            if not next_role:
                next_role = self._next_probably_local_role()
        if next_role:
            self.mem.next_role = next_role
        else:
            print("[{}] All creep targets reached!".format(self.room_name))
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
    min_sane_wall_hits = property(get_min_sane_wall_hits)


profiling.profile_whitelist(RoomMind, [
    "recalculate_roles_alive",
    "precreep_tick_actions",
    "poll_hostiles",
    "plan_next_role",
])
