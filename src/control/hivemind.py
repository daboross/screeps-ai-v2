import math

import creep_wrappers
import flags
import spawning
from constants import *
from control import defense
from control import live_creep_utils
from control.building import ConstructionMind
from control.defense import RoomDefense
from control.links import LinkingMind
from control.minerals import MineralMind
from control.mining import MiningMind
from control.pathdef import HoneyTrails
from role_base import RoleBase
from tools import profiling
from utilities import consistency
from utilities import movement
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
        trying = spawning.ceil_sections(needed / num - extra_initial)
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


def clamp_room_coord(coord):
    return (coord if coord < 49 else 49) if coord > 0 else 0


class HiveMind:
    """
    :type target_mind: control.targets.TargetMind
    :type honey: control.pathdef.HoneyTrails
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
        # Needed in RoomMind.__init__()
        if 'enemy_rooms' not in Memory:
            Memory.enemy_rooms = []
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

    __pragma__('fcall')

    def get_room(self, room_name):
        """
        Gets a visible room given its room name.
        :rtype: RoomMind
        """
        if self._all_rooms is None:
            self.find_visible_rooms()
        return self._room_to_mind[room_name]

    __pragma__('nofcall')

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
                if 'sponsor' in flag.memory:
                    sponsor = self.get_room(flag.memory.sponsor)
                else:
                    sponsor = self.get_room(flag.name.split('_')[0])
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

    __pragma__('fcall')

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
            distance = movement.squared_distance(current_pos, room.position)
            if distance < closest_squared_distance:
                closest_squared_distance = distance
                closest_room = room
        if not closest_room:
            print("[{}] ERROR: could not find closest owned room!".format(current_room_name))
        return closest_room

    __pragma__('nofcall')

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

    def balance_rooms(self):
        if not _.some(self.my_rooms, lambda r: r.rcl >= 8 and not r.minerals.has_no_terminal_or_storage()):
            print("[hive][balance_rooms] Canceling: no RCL8 rooms.")
            return

        def map_to_walls(room):
            smallest = _(room.find(FIND_STRUCTURES)) \
                .filter(lambda s: s.structureType == STRUCTURE_WALL or s.structureType == STRUCTURE_RAMPART) \
                .min(lambda s: s.hits)

            if smallest == Infinity:
                return room, Infinity
            else:
                return room, smallest.hits

        rooms_with_walls = _(self.my_rooms) \
            .filter(lambda r: r.rcl >= 6 and not r.minerals.has_no_terminal_or_storage()) \
            .map(map_to_walls).value()
        biggest_rcl8_room = _(rooms_with_walls) \
            .filter(lambda t: t[0].rcl >= 8 and _.isEmpty(t[0].minerals.fulfilling[RESOURCE_ENERGY])) \
            .max(lambda t: t[1])
        smallest_room = _.min(rooms_with_walls, lambda t: t[1])

        if biggest_rcl8_room == -Infinity or smallest_room == Infinity or smallest_room[1] == Infinity \
                or (smallest_room[0].rcl >= 8 and smallest_room[1] >= 49 * 1000 * 1000) \
                or smallest_room[0].room_name == biggest_rcl8_room[0].room_name:
            print("[hive][balance_rooms] Canceling.")
            return
        biggest_rcl8_room = biggest_rcl8_room[0]
        smallest_room = smallest_room[0]
        assert isinstance(biggest_rcl8_room, RoomMind)
        assert isinstance(smallest_room, RoomMind)
        total_cutoff = 300 * 1000
        energy_cutoff = 100 * 1000
        extra_energy = min(_.sum(biggest_rcl8_room.minerals.get_total_room_resource_counts()) - total_cutoff,
                           biggest_rcl8_room.minerals.get_total_room_resource_counts().energy - energy_cutoff)
        if js_isNaN(extra_energy) or extra_energy <= 0:
            print("[hive][balance_rooms] Canceling: no extra energy in {}.".format(biggest_rcl8_room.room_name))
            return

        distance = Game.map.getRoomLinearDistance(biggest_rcl8_room.room_name, smallest_room.room_name, True)
        total_cost_of_1_energy = 1 + 1 * (math.log((distance + 9) * 0.1) + 0.1)
        max_to_send = math.floor(extra_energy / total_cost_of_1_energy)

        if max_to_send <= 0:
            print("[hive][balance_rooms] Extra energy in {} ({}) isn't enough to send any to {} via a terminal."
                  .format(biggest_rcl8_room.room_name, extra_energy, smallest_room.room_name))
            return

        print("[hive] Balancing rooms: sending {} energy from {} to {}."
              .format(max_to_send, biggest_rcl8_room.room_name, smallest_room.room_name))

        biggest_rcl8_room.minerals.send_minerals(smallest_room.room_name, RESOURCE_ENERGY, max_to_send)

    def mineral_report(self):
        result = []
        tally = {}
        for room in self.my_rooms:
            if room.minerals and not room.minerals.has_no_terminal_or_storage():
                result.append(room.minerals.mineral_report())
                for mineral, amount in _.pairs(room.minerals.get_total_room_resource_counts()):
                    if mineral in tally:
                        tally[mineral] += amount
                    else:
                        tally[mineral] = amount
        result.push("totals:\t{}".format(
            "\t".join(["{} {}".format(amount, mineral) for mineral, amount in _.pairs(tally)])
        ))
        return "\n".join(result)

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
_rcl8_energy_to_resume_upgrading = 200000
_rcl8_energy_to_pause_upgrading = 100000
_energy_to_pause_building = 14000
_energy_to_resume_building = 28000
_min_stored_energy_to_draw_from_before_refilling = 20000

_rcl_to_min_wall_hits = [
    1,  # RCL 1
    20 * 1000,  # RCL 2
    50 * 1000,  # RCL 3
    150 * 1000,  # RCL 4
    500 * 1000,  # RCL 5
    1000 * 1000,  # RCL 6
    3 * 1000 * 1000,  # RCL 7
    10 * 1000 * 1000,  # RCL 8
]
_rcl_to_sane_wall_hits = [
    2,  # RCL 1
    40 * 1000,  # RCL 2
    80 * 1000,  # RCL 3
    250 * 1000,  # RCL 4
    1000 * 1000,  # RCL 5
    1500 * 1000,  # RCL 6
    5 * 1000 * 1000,  # RCL 7
    50 * 1000 * 1000  # RCL 8
]


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
        self.room_name = self.room.name
        self.my = room.controller and room.controller.my
        if self.my:
            self.rcl = self.room.controller.level
            self.building = ConstructionMind(self)
            self.links = LinkingMind(self)
            self.mining = MiningMind(self)
            self.minerals = MineralMind(self)
        else:
            self.rcl = 0
        self.defense = RoomDefense(self)
        self.subsidiaries = []
        self._remote_mining_operations = None
        self._sources = None
        self._creeps = None
        self._work_mass = None
        self._position = None
        __pragma__('skip')
        self._upgrader_source = undefined
        __pragma__('noskip')
        self._extra_fill_targets = None
        self._ideal_big_miner_count = None
        self._all_big_miners_placed = None
        self._trying_to_get_full_storage_use = None
        self._full_storage_use = None
        self._building_paused = None
        self._overprioritize_building = None
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
        self._target_room_reserve_count = None
        self._target_spawn_fill_mass = None
        self._target_td_healer_count = None
        self._target_td_goader_count = None
        self._target_simple_dismantler_count = None
        self._target_remote_hauler_count = None
        self._target_upgrader_work_mass = None
        self._target_upgrade_fill_work_mass = None
        self._total_needed_spawn_fill_mass = None
        self._max_sane_wall_hits = None
        self._conducting_siege = None
        self._spawns = None
        # self._look_cache = new_map()
        self._find_cache = new_map()
        # source keeper rooms are hostile
        self.hostile = not room.controller or (room.controller.owner and not room.controller.my)
        enemy_structures = _.find(self.find(FIND_HOSTILE_STRUCTURES), lambda s: s.structureType == STRUCTURE_SPAWN
                                                                                or s.structureType == STRUCTURE_TOWER)
        self.enemy = room.controller and room.controller.owner and not room.controller.my \
                     and not Memory.meta.friends.includes(self.room.controller.owner.username) \
                     and enemy_structures
        if self.enemy:
            if not Memory.enemy_rooms.includes(self.room_name):
                Memory.enemy_rooms.push(room.name)
        elif (not room.controller or room.controller.owner) \
                and Memory.enemy_rooms.includes(self.room_name) \
                and not enemy_structures:
            Memory.enemy_rooms.splice(Memory.enemy_rooms.indexOf(self.room_name), 1)
        self.spawn = self.spawns[0] if self.spawns and len(self.spawns) else None
        if self.mem.sponsor:
            self.sponsor_name = self.mem.sponsor
        else:
            self.sponsor_name = None

    __pragma__('fcall')

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
        if self._find_cache.has(parameter):
            return self._find_cache.get(parameter)
        else:
            # this is patched in here because we pretty much never want to find hostile creeps besides like this:
            if parameter == FIND_HOSTILE_CREEPS and len(Memory.meta.friends):
                result = self.room.find(FIND_HOSTILE_CREEPS, {
                    "filter": lambda c: not Memory.meta.friends.includes(c.owner.username)
                })
            elif parameter is PYFIND_REPAIRABLE_ROADS:
                result = _.filter(self.find(FIND_STRUCTURES),
                                  lambda s:
                                  (
                                      (s.structureType == STRUCTURE_ROAD
                                       and not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_ROAD))
                                      or (s.structureType == STRUCTURE_CONTAINER and
                                          not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_CONTAINER))
                                  ) and s.hits < s.hitsMax)
            elif parameter is PYFIND_BUILDABLE_ROADS:
                result = _.filter(self.find(FIND_CONSTRUCTION_SITES),
                                  lambda s:
                                  (
                                      s.structureType == STRUCTURE_ROAD
                                      and not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                                  ) or (
                                      s.structureType == STRUCTURE_CONTAINER
                                      and not flags.look_for(self, s, flags.MAIN_DESTRUCT, flags.SUB_CONTAINER))
                                  )
            elif parameter is PYFIND_HURT_CREEPS:
                result = _.filter(self.find(FIND_MY_CREEPS),
                                  lambda c: c.hits < c.hitsMax)
            else:
                result = self.room.find(parameter)
            self._find_cache.set(parameter, result)
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

    def look_at(self, look_type, pos, optional_y=None):
        x, y, room_name = parse_xy_arguments(pos, optional_y)
        if room_name is not None and room_name != self.room_name:
            room = self.hive_mind.get_room(room_name)
            if room:
                return room.look_at(look_type, x, y)
            else:
                return []
        # ser = (x | y << 6) + look_type
        # if self._look_cache.has(ser):
        #     return self._look_cache.get(ser)
        result = self.room.lookForAt(look_type, x, y)
        # self._look_cache.set(ser, result)
        return result

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
            distance = movement.chebyshev_distance_room_pos(pos, element.pos)
            if distance < closest_distance:
                closest_element = element
                closest_distance = distance
        return closest_element

    def look_for_in_area_around(self, look_type, pos, look_range):
        """
        Runs Room.lookForAtArea(look_type, ..., true) on an area a specific range around the pos, ensuring to clamp
        positions to relative room positions
        :param look_type:
        :param pos:
        :param look_range:
        :return:
        """
        if pos.pos:
            pos = pos.pos
        return self.room.lookForAtArea(look_type,
                                       clamp_room_coord(pos.y - look_range),
                                       clamp_room_coord(pos.x - look_range),
                                       clamp_room_coord(pos.y + look_range),
                                       clamp_room_coord(pos.x + look_range),
                                       True)

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
                paving = (self.room.storage or self.spawn) and \
                         (self.get_max_mining_op_count() >= 1 or self.room.storage) \
                         and len(self.mining.available_mines) >= 1 \
                         and self.room.energyCapacityAvailable >= 600
            else:
                paving = False
                for flag in flags.find_flags(self, flags.REMOTE_MINE):
                    if flag.memory.sponsor:
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
                if flag.pos.roomName == self.room_name:
                    continue
                room = self.hive_mind.get_room(flag.pos.roomName)
                if room:
                    if not room.all_paved():
                        paved = False
                        break
                else:
                    unreachable_rooms = True  # Cache for less time
                    paved = False
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

        if time >= meta.clear_next:
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
        if time >= meta.reset_spawn_on:
            self.reset_planned_role()
            meta.reset_spawn_on = consistency.get_next_replacement_time(self) + 1

        # TODO: this will make both rooms do it at the same time, but this is better than checking every time memory is
        # cleared! Actually, it's quite cheap.
        if Game.time % 10 == 0:
            self.reassign_roles()

    def reassign_roles(self):
        return consistency.reassign_room_roles(self)

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

    def get_upgrader_energy_struct(self):
        if self._upgrader_source is undefined:
            structure_id = self.get_cached_property("upgrader_source_id")
            if structure_id:
                if structure_id == -1:
                    self._upgrader_source = None
                    return None
                else:
                    structure = Game.getObjectById(structure_id)
                    if structure:
                        self._upgrader_source = structure
                        return structure
            structure = None
            if self.room.storage and not self.being_bootstrapped():
                if self.room.storage.pos.inRangeTo(self.room.controller, 4):
                    structure = self.room.storage
                else:
                    all_structs_near = _(self.find_in_range(FIND_STRUCTURES, 4, self.room.controller.pos))
                    if all_structs_near.find({'structureType': STRUCTURE_LINK, 'my': True}):
                        structure = all_structs_near.filter({'structureType': STRUCTURE_LINK}) \
                            .min(lambda s: movement.chebyshev_distance_room_pos(s, self.room.controller))
                    elif all_structs_near.find({'structureType': STRUCTURE_CONTAINER}):
                        structure = all_structs_near.filter({'structureType': STRUCTURE_CONTAINER}) \
                            .min(lambda s: movement.chebyshev_distance_room_pos(s, self.room.controller))
            if structure:
                structure_id = structure.id
            else:
                structure_id = -1
            self._upgrader_source = structure
            self.store_cached_property("upgrader_source_id", structure_id, 15)
        return self._upgrader_source

    def get_extra_fill_targets(self):
        if self._extra_fill_targets is None:
            extra_targets = []
            cont = self.get_upgrader_energy_struct()
            if cont and cont.structureType == STRUCTURE_CONTAINER:
                extra_targets.push(cont)
            self._extra_fill_targets = _.filter(extra_targets,
                                                lambda s: (s.storeCapacity and _.sum(s.store) < s.storeCapacity)
                                                          or (s.energyCapacity and s.energy < s.energyCapacity))
        return self._extra_fill_targets

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
                if not _.find(self.find_in_range(FIND_MY_CREEPS, 1, source),
                              lambda c: c.memory.role == role_miner):
                    all_placed = False
                    break
            self._all_big_miners_placed = all_placed
        return self._all_big_miners_placed

    def get_trying_to_get_full_storage_use(self):
        """
        :rtype: bool
        """
        if self._trying_to_get_full_storage_use is None:
            self._trying_to_get_full_storage_use = self.room.storage and (
                self.room.storage.store[RESOURCE_ENERGY] >= _min_stored_energy_to_draw_from_before_refilling
                or (
                    self.are_all_big_miners_placed and self.work_mass >=
                    _min_work_mass_per_source_for_full_storage_use * len(self.sources)
                )
            )
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
            elif self.room.storage and not self.room.storage.storeCapacity:
                if self.room.storage.store.energy > 0:
                    self._full_storage_use = True
                else:
                    self._full_storage_use = False
                    if not self.room.storage.my:
                        self.room.storage.destroy()
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

    def being_bootstrapped(self):
        if self.rcl >= 6 or not self.sponsor_name or self.spawn:
            return False
        sponsor = self.hive_mind.get_room(self.sponsor_name)
        if not sponsor or not sponsor.my or not sponsor.spawn:
            return False
        return True

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
        if self.rcl < 4 or not self.room.storage or self.room.storage.storeCapacity <= 0:
            return False
        # TODO: constant here and below in upgrader_work_mass
        if self.conducting_siege() and (self.room.storage.store.energy < 100 * 1000 or (
                        self.rcl < 7 and self.room.storage.store.energy < 500 * 1000)):
            return True  # Don't upgrade while we're taking someone down.
        if self.rcl >= 8:
            if self.mem.upgrading_paused and self.room.storage.store.energy > _rcl8_energy_to_resume_upgrading:
                self.mem.upgrading_paused = False
            if not self.mem.upgrading_paused and self.room.storage.store.energy < _rcl8_energy_to_pause_upgrading:
                self.mem.upgrading_paused = True
        else:
            if self.mem.upgrading_paused and self.room.storage.store.energy > _energy_to_resume_upgrading:
                self.mem.upgrading_paused = False
            if not self.mem.upgrading_paused and self.room.storage.store.energy < _energy_to_pause_upgrading:
                self.mem.upgrading_paused = True
        return not not self.mem.upgrading_paused

    def under_siege(self):
        return not not self.mem.attack

    def any_remotes_under_siege(self):
        return self.mem.attack or self.mem.remotes_attack

    def remote_under_siege(self, flag):
        return self.any_remotes_under_siege() \
               and flag.pos.roomName != self.room_name \
               and (not self.mem.remotes_safe or not self.mem.remotes_safe.includes(flag.pos.roomName))

    def upgrading_deprioritized(self):
        deprioritized = self.get_cached_property("upgrading_deprioritized")
        if deprioritized is not None:
            return deprioritized
        deprioritized = not not (
            (
                self.upgrading_paused()
                or (self.rcl < 4 and len(self.subsidiaries) and not self.being_bootstrapped())
                or (not self.spawn and not self.being_bootstrapped())
                or (self.under_siege() and (not self.room.storage or self.room.storage.storeCapacity))
            )
            and self.room.controller.ticksToDowngrade >= 1000
            and (not self.room.storage or self.room.storage.store.energy < 700 * 1000)
        )
        self.store_cached_property("upgrading_deprioritized", deprioritized, 15)
        return deprioritized

    def building_paused(self):
        if self._building_paused is None:
            if self.rcl < 4 or not self.room.storage or self.room.storage.storeCapacity <= 0:
                self._building_paused = False
            elif self.conducting_siege() and self.rcl < 7:
                self._building_paused = True  # Don't build while we're taking someone down.
            else:
                if self.mem.building_paused and self.room.storage.store.energy > _energy_to_resume_building:
                    self.mem.building_paused = False
                if not self.mem.building_paused and self.room.storage.store.energy < _energy_to_pause_building:
                    self.mem.building_paused = True
                if self.mem.building_paused:
                    # this is somewhat expensive, so do this calculation last
                    # If building is paused and we have fewer spawns/extensions than spawn/extension build sites, don't
                    # pause building!
                    self._building_paused = self.spawn and (
                        len(_.filter(self.find(FIND_MY_STRUCTURES),
                                     lambda s: s.structureType == STRUCTURE_SPAWN or
                                               s.structureType == STRUCTURE_EXTENSION))
                        > len(_.filter(self.find(FIND_MY_CONSTRUCTION_SITES),
                                       lambda s: s.structureType == STRUCTURE_SPAWN or
                                                 s.structureType == STRUCTURE_EXTENSION))
                    )
                else:
                    self._building_paused = False
        return self._building_paused

    def overprioritize_building(self):
        if self._overprioritize_building is None:
            if self.spawn:
                prioritize = ((self.room.energyCapacityAvailable < 550
                               and self.get_open_source_spaces() < len(self.sources) * 2)
                              or (self.rcl >= 3 and not len(self.defense.towers()))
                              or (self.rcl >= 3 and self.room.energyCapacityAvailable < 650)
                              or (self.rcl >= 4 and self.room.energyCapacityAvailable < 1300)) \
                             and len(self.building.next_priority_construction_targets()) \
                             and (self.room.controller.ticksToDowngrade > 100)
            else:
                prioritize = not self.being_bootstrapped()
            self._overprioritize_building = prioritize
        return self._overprioritize_building

    def _any_closest_to_me(self, flag_type):
        for flag in flags.find_flags_global(flag_type):
            if 'sponsor' in flag.memory:
                if flag.memory.sponsor == self.room_name:
                    return True
            else:
                # We would do .split('_', 1), but the Python->JS conversion makes that more expensive than just this
                possible_sponsor = str(flag.name).split('_')[0]
                if possible_sponsor in Game.rooms:
                    if possible_sponsor == self.room_name:
                        return True
                else:
                    if self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name:
                        return True

        return False

    def conducting_siege(self):
        if self._conducting_siege is None:
            self._conducting_siege = Game.cpu.bucket > 4500 and not not (
                (self._any_closest_to_me(flags.TD_D_GOAD) or self._any_closest_to_me(flags.ATTACK_POWER_BANK)
                 or self._any_closest_to_me(flags.ATTACK_DISMANTLE))
                and self._any_closest_to_me(flags.TD_H_H_STOP) and self._any_closest_to_me(flags.TD_H_D_STOP)
            )
        return self._conducting_siege

    def get_max_mining_op_count(self):
        if not self.my:
            print("[{}] WARNING: get_max_mining_op_count called for non-owned room!".format(self.room_name))
            return 0
        sources = len(self.sources)

        if sources <= 1:
            if len(self.spawns) < 2:
                return 5
            elif self.rcl == 7:
                return 7
            elif self.mining_ops_paused():
                # We only want to *actually* pause them at RCL8:
                return 0
            else:
                return 9
        else:
            if len(self.spawns) < 2:
                return 5
            elif self.rcl == 7:
                return 6
            elif self.mining_ops_paused():
                # We only want to *actually* pause them at RCL8:
                return 0
            else:
                return 9

    def get_max_sane_wall_hits(self):
        """
        :rtype: int
        """
        return _rcl_to_sane_wall_hits[self.rcl - 1] or 0  # 1-to-0-based index

    def get_min_sane_wall_hits(self):
        return _rcl_to_min_wall_hits[self.rcl - 1] or 0  # 1-to-0 based index

    __pragma__('nofcall')

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

    def get_target_wall_defender_count(self):
        if self.under_siege():
            rampart_count = _.sum(self.find(FIND_MY_STRUCTURES),
                                  lambda s:
                                  s.structureType == STRUCTURE_RAMPART
                                  and movement.is_block_empty(self, s.pos.x, s.pos.y))
            if len(defense.stored_hostiles_near(self.room_name)):  # Here or neighboring rooms
                flag_count = _.sum(self.find(FIND_FLAGS),
                                   lambda s:
                                   s.color == COLOR_GREEN
                                   and (s.secondaryColor == COLOR_GREEN
                                        or s.secondaryColor == COLOR_RED))
            else:
                flag_count = _.sum(self.find(FIND_FLAGS),
                                   lambda s:
                                   s.color == COLOR_GREEN
                                   and s.secondaryColor == COLOR_GREEN)
            return min(rampart_count, flag_count)
        else:
            return 0

    def get_target_simple_defender_count(self, first=False):
        """
        :rtype: int
        """
        if self.under_siege():
            return 0
        if (self._first_simple_target_defender_count if first else self._target_defender_count) is None:
            needed_local = math.ceil(_.sum(self.defense.dangerous_hostiles(),
                                           lambda h: self.defense.danger_level(h) >= 2) / 3)

            if first:
                self._first_simple_target_defender_count = needed_local
            else:
                invaded_rooms = new_map()
                for h in self.defense.remote_hostiles():
                    if h.user == INVADER_USERNAME:
                        if h.heal:
                            need = 8
                        elif h.ranged and not h.attack:
                            need = -100  # Don't try to defend against kiting invaders
                        else:
                            need = 1
                        if invaded_rooms.has(h.room):
                            invaded_rooms.set(h.room, invaded_rooms.get(h.room) + need)
                        else:
                            invaded_rooms.set(h.room, need)
                needed_for_mines = _.sum(list(invaded_rooms.values()), lambda v: max(0, math.ceil(v / 3)))
                self._target_defender_count = needed_local + needed_for_mines
        return self._first_simple_target_defender_count if first else self._target_defender_count

    def get_target_colonist_work_mass(self):
        if self.under_siege():
            return 0
        if not self._target_colonist_work_mass:
            worker_mass = spawning.max_sections_of(self, creep_base_worker)
            hauler_mass = spawning.max_sections_of(self, creep_base_half_move_hauler)
            needed = 0
            mineral_steal = 0
            for room in self.subsidiaries:
                if not room.room.controller.safeMode \
                        and _.find(room.defense.dangerous_hostiles(),
                                   lambda c: c.hasBodyparts(ATTACK) or c.hasBodyparts(RANGED_ATTACK)):
                    continue
                distance = len(self.hive_mind.honey.find_path(
                    self.spawn, __new__(RoomPosition(25, 25, room.room_name)), {'range': 15}))
                room_work_mass = 0
                rt_map = room.rt_map
                for role in Object.keys(room.work_mass_map):
                    room_work_mass += room.work_mass_map[role]
                    # manual copy of work_mass_of_replacements_currently_needed_for which accounts for distance to room
                    if role in rt_map and len(rt_map[role]):
                        for creep, replacement_time in rt_map[role]:
                            if Game.creeps[creep] and not Memory.creeps[creep].replacement \
                                    and replacement_time + distance <= Game.time:
                                room_work_mass -= spawning.work_count(Game.creeps[creep])
                            else:
                                break  # this is sorted
                if room.room.storage:
                    target = min(10, 5 + room.room.storage.store.energy / 20 * 1000) * worker_mass
                elif len(room.sources) >= 2:
                    target = 5 * worker_mass
                else:
                    target = 10
                needed += max(0, target - room_work_mass)
                if room.room.storage and _.sum(room.room.storage.store) > room.room.storage.store.energy \
                        and room.room.storage.storeCapacity <= 0:
                    mineral_steal += hauler_mass
            if Game.cpu.bucket < 4000:
                needed = 0
            self._target_colonist_work_mass = needed
            self._target_mineral_steal_mass = mineral_steal
        return self._target_colonist_work_mass

    def get_target_mineral_steal_mass(self):
        if not self._target_mineral_steal_mass:
            self.get_target_colonist_work_mass()
        return self._target_mineral_steal_mass

    def get_target_spawn_fill_backup_carry_mass(self):
        # TODO: 7 should be a constant.
        if self.full_storage_use or self.are_all_big_miners_placed:
            if self.full_storage_use and (self.are_all_big_miners_placed or
                                              (self.work_mass > 25 and self.role_count(role_tower_fill) > 0
                                               and self.role_count(role_spawn_fill) > 0)):
                return 0
            else:
                return 3
        elif self.rcl < 3:
            return len(self.sources) * spawning.max_sections_of(self, creep_base_worker)
        else:
            return math.floor(self.get_target_total_spawn_fill_mass() / 2)

    def get_target_spawn_fill_mass(self):
        if self._target_spawn_fill_mass is None:
            if self.full_storage_use or self.are_all_big_miners_placed:
                tower_fill = self.carry_mass_of(role_tower_fill)
                total_mass = math.ceil(self.get_target_total_spawn_fill_mass())
                if self.rcl < 4 or not self.room.storage:
                    fill_size = fit_num_sections(total_mass,
                                                 spawning.max_sections_of(self, creep_base_hauler), 0, 2)
                    for flag in self.mining.local_mines:
                        sitting = self.mining.energy_sitting_at(flag)
                        if sitting > 1000:
                            total_mass += math.ceil(sitting / 500) * fill_size
                if self.under_siege() or self.mem.prepping_defenses:
                    self._target_spawn_fill_mass = total_mass
                else:
                    self._target_spawn_fill_mass = max(0, min(1, total_mass), total_mass - tower_fill)

            else:
                self._target_spawn_fill_mass = 0
        return self._target_spawn_fill_mass

    def get_target_total_spawn_fill_mass(self):
        if self._total_needed_spawn_fill_mass is None:
            if self.room.energyCapacityAvailable < 550 and self.get_open_source_spaces() < len(self.sources) * 2:
                self._total_needed_spawn_fill_mass = 3
            else:
                self._total_needed_spawn_fill_mass = math.pow(self.room.energyCapacityAvailable / 50.0 * 200, 0.3)
                if self.under_siege() or self.mem.prepping_defenses:
                    self._total_needed_spawn_fill_mass *= 1.5
                elif len(self.mining.active_mines) < 2:  # This includes local sources.
                    self._total_needed_spawn_fill_mass /= 2
        return self._total_needed_spawn_fill_mass

    def get_target_spawn_fill_size(self):
        if self.under_siege() or self.mem.prepping_defenses:
            return fit_num_sections(self.get_target_total_spawn_fill_mass(),
                                    spawning.max_sections_of(self, creep_base_hauler))
        else:
            return fit_num_sections(self.get_target_total_spawn_fill_mass(),
                                    spawning.max_sections_of(self, creep_base_hauler), 0, 2)

    def get_target_builder_work_mass(self):
        if not self.building_paused():
            base_num = self.building.get_target_num_builders()
            if base_num > 0:
                extra = 0
                if self.room.storage:
                    if self.mem.prepping_defenses:
                        # purposefully a smaller threshold than upgrading has
                        overflow = min(_.sum(self.room.storage.store) - 400 * 1000,
                                       self.room.storage.store.energy - 100 * 1000)
                    else:
                        overflow = min(_.sum(self.room.storage.store) - 500 * 1000,
                                       self.room.storage.store.energy - 150 * 1000)
                    if not self.room.storage.storeCapacity:
                        overflow = self.room.storage.store.energy
                    if overflow > 0:
                        # TODO: utility method for "empty storage asap"
                        if not self.room.storage.storeCapacity:
                            extra = min(25, math.floor(overflow / (20 * 1000)))
                        else:
                            extra = min(5, math.floor(overflow / (20 * 1000)))
                    elif overflow < -100 * 1000 and base_num > 2:
                        base_num = 2
                if self.rcl < 8:
                    if self.rcl < 4 and self.room.energyCapacityAvailable < 550:
                        worker_size = 1
                    else:
                        worker_size = max(2, min(8, spawning.max_sections_of(self, creep_base_worker)))
                    return (base_num + extra) * worker_size
                else:
                    if extra > 0:
                        worker_size = spawning.max_sections_of(self, creep_base_worker)
                        return (base_num + extra) * worker_size
                    else:
                        # Since we have a constant 15-part upgrader going at RCL8, workers have to be more of the
                        # 'scaling' factor.
                        worker_size = min(4, spawning.max_sections_of(self, creep_base_worker))
                        return 1 * worker_size
        return 0

    def get_open_source_spaces(self):
        if 'oss' not in self.mem:
            oss = 0
            for source in self.sources:
                for x in range(source.pos.x - 1, source.pos.x + 2):
                    for y in range(source.pos.y - 1, source.pos.y + 2):
                        if movement.is_block_empty(self, x, y):
                            oss += 1
            self.mem.oss = oss
        return self.mem.oss

    def get_open_source_spaces_around(self, source):
        key = 'oss-{}'.format(source.id)
        if key not in self.mem:
            oss = 0
            for x in range(source.pos.x - 1, source.pos.x + 2):
                for y in range(source.pos.y - 1, source.pos.y + 2):
                    if movement.is_block_empty(self, x, y):
                        oss += 1
            self.mem[key] = oss
        return self.mem[key]

    def get_target_upgrade_fill_mass(self):
        if self._target_upgrade_fill_work_mass is None:
            target = self.get_upgrader_energy_struct()
            if not target or target.structureType != STRUCTURE_CONTAINER:
                self._target_upgrade_fill_work_mass = 0
            elif self.upgrading_deprioritized() or self.overprioritize_building():
                if self.room.controller.ticksToDowngrade > 5000:
                    self._target_upgrade_fill_work_mass = 0
                else:
                    self._target_upgrade_fill_work_mass = 1
            elif _.sum(target.store) >= target.storeCapacity * 0.5 and self.role_count(role_upgrader) <= 1:
                self._target_upgrade_fill_work_mass = 0
            else:
                # TODO: dynamic calculation here
                self._target_upgrade_fill_work_mass = min(8, spawning.max_sections_of(self, creep_base_hauler))
                if self.full_storage_use:
                    if Memory.hyper_upgrade:
                        extra = min(_.sum(self.room.storage.store) - 100 * 1000,
                                    self.room.storage.store.energy - 50 * 1000)
                    else:
                        extra = min(_.sum(self.room.storage.store) - 500 * 1000,
                                    self.room.storage.store.energy - 150 * 1000)
                    if extra > 0:
                        self._target_upgrade_fill_work_mass *= 2
        return self._target_upgrade_fill_work_mass

    def get_target_upgrader_work_mass(self):
        if self._target_upgrader_work_mass is None:
            base = self.get_variable_base(role_upgrader)
            sections = spawning.max_sections_of(self, base)
            if base is creep_base_full_upgrader:
                worker_size = max(4, 2 * sections)
            else:
                # A half (0.5) section represents one work and no carry.
                worker_size = max(1, math.ceil(sections))

            if self.upgrading_deprioritized() or self.overprioritize_building():
                if self.room.controller.ticksToDowngrade <= 5000:
                    wm = 1
                else:
                    wm = 0
                self._target_upgrader_work_mass = wm
                return wm  # Upgrading auto-turns-off being deprioritized if energy is above 700 * 1000
            elif self.rcl == 8:
                if _.sum(self.room.storage.store) > 700 * 1000 \
                        and self.room.storage.store.energy > 200 * 1000:
                    wm = 7
                else:
                    wm = max(2, min(7, math.floor(self.room.storage.store.energy / (50 * 1000))))
            elif self.mining_ops_paused():
                wm = worker_size * 4
            elif self.trying_to_get_full_storage_use:
                wm = 4
            elif self.room.energyCapacityAvailable < 550:
                wm = self.get_open_source_spaces() * worker_size
                for source in self.sources:
                    energy = _.sum(self.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount')
                    wm += energy / 200.0
            else:
                wm = len(self.sources) * 2 * worker_size
            if self.full_storage_use:
                if self.room.storage.storeCapacity:
                    if self.mem.prepping_defenses:
                        extra = min(_.sum(self.room.storage.store) - 600 * 1000,
                                    self.room.storage.store.energy - 200 * 1000)
                    elif Memory.hyper_upgrade:
                        extra = min(_.sum(self.room.storage.store) - 100 * 1000,
                                    self.room.storage.store.energy - 50 * 1000)
                    else:
                        extra = min(_.sum(self.room.storage.store) - 500 * 1000,
                                    self.room.storage.store.energy - 150 * 1000)
                else:
                    extra = 200 * 1000 + self.room.storage.store.energy
                if extra > 0:
                    if Memory.hyper_upgrade:
                        wm += math.ceil(extra / 1000)
                    else:
                        wm += math.floor(extra / 2000)
                    if extra >= 200 * 1000:
                        wm += math.ceil((extra - 200 * 1000) / 400)
                        print("[{}] Spawning more emergency upgraders! Target work mass: {} (worker_size: {})"
                              .format(self.room_name, wm, worker_size))

            if self.rcl >= 8:
                wm = min(wm, 15)

            # TODO: calculate open spaces near controller to determine this
            if base is creep_base_full_upgrader:
                self._target_upgrader_work_mass = min(wm, worker_size * 4)
            elif self.room.storage and not self.room.storage.storeCapacity:
                self._target_upgrader_work_mass = min(wm, worker_size * 15)
            else:
                self._target_upgrader_work_mass = min(wm, worker_size * 8)
        return self._target_upgrader_work_mass

    def get_upgrader_size(self):
        base = self.get_variable_base(role_upgrader)
        sections = self.get_target_upgrader_work_mass()
        target = self.get_target_upgrader_work_mass()
        if base == creep_base_full_upgrader and target > 1:
            return spawning.ceil_sections(min(sections, target / 2), base)
        else:
            return spawning.ceil_sections(min(sections, target), base)

    def get_builder_size(self):
        base = self.get_variable_base(role_builder)
        if self.rcl < 8:
            return min(8, spawning.max_sections_of(self, base))
        else:
            return min(self.get_target_builder_work_mass(), spawning.max_sections_of(self, base))

    def get_target_tower_fill_mass(self):
        if not self.get_target_spawn_fill_mass():
            return 0
        towers = self.defense.towers()
        if len(towers):
            size = max(1, min(5, spawning.max_sections_of(self, creep_base_hauler))) * 0.75
            return math.ceil(min(size * len(towers), self.get_target_total_spawn_fill_mass()))
        else:
            return 0

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

    def _check_role_reqs(self, role_list):
        """
        Utility function to check the number of creeps in a role, optionally checking the work or carry mass for that
        role instead.
        """
        role_needed = None
        for role, get_ideal, count_carry, count_work in role_list:
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

    def wall_defense(self):
        return self._check_role_reqs([
            [role_wall_defender, self.get_target_wall_defender_count],
        ])

    def _next_needed_local_mining_role(self):
        if spawning.would_be_emergency(self):
            if not self.full_storage_use and not self.are_all_big_miners_placed:
                next_role = self._check_role_reqs([
                    [role_spawn_fill_backup, self.get_target_spawn_fill_backup_carry_mass, True],
                ])
                if next_role is not None:
                    return next_role
            next_role = self._check_role_reqs([
                [role_tower_fill, self.get_target_tower_fill_mass, True],
                [role_spawn_fill, self.get_target_spawn_fill_mass, True],
            ])
            if next_role is not None:
                return next_role

        # if self.room.energyCapacityAvailable < 550:
        #     return self._check_role_reqs([
        #         [role_spawn_fill_backup, self.get_target_spawn_fill_backup_carry_mass, True],
        #     ])
        next_role = self._check_role_reqs([
            [role_defender, lambda: self.get_target_simple_defender_count(True)],
            [role_link_manager, self.get_target_link_manager_count],
        ])
        if next_role is not None:
            return next_role

        mining_role = self.mining.next_mining_role(len(self.sources))
        if mining_role is not None and mining_role.role == role_miner:
            return mining_role

        next_role = self._check_role_reqs([
            [role_tower_fill, self.get_target_tower_fill_mass, True],
            [role_spawn_fill, self.get_target_spawn_fill_mass, True],
            [role_wall_defender, self.get_target_wall_defender_count],
            [role_defender, self.get_target_simple_defender_count],
            [role_colonist, self.get_target_colonist_work_mass, False, True],
        ])
        if next_role is not None:
            return next_role

        if self.room.controller.ticksToDowngrade < 2000:
            upgrader = self._check_role_reqs([
                [role_upgrade_fill, self.get_target_upgrade_fill_mass, True],
                [role_upgrader, self.get_target_upgrader_work_mass, False, True],
            ])
            if upgrader is not None:
                return upgrader
        elif _.get(self, 'room.storage.store.energy', 0) > 800 * 1000:
            overflow_role = self._check_role_reqs([
                [role_builder, self.get_target_builder_work_mass, False, True],
                [role_upgrade_fill, self.get_target_upgrade_fill_mass, True],
                [role_upgrader, self.get_target_upgrader_work_mass, False, True],
            ])
            if overflow_role is not None:
                return overflow_role

        if mining_role is not None:
            return mining_role

        return None

    def _next_needed_local_role(self):
        requirements = [
            [role_upgrade_fill, self.get_target_upgrade_fill_mass, True],
            [role_builder, self.get_target_builder_work_mass, False, True],
            [role_upgrader, self.get_target_upgrader_work_mass, False, True],
            [role_room_reserve, self.get_target_room_reserve_count],
            # TODO: a "first" argument to this which checks energy, then do another one at the end of remote.
            [role_colonist, self.get_target_colonist_work_mass, False, True],
            [role_mineral_steal, self.get_target_mineral_steal_mass, True],
            [role_mineral_hauler, self.minerals.get_target_mineral_hauler_count],
            [role_mineral_miner, self.minerals.get_target_mineral_miner_count],
        ]
        return self._check_role_reqs(requirements)

    def get_max_sections_for_role(self, role):
        max_mass = {
            role_spawn_fill_backup:
                lambda: fit_num_sections(self.get_target_spawn_fill_backup_carry_mass()
                                         if spawning.using_lower_energy_section(self, creep_base_worker)
                                         else spawning.ceil_sections(self.get_target_spawn_fill_backup_carry_mass() / 3,
                                                                     creep_base_worker),
                                         spawning.max_sections_of(self, creep_base_worker)),
            role_link_manager:
                lambda: min(self.get_target_link_manager_count() * 8,
                            spawning.max_sections_of(self, creep_base_hauler)),
            role_spawn_fill: self.get_target_spawn_fill_size,
            role_tower_fill: self.get_target_spawn_fill_size,
            role_upgrader: self.get_upgrader_size,
            role_upgrade_fill: self.get_target_upgrade_fill_mass,
            role_defender: lambda: min(4, spawning.max_sections_of(self, creep_base_defender)),
            role_wall_defender: lambda: min(9, spawning.max_sections_of(self, creep_base_rampart_defense)),
            role_room_reserve:
                lambda: min(2, spawning.max_sections_of(self, creep_base_reserving)),
            role_colonist:
                lambda: spawning.max_sections_of(self, creep_base_worker),
            role_builder: self.get_builder_size,
            role_mineral_miner:
                lambda: min(4, spawning.max_sections_of(self, creep_base_mammoth_miner)),
            role_mineral_hauler:
                lambda: min(10, spawning.max_sections_of(self, creep_base_hauler)),
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
        if role == role_hauler:
            if self.all_paved():
                return creep_base_work_half_move_hauler
            elif self.paving():
                return creep_base_work_full_move_hauler
            else:
                return creep_base_hauler
        elif role == role_upgrader:
            if self.get_upgrader_energy_struct():
                return creep_base_full_upgrader
            else:
                return creep_base_worker
        else:
            return role_bases[role]

    def _next_cheap_military_role(self):
        return self.spawn_one_creep_per_flag(flags.SCOUT, role_scout, creep_base_scout, creep_base_scout, 1)

    def _next_complex_defender(self):
        if self.room.energyCapacityAvailable >= 500:
            flag_list = self.flags_without_target(flags.RANGED_DEFENSE)

            if len(flag_list):
                flag = flag_list[0]
                if flag.name in Memory.flags and flag.memory.heal:
                    base = creep_base_3h
                else:
                    base = creep_base_ranged_offense
                return self.get_spawn_for_flag(role_ranged_offense, base, base, flag, 0)
            return None

    def _next_claim(self):
        if self.room.energyCapacityAvailable >= 650:
            flag_list = self.flags_without_target(flags.CLAIM_LATER)

            def _needs_claim(flag):
                if Memory.enemy_rooms.includes(flag.pos.roomName) and self.room.energyCapacityAvailable < 650 * 5:
                    return False
                elif flag.pos.roomName not in Game.rooms:
                    return True
                else:
                    room = Game.rooms[flag.pos.roomName]
                    if not room.controller or room.controller.my:
                        return False
                    elif room.controller.owner and self.room.energyCapacityAvailable < 650 * 5:
                        return False
                    else:
                        return True

            needed = _.find(flag_list, _needs_claim)
            if needed:
                if Memory.enemy_rooms.includes(needed.pos.roomName):
                    return self.get_spawn_for_flag(role_simple_claim, creep_base_claim_attack,
                                                   creep_base_claim_attack, needed)
                else:
                    return self.get_spawn_for_flag(role_simple_claim, creep_base_claiming,
                                                   creep_base_claiming, needed, 1)
        return None

    def flags_without_target(self, flag_type):
        result = []  # TODO: yield
        for flag in flags.find_flags_global(flag_type):
            if flag.memory.sponsor:
                ours = flag.memory.sponsor == self.room_name
            else:
                # We would do .split('_', 1), but the Python->JS conversion makes that more expensive than just this
                possible_sponsor = str(flag.name).split('_')[0]
                if possible_sponsor in Game.rooms:
                    ours = possible_sponsor == self.room_name
                else:
                    ours = self.hive_mind.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name
            if ours:
                flag_id = "flag-{}".format(flag.name)
                noneol_targeting_count = self.count_noneol_creeps_targeting(target_single_flag, flag_id)
                if noneol_targeting_count < 1:
                    result.append(flag)
        return result

    def get_spawn_for_flag(self, role, half_move_base, full_move_base, flag, max_sections=0):
        if movement.distance_squared_room_pos(self.spawn, flag) > math.pow(200, 2):
            base = full_move_base
        else:
            base = half_move_base
        sections = spawning.max_sections_of(self, base)
        if max_sections:
            sections = min(sections, max_sections)
        if flag.memory.size:
            sections = min(sections, flag.memory.size)
        obj = {
            "role": role,
            "base": base,
            "num_sections": sections,
            "targets": [
                [target_single_flag, "flag-{}".format(flag.name)],
            ]
        }
        if 'boosted' in flag.memory and not flag.memory.boosted:
            obj.memory = {'boosted': 2}
        return obj

    def spawn_one_creep_per_flag(self, flag_type, role, half_move_base, full_move_base, max_sections=0):
        flag_list = self.flags_without_target(flag_type)
        if len(flag_list):
            return self.get_spawn_for_flag(role, half_move_base, full_move_base, flag_list[0], max_sections)
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

        role_obj = self.spawn_one_creep_per_flag(flags.ENERGY_GRAB, role_energy_grab, creep_base_hauler,
                                                 creep_base_hauler)

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
        #         bank = room.look_at(LOOK_STRUCTURES, flag.pos)[0]
        #         if bank and bank.hits < bank.hitsMax * 0.1:
        #             return self.get_spawn_for_flag(role_power_cleanup, creep_base_half_move_hauler,
        #                                            creep_base_hauler, flag)

        return None

    def next_cheap_dismantle_goal(self):
        if self.conducting_siege() or self.under_siege():
            return

        role_obj = self.spawn_one_creep_per_flag(flags.ENERGY_GRAB, role_energy_grab, creep_base_hauler,
                                                 creep_base_hauler)

        if role_obj:
            return role_obj

        role_obj = self.spawn_one_creep_per_flag(flags.ATTACK_DISMANTLE,
                                                 role_simple_dismantle,
                                                 creep_base_dismantler,
                                                 creep_base_full_move_dismantler)
        if role_obj:
            return role_obj

    def reset_planned_role(self):
        del self.mem.next_role
        if not self.spawn:
            sponsor = self.hive_mind.get_room(self.sponsor_name)
            if sponsor and sponsor.spawn:
                if _.sum(self.role_counts) < 3 and sponsor.next_role is None:
                    sponsor.reset_planned_role()

    def plan_next_role(self):
        if not self.my:
            return None
        if self.mem.completely_sim_testing:
            funcs_to_try = [
                lambda: self._check_role_reqs([
                    [role_spawn_fill, self.get_target_spawn_fill_mass, True],
                ]),
                self.wall_defense,
                self._next_cheap_military_role,
                self._next_tower_breaker_role,
                self._next_complex_defender,
            ]
        else:
            funcs_to_try = [
                self._next_needed_local_mining_role,
                self.wall_defense,
                self._next_cheap_military_role,
                self.next_cheap_dismantle_goal,
                self._next_complex_defender,
                self.mining.next_mining_role,
                self._next_tower_breaker_role,
                self._next_needed_local_role,
                self._next_claim,
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
            self.mem.next_role = next_role
        else:
            print("[{}] All creep targets reached!".format(self.room_name))
            self.mem.next_role = None

    def get_next_role(self):
        if self.mem.next_role is undefined:
            self.plan_next_role()
            # This function modifies the role.
            spawning.validate_role(self.mem.next_role)
        return self.mem.next_role

    def toString(self):
        return "RoomMind[room_name: {}, my: {}, using_storage: {}, conducting_siege: {}]".format(
            self.room_name, self.my, self.full_storage_use, self.conducting_siege())

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
    "find",
    "find_at",
    "look_at",
    "find_in_range",
    "find_closest_by_range",
    "look_for_in_area_around",
    "register_to_role",
    "recalculate_roles_alive",
    "get_next_replacement_name",
    "next_x_to_die_of_role",
    "extra_creeps_with_carry_in_role",
    "extra_creeps_with_work_in_role",
    "register_new_replacing_creep",
    "replacements_currently_needed_for",
    "count_noneol_creeps_targeting",
    "carry_mass_of_replacements_currently_needed_for",
    "work_mass_of_replacements_currently_needed_for",
    "precreep_tick_actions",
    "reassign_roles",
    "get_position",
    "get_sources",
    "get_spawns",
    "get_creeps",
    "get_upgrader_energy_struct",
    "get_extra_fill_targets",
    "get_work_mass",
    "get_if_all_big_miners_are_placed",
    "get_trying_to_get_full_storage_use",
    "get_full_storage_use",
    "being_bootstrapped",
    "mining_ops_paused",
    "upgrading_deprioritized",
    "building_paused",
    "overprioritize_building",
    "_any_closest_to_me",
    "conducting_siege",
    "get_target_link_manager_count",
    "get_target_wall_defender_count",
    "get_target_simple_defender_count",
    "get_target_colonist_work_mass",
    "get_target_mineral_steal_mass",
    "get_target_spawn_fill_backup_carry_mass",
    "get_target_spawn_fill_mass",
    "get_target_total_spawn_fill_mass",
    "get_target_builder_work_mass",
    "get_open_source_spaces",
    "get_target_upgrade_fill_mass",
    "get_target_upgrader_work_mass",
    "get_upgrader_size",
    "get_target_tower_fill_mass",
    "get_target_room_reserve_count",
    "get_next_spawn_fill_body_size",
    "_check_role_reqs",
    "wall_defense",
    "_next_needed_local_mining_role",
    "_next_needed_local_role",
    "get_max_sections_for_role",
    "get_variable_base",
    "_next_cheap_military_role",
    "_next_complex_defender",
    "flags_without_target",
    "get_spawn_for_flag",
    "spawn_one_creep_per_flag",
    "_next_tower_breaker_role",
    "next_cheap_dismantle_goal",
    "plan_next_role",
    # "recalculate_roles_alive",
    # "precreep_tick_actions",
    # "poll_hostiles",
    # "plan_next_role",
    # "find",
    # "find_at",
    # "find_in_range",
    # "find_closest_by_range",
    # "look_at",
    # "look_for_in_area_around",
])
