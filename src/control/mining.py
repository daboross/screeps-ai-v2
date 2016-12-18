import math

import flags
import spawning
from constants import creep_base_work_half_move_hauler, creep_base_work_full_move_hauler, creep_base_hauler, \
    target_energy_miner_mine, role_miner, creep_base_3000miner, role_remote_mining_reserve, \
    creep_base_reserving, target_energy_hauler_mine, role_hauler, creep_base_4000miner, creep_base_carry3000miner, \
    creep_base_1500miner, creep_base_half_move_hauler
from control import defense
from utilities import movement
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


# TODO: this is duplicated in HiveMind
def fit_num_sections(needed, maximum, extra_initial=0.0, min_split=1):
    if maximum <= 1:
        return maximum

    num = min_split
    trying = Infinity
    while trying > maximum:
        trying = spawning.ceil_sections(needed / num - extra_initial)
        num += 1
    return trying


__pragma__('fcall')


class MiningMind:
    """
    :type room: control.hivemind.RoomMind
    :type hive: control.hivemind.HiveMind
    :type targets: control.targets.TargetMind
    """

    def __init__(self, room):
        self.room = room
        self.hive = room.hive_mind
        self.targets = self.hive.target_mind
        self._available_mining_flags = None
        self._local_mining_flags = None
        self._active_mining_flags = None

    def closest_deposit_point_to_mine(self, flag):
        key = "mine_{}_deposit".format(flag.name)
        target_id = self.room.get_cached_property(key)
        if target_id:
            target = Game.getObjectById(target_id)
            if target:
                return target
        # Even if we don't have a link manager active right now, we will soon if there is a main link
        if self.room.links.main_link and flag.pos.roomName == self.room.room_name:
            main_link_id = self.room.links.main_link.id
            upgrader_link = self.room.get_upgrader_energy_struct()
            upgrader_link_id = upgrader_link and upgrader_link.id or None
            best_priority = Infinity
            best = None
            for structure in self.room.find(FIND_MY_STRUCTURES):
                if structure.structureType == STRUCTURE_LINK and structure.energyCapacity > 0:
                    if structure.id == main_link_id or structure.id == upgrader_link_id:
                        continue
                    priority = movement.chebyshev_distance_room_pos(structure, flag)
                    if priority <= 2:
                        priority -= 14
                elif structure.structureType == STRUCTURE_STORAGE and structure.storeCapacity > 0:
                    priority = movement.chebyshev_distance_room_pos(structure, flag) - 10
                else:
                    continue
                if priority < best_priority:
                    best_priority = priority
                    best = structure
            target = best
        elif self.room.room.storage and self.room.room.storage.storeCapacity > 0:
            target = self.room.room.storage
        elif self.room.spawn:
            target = self.room.spawn
        else:
            return None

        target_id = target.id
        self.room.store_cached_property(key, target_id, 50)
        return target

    def mine_priority(self, flag):
        priority = self.distance_to_mine(flag)
        if flag.pos.roomName == self.room.room_name:
            priority -= 50
        if flag.memory.sk_room:
            priority -= 40
        elif self.should_reserve(flag.pos.roomName):
            priority -= 30
        return priority

    def distance_to_mine(self, flag):
        deposit_point = self.closest_deposit_point_to_mine(flag)
        if deposit_point:
            if deposit_point.structureType == STRUCTURE_SPAWN:
                return self.hive.honey.find_path_length(deposit_point, flag) + 20
            else:
                return self.hive.honey.find_path_length(deposit_point, flag)
        else:
            # This will happen if we have no storage nor spawn
            return Infinity

    def calculate_ideal_mass_for_mine(self, flag):
        key = "mine_{}_ideal_mass".format(flag.name)
        target_mass = self.room.get_cached_property(key)
        if target_mass:
            return target_mass
        # each carry can carry 50 energy.
        carry_per_tick = 50.0 / (self.distance_to_mine(flag) * 2.1 + 5)
        room = Game.rooms[flag.pos.roomName]
        # With 1 added to have some leeway
        if room and room.controller and room.controller.my:
            mining_per_tick = 10.0
        elif flag.memory.sk_room or (room and not room.controller):
            mining_per_tick = 15.0
        elif self.should_reserve(flag.pos.roomName):
            mining_per_tick = 10.0
        else:
            mining_per_tick = 5.0
        produce_per_tick = mining_per_tick
        target_mass = math.ceil(produce_per_tick / carry_per_tick) + 1
        self.room.store_cached_property(key, target_mass, 50)
        return target_mass

    def calculate_current_target_mass_for_mine(self, flag):
        ideal_mass = self.calculate_ideal_mass_for_mine(flag)
        if not self.room.room.storage:
            return ideal_mass
        # sitting = self.energy_sitting_at(flag)
        # if sitting > 1000:
        #     carry_per_tick = 50.0 / (self.distance_to_mine(flag) * 2.1 + 10)
        #     # Count every 200 already there as an extra 1 production per turn
        #     return ideal_mass + min(math.ceil(sitting / 500 / carry_per_tick), ideal_mass)
        # else:
        return ideal_mass

    def poll_flag_energy_sitting(self):
        for flag in self.available_mines:
            if 'sitting' in flag.memory and flag.memory.sitting < Game.time - flag.memory.sitting_set \
                    and Game.time - flag.memory.sitting_set > 10:
                del flag.memory.sitting
                del flag.memory.sitting_set
                del flag.memory.remote_miner_targeting

    def energy_sitting_at(self, flag):
        if 'sitting' not in flag.memory or Game.time > flag.memory.sitting_set + 10:
            room = self.hive.get_room(flag.pos.roomName)
            if room:
                flag.memory.sitting = _.sum(room.look_for_in_area_around(LOOK_RESOURCES, flag, 1),
                                            'resource.amount')
            elif 'sitting_set' in flag.memory:
                flag.memory.sitting = max(0, flag.memory.sitting + flag.memory.sitting_set - Game.time)
            else:
                flag.memory.sitting = 0
            flag.memory.sitting_set = Game.time
        return max(0, flag.memory.sitting - (Game.time - flag.memory.sitting_set)) or 0

    def get_local_mining_flags(self):
        if self._local_mining_flags is None:
            result = []
            for source in self.room.sources:
                flag = flags.look_for(self.room, source, flags.LOCAL_MINE)
                if not flag:
                    name = flags.create_flag(source, flags.LOCAL_MINE)
                    if not name:
                        print("[{}][mining] Warning: Couldn't create local mining flag!".format(
                            self.room.room_name))
                        continue
                    flag = Game.flags[name]
                    if not flag:
                        print("[{}][mining] Warning: Couldn't find local mining flag with name {}!".format(
                            self.room.room_name, name))
                        continue
                if 'sponsor' not in flag.memory:
                    flag.memory.sponsor = self.room.room_name
                    flag.memory.active = True
                result.append(flag)
            self._local_mining_flags = result
        return self._local_mining_flags

    local_mines = property(get_local_mining_flags)

    def get_available_mining_flags(self):
        if self._available_mining_flags is None:
            if self.room.any_remotes_under_siege():
                result = list(_(self.get_local_mining_flags())
                              .concat(self.room.possible_remote_mining_operations)
                              .filter(lambda f: not self.room.remote_under_siege(f))
                              .sortBy(self.mine_priority)
                              .value())
            else:
                result = list(_(self.get_local_mining_flags())
                              .concat(self.room.possible_remote_mining_operations)
                              .sortBy(self.mine_priority)
                              .value())
            self._available_mining_flags = result
        return self._available_mining_flags

    available_mines = property(get_available_mining_flags)

    def get_active_mining_flags(self):
        if self._active_mining_flags is None:
            max_count = len(self.room.sources) + self.room.get_max_mining_op_count()
            if max_count > len(self.available_mines):
                max_count = len(self.available_mines)
            self._active_mining_flags = self.available_mines[:max_count]
        return self._active_mining_flags

    active_mines = property(get_active_mining_flags)

    def calculate_creep_num_sections_for_mine(self, flag):
        double = False
        if flag.pos.roomName == self.room.room_name:
            if self.room.all_paved():
                maximum = spawning.max_sections_of(self.room, creep_base_half_move_hauler)
                double = True
            else:
                maximum = spawning.max_sections_of(self.room, creep_base_hauler)
        elif self.room.all_paved():
            maximum = spawning.max_sections_of(self.room, creep_base_work_half_move_hauler)
            double = True
        elif self.room.paving():
            maximum = spawning.max_sections_of(self.room, creep_base_work_full_move_hauler)
        else:
            maximum = spawning.max_sections_of(self.room, creep_base_hauler)
        needed = self.calculate_ideal_mass_for_mine(flag)
        if double:
            # Each section has twice the carry, -and the initial section has half the carry of one regular section.-
            # as of 2016/11/02, we have WWM initial sections, not CWM
            return fit_num_sections(needed / 2, maximum)
        else:
            return fit_num_sections(needed, maximum)

    def should_reserve(self, room_name):
        if self.room.room.energyCapacityAvailable < 1300:
            return False
        flag_list = _.filter(flags.find_flags(room_name, flags.REMOTE_MINE), lambda f: f.memory.active)
        if _.find(flag_list, lambda f: f.memory.sk_room):
            return False
        if _.find(flag_list, lambda f: f.memory.do_reserve):
            return True
        if len(flag_list) < 2:
            return False
        return True

    def open_spaces_around(self, flag):
        if 'osa' not in flag.memory:
            osa = 0
            room = self.hive.get_room(flag.pos.roomName)
            for x in range(flag.pos.x - 1, flag.pos.x + 2):
                for y in range(flag.pos.y - 1, flag.pos.y + 2):
                    if room:
                        if movement.is_block_empty(room, x, y):
                            osa += 1
                    else:
                        if Game.map.getTerrainAt(x, y, flag.pos.roomName) != 'wall':
                            osa += 1
            flag.memory.osa = osa
        return flag.memory.osa

    def reserver_needed(self, flag):
        """
        Gets the spawn data for a reserver if a reserver is needed. Separate method so that early return statements can
        be used and we don't get tons and tons of nested if statements.
        """
        room_name = flag.pos.roomName

        if flag.memory.sk_room or Memory.no_controller and Memory.no_controller[room_name] \
                or not self.should_reserve(room_name):
            return None

        if room_name in Game.rooms:
            controller = Game.rooms[room_name].controller
            if not controller:
                if 'no_controller' in Memory:
                    Memory.no_controller[room_name] = True
                else:
                    Memory.no_controller = {room_name: True}
                return None
            elif controller.my:
                return None
        if not Memory.reserving:
            Memory.reserving = {}

        # Reservation ends at, set in the RemoteReserve class
        if room_name in Memory.rooms and 'rea' in Memory.rooms[room_name]:
            ticks_to_end = Memory.rooms[room_name].rea - Game.time
            if ticks_to_end >= 1000:
                max_sections = min(5, spawning.max_sections_of(self.room, creep_base_reserving))
                if 5000 - ticks_to_end < max_sections * 600:
                    return None

        claimer = Game.creeps[Memory.reserving[room_name]]
        if not claimer or self.room.replacement_time_of(claimer) <= Game.time \
                and not Game.creeps[claimer.memory.replacement]:
            room = Game.rooms[room_name]
            if room and not room.controller:
                Memory.no_controller[room_name] = True
            else:
                return {
                    'role': role_remote_mining_reserve,
                    'base': creep_base_reserving,
                    'num_sections': min(5, spawning.max_sections_of(self.room, creep_base_reserving)),
                    'memory': {
                        'claiming': room_name
                    },
                    'run_after': '(name) => Memory.reserving[\'{}\'] = name'.format(room_name),
                }
        else:
            return None

    def get_ideal_miner_workmass_for(self, flag):
        if flag.memory.sk_room:
            return 7
        elif flag.pos.roomName == self.room.room_name or self.should_reserve(flag.pos.roomName):
            return 5
        else:
            return 3

    def haulers_can_target_mine(self, flag):
        # TODO: duplicated in get_next_needed_mining_role_for

        miner_carry_no_haulers = (
            flag.pos.roomName == self.room.room_name
            and self.room.room.energyCapacityAvailable >= 600
            and flag.pos.inRangeTo(self.closest_deposit_point_to_mine(flag), 2)
        )
        no_haulers = (
            flag.pos.roomName == self.room.room_name
            and (self.room.rcl < 4 or not self.room.room.storage)
        )
        return not miner_carry_no_haulers and not no_haulers

    def get_next_needed_mining_role_for(self, flag):
        flag_id = "flag-{}".format(flag.name)
        miner_carry_no_haulers = (
            flag.pos.roomName == self.room.room_name
            and self.room.room.energyCapacityAvailable >= 600
            and flag.pos.inRangeTo(self.closest_deposit_point_to_mine(flag), 2)
        )
        no_haulers = (
            flag.pos.roomName == self.room.room_name
            and (self.room.rcl < 4 or not self.room.room.storage)
        )

        if len(defense.stored_hostiles_in(flag.pos.roomName)):
            return None

        miners = self.targets.creeps_now_targeting(target_energy_miner_mine, flag_id)
        miner_needed = False
        if len(miners):
            # In order to have replacement miners correctly following the cached path and saving CPU, we no longer use
            # the generic "replacing" class, and instead just assign the new miner to the same source. The miner has
            # code to replace the old miner successfully through suicide itself.
            # TODO: utility function
            if self.room.rcl < 4:
                work_mass_needed = self.get_ideal_miner_workmass_for(flag)

                # We don't want to do more than one miner in any remote mine due to remote haulers not having logic to
                # go for the biggest energy pile instead of moving towards the source itself. We can still do this for
                # local mines though, at low RCL levels.
                if flag.pos.roomName == self.room.room_name:
                    workers_needed = self.open_spaces_around(flag)
                else:
                    workers_needed = 1
            else:
                work_mass_needed = None
                workers_needed = None
            for miner_name in miners:
                creep = Game.creeps[miner_name]
                if not creep:
                    continue
                if self.room.replacement_time_of(creep) > Game.time:
                    if work_mass_needed is None:
                        break
                    work_mass_needed -= spawning.work_count(creep)
                    if work_mass_needed <= 0:
                        break
                    workers_needed -= 1
                    if workers_needed <= 0:
                        break
            else:
                # We only need one miner, so let's just spawn a new one if there aren't any with replacement time left.
                miner_needed = True
        else:
            miner_needed = True
        if miner_needed:
            if miner_carry_no_haulers:
                base = creep_base_carry3000miner
                num_sections = min(5, spawning.max_sections_of(self.room, base))
            elif flag.memory.sk_room:
                base = creep_base_4000miner
                num_sections = min(7, spawning.max_sections_of(self.room, base))
            elif flag.pos.roomName == self.room.room_name or self.should_reserve(flag.pos.roomName):
                base = creep_base_3000miner
                num_sections = min(5, spawning.max_sections_of(self.room, base))
            else:
                base = creep_base_1500miner
                num_sections = min(3, spawning.max_sections_of(self.room, base))
            if self.room.all_paved():
                num_sections = spawning.ceil_sections(num_sections / 2, base)
            return {
                'role': role_miner,
                'base': base,
                'num_sections': num_sections,
                'targets': [
                    [target_energy_miner_mine, flag_id],
                ]
            }

        reserver_needed = self.reserver_needed(flag)
        if reserver_needed:
            return reserver_needed

        if miner_carry_no_haulers or no_haulers:
            return None

        current_noneol_hauler_mass = 0
        for hauler_name in self.targets.creeps_now_targeting(target_energy_hauler_mine, flag_id):
            creep = Game.creeps[hauler_name]
            if not creep:
                continue
            if self.room.replacement_time_of(creep) > Game.time:
                current_noneol_hauler_mass += spawning.carry_count(creep)
        if current_noneol_hauler_mass < self.calculate_current_target_mass_for_mine(flag):
            if flag.pos.roomName == self.room.room_name:
                if self.room.all_paved():
                    base = creep_base_half_move_hauler
                else:
                    base = creep_base_hauler
            elif self.room.all_paved():
                base = creep_base_work_half_move_hauler
            elif self.room.paving():
                # TODO: better all_paved detection *per mine* (all_paved currently is always set to paving() value)
                base = creep_base_work_full_move_hauler
            else:
                base = creep_base_hauler

            # TODO: make an "colony report" module which this can be included in
            # new_hauler_num_sections = self.calculate_creep_num_sections_for_mine(flag)
            # if base == creep_base_work_half_move_hauler:
            #     new_hauler_mass = new_hauler_num_sections * 2 + 1
            # else:
            #     new_hauler_mass = new_hauler_num_sections
            # print('[{}][mining] Hauler stats for {}: ideal_mass: {}, current_target: {}, current_hauler_mass: {},'
            #       ' eol_hauler_mass: {}, hauler_size: {} ({} sections)'
            #       .format(self.room.room_name, flag.name, self.calculate_ideal_mass_for_mine(flag),
            #               self.calculate_current_target_mass_for_mine(flag), current_noneol_hauler_mass, eol_mass,
            #               new_hauler_mass, new_hauler_num_sections))

            return {
                'role': role_hauler,
                'base': base,
                'num_sections': self.calculate_creep_num_sections_for_mine(flag),
                'targets': [
                    [target_energy_hauler_mine, flag_id]
                ],
            }

        # print("[{}][mining] All roles reached for {}!".format(self.room.room_name, flag.name))
        return None

    def next_mining_role(self, max_to_check=Infinity):
        if max_to_check <= 0: return None
        mines = self.active_mines
        if len(mines) <= 0: return None
        if self.room.room.storage and self.room.room.storage.store.energy > self.room.room.storage.storeCapacity:
            return None
        known_nothing_needed = volatile_cache.setmem("rolechecked_mines")
        checked_count = 0
        for mining_flag in mines:
            if not known_nothing_needed.has(mining_flag.name):
                role = self.get_next_needed_mining_role_for(mining_flag)
                if role:
                    return role
                else:
                    known_nothing_needed.add(mining_flag.name)
            checked_count += 1
            if checked_count >= max_to_check:
                break

        return None


__pragma__('nofcall')
