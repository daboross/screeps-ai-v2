import math
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Tuple, Union, cast

import random

from cache import consistency
from constants import *
from constants.memkeys.room import *
from creep_management import creep_wrappers, spawning
from creep_management.spawning import fit_num_sections
from empire import stored_data
from jstools import errorlog
from jstools.js_set_map import new_map
from jstools.screeps import *
from position_management import flags
from rooms.building import ConstructionMind
from rooms.defense import RoomDefense
from rooms.links import LinkingMind
from rooms.minerals import MineralMind
from rooms.mining import MiningMind
from rooms.room_constants import *
from rooms.squads import SquadTactics
from utilities import hostile_utils, movement, naming, rndrs, speech
from utilities.positions import clamp_room_x_or_y, parse_xy_arguments

if TYPE_CHECKING:
    from empire.hive import HiveMind
    from creeps.base import RoleBase

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


class RoomMind:
    """
    :type hive: empire.hive.HiveMind
    :type room: Room
    :type name: str
    :type building: Optional[ConstructionMind]
    :type links: Optional[LinkingMind]
    :type mining: Optional[MiningMind]
    :type minerals: Optional[MineralMind]
    :type squads: Optional[SquadTactics]
    :type subsidiaries: list[RoomMind]
    :type sources: list[Source]
    :type creeps: list[Creep]
    :type work_mass: int
    :type trying_to_get_full_storage_use: bool
    :type full_storage_use: bool
    :type max_sane_wall_hits: int
    :type min_sane_wall_hits: int
    """

    def __init__(self, hive, room):
        # type: (HiveMind, Room) -> None
        self.hive = hive
        self.room = room  # type: Room
        Object.defineProperty(self, 'name', {'value': self.room.name})
        __pragma__('skip')
        self.name = str(self.room.name)
        __pragma__('noskip')
        self.my = room.controller and room.controller.my
        if self.my:
            self.rcl = self.room.controller.level
            self.building = ConstructionMind(self)  # type: Optional[ConstructionMind]
            self.links = LinkingMind(self)  # type: Optional[LinkingMind]
            self.mining = MiningMind(self)  # type: Optional[MiningMind]
            self.minerals = MineralMind(self)  # type: Optional[MineralMind]
            self.squads = SquadTactics(self)  # type: Optional[SquadTactics]
        else:
            self.rcl = 0
            __pragma__('skip')
            self.building = None  # type: Optional[ConstructionMind]
            self.links = None  # type: Optional[LinkingMind]
            self.mining = None  # type: Optional[MiningMind]
            self.minerals = None  # type: Optional[MineralMind]
            self.squads = None  # type: Optional[SquadTactics]
            __pragma__('noskip')

        self.defense = RoomDefense(self)
        self.subsidiaries = []
        __pragma__('skip')
        # properties that could exist for any room
        self._position = undefined  # type: Optional[Tuple[int, int]]
        self._sources = undefined  # type: Optional[List[Source]]
        self._spawns = undefined  # type: Optional[List[StructureSpawn]]
        self._spawn = undefined  # type: Optional[StructureSpawn]
        self._unique_owned_index = undefined  # type: Optional[int]
        self._paving = undefined  # type: Optional[bool]

        # properties generally set via a poll in hive mind
        self._creeps = undefined  # type: Optional[List[Creep]]
        self._remote_mining_operations = undefined  # type: Optional[List[Flag]]

        # properties that are purely based on per-tick polling
        self._work_mass = undefined  # type: Optional[Dict[str, int]]
        self._any_miners = undefined  # type: Optional[bool]
        self._all_miners = undefined  # type: Optional[bool]
        self._trying_to_get_full_storage_use = undefined  # type: Optional[bool]
        self._full_storage_use = undefined  # type: Optional[bool]
        self._smallest_wall_hits = undefined  # type: Optional[int]

        # properties which represent some multi-tick state
        self._upgrader_source = undefined  # type: Optional[Structure]
        self._extra_fill_targets = undefined  # type: Optional[List[Structure]]
        self._building_paused = undefined  # type: Optional[bool]
        self._upgrading_paused = undefined  # type: Optional[bool]
        self._overprioritize_building = undefined  # type: Optional[bool]
        self._conducting_siege = undefined  # type: Optional[bool]

        # role target counts
        self._target_link_managers = undefined  # type: Optional[int]
        self._target_defender_count = undefined  # type: Optional[int]
        self._first_simple_target_defender_count = undefined  # type: Optional[int]
        self._target_colonist_work_mass = undefined  # type: Optional[int]
        self._target_mineral_steal_mass = undefined  # type: Optional[int]
        self._target_room_reserve_count = undefined  # type: Optional[int]
        self._target_spawn_fill_mass = undefined  # type: Optional[int]
        self._target_upgrader_work_mass = undefined  # type: Optional[int]
        self._target_upgrade_fill_work_mass = undefined  # type: Optional[int]
        self._total_needed_spawn_fill_mass = undefined  # type: Optional[int]
        self._target_builder_work_mass = undefined  # type: Optional[int]
        __pragma__('noskip')

        # Other properties to calculate for every room
        self._find_cache = new_map()
        # source keeper rooms are hostile
        self.hostile = not room.controller or (room.controller.owner and not room.controller.my)
        if room.controller and room.controller.owner:
            enemy_structures = _.find(
                self.find(FIND_HOSTILE_STRUCTURES),
                lambda s: s.structureType == STRUCTURE_SPAWN or s.structureType == STRUCTURE_TOWER
            )

            self.enemy = not room.controller.my \
                         and not Memory.meta.friends.includes(self.room.controller.owner.username) \
                         and enemy_structures
            if self.enemy:
                stored = stored_data.get_data(self.name)
                if not stored or not stored.owner:
                    stored_data.update_data(self.room)
        else:
            self.enemy = False
        if mem_key_sponsor in self.mem:
            self.sponsor_name = self.mem[mem_key_sponsor]
        else:
            self.sponsor_name = None

    __pragma__('fcall')

    def _get_mem(self):
        # type: () -> _MemoryValue
        return self.room.memory

    mem = property(_get_mem)

    def get_cached_property(self, name):
        # type: (str) -> Optional[_MemoryValue]
        if not self.mem[mem_key_cache]:
            return None
        prop_mem = self.mem[mem_key_cache][name]
        if prop_mem and prop_mem.dead_at > Game.time:
            return prop_mem.value
        else:
            return None

    def store_cached_property(self, name, value, ttl):
        # type: (str, Any, int) -> None
        if not self.mem[mem_key_cache]:
            self.mem[mem_key_cache] = {}
        self.mem[mem_key_cache][name] = {"value": value, "dead_at": Game.time + ttl}

    def store_cached_property_at(self, name, value, dead_at):
        # type: (str, Any, int) -> None
        if not self.mem[mem_key_cache]:
            self.mem[mem_key_cache] = {}
        self.mem[mem_key_cache][name] = {"value": value, "dead_at": dead_at}

    def delete_cached_property(self, name):
        # type: (str) -> None
        if not self.mem[mem_key_cache]:
            return
        del self.mem[mem_key_cache][name]

    def expire_property_next_tick(self, name):
        # type: (str) -> None
        if not self.mem[mem_key_cache]:
            return
        if name not in self.mem[mem_key_cache]:
            return
        self.mem[mem_key_cache][name].dead_at = Game.time + 1

    def find(self, parameter):
        # type: (int) -> List[RoomObject]
        if self._find_cache.has(parameter):
            return self._find_cache.get(parameter)
        else:
            # this is patched in here because we pretty much never want to find hostile creeps besides like this:
            if parameter == FIND_HOSTILE_CREEPS and len(Memory.meta.friends):
                result = self.room.find(FIND_HOSTILE_CREEPS, {
                    "filter": lambda c: not Memory.meta.friends.includes(c.owner.username.toLowerCase())
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

    def look_at(self, look_type, pos, optional_y=None):
        # type: (str, Union[RoomPosition, int], Optional[int]) -> List[RoomObject]
        x, y, room_name = parse_xy_arguments(pos, optional_y)
        if room_name is not None and room_name != self.name:
            room = self.hive.get_room(room_name)
            if room:
                return room.look_at(look_type, x, y)
            else:
                return []
        if x > 49 or x < 0 or y > 49 or y < 0:
            print('[{}] warning: looked for {} at {}, {},{}'.format(self.name, look_type, self.name, x, y))
            return []
        result = self.room.lookForAt(look_type, x, y)
        return result

    def find_in_range(self, find_type, find_range, pos, optional_y=None):
        # type: (int, int, Union[RoomPosition, int], Optional[int]) -> List[RoomObject]
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
        if room_name is not None and room_name != self.name:
            room = self.hive.get_room(pos.roomName)
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
        # type: (int, RoomPosition, Union[Dict[str, Any], Callable[[RoomObject], bool], None]) -> Optional[RoomObject]
        """
        Looks for something in this room closest the the given position, and caches the result for this tick.

        This is meant as a drop-in replacement for pos.findClosestByRange()

        :param find_type: thing to look for, one of the FIND_* constants
        :type find_type: str
        :param pos: The position to look for at
        :type pos: RoomPosition | RoomObject
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
        closest_distance = Infinity
        closest_element = None
        for element in raw_find_results:
            distance = movement.chebyshev_distance_room_pos(pos, element.pos)
            if distance < closest_distance:
                closest_element = element
                closest_distance = distance
        return closest_element

    def look_for_in_area_around(self, look_type, pos, look_range):
        # type: (str, RoomPosition, int) -> List[Dict[str, RoomObject]]
        """
        Runs Room.lookForAtArea(look_type, ..., true) on an area a specific range around the pos, ensuring to clamp
        positions to relative room positions
        :param look_type:
        :param pos:
        :param look_range:
        :return:
        """
        return self.room.lookForAtArea(look_type,
                                       clamp_room_x_or_y(pos.y - look_range),
                                       clamp_room_x_or_y(pos.x - look_range),
                                       clamp_room_x_or_y(pos.y + look_range),
                                       clamp_room_x_or_y(pos.x + look_range),
                                       True)

    def get_position(self):
        # type: () -> Tuple[int, int]
        if '_position' not in self:
            self._position = movement.parse_room_to_xy(self.room.name)
        return self._position

    def get_sources(self):
        # type: () -> List[Source]
        if '_sources' not in self:
            self._sources = self.find(FIND_SOURCES)  # type: List[Source]
        return self._sources

    def get_spawns(self):
        # type: () -> List[StructureSpawn]
        if '_spawns' not in self:
            self._spawns = self.find(FIND_MY_SPAWNS)  # type: List[StructureSpawn]
        return self._spawns

    def get_spawn(self):
        # type: () -> StructureSpawn
        if '_spawn' not in self:
            self._spawn = self.spawns[0] or None
        return self._spawn

    def get_creeps(self):
        # type: () -> List[Creep]
        if '_creeps' not in self:
            if self.my and not self.hive.has_polled_for_creeps:
                print("[{}] Warning: tried to retrieve creeps of room {} before calling poll_all_creeps!"
                      .format(self.name, self.name))
                creeps = []
                for name in Object.keys(Game.creeps):
                    creep = Game.creeps[name]
                    if creep.memory.home == self.name:
                        creeps.append(creep)
                self._creeps = creeps
            else:
                self._creeps = []
        return self._creeps

    def get_unique_owned_index(self):
        # type: () -> int
        if '_unique_owned_index' not in self:
            if self.my:
                if '_owned_rooms_index' not in Memory.meta:
                    Memory.meta._owned_rooms_index = _(self.hive.my_rooms).sortByOrder(
                        [
                            'rcl',
                            lambda r: r.position[0],
                            lambda r: r.position[1],
                        ],
                        [
                            'desc',
                            'asc',
                            'asc',
                        ]
                    ).pluck('name').value()
                    index = Memory.meta._owned_rooms_index.indexOf(self.name)
                else:
                    index = Memory.meta._owned_rooms_index.indexOf(self.name)
                    if index == -1:
                        index = Memory.meta._owned_rooms_index.push(self.name) - 1
                self._unique_owned_index = index
            else:
                self._unique_owned_index = -1
        return self._unique_owned_index

    def _get_remote_mining_operations(self):
        # type: () -> List[Flag]
        if '_remote_mining_operations' not in self:
            if self.my:
                self.hive.poll_remote_mining_flags()
            else:
                print("[{}] Warning: accessing remote mining operations of unowned room {}."
                      .format(self.name, self.name))
                self._remote_mining_operations = []
        return self._remote_mining_operations

    possible_remote_mining_operations = property(_get_remote_mining_operations)

    def _get_role_counts(self):
        # type: () -> Dict[str, int]
        if not self.mem[mem_key_creeps_by_role]:
            self.recalculate_roles_alive()
        return self.mem[mem_key_creeps_by_role]

    role_counts = property(_get_role_counts)

    def _get_work_mass(self):
        # type: () -> Dict[str, int]
        if not self.mem[mem_key_work_parts_by_role]:
            self.recalculate_roles_alive()
        return self.mem[mem_key_work_parts_by_role]

    work_mass_map = property(_get_work_mass)

    def _get_carry_mass(self):
        # type: () -> Dict[str, int]
        if not self.mem[mem_key_carry_parts_by_role]:
            self.recalculate_roles_alive()
        return self.mem[mem_key_carry_parts_by_role]

    carry_mass_map = property(_get_carry_mass)

    def _get_rt_map(self):
        # type: () -> Dict[str, List[Tuple[str, int]]]
        if not self.mem[mem_key_creeps_by_role_and_replacement_time]:
            self.recalculate_roles_alive()
        return self.mem[mem_key_creeps_by_role_and_replacement_time]

    def role_count(self, role):
        # type: (str) -> int
        count = self.role_counts[role]
        if count:
            return count
        else:
            return 0

    def carry_mass_of(self, role):
        # type: (str) -> int
        mass = self.carry_mass_map[role]
        if mass:
            return mass
        else:
            return 0

    def work_mass_of(self, role):
        # type: (str) -> int
        mass = self.work_mass_map[role]
        if mass:
            return mass
        else:
            return 0

    def register_to_role(self, creep):
        # type: (Union[Creep, RoleBase]) -> None
        """
        Registers the creep's role and time till replacement in permanent memory. Should only be called once per creep.
        """
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
        rt_pair = [creep.name, self.replacement_time_of(creep)]
        if not rt_map[role]:
            rt_map[role] = [rt_pair]
        else:
            # _.sortedIndex(array, value, [iteratee=_.identity])
            # Lodash version is 3.10.0 - this was replaced by sortedIndexBy in 4.0.0
            rt_map[role].splice(_.sortedIndex(rt_map[role], rt_pair, lambda p: p[1]), 0, rt_pair)

    def recalculate_roles_alive(self):
        # type: () -> None
        """
        Forcibly recalculates the current roles in the room. If everything's working correctly, this method should have
        no effect. However, it is useful to run this method frequently, for if memory becomes corrupted or a bug is
        introduced, this can ensure that everything is entirely correct.
        """
        # print("[{}] Recalculating roles alive.".format(self.name))
        # old_rt_map = self.mem[mem_key_creeps_by_role_and_replacement_time]
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

            rt_pair = (creep.name, self.replacement_time_of(creep))

            if not rt_map[role]:
                rt_map[role] = [rt_pair]
            else:
                # _.sortedIndex(array, value, [iteratee=_.identity])
                # Lodash version is 3.10.0 - this was replaced by sortedIndexBy in 4.0.0
                rt_map[role].splice(_.sortedIndex(rt_map[role], rt_pair, lambda p: p[1]), 0, rt_pair)
        self.mem[mem_key_creeps_by_role] = roles_alive
        self.mem[mem_key_work_parts_by_role] = roles_work
        self.mem[mem_key_carry_parts_by_role] = roles_carry
        self.mem[mem_key_creeps_by_role_and_replacement_time] = rt_map

    def get_next_replacement_name(self, role):
        # type: (str) -> Optional[str]
        rt_map = self.rt_map
        if role in rt_map and len(rt_map[role]):
            for rt_pair in rt_map[role]:
                if rt_pair[1] > Game.time:
                    break
                name = rt_pair[0]
                if Memory.creeps[name] and not Memory.creeps[name].replacement:
                    return name

        return None

    def register_new_replacing_creep(self, replaced_name, replacing_name):
        # type: (str, str) -> None
        # print("[{}][{}] Registering as replacement for {} (a {}).".format(self.room_name, replacing_name,
        #                                                                   replaced_name, role))
        if Memory.creeps[replaced_name]:
            Memory.creeps[replaced_name].replacement = replacing_name
        else:
            print("[{}] Couldn't find creep-needing-replacement {} to register {} as the replacer to!".format(
                self.name, replaced_name, replacing_name
            ))

    def replacements_currently_needed_for(self, role):
        # type: (str) -> int
        rt_map = self._get_rt_map()
        count = 0
        if role in rt_map and len(rt_map[role]):
            for creep, replacement_time in rt_map[role]:
                if Game.creeps[creep] and not Memory.creeps[creep].replacement and replacement_time <= Game.time:
                    count += 1
        return count

    def count_noneol_creeps_targeting(self, target_type, target_id):
        # type: (int, str) -> int
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
        targeters = self.hive.targets.creeps_now_targeting(target_type, target_id)
        for name in targeters:
            creep = Game.creeps[name]
            if creep and Game.time < self.replacement_time_of(creep):
                count += 1
        return count

    def carry_mass_of_replacements_currently_needed_for(self, role):
        # type: (str) -> int
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
        # type: (str) -> int
        mass = 0
        rt_map = self._get_rt_map()
        if role in rt_map and len(rt_map[role]):
            for creep, replacement_time in rt_map[role]:
                if Game.creeps[creep] and not Memory.creeps[creep].replacement and replacement_time <= Game.time:
                    mass += spawning.work_count(Game.creeps[creep])
                else:
                    break  # this is sorted
        return mass

    def replacement_time_of(self, creep):
        # type: (Union[Creep, RoleBase]) -> int
        if 'get_replacement_time' in creep:
            return cast(RoleBase, creep).get_replacement_time()

        if creep.memory.home != self.name:
            home_room = self.hive.get_room(creep.memory.home)
            if home_room:
                return home_room.replacement_time_of(creep)
            else:
                print("Couldn't find home of {} ({})!".format(creep.name, creep.memory.home))

        if 'wrapped' in creep:
            creep = creep.wrapped
        else:

            creep = errorlog.execute(creep_wrappers.wrap_creep, self.hive, self.hive.targets, self, creep)
            if creep is None:
                print("[{}] could not wrap creep {} to get replacement time.".format(self.name, creep.name))
                return Infinity

        return creep.get_replacement_time()

    def check_all_creeps_next_tick(self):
        # type: () -> None
        meta = self.mem[mem_key_metadata]
        if meta:
            meta["clear_next"] = 0

    def precreep_tick_actions(self):
        # type: () -> None
        time = Game.time
        meta = self.mem[mem_key_metadata]
        if not meta:
            self.mem[mem_key_metadata] = meta = {"clear_next": 0, "reset_spawn_on": 0}

        if time >= meta.clear_next:
            # print("[{}] Clearing memory".format(self.name))
            consistency.clear_memory(self)
            self.recalculate_roles_alive()
            # Recalculate spawning - either because a creep death just triggered our clearing memory, or we haven't
            # recalculated in the last 500 ticks.
            # TODO: do we really need to recalculate every 500 ticks? even though it really isn't expensive
            self.reset_planned_role()
            del meta.clear_now
            # print("[{}] Next clear in {} ticks.".format(self.name, meta.clear_next - Game.time))

        # reset_spawn_on is set to the tick after the next creep's TTR expires in consistency.clear_memory()
        if time >= meta.reset_spawn_on:
            self.reset_planned_role()
            meta.reset_spawn_on = consistency.get_next_replacement_time(self) + 1

        # TODO: this will make both rooms do it at the same time, but this is better than checking every time memory is
        # cleared! Actually, it's quite cheap.
        if Game.time % 10 == 0:
            self.reassign_roles()
        if Game.time % 500 == 0:
            self._check_request_expirations()

    def reassign_roles(self):
        # type: () -> None
        return consistency.reassign_room_roles(self)

    def is_urgent(self):
        # type: () -> bool
        return self.mem.urgency > 0

    def constant_energy_to_keep_in_reserve(self):
        # type: () -> int
        if self.is_urgent():
            return energy_to_keep_always_in_reserve_urgent
        else:
            return energy_to_keep_always_in_reserve

    def constant_pre_rcl8_energy_balance_point(self):
        # type: () -> int
        if self.is_urgent():
            return energy_pre_rcl8_scaling_balance_point_urgent
        else:
            return energy_pre_rcl8_scaling_balance_point

    def constant_balance_point_for_rcl8_upgrading_energy(self):
        # type: () -> int
        if self.is_urgent():
            return energy_balance_point_for_rcl8_upgrading_urgent
        else:
            return energy_balance_point_for_rcl8_upgrading

    def constant_balance_point_for_rcl8_building_energy(self):
        # type: () -> int
        if self.is_urgent():
            return energy_balance_point_for_rcl8_building_urgent
        else:
            return energy_balance_point_for_rcl8_building

    def constant_balance_point_for_rcl8_supporting_energy(self):
        # type: () -> int
        if self.is_urgent():
            return energy_balance_point_for_rcl8_supporting_urgent
        else:
            return energy_balance_point_for_rcl8_supporting

    def constant_balance_point_for_pre_rcl8_backup_energy_spending(self):
        # type: () -> int
        return energy_pre_rcl8_building_when_upgrading_balance_point

    def tick_observer(self):
        # type: () -> None
        if self.rcl < 8:
            return
        offset = (Game.time + self.get_unique_owned_index()) % 20
        if offset == 3:
            # on offset=3, set observer to observer a room.
            observer = cast(StructureObserver, _.find(self.find(FIND_MY_STRUCTURES), lambda s: s.observeRoom))
            if not observer:
                return
            saved_mem = self.mem[mem_key_observer_plans]
            if saved_mem:
                assert isinstance(saved_mem, str)
                split_mem = saved_mem.split(',')
                if len(split_mem) == 1:
                    # this means we're delaying a bit since nothing was found.
                    if not split_mem[0].isnumeric() or Game.time > int(split_mem[0]):
                        del self.mem[mem_key_observer_plans]
                    return
                else:
                    to_observe = split_mem[0]
            else:
                retry_with, try_next = stored_data.find_oldest_rooms_to_check_in_observer_range_of(self.name)

                if len(try_next):
                    self.mem[mem_key_observer_plans] = try_next.concat([retry_with]).join(',')
                    to_observe = try_next[0]
                else:
                    self.mem[mem_key_observer_plans] = str(Game.time + 2000)
                    return
            result = observer.observeRoom(to_observe)
            if result != OK:
                print("[{}][observer] Unknown result from {}.observeRoom({}): {}"
                      .format(self.name, observer, to_observe, result))
        elif offset == 4:
            # on offset=4, serialize the results of that observation.
            saved_mem = self.mem[mem_key_observer_plans]
            if not saved_mem:
                return

            split_mem = saved_mem.split(',')
            if len(split_mem) < 2:
                return

            to_try = split_mem[0]
            room = Game.rooms[to_try]
            if not room:
                print("[{}][observer] WARNING: Could not find room {} which was observed last tick."
                      .format(self.name, to_try))
                return

            stored_data.update_data(room)
            print("[{}][observer] Updated {}.".format(self.name, room.name))

            if len(split_mem) == 2:
                saved_pos = int(split_mem[1])
                retry_with, try_next = stored_data.find_oldest_rooms_to_check_in_observer_range_of(self.name, saved_pos)
                if len(try_next):
                    self.mem[mem_key_observer_plans] = try_next.concat([retry_with]).join(',')
                else:
                    self.mem[mem_key_observer_plans] = str(Game.time + 2000)
            else:
                self.mem[mem_key_observer_plans] = split_mem[1:].join(',')

    def paving(self):
        # type: () -> bool
        if '_paving' not in self:
            if not self.my:
                self._paving = False
            else:
                paving = self.get_cached_property("paving_here")
                if paving is None:
                    needed_energy_capacity = (
                        BODYPART_COST[WORK] * 2
                        + BODYPART_COST[MOVE] * 4
                        + BODYPART_COST[CARRY] * 6
                    )
                    paving = (self.room.storage or self.spawn) and \
                             (self.get_max_mining_op_count() >= 1 or self.room.storage) \
                             and len(self.mining.available_mines) >= 1 \
                             and self.room.energyCapacityAvailable >= needed_energy_capacity
                    self.store_cached_property("paving_here", paving, 200)
                self._paving = paving
        return self._paving

    def any_local_miners(self):
        # type: () -> bool
        if '_any_miners' not in self:
            any_miners = False
            for flag in self.mining.local_mines:
                if self.hive.targets.workforce_of(target_energy_miner_mine, "flag-{}".format(flag.name)) > 0:
                    any_miners = True
                    break
            self._any_miners = any_miners
        return self._any_miners

    def all_local_miners(self):
        # type: () -> bool
        if '_all_miners' not in self:
            all_miners = True
            for flag in self.mining.local_mines:
                if self.hive.targets.workforce_of(target_energy_miner_mine, "flag-{}".format(flag.name)) <= 0:
                    all_miners = False
                    break
            self._all_miners = all_miners
        return self._all_miners

    def get_work_mass(self):
        # type: () -> int
        if '_work_mass' not in self:
            mass = 0
            for creep in self.get_creeps():
                for part in creep.body:
                    if part.type == WORK or part.type == CARRY:
                        mass += 1
            self._work_mass = int(math.floor(mass / 2))
        return self._work_mass

    def get_trying_to_get_full_storage_use(self):
        # type: () -> bool
        if '_trying_to_get_full_storage_use' not in self:
            self._trying_to_get_full_storage_use = self.room.storage and (
                self.room.storage.store[RESOURCE_ENERGY] >= min_stored_energy_to_draw_from_before_refilling
                or (self.any_local_miners() and self.work_mass >=
                    min_work_mass_per_source_for_full_storage_use * len(self.sources)
                    )
            )
        return self._trying_to_get_full_storage_use

    def get_full_storage_use(self):
        # type: () -> bool
        if '_full_storage_use' not in self:
            if self.room.storage and (self.room.storage.store[RESOURCE_ENERGY]
                                          >= min_stored_energy_to_draw_from_before_refilling or
                                          (not self.spawn and self.room.storage.store[RESOURCE_ENERGY] > 0)):
                self._full_storage_use = True
            elif self.room.storage and not self.room.storage.storeCapacity:
                if self.room.storage.store[RESOURCE_ENERGY] > 0:
                    self._full_storage_use = True
                else:
                    self._full_storage_use = False
                    if not self.room.storage.my:
                        self.room.storage.destroy()
            else:
                if self.trying_to_get_full_storage_use:
                    if self.mem[mem_key_storage_use_enabled] and self.room.storage.store[RESOURCE_ENERGY] \
                            <= max_energy_disable_full_storage_use:
                        print("[{}] Disabling full storage use.".format(self.name))
                        del self.mem[mem_key_storage_use_enabled]
                    if not self.mem[mem_key_storage_use_enabled] and self.room.storage.store[RESOURCE_ENERGY] \
                            > min_energy_enable_full_storage_use:
                        print("[{}] Enabling full storage use.".format(self.name))
                        self.mem[mem_key_storage_use_enabled] = True
                    self._full_storage_use = self.mem[mem_key_storage_use_enabled]
                else:
                    self._full_storage_use = False
        return self._full_storage_use

    def being_bootstrapped(self):
        # type: () -> bool
        if self.rcl >= 6 or not self.sponsor_name or self.spawn:
            return False
        sponsor = self.hive.get_room(self.sponsor_name)
        if not sponsor or not sponsor.my or not sponsor.spawn:
            return False
        return True

    def mining_ops_paused(self):
        # type: () -> bool
        if not self.full_storage_use:
            return False
        if self.mem[mem_key_focusing_home] and _.sum(self.room.storage.store) < max_total_resume_remote_mining \
                or self.room.storage.store[RESOURCE_ENERGY] < max_energy_resume_remote_mining:
            del self.mem[mem_key_focusing_home]
        if not self.mem[mem_key_focusing_home] and _.sum(self.room.storage.store) > min_total_pause_remote_mining \
                and self.room.storage.store[RESOURCE_ENERGY]> min_energy_pause_remote_mining:
            self.mem[mem_key_focusing_home] = True
        return not not self.mem[mem_key_focusing_home]

    def upgrading_paused(self):
        # type: () -> bool
        if self.room.storage:
            current_store_energy = self.room.storage.store[RESOURCE_ENERGY]
        else:
            current_store_energy = 0
        if '_upgrading_paused' not in self:
            if self.rcl < 4 or not self.room.storage or self.room.storage.storeCapacity <= 0 \
                    or self.being_bootstrapped():
                self._upgrading_paused = False
            # TODO: constant here and below in upgrader_work_mass
            elif self.conducting_siege() and (current_store_energy < (self.constant_energy_to_keep_in_reserve() / 4)
                    or (self.rcl < 7 and current_store_energy < self.constant_energy_to_keep_in_reserve())
            ):
                self._upgrading_paused = True  # Don't upgrade while we're taking someone down.
            else:
                if self.rcl >= 8:
                    if self.mem[mem_key_upgrading_paused] \
                            and current_store_energy > rcl8_energy_to_resume_upgrading:
                        del self.mem[mem_key_upgrading_paused]
                    if not self.mem[mem_key_upgrading_paused] \
                            and current_store_energy < rcl8_energy_to_pause_upgrading:
                        self.mem[mem_key_upgrading_paused] = True
                else:
                    if self.mem[mem_key_upgrading_paused] \
                            and current_store_energy > energy_to_resume_upgrading:
                        del self.mem[mem_key_upgrading_paused]
                    if not self.mem[mem_key_upgrading_paused] \
                            and current_store_energy < energy_to_pause_upgrading:
                        self.mem[mem_key_upgrading_paused] = True
                self._upgrading_paused = not not self.mem[mem_key_upgrading_paused]
        return self._upgrading_paused

    def building_paused(self):
        # type: () -> bool
        if '_building_paused' not in self:
            if self.rcl < 4 or not self.room.storage or self.room.storage.storeCapacity <= 0:
                self._building_paused = False
            elif self.conducting_siege() and self.rcl < 7:
                self._building_paused = True  # Don't build while we're taking someone down.
            else:
                energy = self.room.storage.store[RESOURCE_ENERGY]
                if self.mem[mem_key_building_paused] and energy > energy_to_resume_building:
                    del self.mem[mem_key_building_paused]
                if not self.mem[mem_key_building_paused] and energy < energy_to_pause_building:
                    self.mem[mem_key_building_paused] = True
                if self.mem[mem_key_building_paused]:
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
        # type: () -> bool
        if '_overprioritize_building' not in self:
            if self.spawn:
                prioritize = (
                    ((self.room.energyCapacityAvailable
                      < BODYPART_COST[WORK] * 5 + BODYPART_COST[MOVE]  # 550 on official servers
                      and self.get_open_source_spaces() < len(self.sources) * 2)
                     or (self.rcl >= 3 and not len(self.defense.towers()))
                     or (self.rcl >= 3 and self.room.energyCapacityAvailable
                         < BODYPART_COST[CLAIM] + BODYPART_COST[MOVE])  # 650 on official servers
                     or (self.rcl >= 4 and self.room.energyCapacityAvailable
                         < BODYPART_COST[CLAIM] * 2 + BODYPART_COST[MOVE] * 2))  # 1300 on official servers
                    and len(self.building.get_construction_targets())
                    and (self.room.controller.ticksToDowngrade > 100)
                )
            else:
                prioritize = not self.being_bootstrapped()
            self._overprioritize_building = prioritize
        return self._overprioritize_building

    def upgrading_deprioritized(self):
        # type: () -> bool
        deprioritized = cast(bool, self.get_cached_property("upgrading_deprioritized"))
        if deprioritized is not None:
            return deprioritized
        deprioritized = not not (
            (
                self.upgrading_paused()
                or (self.rcl == 8 and Memory[gmem_key_pause_rcl8_upgrading])
                or (self.rcl < 4 and len(self.subsidiaries) and not self.being_bootstrapped())
                or (not self.spawn and not self.being_bootstrapped())
                or (self.under_siege() and (not self.room.storage or self.room.storage.storeCapacity))
            )
            and self.room.controller.ticksToDowngrade >= 1000
            and (not self.room.storage or self.room.storage.store[RESOURCE_ENERGY] < STORAGE_CAPACITY * 0.7)
        )
        self.store_cached_property("upgrading_deprioritized", deprioritized, 15)
        return deprioritized

    def under_siege(self):
        # type: () -> bool
        return not not self.mem[mem_key_currently_under_siege]

    def any_remotes_under_siege(self):
        # type: () -> bool
        return self.mem[mem_key_currently_under_siege] or self.mem[mem_key_remotes_explicitly_marked_under_attack]

    def remote_under_siege(self, flag):
        # type: (Flag) -> bool
        return self.any_remotes_under_siege() \
               and flag.pos.roomName != self.name \
               and (not self.mem[mem_key_remotes_safe_when_under_siege]
                    or not self.mem[mem_key_remotes_safe_when_under_siege].includes(flag.pos.roomName))

    def conducting_siege(self):
        # type: () -> bool
        if '_conducting_siege' not in self:
            self._conducting_siege = Game.cpu.bucket > 4500 and not not (
                (self._any_closest_to_me(TD_D_GOAD) or self._any_closest_to_me(ATTACK_POWER_BANK)
                 or self._any_closest_to_me(ATTACK_DISMANTLE))
                and self._any_closest_to_me(TD_H_H_STOP) and self._any_closest_to_me(TD_H_D_STOP)
            )
        return self._conducting_siege

    def get_max_mining_op_count(self):
        # type: () -> int
        if not self.my:
            print("[{}] WARNING: get_max_mining_op_count called for non-owned room!".format(self.name))
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
        # type: () -> int
        return rcl_to_max_wall_hits[self.rcl - 1] or 0  # 1-to-0-based index

    def get_min_sane_wall_hits(self):
        # type: () -> int
        return rcl_to_target_wall_hits[self.rcl - 1] or 0  # 1-to-0 based index

    def get_upgrader_energy_struct(self):
        # type: () -> Optional[Union[StructureContainer, StructureStorage, StructureLink]]
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
                        return cast(Any, structure)
            structure = None
            if self.room.storage and not self.being_bootstrapped():
                if self.room.storage.pos.inRangeTo(self.room.controller, 4):
                    structure = self.room.storage
                else:
                    all_structs_near = _(self.find_in_range(FIND_STRUCTURES, 4, self.room.controller.pos))
                    if self.links.main_link and all_structs_near.find({'structureType': STRUCTURE_LINK, 'my': True}):
                        structure = all_structs_near.filter({'structureType': STRUCTURE_LINK}) \
                            .min(lambda s: movement.chebyshev_distance_room_pos(s.pos, self.room.controller.pos))
                    elif all_structs_near.find({'structureType': STRUCTURE_CONTAINER}):
                        structure = all_structs_near.filter({'structureType': STRUCTURE_CONTAINER}) \
                            .min(lambda s: movement.chebyshev_distance_room_pos(s.pos, self.room.controller.pos))
            else:
                structure = _(self.find_in_range(FIND_STRUCTURES, 4, self.room.controller.pos)).filter(
                    {'structureType': STRUCTURE_CONTAINER}) \
                    .min(lambda s: movement.chebyshev_distance_room_pos(s.pos, self.room.controller.pos))
                if structure == Infinity or structure == -Infinity:
                    structure = None
            if structure:
                structure_id = structure.id
            else:
                structure_id = -1
            self._upgrader_source = structure
            self.store_cached_property("upgrader_source_id", structure_id, 15)
        return self._upgrader_source

    def get_extra_fill_targets(self):
        # type: () -> List[StructureContainer]
        if '_extra_fill_targets' not in self:
            extra_targets = []
            cont = self.get_upgrader_energy_struct()
            if cont and cont.structureType == STRUCTURE_CONTAINER:
                extra_targets.push(cont)
            self._extra_fill_targets = _.filter(extra_targets,
                                                lambda s: (s.storeCapacity and _.sum(s.store) < s.storeCapacity)
                                                          or (s.energyCapacity and s.energy < s.energyCapacity))
        return self._extra_fill_targets

    def get_open_source_spaces(self):
        # type: () -> int
        cached = self.get_cached_property('oss')
        if cached:
            return cached
        oss = 0
        for source in self.sources:
            for x in range(source.pos.x - 1, source.pos.x + 2):
                for y in range(source.pos.y - 1, source.pos.y + 2):
                    if movement.is_block_empty(self, x, y):
                        oss += 1
        self.store_cached_property('oss', oss, 1000 * 1000)
        return oss

    def get_open_source_spaces_around(self, source):
        # type: (Source) -> int
        key = 'oss-{}'.format(source.id)
        cached = self.get_cached_property(key)
        if cached:
            return cached
        oss = 0
        for x in range(source.pos.x - 1, source.pos.x + 2):
            for y in range(source.pos.y - 1, source.pos.y + 2):
                if movement.is_block_empty(self, x, y):
                    oss += 1
        self.store_cached_property(key, oss, 1000 * 1000)
        return oss

    def calculate_smallest_wall(self):
        # type: () -> int
        if self._smallest_wall_hits is undefined:
            least_hits = Infinity
            for struct in self.find(FIND_STRUCTURES):
                struct = cast(Structure, struct)
                if struct.structureType == STRUCTURE_WALL or struct.structureType == STRUCTURE_RAMPART:
                    struct = cast(Union[StructureWall, StructureRampart], struct)
                    if struct.hits < least_hits:
                        least_hits = struct.hits
            if least_hits is Infinity:
                least_hits = 0
            self._smallest_wall_hits = least_hits
        return self._smallest_wall_hits

    def set_supporting_room(self, target):
        # type: (Optional[str]) -> None
        old_target = self.mem[mem_key_now_supporting]
        self.mem[mem_key_now_supporting] = target

        if target != old_target or (target is not None
                                    and _.get(Memory, ['rooms', target, mem_key_currently_under_siege])
                                    and self.get_spending_target() != room_spending_state_supporting_sieged):
            self.reset_spending_state()

    def reset_spending_state(self):
        # type: () -> None
        self.delete_cached_property(cache_key_spending_now)
        self.reset_planned_role()

    def get_spending_target(self):
        # type: () -> str
        cached = self.get_cached_property(cache_key_spending_now)
        if cached:
            return cached
        if not self.full_storage_use:
            self.store_cached_property(cache_key_spending_now, room_spending_state_saving, 500)
            return room_spending_state_saving
        state = None
        if self.mem[mem_key_sell_all_but_empty_resources_to]:
            state = room_spending_state_selling
        elif self.mem[mem_key_now_supporting]:
            room = self.hive.get_room(self.mem[mem_key_now_supporting])
            if room and not room.minerals.has_no_terminal_or_storage() \
                    and room.minerals.get_estimate_total_energy() < energy_at_which_to_stop_supporting:
                if room.mem[mem_key_currently_under_siege]:
                    state = room_spending_state_supporting_sieged
                else:
                    energy = self.minerals.get_estimate_total_energy()
                    if energy < self.constant_energy_to_keep_in_reserve() / 2:
                        state = room_spending_state_saving
                    elif self.room.terminal \
                            and self.minerals.get_estimate_total_non_energy() > max_minerals_to_keep / 2:
                        if energy > self.constant_energy_to_keep_in_reserve() + energy_for_terminal_when_selling:
                            state = room_spending_state_selling_and_supporting
                        else:
                            state = room_spending_state_selling
                    elif energy < self.constant_energy_to_keep_in_reserve():
                        state = room_spending_state_saving
                    else:
                        state = room_spending_state_supporting

        if state is None:
            energy = self.minerals.get_estimate_total_energy()
            non_energy = self.room.terminal and self.minerals.get_estimate_total_non_energy()
            if energy < self.constant_energy_to_keep_in_reserve() / 2:
                state = room_spending_state_saving
            elif self.room.terminal and non_energy > max_minerals_to_keep:
                if energy > self.constant_energy_to_keep_in_reserve() + energy_for_terminal_when_selling:
                    if self.rcl >= 8:
                        state = room_spending_state_selling_and_rcl8building
                    else:
                        if self.building.get_target_num_builders() > 1 \
                                and self.building.get_max_builder_work_parts() > 5:
                            state = room_spending_state_selling_and_building
                        else:
                            least_hits = self.calculate_smallest_wall()
                            if least_hits < self.min_sane_wall_hits:
                                state = room_spending_state_selling_and_building
                            else:
                                state = room_spending_state_selling_and_upgrading
                else:
                    state = room_spending_state_selling
            elif energy < self.constant_energy_to_keep_in_reserve():
                state = room_spending_state_saving
            elif self.room.terminal and non_energy > max_minerals_to_keep / 2:
                if energy > self.constant_energy_to_keep_in_reserve() + energy_for_terminal_when_selling:
                    if self.rcl >= 8:
                        state = room_spending_state_selling_and_rcl8building
                    else:
                        if self.building.get_target_num_builders() > 1 \
                                and self.building.get_max_builder_work_parts() > 5:
                            state = room_spending_state_selling_and_building
                        else:
                            least_hits = self.calculate_smallest_wall()
                            if least_hits < self.min_sane_wall_hits:
                                state = room_spending_state_selling_and_building
                            else:
                                state = room_spending_state_selling_and_upgrading
                else:
                    state = room_spending_state_selling
            elif self.rcl >= 8:
                state = room_spending_state_rcl8_building
            else:
                if self.building.get_target_num_builders() > 1 and self.building.get_max_builder_work_parts() > 5:
                    state = room_spending_state_building
                else:
                    least_hits = self.calculate_smallest_wall()
                    if least_hits < self.min_sane_wall_hits:
                        state = room_spending_state_building
                    else:
                        state = room_spending_state_upgrading

        self.store_cached_property(cache_key_spending_now, state, 500)
        return state

    __pragma__('nofcall')

    def _any_closest_to_me(self, flag_type):
        # type: (int) -> bool
        for flag in flags.find_flags_global(flag_type):
            if flags.flag_sponsor(flag, self.hive) == self.name:
                return True

        return False

    def flags_without_target(self, flag_type, filter_func=None):
        # type: (int, Optional[Callable[[Flag], bool]]) -> List[Flag]
        result = []  # TODO: yield
        for flag in flags.find_flags_global(flag_type):
            if flags.flag_sponsor(flag, self.hive) == self.name:
                if filter_func is not None and not filter_func(flag):
                    continue
                flag_id = "flag-{}".format(flag.name)
                noneol_targeting_count = self.count_noneol_creeps_targeting(target_single_flag, flag_id)
                if noneol_targeting_count < 1:
                    result.append(flag)
        return result

    def get_spawn_for_flag(self, role, half_move_base, full_move_base, flag, max_sections=0):
        # type: (str, str, str, Flag, int) -> Dict[str, Any]
        if movement.distance_squared_room_pos(self.spawn.pos, flag.pos) > math.pow(200, 2):
            base = full_move_base
        else:
            base = half_move_base
        sections = spawning.max_sections_of(self, base)
        if max_sections:
            sections = min(sections, max_sections)
        if flag.memory.size:
            sections = min(sections, flag.memory.size)
        obj = {
            roleobj_key_role: role,
            roleobj_key_base: base,
            roleobj_key_num_sections: sections,
            roleobj_key_initial_targets: [
                [target_single_flag, "flag-{}".format(flag.name)],
            ]
        }
        if 'boosted' in flag.memory and not flag.memory.boosted:
            obj.memory = {'boosted': 2}
        return obj

    def spawn_one_creep_per_flag(self, flag_type, role, half_move_base, full_move_base, max_sections=0,
                                 filter_func=None):
        # type: (int, str, str, str, int, Optional[Callable[[Flag], bool]]) -> Optional[Dict[str, Any]]
        flag_list = self.flags_without_target(flag_type, filter_func)
        if len(flag_list):
            return self.get_spawn_for_flag(role, half_move_base, full_move_base, flag_list[0], max_sections)
        return None

    def get_target_link_manager_count(self):
        # type: () -> int
        if '_target_link_managers' not in self:
            links = 0
            for s in self.find(FIND_STRUCTURES):
                s = cast(Structure, s)
                if s.structureType == STRUCTURE_LINK:
                    links += 1
            if links >= 2 and self.trying_to_get_full_storage_use:
                self._target_link_managers = 1
            else:
                self._target_link_managers = 0
        return self._target_link_managers

    def get_target_wall_defender_count(self):
        # type: () -> int
        if self.under_siege():
            hot, cold = self.defense.get_current_defender_spots()
            return int(math.ceil(len(hot) + len(cold) / 2))

    def get_target_simple_defender_count(self, first=False):
        # type: (bool) -> int
        if self.under_siege():
            return 0
        if ('_first_simple_target_defender_count' if first else '_target_defender_count') not in self:
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
                self._target_defender_count = int(math.ceil(needed_local + needed_for_mines))
        return self._first_simple_target_defender_count if first else self._target_defender_count

    def get_target_colonist_work_mass(self):
        # type: () -> float
        if self.under_siege():
            return 0
        if '_target_colonist_work_mass' not in self:
            worker_mass = spawning.max_sections_of(self, creep_base_worker)
            hauler_mass = spawning.max_sections_of(self, creep_base_half_move_hauler)
            needed = 0
            mineral_steal = 0
            for room in self.subsidiaries:
                if not room.room.controller.safeMode \
                        and _.find(room.defense.dangerous_hostiles(),
                                   lambda c: c.hasBodyparts(ATTACK) or c.hasBodyparts(RANGED_ATTACK)):
                    continue
                distance = self.hive.honey.find_path_length(
                    self.spawn.pos, movement.center_pos(room.name), {'range': 15})
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
                    target = min(10.0, 5 + room.room.storage.store[RESOURCE_ENERGY] / 20 * 1000) * worker_mass
                elif len(room.sources) >= 2:
                    target = 5 * worker_mass
                else:
                    target = 10
                needed += max(0, target - room_work_mass)
                if room.room.storage and _.sum(room.room.storage.store) > room.room.storage.store[RESOURCE_ENERGY]\
                        and room.room.storage.storeCapacity <= 0:
                    mineral_steal += hauler_mass
            if Game.cpu.bucket < 4000:
                needed = 0
            self._target_colonist_work_mass = needed
            self._target_mineral_steal_mass = mineral_steal
        return self._target_colonist_work_mass

    def get_target_mineral_steal_mass(self):
        # type: () -> float
        if '_target_mineral_steal_mass' not in self:
            self.get_target_colonist_work_mass()
        return self._target_mineral_steal_mass

    def get_target_spawn_fill_backup_carry_mass(self):
        # type: () -> float
        # TODO: 25 should be a constant.
        if self.full_storage_use or self.all_local_miners():
            if self.full_storage_use and (self.any_local_miners() or
                                              (self.work_mass > 25 and self.role_count(role_tower_fill) > 0
                                               and self.role_count(role_spawn_fill) > 0)):
                return 0
            else:
                return 3
        elif self.rcl < 3:
            return len(self.sources) * spawning.max_sections_of(self, creep_base_worker)
        else:
            return int(math.floor(self.get_target_total_spawn_fill_mass() / 2))

    def get_target_spawn_fill_mass(self):
        # type: () -> float
        if '_target_spawn_fill_mass' not in self:
            if self.full_storage_use or self.any_local_miners():
                tower_fill = self.carry_mass_of(role_tower_fill)
                total_mass = math.ceil(self.get_target_total_spawn_fill_mass())
                if self.rcl < 4 or not self.room.storage:
                    fill_size = fit_num_sections(total_mass,
                                                 spawning.max_sections_of(self, creep_base_hauler), 0, 2)
                    for flag in self.mining.local_mines:
                        sitting = self.mining.energy_sitting_at(flag)
                        if sitting > 1000:
                            total_mass += math.ceil(sitting / 500) * fill_size
                if self.under_siege() or self.mem[mem_key_prepping_defenses]:
                    self._target_spawn_fill_mass = total_mass
                else:
                    self._target_spawn_fill_mass = max(0, min(1, total_mass), total_mass - tower_fill)

            else:
                self._target_spawn_fill_mass = 0
        return self._target_spawn_fill_mass

    def get_target_total_spawn_fill_mass(self):
        # type: () -> float
        if '_total_needed_spawn_fill_mass' not in self:
            if self.room.energyCapacityAvailable < 550 and self.get_open_source_spaces() < len(self.sources) * 2:
                self._total_needed_spawn_fill_mass = 3
            else:
                self._total_needed_spawn_fill_mass = math.pow(self.room.energyCapacityAvailable / 50.0 * 200, 0.3)
                if self.under_siege() or self.mem[mem_key_prepping_defenses]:
                    self._total_needed_spawn_fill_mass *= 1.5
                elif len(self.mining.active_mines) < 2:  # This includes local sources.
                    self._total_needed_spawn_fill_mass /= 2

        return self._total_needed_spawn_fill_mass

    def get_target_builder_work_mass(self):
        # type: () -> float
        if '_target_builder_work_mass' in self:
            return self._target_builder_work_mass

        self._target_builder_work_mass = 0
        if self.building_paused():
            self._target_builder_work_mass = 0
            return 0
        base_num = self.building.get_target_num_builders()
        if base_num <= 0:
            self._target_builder_work_mass = 0
            return 0

        if self.full_storage_use:
            spending = self.get_spending_target()
            if spending == room_spending_state_building:
                extra = self.minerals.get_estimate_total_energy() - self.constant_pre_rcl8_energy_balance_point()
                wm = spawning.max_sections_of(self, creep_base_worker)
                if extra > 0:
                    wm += math.floor(extra / 2500)
                wm = min(wm, self.building.get_max_builder_work_parts())
            elif spending == room_spending_state_selling_and_building:
                extra = self.minerals.get_estimate_total_energy() - self.constant_pre_rcl8_energy_balance_point() \
                        - energy_for_terminal_when_selling
                wm = spawning.max_sections_of(self, creep_base_worker)
                if extra > 0:
                    wm += math.floor(extra / 2500)
                wm = min(wm, self.building.get_max_builder_work_parts())
            elif spending == room_spending_state_rcl8_building:
                extra = self.minerals.get_estimate_total_energy() - \
                        self.constant_balance_point_for_rcl8_building_energy()
                wm = min(4, spawning.max_sections_of(self, creep_base_worker))
                if extra > 0:
                    wm += math.floor(extra / 2500)
                wm = min(wm, self.building.get_max_builder_work_parts())
            elif spending == room_spending_state_selling_and_rcl8building:
                extra = self.minerals.get_estimate_total_energy() - \
                        self.constant_balance_point_for_rcl8_building_energy() \
                        - energy_for_terminal_when_selling
                wm = min(4, spawning.max_sections_of(self, creep_base_worker))
                if extra > 0:
                    wm += math.floor(extra / 2500)
                wm = min(wm, self.building.get_max_builder_work_parts())
            elif spending == room_spending_state_supporting_sieged:
                wm = self.building.get_max_builder_work_parts_urgent()
            elif spending == room_spending_state_under_siege:
                if self.minerals.get_estimate_total_energy() < self.constant_energy_to_keep_in_reserve() / 2:
                    wm = self.building.get_max_builder_work_parts_urgent()
                else:
                    extra = self.minerals.get_estimate_total_energy() - \
                            self.constant_balance_point_for_rcl8_building_energy()
                    wm = spawning.max_sections_of(self, creep_base_worker) * 3
                    if extra > 0:
                        wm += math.floor(extra / 2500)
                    wm = min(wm, self.building.get_max_builder_work_parts())
            else:
                extra = self.minerals.get_estimate_total_energy() - \
                        self.constant_balance_point_for_pre_rcl8_backup_energy_spending()
                if extra > 0:
                    wm = min(
                        min(4, spawning.max_sections_of(self, creep_base_worker)) + math.floor(extra / 2500),
                        self.building.get_max_builder_work_parts()
                    )
                else:
                    wm = min(
                        spawning.max_sections_of(self, creep_base_worker) * 3,
                        self.building.get_max_builder_work_parts_noextra(),
                    )
        elif self.trying_to_get_full_storage_use:
            wm = min(
                spawning.max_sections_of(self, creep_base_worker) * 2,
                self.building.get_max_builder_work_parts()
            )
        elif self.room.energyCapacityAvailable < 550:
            wm = min(
                base_num * spawning.max_sections_of(self, creep_base_worker),
                self.building.get_max_builder_work_parts()
            )
        else:
            wm = min(
                base_num * max(2, min(8, spawning.max_sections_of(self, creep_base_worker))),
                self.building.get_max_builder_work_parts()
            )

        self._target_builder_work_mass = wm
        return wm

    def get_target_upgrade_fill_mass(self):
        # type: () -> float
        if '_target_upgrade_fill_work_mass' not in self:
            target = self.get_upgrader_energy_struct()
            if not target or target.structureType != STRUCTURE_CONTAINER:
                self._target_upgrade_fill_work_mass = 0
            else:
                upgrader_work_mass = self.get_target_upgrader_work_mass()
                if upgrader_work_mass <= 0:
                    self._target_upgrade_fill_work_mass = 0
                elif upgrader_work_mass <= 1:
                    self._target_upgrade_fill_work_mass = 1
                else:
                    if self.room.storage:
                        distance = self.hive.honey.find_path_length(self.room.storage.pos, target.pos,
                                                                    {'use_roads': False})
                    else:
                        distance = 0
                        for source in self.sources:
                            distance += self.hive.honey.find_path_length(source.pos, target.pos, {'use_roads': False})
                        distance /= len(self.sources)
                    carry_per_tick_per_part = CARRY_CAPACITY / (distance * 2) + 5
                    need_per_tick = upgrader_work_mass * UPGRADE_CONTROLLER_POWER
                    self._target_upgrade_fill_work_mass = math.ceil(need_per_tick / carry_per_tick_per_part)
        return self._target_upgrade_fill_work_mass

    def get_target_upgrader_work_mass(self):
        # type: () -> float
        if '_target_upgrader_work_mass' in self:
            return self._target_upgrader_work_mass
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
            return wm
        elif self.full_storage_use:
            spending = self.get_spending_target()
            if spending == room_spending_state_upgrading:
                wm = 4
                extra = self.minerals.get_estimate_total_energy() - self.constant_energy_to_keep_in_reserve()
                if extra > 0:
                    wm += math.floor(extra / 2000)
                    if extra >= STORAGE_CAPACITY / 5:
                        wm += math.ceil((extra - STORAGE_CAPACITY / 5) / 400)
            elif spending == room_spending_state_selling_and_upgrading:
                wm = 4
                extra = self.minerals.get_estimate_total_energy() - self.constant_energy_to_keep_in_reserve() \
                        - energy_for_terminal_when_selling
                if extra > 0:
                    wm += math.floor(extra / 2000)
                    if extra >= STORAGE_CAPACITY / 5:
                        wm += math.ceil((extra - STORAGE_CAPACITY / 5) / 400)
            elif spending == room_spending_state_rcl8_building:
                extra = self.minerals.get_estimate_total_energy() - self.constant_balance_point_for_rcl8_upgrading_energy()
                if extra < 0:
                    wm = 4
                else:
                    wm = 15
            elif spending == room_spending_state_selling_and_rcl8building:
                extra = self.minerals.get_estimate_total_energy() \
                        - self.constant_balance_point_for_rcl8_upgrading_energy() \
                        - energy_for_terminal_when_selling
                if extra < 0:
                    wm = 4
                else:
                    wm = 15
            elif spending == room_spending_state_supporting:
                extra = self.minerals.get_estimate_total_energy() \
                        - self.constant_balance_point_for_rcl8_upgrading_energy()
                if extra < 0:
                    wm = 4
                # TODO: see if this is the best possible condition we could have...
                elif len(self.possible_remote_mining_operations) >= 3:
                    wm = 15
                else:
                    wm = 10
            elif spending == room_spending_state_supporting_sieged or spending == room_spending_state_under_siege:
                if self.room.controller.ticksToDowngrade <= 10 * 1000:
                    wm = 1
                else:
                    wm = 0
            else:
                wm = 4
        elif self.room.energyCapacityAvailable < 550:
            wm = self.get_open_source_spaces() * worker_size
            for source in self.sources:
                energy = _.sum(self.find_in_range(FIND_DROPPED_RESOURCES, 1, source.pos), 'amount')
                wm += energy / 200.0
        else:
            wm = len(self.sources) * 2 * worker_size

        if wm > 0:
            if base is creep_base_full_upgrader:
                if len(flags.find_flags(self, UPGRADER_SPOT)):
                    max_upgraders = len(flags.find_flags(self, UPGRADER_SPOT))
                else:
                    max_upgraders = 4
                wm = min(wm, worker_size * max_upgraders)
            elif self.room.storage and not self.room.storage.storeCapacity:
                wm = min(wm, worker_size * 15)
            else:
                max_upgraders = max(8, len(flags.find_flags(self, UPGRADER_SPOT)))
                wm = min(wm, worker_size * max_upgraders)

            energy_struct = self.get_upgrader_energy_struct()
            if energy_struct and energy_struct.structureType == STRUCTURE_LINK:
                distance = movement.chebyshev_distance_room_pos(self.links.main_link, energy_struct.pos)
                total_throughput = LINK_CAPACITY * (1 - LINK_LOSS_RATIO) / distance
                if self.links.secondary_link:
                    secondary_distance = movement.chebyshev_distance_room_pos(self.links.secondary_link,
                                                                              energy_struct.pos)
                    total_throughput += LINK_CAPACITY * (1 - LINK_LOSS_RATIO) / secondary_distance
                wm = min(wm, math.ceil(total_throughput))
        self._target_upgrader_work_mass = wm
        return wm

    def get_target_tower_fill_mass(self):
        # type: () -> float
        if not self.get_target_spawn_fill_mass():
            return 0
        towers = self.defense.towers()
        if len(towers):
            size = max(1, min(5, spawning.max_sections_of(self, creep_base_hauler))) * 0.75
            return math.ceil(min(size * len(towers), self.get_target_total_spawn_fill_mass()))
        else:
            return 0

    def get_target_room_reserve_count(self):
        # type: () -> int
        if '_target_room_reserve_count' not in self:
            count = 0
            if self.room.energyCapacityAvailable >= 650:
                for flag in flags.find_flags_global(RESERVE_NOW):
                    room_name = flag.pos.roomName
                    room = Game.rooms[room_name]
                    if not room or (room.controller and not room.controller.my and not room.controller.owner):
                        # TODO: save in memory and predict the time length this room is reserved, and only send out a
                        # reserve creep for <3000 ticks reserved.
                        if self.hive.get_closest_owned_room(flag.pos.roomName).name != self.name:
                            # there's a closer room, let's not claim here.
                            continue
                        count += 1
            self._target_room_reserve_count = count
            # claimable!
        return self._target_room_reserve_count

    def get_target_spawn_fill_size(self):
        # type: () -> float
        if self.under_siege() or self.mem[mem_key_prepping_defenses]:
            return fit_num_sections(self.get_target_total_spawn_fill_mass(),
                                    spawning.max_sections_of(self, creep_base_hauler))
        else:
            return fit_num_sections(self.get_target_total_spawn_fill_mass(),
                                    spawning.max_sections_of(self, creep_base_hauler), 0, 2)

    def get_upgrader_size(self):
        # type: () -> float
        base = self.get_variable_base(role_upgrader)
        sections = spawning.max_sections_of(self, base)
        target = self.get_target_upgrader_work_mass()
        if base == creep_base_full_upgrader and target > 1:
            target = spawning.ceil_sections(target / 2)
        return fit_num_sections(target, sections)

    def get_builder_size(self):
        # type: () -> float
        base = self.get_variable_base(role_builder)
        return fit_num_sections(self.get_target_builder_work_mass(), spawning.max_sections_of(self, base))

    def get_upgrade_fill_size(self):
        # type: () -> float
        mass = self.get_target_upgrade_fill_mass()
        if mass <= 0:
            return 1
        else:
            return fit_num_sections(mass + 2, spawning.max_sections_of(self, creep_base_hauler))

    def request_creep(self, role, opts=None):
        # type: (str, Optional[Dict[str, Any]]) -> None
        """
        Performs a very simple creep request.
        :param role: The role of the creep
        :param opts: Any additional spawning options (described as role_obj in register_creep_request)
        """

        req_key = naming.random_digits()
        if mem_key_spawn_requests in self.mem:
            while req_key in self.mem[mem_key_spawn_requests]['s']:
                req_key += naming.random_digits()
        self.register_creep_request(
            req_key,
            request_priority_low,
            Game.time + 50 * 1000,
            _.merge({
                roleobj_key_role: role,
                roleobj_key_base: self.get_variable_base(role),
                roleobj_key_num_sections: self.get_max_sections_for_role(role)
            }, opts)
        )

    def register_creep_request(self, specific_key, priority, expire_at, role_obj):
        # type: (str, int, int, Optional[Dict[str, Any]]) -> None
        """
        Registers a creep request with unique key `specific_key`.
        :param specific_key: The unique key to represent this creep order. Any other order with this key will replace
                            it.
        :param priority: The priority of the request. 0 is highest priority.
        :param expire_at: If game time passes this point and the creep has not yet been spawned, the request should
                            expire.
        :param role_obj: A description of the creep to spawn - an object with role,base and num_sections, with
                            other additional optional properties: memory (obj), replacing (string), targets
                            (list of [target_type, target_id] items), run_after (string of a function to run after
                            successful spawning)
        """
        if mem_key_spawn_requests not in self.mem:
            self.mem[mem_key_spawn_requests] = {'q': [], 's': {}}
        req = self.mem[mem_key_spawn_requests]
        old_priority = _.get(req, ['s', specific_key, 'p'], None)
        req['s'][specific_key] = {'e': expire_at, 'p': priority, 'o': JSON.stringify(role_obj)}

        if req['q'].includes(specific_key):
            if old_priority is None or old_priority == priority:
                return
            else:
                req['q'].splice(req['q'].indexOf(specific_key), 1)
        # push into sorted array
        req['q'].splice(_.sortedIndex(req['q'], specific_key, lambda key: req['s'][key]['p']), 0, specific_key)
        if len(req['q']) <= 1 and self.get_next_role() is None:
            self.reset_planned_role()

    def _get_next_requested_creep(self, max_priority=Infinity):
        # type: (float) -> Optional[Dict[str, Any]]
        if mem_key_spawn_requests not in self.mem:
            return
        requests = self.mem[mem_key_spawn_requests]
        while len(requests['q']) > 0:
            request_key = requests['q'][0]
            request = requests['s'][request_key]
            if request.e < Game.time:
                requests['q'].shift()
                continue
            if request.p > max_priority:
                break
            role_obj = JSON.parse(request.o)
            role_obj['rkey'] = request_key
            return role_obj
        return None

    def successfully_spawned_request(self, request_key):
        # type: (str) -> None
        if mem_key_spawn_requests not in self.mem:
            return
        requests = self.mem[mem_key_spawn_requests]
        index = requests['q'].indexOf(request_key)
        if index != -1:
            requests['q'].splice(index, 1)
        del requests['s'][request_key]

    def _check_request_expirations(self):
        # type: () -> None
        if mem_key_spawn_requests not in self.mem:
            return
        requests = self.mem[mem_key_spawn_requests]
        for key in _.remove(requests['q'],
                            lambda key: _.get(requests['s'], [key, 'e'], 0) < Game.time):
            del requests['s'][key]
        if not len(requests['q']):
            del self.mem[mem_key_spawn_requests]

    def _check_role_reqs(self, role_list):
        # type: (List[List[Union[str, Callable[[], int], bool]]]) -> Optional[Dict[str, Any]]
        """
        Utility function to check the number of creeps in a role, optionally checking the work or carry mass for that
        role instead.
        """
        role_needed = None
        for role, get_ideal, count_carry, count_work in role_list:
            if count_carry:
                if self.carry_mass_of(role) - self.carry_mass_of_replacements_currently_needed_for(
                        role) < get_ideal():
                    role_needed = role
                    break
            elif count_work:
                if self.work_mass_of(role) - self.work_mass_of_replacements_currently_needed_for(
                        role) < get_ideal():
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
                roleobj_key_role: role_needed,
                roleobj_key_base: self.get_variable_base(role_needed),
                "replacing": self.get_next_replacement_name(role_needed),
                roleobj_key_num_sections: self.get_max_sections_for_role(role_needed),
            }
        else:
            return None

    def get_variable_base(self, role):
        # type: (str) -> Optional[str]
        if role == role_hauler:
            if self.paving():
                return creep_base_work_half_move_hauler
            else:
                return creep_base_hauler
        elif role == role_upgrader:
            if self.get_upgrader_energy_struct():
                return creep_base_full_upgrader
            else:
                return creep_base_worker
        else:
            return role_bases[role]

    def get_max_sections_for_role(self, role):
        # type: (str) -> int
        max_mass = {
            role_spawn_fill_backup:
                lambda: fit_num_sections(
                    self.get_target_spawn_fill_backup_carry_mass()
                    if spawning.using_lower_energy_section(self, creep_base_worker)
                    else spawning.ceil_sections(self.get_target_spawn_fill_backup_carry_mass() / 3, creep_base_worker),
                    spawning.max_sections_of(self, creep_base_worker)
                ),
            role_link_manager:
                lambda: min(self.get_target_link_manager_count() * 8,
                            spawning.max_sections_of(self, creep_base_hauler)),
            role_spawn_fill: self.get_target_spawn_fill_size,
            role_tower_fill: self.get_target_spawn_fill_size,
            role_upgrader: self.get_upgrader_size,
            role_upgrade_fill: self.get_target_upgrade_fill_mass,
            role_defender: lambda: min(4, spawning.max_sections_of(self, creep_base_defender)),
            role_wall_defender: lambda: spawning.max_sections_of(self, creep_base_rampart_defense),
            role_room_reserve:
                lambda: min(2, spawning.max_sections_of(self, creep_base_reserving)),
            role_colonist:
                lambda: spawning.max_sections_of(self, creep_base_worker),
            role_sacrifice:
                lambda: spawning.max_sections_of(self, creep_base_half_move_hauler),
            role_builder: self.get_builder_size,
            role_mineral_miner:
                lambda: min(4, spawning.max_sections_of(self, creep_base_mammoth_miner)),
            role_mineral_hauler:
                lambda: min(self.minerals.get_target_mineral_hauler_size(),
                            spawning.max_sections_of(self, creep_base_hauler)),
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
            print("[{}] Can't find max section function for role {}!".format(self.name, role))
            return Infinity

    def _next_needed_local_mining_role(self):
        # type: () -> Optional[Dict[str, Any]]
        if spawning.would_be_emergency(self):
            if not self.full_storage_use and not self.any_local_miners():
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
        if mining_role is not None and mining_role[roleobj_key_role] == role_miner:
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

    def _next_attack_role(self):
        # type: () -> Optional[Dict[str, Any]]
        attack_req = self._get_next_requested_creep(request_priority_attack)
        if attack_req:
            hauler = self._check_role_reqs([
                [role_mineral_hauler, self.minerals.get_target_mineral_hauler_count],
            ])
            if hauler:
                return hauler
            else:
                return attack_req
        else:
            return None

    def _next_needed_local_role(self):
        # type: () -> Optional[Dict[str, Any]]
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
            [role_sacrifice, self.minerals.get_target_sacrifice_count],
        ]
        return self._check_role_reqs(requirements)

    def _next_cheap_military_role(self):
        # type: () -> Optional[Dict[str, Any]]
        return self.spawn_one_creep_per_flag(SCOUT, role_scout, creep_base_scout, creep_base_scout, 1)

    def wall_defense(self):
        # type: () -> Optional[Dict[str, Any]]
        return self._check_role_reqs([
            [role_wall_defender, self.get_target_wall_defender_count],
        ])

    def _next_complex_defender(self):
        # type: () -> Optional[Dict[str, Any]]
        if self.room.energyCapacityAvailable >= 500:
            flag_list = self.flags_without_target(RANGED_DEFENSE)

            if len(flag_list):
                flag = flag_list[0]
                if flag.name in Memory.flags and flag.memory.heal:
                    base = creep_base_3h
                else:
                    base = creep_base_ranged_offense
                return self.get_spawn_for_flag(role_ranged_offense, base, base, flag, 0)
            return None

    def _next_claim(self):
        # type: () -> Optional[Dict[str, Any]]
        if self.room.energyCapacityAvailable >= 650:
            flag_list = self.flags_without_target(CLAIM_LATER)

            def _needs_claim(flag):
                c_m_cost = BODYPART_COST[MOVE] + BODYPART_COST[CLAIM]
                if self.room.energyCapacityAvailable < c_m_cost * 5 \
                        and hostile_utils.enemy_owns_room(flag.pos.roomName):
                    return False
                elif flag.pos.roomName not in Game.rooms:
                    return True
                else:
                    room = Game.rooms[flag.pos.roomName]
                    if not room.controller or room.controller.my:
                        return False
                    elif room.controller.owner and self.room.energyCapacityAvailable < c_m_cost * 5:
                        return False
                    else:
                        return True

            needed = _.find(flag_list, _needs_claim)
            if needed:
                if hostile_utils.enemy_owns_room(needed.pos.roomName):
                    return self.get_spawn_for_flag(role_simple_claim, creep_base_claim_attack,
                                                   creep_base_claim_attack, needed)
                else:
                    return self.get_spawn_for_flag(role_simple_claim, creep_base_claiming,
                                                   creep_base_claiming, needed, 1)
        return None

    def _next_tower_breaker_role(self):
        # type: () -> Optional[Dict[str, Any]]
        if not self.conducting_siege():
            return None
        role_obj = self.spawn_one_creep_per_flag(TD_H_H_STOP, role_td_healer, creep_base_half_move_healer,
                                                 creep_base_full_move_healer)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(TD_D_GOAD, role_td_goad, creep_base_goader,
                                                 creep_base_full_move_goader)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(ATTACK_DISMANTLE, role_simple_dismantle, creep_base_dismantler,
                                                 creep_base_full_move_dismantler)

        if role_obj:
            return role_obj

        role_obj = self.spawn_one_creep_per_flag(ENERGY_GRAB, role_energy_grab, creep_base_hauler,
                                                 creep_base_hauler)

        if role_obj:
            return role_obj

        role_obj = self.spawn_one_creep_per_flag(ATTACK_POWER_BANK, role_power_attack, creep_base_power_attack,
                                                 creep_base_full_move_attack)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(ATTACK_POWER_BANK, role_power_attack, creep_base_power_attack,
                                                 creep_base_full_move_attack)
        if role_obj:
            return role_obj
        role_obj = self.spawn_one_creep_per_flag(REAP_POWER_BANK, role_power_cleanup, creep_base_half_move_hauler,
                                                 creep_base_hauler)
        if role_obj:
            return role_obj
        # for flag in flags.find_flags_global(REAP_POWER_BANK):
        #     if self.hive.get_closest_owned_room(flag.pos.roomName).room_name == self.room_name:
        #         # TODO: don't duplicate in TargetMind
        #         room = self.hive.get_room(flag.pos.roomName)
        #         if not room:
        #             continue
        #         bank = room.look_at(LOOK_STRUCTURES, flag.pos)[0]
        #         if bank and bank.hits < bank.hitsMax * 0.1:
        #             return self.get_spawn_for_flag(role_power_cleanup, creep_base_half_move_hauler,
        #                                            creep_base_hauler, flag)

        return None

    def next_cheap_dismantle_goal(self):
        # type: () -> Optional[Dict[str, Any]]
        if self.conducting_siege() or self.under_siege():
            return

        def is_energy_grab_efficient(flag):
            # type: (Flag) -> bool
            home_point = self.room.storage
            add_extra = 0
            if not home_point:
                home_point = self.spawn
                add_extra = 20
            round_trip_distance = (
                self.hive.honey.find_path_length(home_point.pos, flag.pos, {'use_roads': False})
                + self.hive.honey.find_path_length(flag.pos, home_point.pos)
                + add_extra
            )
            # assuming full energy grab on recycling
            cost_per_section_per_tick = (BODYPART_COST[MOVE] + BODYPART_COST[CARRY]) / CREEP_LIFE_TIME
            profit_per_section_per_tick = (CARRY_CAPACITY / round_trip_distance)
            choosing = profit_per_section_per_tick > cost_per_section_per_tick
            print("[{}] Energy grab flag {} has {} cost/tick, {} profit/tick. {}"
                  .format(self.name, flag.name, cost_per_section_per_tick.toFixed(3),
                          profit_per_section_per_tick.toFixed(3),
                          "Spawning." if choosing else "Ignoring."))
            return choosing

        role_obj = self.spawn_one_creep_per_flag(ENERGY_GRAB, role_energy_grab, creep_base_hauler,
                                                 creep_base_hauler, 0, is_energy_grab_efficient)

        if role_obj:
            return role_obj

        role_obj = self.spawn_one_creep_per_flag(ATTACK_DISMANTLE,
                                                 role_simple_dismantle,
                                                 creep_base_dismantler,
                                                 creep_base_full_move_dismantler)
        if role_obj:
            return role_obj

    def _next_neighbor_support_creep(self):
        # type: () -> Optional[Dict[str, Any]]
        # flags_without_target is a cheap hack here, since we never target it with TARGET_SINGLE_FLAG.
        # this always gets all SUPPORT_MINE flags we own.
        mine_flags = self.flags_without_target(SUPPORT_MINE)

        def calculate_ideal_mass_for_mine(mine, wall):
            key = "smh_mass_{}".format(mine_flag.name)
            target_mass = self.get_cached_property(key)
            if target_mass:
                return target_mass
            distance = self.hive.honey.find_path_length(mine, wall, {"use_roads": False})
            carry_per_tick = CARRY_CAPACITY / (distance * 2.04 + 5)
            # With 1 added to have some leeway
            mining_per_tick = SOURCE_ENERGY_NEUTRAL_CAPACITY / ENERGY_REGEN_TIME
            target_mass = math.ceil(mining_per_tick / carry_per_tick) + 1
            self.store_cached_property(key, target_mass, 50)
            return target_mass

        for mine_flag in mine_flags:
            wall_flag = Game.flags[mine_flag.memory.wall]
            if not wall_flag:
                print("[{}] Support mine {} has no wall flag!".format(self.name, mine_flag))
                continue
            mine_flag_id = "flag-{}".format(mine_flag.name)
            wall_flag_id = "flag-{}".format(wall_flag.name)
            if self.count_noneol_creeps_targeting(target_support_miner_mine, mine_flag_id) < 1:
                return {
                    roleobj_key_role: role_support_miner,
                    roleobj_key_base: creep_base_1500miner,
                    roleobj_key_num_sections: min(3, spawning.max_sections_of(self, creep_base_1500miner)),
                    'targets': [
                        [target_support_miner_mine, mine_flag_id],
                    ]
                }
            if self.count_noneol_creeps_targeting(target_support_builder_wall, wall_flag_id) < 1:
                return {
                    roleobj_key_role: role_support_builder,
                    roleobj_key_base: creep_base_worker,
                    roleobj_key_num_sections: min(6, spawning.max_sections_of(self, creep_base_worker)),
                    'targets': [
                        [target_support_builder_wall, wall_flag_id],
                    ]
                }
            needed_hauler_mass = calculate_ideal_mass_for_mine(mine_flag, wall_flag)
            current_noneol_hauler_mass = 0
            for hauler_name in self.hive.targets.creeps_now_targeting(target_support_hauler_mine, mine_flag_id):
                creep = Game.creeps[hauler_name]
                if not creep:
                    continue
                if self.replacement_time_of(creep) > Game.time:
                    current_noneol_hauler_mass += spawning.carry_count(creep)
            if current_noneol_hauler_mass < needed_hauler_mass:
                print("[{}] Spawning hauler for {}:{}!".format(self.name, mine_flag_id, wall_flag_id))
                return {
                    roleobj_key_role: role_support_hauler,
                    roleobj_key_base: creep_base_hauler,
                    roleobj_key_num_sections: fit_num_sections(needed_hauler_mass,
                                                               spawning.max_sections_of(self, creep_base_hauler)),
                    'targets': [
                        [target_support_hauler_mine, mine_flag_id],
                        [target_support_hauler_fill, wall_flag_id]
                    ],
                }

    def spots_around_controller(self):
        # type: () -> bool
        any_spots = self.get_cached_property('controller-spots')
        if any_spots is None:
            controller_pos = self.room.controller.pos
            any_spots = False
            for x in range(controller_pos.x - 1, controller_pos.x + 2):
                for y in range(controller_pos.y - 1, controller_pos.y + 2):
                    if movement.is_block_empty(self, x, y):
                        any_spots = True
                        break
                else:
                    continue
                break
            self.store_cached_property('controller-spots', any_spots, 5000)
        return any_spots

    def _next_message_creep(self):
        # type: () -> Optional[Dict[str, Any]]
        if self.under_siege() or not self.spots_around_controller():
            return None
        message = self.get_message()
        if (self.room.controller.sign == undefined or message != self.room.controller.sign.text) \
                and self.role_count(role_sign) < 1:
            return {
                roleobj_key_role: role_sign,
                roleobj_key_base: creep_base_scout,
                roleobj_key_num_sections: 1,
            }

    def reset_planned_role(self):
        # type: () -> None
        del self.mem[mem_key_planned_role_to_spawn]
        if not self.spawn:
            sponsor = self.hive.get_room(self.sponsor_name)
            if sponsor and sponsor.spawn:
                if _.sum(self.role_counts) < 3 and sponsor.next_role is None:
                    sponsor.reset_planned_role()

    def plan_next_role(self):
        # type: () -> None
        if not self.my:
            return None
        if self.mem[mem_key_flag_for_testing_spawning_in_simulation]:
            funcs_to_try = [
                lambda: self._check_role_reqs([
                    [role_spawn_fill, self.get_target_spawn_fill_mass, True],
                ]),
                self.wall_defense,
                self._next_cheap_military_role,
                self._next_tower_breaker_role,
                self._next_complex_defender,
                self._get_next_requested_creep,
                self._next_message_creep,
                self._next_neighbor_support_creep,
            ]
        else:
            funcs_to_try = [
                self._next_needed_local_mining_role,
                lambda: self._get_next_requested_creep(request_priority_imminent_threat_defense),
                self.wall_defense,
                self._next_cheap_military_role,
                self.next_cheap_dismantle_goal,
                self._next_complex_defender,
                self._next_attack_role,
                self.mining.next_mining_role,
                lambda: self._get_next_requested_creep(request_priority_economy),
                self._next_tower_breaker_role,
                self._next_needed_local_role,
                self._next_claim,
                self._get_next_requested_creep,
                self._next_message_creep,
                self._next_neighbor_support_creep,
            ]
        next_role = None
        for func in funcs_to_try:
            next_role = func()
            if next_role:
                maximum = spawning.max_sections_of(self, next_role[roleobj_key_base])
                if next_role.num_sections is not None and next_role.num_sections > maximum:
                    print("[{}] Function decided on {} sections for {} (a {}), which is more than the allowed {}."
                          .format(self.name, next_role.num_sections, next_role[roleobj_key_base],
                                  next_role[roleobj_key_role], maximum))
                    next_role.num_sections = maximum
                break
        if next_role:
            self.mem[mem_key_planned_role_to_spawn] = next_role
        else:
            if len(self.spawns) <= 1:
                print("[{}] All creep targets reached!".format(self.name))
            self.mem[mem_key_planned_role_to_spawn] = None

    def get_next_role(self):
        # type: () -> Optional[Dict[str, Any]]
        if self.mem[mem_key_planned_role_to_spawn] is undefined:
            self.plan_next_role()
            # This function modifies the role.
            spawning.validate_role(self.mem[mem_key_planned_role_to_spawn])
        return self.mem[mem_key_planned_role_to_spawn]

    def sing(self, creeps_here_now):
        # type: (List[Creep]) -> None
        if self.name not in Memory['_ly']:
            Memory['_ly'][self.name] = [_(speech.songs).keys().sample(), 0]
        song_key, position = Memory['_ly'][self.name]
        if song_key not in speech.songs or position >= len(speech.songs[song_key]):
            song_key = _(speech.songs).keys().sample()
            position = 0
        note = speech.songs[song_key][position]
        if note is not None:
            _.sample(creeps_here_now).say(note, True)
        Memory['_ly'][self.name] = [song_key, position + 1]

    def get_message(self):
        # type: () -> str
        message = self.get_cached_property("_msg")

        if not message:
            message = rndrs.rs()
            self.store_cached_property("_msg", message, random.randint(500, 1000))
        return message

    def toString(self):
        # type: () -> str
        return "RoomMind[name: {}, my: {}, using_storage: {}, conducting_siege: {}]".format(
            self.name, self.my, self.full_storage_use, self.conducting_siege())

    position = property(get_position)
    sources = property(get_sources)
    spawns = property(get_spawns)
    spawn = property(get_spawn)
    creeps = property(get_creeps)
    work_mass = property(get_work_mass)
    next_role = property(get_next_role)
    rt_map = property(_get_rt_map)
    trying_to_get_full_storage_use = property(get_trying_to_get_full_storage_use)
    full_storage_use = property(get_full_storage_use)
    max_sane_wall_hits = property(get_max_sane_wall_hits)
    min_sane_wall_hits = property(get_min_sane_wall_hits)
