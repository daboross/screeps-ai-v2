import math

import context
import creep_wrappers
import flags
from constants import *
from control.building import ConstructionMind
from control.pathdef import HoneyTrails, CachedTrails
from role_base import RoleBase
from tools import profiling
from utilities import consistency
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_MAX_BUILDERS = 3

SLIGHTLY_SMALLER_THAN_MAX_INT = math.pow(2, 30)


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
_min_work_mass_remote_mining_operation = 25
_extra_work_mass_per_extra_remote_mining_operation = 10
_min_energy_pause_remote_mining = 950000
_max_energy_resume_remote_mining = 700000
_min_work_mass_for_full_storage_use = 35

_min_energy_enable_full_storage_use = 10000
_max_energy_disable_full_storage_use = 5000
_energy_to_resume_upgrading = 10000
_energy_to_pause_upgrading = 8000
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
    :type honey: HoneyTrails
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
        self.honey = HoneyTrails(self)
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
        self.store_cached_property(key, result, 0)
        self.mem.cache[key].dead_at = self.mem.meta.clear_next + 1
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

    def precreep_tick_actions(self):
        time = Game.time
        meta = self.mem.meta
        if not meta:
            meta = {"clear_next": 0, "reset_spawn_on": 0}
            self.mem.meta = meta

        if time > meta.clear_next:
            print("[{}] Clearing memory".format(self.room_name))
            consistency.clear_memory(self)
            self.recalculate_roles_alive()
            # Recalculate spawning - either because a creep death just triggered our clearing memory, or we haven't
            # recalculated in the last 500 ticks.
            # TODO: do we really need to recalculate every 500 ticks? even though it really isn't expensive
            self.reset_planned_role()
            del meta.clear_now
            print("[{}] Next clear in {} ticks.".format(self.room_name, meta.clear_next - Game.time))

        # reset_spawn_on is set to the tick after the next creep's TTR expires in consistency.clear_memory()
        if time > meta.reset_spawn_on:
            self.reset_planned_role()

        # TODO: this will make both rooms do it at the same time, but this is better than checking every time memory is cleared!
        if Game.time % 100 == 0:
            consistency.reassign_room_roles(self)

    def poll_hostiles(self):
        if not Memory.hostiles:
            Memory.hostiles = []
        if not Memory.hostile_last_rooms:
            Memory.hostile_last_rooms = {}
        if not Memory.hostile_last_positions:
            Memory.hostile_last_positions = {}
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
            Memory.hostile_last_positions[hostile.id] = hostile.pos

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
        if not self.full_storage_use:
            return False
        if self.mem.upgrading_paused and self.room.storage.store.energy > _energy_to_resume_upgrading:
            self.mem.upgrading_paused = False
        if not self.mem.upgrading_paused and self.room.storage.store.energy < _energy_to_pause_upgrading:
            self.mem.upgrading_paused = True
        return not not self.mem.upgrading_paused

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
            if self.work_mass > _min_work_mass_remote_mining_operation and not self.mining_ops_paused():
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
            if self.room_name == "W46N28":
                # TODO: Make it possible to scale things based off of "input energy" or hauler count of mined sources.
                # more are needed because there are no links and storage is a long way from spawn.
                total_needed = 3 + len(self.sources) + len(_.filter(
                    self.remote_mining_operations, lambda flag: not not flag.memory.remote_miner_targeting))
                print("[{}] Activating special spawn fill target count. TODO: remove".format(self.room_name))
            else:
                total_needed = 2 + len(self.sources)
            regular_count = max(0, total_needed - tower_fill - spawn_fill_backup)
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
        if self.upgrading_paused() and not len(self.building.next_priority_construction_targets()):
            return 0
        elif self.mining_ops_paused():
            return 4 + 2 * len(self.sources)
        else:
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


profiling.profile_whitelist(RoomMind, [
    "recalculate_roles_alive",
    "precreep_tick_actions",
    "poll_hostiles",
    "plan_next_role"
])
