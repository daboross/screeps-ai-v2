import math

import spawning
from constants import creep_base_work_half_move_hauler, creep_base_work_full_move_hauler, creep_base_hauler, \
    target_remote_mine_miner, role_remote_miner, creep_base_3000miner, role_remote_mining_reserve, \
    creep_base_reserving, \
    target_remote_mine_hauler, role_remote_hauler, creep_base_4500miner
from control import live_creep_utils
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


# TODO: this is duplicated in HiveMind
def fit_num_sections(needed, maximum, extra_initial=0.0, min_split=1):
    if maximum <= 1:
        return maximum

    num = min_split
    trying = Infinity
    while trying > maximum:
        trying = math.ceil(needed / num - extra_initial)
        num += 1
    return trying


# TODO: expand this for local dedicated mining as well as the remote mining
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
        self._active_mining_flags = None

    def closest_deposit_point_to_mine(self, flag):
        key = "mine_{}_deposit".format(flag.name)
        target_id = self.room.get_cached_property(key)
        if target_id:
            target = Game.getObjectById(target_id)
            if target:
                return target
        # Even if we don't have a link manager active right now, we will soon if there is a main link
        if self.room.links.main_link:
            main_link_id = self.room.links.main_link.id
            target = self.room.find_closest_by_range(
                FIND_MY_STRUCTURES, flag,
                lambda s: (s.structureType == STRUCTURE_LINK or s.structureType == STRUCTURE_STORAGE)
                          and s.id != main_link_id
            )
        elif self.room.room.storage:
            target = self.room.room.storage
        elif self.room.spawn:
            target = self.room.spawn
        else:
            return None

        target_id = target.id
        if not self.room.links.enabled_last_turn and self.room.links.main_link:
            self.room.store_cached_property(key, target_id, 5)
        else:
            self.room.store_cached_property(key, target_id, 50)
        return target

    def distance_to_mine(self, flag):
        deposit_point = self.closest_deposit_point_to_mine(flag)
        if deposit_point:
            return len(self.hive.honey.find_path(deposit_point, flag))
        else:
            # This will happen if we have no storage nor spawn
            return Infinity

    def calculate_ideal_mass_for_mine(self, flag):
        key = "mine_{}_ideal_mass".format(flag.name)
        target_mass = self.room.get_cached_property(key)
        if target_mass:
            return target_mass
        # each carry can carry 50 energy.
        carry_per_tick = 50.0 / (self.distance_to_mine(flag) * 2.1)
        room = Game.rooms[flag.pos.roomName]
        if room and room.controller and room.controller.reservation:
            mining_per_tick = 11.0  # With 1 added just to have some leeway
        elif flag.memory.sk_room:
            mining_per_tick = 16.0  # With 1 added to have some leeway
        else:
            mining_per_tick = 6.0  # With 1 added just to have some leeway
        produce_per_tick = mining_per_tick
        target_mass = math.ceil(produce_per_tick / carry_per_tick) + 2
        self.room.store_cached_property(key, target_mass, 50)
        return target_mass

    def calculate_current_target_mass_for_mine(self, flag):
        ideal_mass = self.calculate_ideal_mass_for_mine(flag)
        sitting = flag.memory.sitting if flag.memory.sitting else 0
        if sitting > 1000:
            carry_per_tick = 50.0 / (self.distance_to_mine(flag) * 2.1)
            # Count every 200 already there as an extra 1 production per turn
            return ideal_mass + min(math.ceil(sitting / 500 / carry_per_tick), ideal_mass)
        else:
            return ideal_mass

    def poll_flag_energy_sitting(self):
        for flag in self.available_mines:
            room = self.hive.get_room(flag.pos.roomName)
            if room:
                sitting = _.sum(room.find_in_range(FIND_DROPPED_RESOURCES, 1, flag.pos), 'amount')
                flag.memory.sitting = sitting
            else:
                if flag.memory.sitting > 0:
                    flag.memory.sitting -= 1
                else:
                    flag.memory.sitting = 0
            if flag.memory.remote_miner_targeting and not Game.creeps[flag.memory.remote_miner_targeting]:
                del flag.memory.remote_miner_targeting

    def get_available_mining_flags(self):
        if self._available_mining_flags is None:
            # list() here since lodash-returned lists aren't instanceof the Array prototype given to our code.
            self._available_mining_flags = list(
                _.sortBy(self.room.possible_remote_mining_operations, self.distance_to_mine))
        return self._available_mining_flags

    available_mines = property(get_available_mining_flags)

    def get_active_mining_flags(self):
        if self._active_mining_flags is None:
            max_count = self.room.get_max_mining_op_count()
            if max_count > len(self.available_mines):
                max_count = len(self.available_mines)
            self._active_mining_flags = self.available_mines[:max_count]
        return self._active_mining_flags

    active_mines = property(get_active_mining_flags)

    def calculate_creep_num_sections_for_mine(self, flag):
        if self.room.all_paved():
            maximum = spawning.max_sections_of(self.room, creep_base_work_half_move_hauler)
        elif self.room.paving():
            maximum = spawning.max_sections_of(self.room, creep_base_work_full_move_hauler)
        else:
            maximum = spawning.max_sections_of(self.room, creep_base_hauler)
        needed = self.calculate_ideal_mass_for_mine(flag)
        if self.room.all_paved():
            # Each section has twice the carry, and the initial section has half the carry of one regular section.
            return fit_num_sections(needed / 2, maximum, 0.5)
        else:
            return fit_num_sections(needed, maximum)

    def reserver_needed(self, flag):
        """
        Gets the spawn data for a reserver if a reserver is needed. Separate method so that early return statements can
        be used and we don't get tons and tons of nested if statements.
        """
        if flag.memory.sk_room or Memory.no_controller and Memory.no_controller[flag.pos.roomName]:
            return None

        if not Memory.reserving:
            Memory.reserving = {}

        room_name = flag.pos.roomName
        # Reservation ends at, set in the RemoteReserve class
        if room_name in Memory.rooms and 'rea' in Memory.rooms[room_name]:
            ticks_to_end = Memory.rooms[room_name].rea - Game.time
            if ticks_to_end >= 1000:
                max_sections = min(5, spawning.max_sections_of(self.room, creep_base_reserving))
                if 5000 - ticks_to_end < max_sections * 600:
                    return None

        claimer = Game.creeps[Memory.reserving[flag.pos.roomName]]
        if not claimer or live_creep_utils.replacement_time(claimer) <= Game.time \
                and not Game.creeps[claimer.memory.replacement]:
            room = Game.rooms[flag.pos.roomName]
            if room and not room.controller:
                Memory.no_controller[flag.pos.roomName] = True
            else:
                def run_after(name):
                    Memory.reserving[flag.pos.roomName] = name

                return {
                    'role': role_remote_mining_reserve,
                    'base': creep_base_reserving,
                    'num_sections': min(5, spawning.max_sections_of(self.room, creep_base_reserving)),
                    'memory': {
                        'claiming': flag.pos.roomName
                    },
                    'run_after': run_after,
                }
        else:
            return None

    def get_next_needed_mining_role_for(self, flag):
        flag_id = "flag-{}".format(flag.name)
        miners = self.targets.creeps_now_targeting(target_remote_mine_miner, flag_id)
        miner_needed = False
        if len(miners):
            # In order to have replacement miners correctly following the cached path and saving CPU, we no longer use
            # the generic "replacing" class, and instead just assign the new miner to the same source. The miner has
            # code to replace the old miner successfully through suicide itself.
            for miner_name in miners:
                creep = Game.creeps[miner_name]
                if not creep:
                    continue
                if live_creep_utils.replacement_time(creep) > Game.time:
                    break
            else:
                # We only need one miner, so let's just spawn a new one if there aren't any with replacement time left.
                miner_needed = True
        else:
            miner_needed = True
        if miner_needed:
            if flag.memory.sk_room:
                base = creep_base_4500miner
                num_sections = min(8, spawning.max_sections_of(self.room, base))
            else:
                base = creep_base_3000miner
                num_sections = min(5, spawning.max_sections_of(self.room, base))
            return {
                'role': role_remote_miner,
                'base': base,
                'num_sections': num_sections,
                'targets': [
                    [target_remote_mine_miner, flag_id.format(flag.name)],
                ]
            }

        reserver_needed = self.reserver_needed(flag)
        if reserver_needed:
            return reserver_needed

        current_noneol_hauler_mass = 0
        eol_mass = 0
        for hauler_name in self.targets.creeps_now_targeting(target_remote_mine_hauler, flag_id):
            creep = Game.creeps[hauler_name]
            if not creep:
                continue
            if live_creep_utils.replacement_time(creep) > Game.time:
                current_noneol_hauler_mass += spawning.carry_count(creep)
            else:
                eol_mass += spawning.carry_count(creep)
        if current_noneol_hauler_mass < self.calculate_current_target_mass_for_mine(flag):
            if self.room.all_paved():
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
                'role': role_remote_hauler,
                'base': base,
                'num_sections': self.calculate_creep_num_sections_for_mine(flag),
                'targets': [
                    [target_remote_mine_hauler, flag_id]
                ],
            }

        # print("[{}][mining] All roles reached for {}!".format(self.room.room_name, flag.name))
        return None

    def next_remote_mining_role(self, max_to_check):
        if max_to_check <= 0: return None
        mines = self.available_mines
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
