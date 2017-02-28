import math

from cache import volatile_cache
from constants import LOCAL_MINE, REMOTE_MINE, creep_base_1500miner, creep_base_3000miner, creep_base_4000miner, \
    creep_base_carry3000miner, creep_base_half_move_hauler, creep_base_hauler, creep_base_reserving, \
    creep_base_work_full_move_hauler, creep_base_work_half_move_hauler, role_hauler, role_miner, \
    role_remote_mining_reserve, target_energy_hauler_mine, target_energy_miner_mine
from creep_management import spawning
from creep_management.spawning import fit_num_sections
from empire import stored_data
from jstools.screeps import *
from position_management import flags
from rooms import defense
from utilities import movement, paths

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

__pragma__('fcall')


def is_sk(flag):
    return (flag.name in Memory.flags and flag.memory.sk_room) \
           or (Memory.no_controller and Memory.no_controller[flag.pos.roomName])


class MiningMind:
    """
    :type room: rooms.room_mind.RoomMind
    :type hive: empire.hive.HiveMind
    :type targets: empire.targets.TargetMind
    :type active_mines: list[Flag]
    :type available_mines: list[Flag]
    """

    def __init__(self, room):
        self.room = room
        self.hive = room.hive
        self.targets = self.hive.targets
        self._available_mining_flags = None
        self._local_mining_flags = None
        self._active_mining_flags = None

    def closest_deposit_point_to_mine(self, flag):
        """
        Gets the closest deposit point to the mine. Currently just returns storage or spawn, since we need to do more
        changes in order to support links well anyways.
        :param flag:
        :return:
        """
        key = "mine_{}_deposit".format(flag.name)
        target_id = self.room.get_cached_property(key)
        if target_id:
            target = Game.getObjectById(target_id)
            if target:
                return target
        # Even if we don't have a link manager active right now, we will soon if there is a main link
        if self.room.links.main_link and flag.pos.roomName == self.room.name:
            main_link_id = self.room.links.main_link.id
            upgrader_link = self.room.get_upgrader_energy_struct()
            upgrader_link_id = upgrader_link and upgrader_link.id or None
            storage = self.room.room.storage
            if storage and storage.storeCapacity > 0:
                distance = movement.chebyshev_distance_room_pos(storage, flag)
                if distance <= 2:
                    best_priority = -40
                    best = storage
                else:
                    best_priority = 0
                    best = storage
            else:
                best_priority = Infinity
                best = None
            if best_priority > -40:
                for link in self.room.links.links:
                    if link.energyCapacity <= 0 or link.id == main_link_id:
                        continue
                    distance = movement.chebyshev_distance_room_pos(link, flag)
                    if distance <= 2:
                        priority = -20
                    elif link.id == upgrader_link_id:
                        continue
                    else:
                        priority = distance
                    if priority < best_priority:
                        best_priority = priority
                        best = link
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
        if flag.pos.roomName == self.room.name:
            priority -= 50
        if is_sk(flag):
            priority -= 40
        elif self.should_reserve(flag.pos.roomName):
            priority -= 30
        return priority

    def distance_to_mine(self, flag):
        deposit_point = self.closest_deposit_point_to_mine(flag)
        if deposit_point:
            if deposit_point.structureType == STRUCTURE_SPAWN:
                return self.hive.honey.find_path_length(deposit_point, flag, {"use_roads": False}) + 20
            else:
                return self.hive.honey.find_path_length(deposit_point, flag, {"use_roads": False})
        else:
            # This will happen if we have no storage nor spawn
            return Infinity

    def calculate_ideal_mass_for_mine(self, flag):
        key = "mine_{}_ideal_mass".format(flag.name)
        target_mass = self.room.get_cached_property(key)
        if target_mass:
            return target_mass
        # each carry can carry 50 energy.
        carry_per_tick = CARRY_CAPACITY / (self.distance_to_mine(flag) * 2.04 + 5)
        room = Game.rooms[flag.pos.roomName]
        # With 1 added to have some leeway
        if room and room.controller and room.controller.my:
            mining_per_tick = SOURCE_ENERGY_CAPACITY / ENERGY_REGEN_TIME
        elif is_sk(flag):
            mining_per_tick = SOURCE_ENERGY_KEEPER_CAPACITY / ENERGY_REGEN_TIME
        elif self.should_reserve(flag.pos.roomName):
            mining_per_tick = SOURCE_ENERGY_CAPACITY / ENERGY_REGEN_TIME
        else:
            mining_per_tick = SOURCE_ENERGY_NEUTRAL_CAPACITY / ENERGY_REGEN_TIME
        produce_per_tick = mining_per_tick
        target_mass = math.ceil(produce_per_tick / carry_per_tick) + 1
        self.room.store_cached_property(key, target_mass, 50)
        return target_mass

    def calculate_current_target_mass_for_mine(self, flag):
        return self.calculate_ideal_mass_for_mine(flag)

    def road_repair_work_needed_now(self, flag):
        """
        Gets road health from storage to flag, returning the ideal number of creeps with 2 work parts each who should be
        on this mine.
        :param flag: the flag
        :return: road health
        """
        key = "{}-health".format(flag)
        road_health = self.room.get_cached_property(key)
        if road_health is not None:
            return road_health

        deposit_point = self.closest_deposit_point_to_mine(flag)

        if not deposit_point:
            raise ValueError("mine_road_health called for mine with no deposit point.")

        max_damage = 0
        for room_name, serialized_path in self.hive.honey \
                .get_ordered_list_of_serialized_path_segments(flag, deposit_point, {'paved_for': flag}):
            cut_off_start = room_name == flag.pos.roomName
            room = Game.rooms[room_name]
            if not room:
                continue
            dx_dy = paths.direction_to_dx_dy(int(serialized_path[4]))
            x = int(serialized_path[0:2]) - dx_dy[0]
            y = int(serialized_path[2:4]) - dx_dy[1]
            path_len = len(serialized_path)
            for i in range(4, path_len):
                if (not cut_off_start or i > 8) and 0 < x < 49 and 0 < y < 49:
                    road_list = room.lookForAt(LOOK_STRUCTURES, x, y)
                    road = _.find(road_list, {'structureType': STRUCTURE_ROAD})
                    if road:
                        damage = road.hitsMax - road.hits
                    else:
                        site_list = room.lookForAt(LOOK_CONSTRUCTION_SITES, x, y)
                        road = _.find(site_list, {'structureType': STRUCTURE_ROAD})
                        if road:
                            damage = (road.progressTotal - road.progress) * REPAIR_POWER / BUILD_POWER
                        else:
                            room.createConstructionSite(x, y, STRUCTURE_ROAD)
                            if Game.map.getTerrainAt(x, y, room_name)[0] == "s":
                                damage = CONSTRUCTION_COST_ROAD_SWAMP_RATIO * CONSTRUCTION_COST[STRUCTURE_ROAD] \
                                         * REPAIR_POWER / BUILD_POWER
                            else:
                                damage = CONSTRUCTION_COST[STRUCTURE_ROAD] * REPAIR_POWER / BUILD_POWER

                    if damage > max_damage:
                        max_damage = damage

                dx_dy = paths.direction_to_dx_dy(int(serialized_path[i]))
                x += dx_dy[0]
                y += dx_dy[1]

        work_part_max_per_road = (
            CREEP_LIFE_TIME
            # Half the time is spent moving towards the target, during which no roads are repaired
            / 2
            # The remaining life is divided between each road segment
            / self.hive.honey.find_path_length(flag, deposit_point, {'paved_for': flag})
            # each work part can do one REPAIR_POWER work per tick
            * REPAIR_POWER
        )

        # TODO: we should have something here to make sure that no roads can decay within one creep lifetime,
        # in case the constants change (I don't think it's possible with the current game constants).
        needed_parts = max(
            math.floor(max_damage / work_part_max_per_road / 2) * 2
        )

        self.room.store_cached_property(key, needed_parts, CREEP_LIFE_TIME)
        return needed_parts

    def cleanup_old_flag_sitting_values(self):
        for flag in self.available_mines:
            if flag.name not in Memory.flags:
                continue
            if 'sitting' in flag.memory and flag.memory.sitting < Game.time - flag.memory.sitting_set \
                    and Game.time - flag.memory.sitting_set > 10:
                del flag.memory.sitting
                del flag.memory.sitting_set
            if not len(flag.memory):
                del Memory.flags[flag.name]

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
                flag = flags.look_for(self.room, source, LOCAL_MINE)
                if not flag:
                    name = flags.create_flag(source, LOCAL_MINE, self.room.name)
                    if not name:
                        print("[{}][mining] Warning: Couldn't create local mining flag!".format(self.room.name))
                        continue
                    flag = Game.flags[name]
                    if not flag:
                        print("[{}][mining] Warning: Couldn't find local mining flag with name {}!".format(
                            self.room.name, name))
                        continue
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

    def calculate_creep_num_sections_for_mine(self, flag, base):
        maximum = spawning.max_sections_of(self.room, base)
        needed = self.calculate_ideal_mass_for_mine(flag)
        if base == creep_base_half_move_hauler or base == creep_base_work_half_move_hauler:
            # Each section has twice the carry, ~~and the initial section has half the carry of one regular section.~~
            # as of 2016/11/02, we have WWM initial sections, not CWM
            return fit_num_sections(needed / 2, maximum)
        else:
            return fit_num_sections(needed, maximum)

    def should_reserve(self, room_name):
        if self.room.room.energyCapacityAvailable < (BODYPART_COST[CLAIM] + BODYPART_COST[MOVE]) * 2:
            return False
        if Memory.no_controller and Memory.no_controller[room_name]:
            return False
        flag_list = flags.find_flags(room_name, REMOTE_MINE)
        if _.some(flag_list, is_sk):
            return False
        if _.some(flag_list, lambda f: f.name in Memory.flags and f.memory.do_reserve):
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

        if not self.should_reserve(room_name):
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

        # Set in the RemoteReserve class
        reservation_end_at = stored_data.get_reservation_end_time(room_name)
        if reservation_end_at > 0:
            ticks_to_end = reservation_end_at - Game.time
            if ticks_to_end >= CONTROLLER_RESERVE_MAX / 5:
                max_sections = min(5, spawning.max_sections_of(self.room, creep_base_reserving))
                if CONTROLLER_RESERVE_MAX - ticks_to_end < max_sections * CREEP_CLAIM_LIFE_TIME * CONTROLLER_RESERVE:
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
        if is_sk(flag):
            return math.ceil((SOURCE_ENERGY_KEEPER_CAPACITY / ENERGY_REGEN_TIME) / HARVEST_POWER)
        elif flag.pos.roomName == self.room.name or self.should_reserve(flag.pos.roomName):
            return math.ceil((SOURCE_ENERGY_CAPACITY / ENERGY_REGEN_TIME) / HARVEST_POWER)
        else:
            return math.ceil((SOURCE_ENERGY_NEUTRAL_CAPACITY / ENERGY_REGEN_TIME) / HARVEST_POWER)

    def haulers_can_target_mine(self, flag):
        # TODO: duplicated in get_next_needed_mining_role_for

        miner_carry_no_haulers = (
            flag.pos.roomName == self.room.name
            and self.room.room.energyCapacityAvailable
            >= (BODYPART_COST[MOVE] + BODYPART_COST[CARRY] + BODYPART_COST[WORK] * 5)  # 600 on official server
            and flag.pos.inRangeTo(self.closest_deposit_point_to_mine(flag), 2)
        )
        no_haulers = (
            flag.pos.roomName == self.room.name
            and (self.room.rcl < 4 or not self.room.room.storage)
        )
        return not miner_carry_no_haulers and not no_haulers

    def is_mine_linked(self, source):
        flag = flags.look_for(self.room, source, LOCAL_MINE)
        if flag:
            deposit_point = self.closest_deposit_point_to_mine(flag)
            if deposit_point:
                # TODO: duplicated in get_next_needed_mining_role_for, haulers_can_target_mine
                miner_carry_no_haulers = (
                    flag.pos.roomName == self.room.name
                    and self.room.room.energyCapacityAvailable
                    >= (BODYPART_COST[MOVE] + BODYPART_COST[CARRY] + BODYPART_COST[WORK] * 5)  # 600 on official server
                    and flag.pos.inRangeTo(deposit_point, 2)
                )
                return miner_carry_no_haulers
            else:
                return False
        else:
            # probably not a local mine (remote mine?)
            return False

    def get_next_needed_mining_role_for(self, flag):
        flag_id = "flag-{}".format(flag.name)
        miner_carry_no_haulers = (
            flag.pos.roomName == self.room.name
            and self.room.room.energyCapacityAvailable
            >= (BODYPART_COST[MOVE] + BODYPART_COST[CARRY] + BODYPART_COST[WORK] * 5)  # 600 on official server
            and flag.pos.inRangeTo(self.closest_deposit_point_to_mine(flag), 2)
        )
        no_haulers = (
            flag.pos.roomName == self.room.name
            and (self.room.rcl < 4 or not self.room.room.storage)
        )

        if flag.pos.roomName != self.room.name and len(defense.stored_hostiles_in(flag.pos.roomName)):
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
                if flag.pos.roomName == self.room.name:
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
            elif is_sk(flag):
                base = creep_base_4000miner
                num_sections = min(7, spawning.max_sections_of(self.room, base))
            elif flag.pos.roomName == self.room.name or self.should_reserve(flag.pos.roomName):
                base = creep_base_3000miner
                num_sections = min(5, spawning.max_sections_of(self.room, base))
            else:
                base = creep_base_1500miner
                num_sections = min(3, spawning.max_sections_of(self.room, base))
            if self.room.paving():
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
        current_noneol_hauler_work = 0
        for hauler_name in self.targets.creeps_now_targeting(target_energy_hauler_mine, flag_id):
            creep = Game.creeps[hauler_name]
            if not creep:
                continue
            if self.room.replacement_time_of(creep) > Game.time:
                current_noneol_hauler_mass += spawning.carry_count(creep)
                current_noneol_hauler_work += spawning.work_count(creep)
        if current_noneol_hauler_mass < self.calculate_current_target_mass_for_mine(flag):
            if flag.pos.roomName == self.room.name:
                if self.room.paving():
                    base = creep_base_half_move_hauler
                else:
                    base = creep_base_hauler
            elif self.room.paving():
                ideal_work = self.road_repair_work_needed_now(flag)
                if ideal_work > current_noneol_hauler_work:
                    base = creep_base_work_half_move_hauler
                else:
                    base = creep_base_half_move_hauler
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
            #       .format(self.room.name, flag.name, self.calculate_ideal_mass_for_mine(flag),
            #               self.calculate_current_target_mass_for_mine(flag), current_noneol_hauler_mass, eol_mass,
            #               new_hauler_mass, new_hauler_num_sections))

            return {
                'role': role_hauler,
                'base': base,
                'num_sections': self.calculate_creep_num_sections_for_mine(flag, base),
                'targets': [
                    [target_energy_hauler_mine, flag_id]
                ],
            }

        # print("[{}][mining] All roles reached for {}!".format(self.room.room_name, flag.name))
        return None

    def next_mining_role(self, max_to_check=Infinity):
        if max_to_check <= 0:
            return None
        mines = self.active_mines
        if len(mines) <= 0:
            return None
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
