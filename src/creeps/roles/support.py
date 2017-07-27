import math

from constants import RANGED_DEFENSE, UPGRADER_SPOT, role_recycling, role_support_builder, role_support_hauler, \
    role_support_miner, target_support_builder_wall, target_support_hauler_fill, target_support_hauler_mine, \
    target_support_miner_mine
from creeps.base import RoleBase
from creeps.behaviors.transport import TransportPickup
from jstools.screeps import *
from position_management import flags
from utilities import movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


class SupportMiner(TransportPickup):
    def run(self):
        source_flag = self.targets.get_existing_target(self, target_support_miner_mine)
        if not source_flag:
            if not self.memory.idle_for:
                self.log("WARNING: Support miner has no target.")
                self.memory.idle_for = 1
            else:
                self.memory.idle_for += 1
                if self.memory.idle_for >= 10:
                    self.log("Support miner idle for 10 ticks, committing suicide.")
                    self.creep.suicide()
            return

        if self.creep.hits < self.creep.hitsMax:
            if not len(flags.find_flags(self, RANGED_DEFENSE)) \
                    or not _.some(self.room.find(FIND_CREEPS), lambda creep: creep.hasActiveBodyparts(HEAL)):
                if self.home.defense.healing_capable() and (self.pos.roomName != self.home.name
                                                            or self.pos.x > 40 or self.pos.y > 40
                                                            or self.pos.x < 10 or self.pos.y < 10):
                    self.follow_energy_path(source_flag, self.home.spawn)
                    return
                elif not self.creep.getActiveBodyparts(WORK):
                    self.creep.suicide()
                    return
        if self.memory.container_pos:
            sitting_target = positions.deserialize_xy_to_pos(self.memory.container_pos,
                                                             source_flag.pos.roomName)
        else:
            sitting_target = source_flag.pos
        distance_away = self.pos.getRangeTo(source_flag)
        if distance_away > 2:
            if self.pos.roomName == source_flag.pos.roomName:
                if distance_away <= 3:
                    total_mass = self.home.mining.get_ideal_miner_workmass_for(source_flag)
                    if self.creep.getActiveBodyparts(WORK) >= total_mass:
                        other_miner = _.find(self.room.look_for_in_area_around(LOOK_CREEPS, source_flag.pos, 1),
                                             lambda c: c.creep.my and c.creep.memory.role == role_support_miner
                                                       and c.creep.ticksToLive < self.creep.ticksToLive)
                        if other_miner:
                            other_miner.creep.suicide()
                            del self.memory._move
                self.move_to(sitting_target)
            else:
                self.follow_energy_path(self.home.spawn, sitting_target)
            return False
        elif distance_away > 1:
            creep = _.find(self.room.look_at(LOOK_CREEPS, sitting_target), lambda c: c.my)
            if creep and creep.memory.role == role_support_miner and creep.ticksToLive > 100:
                self.memory.container_pos = None
                sitting_target = source_flag.pos
            self.move_to(sitting_target)
            return False
        if 'container_pos' not in self.memory:
            container = _.find(self.room.find_in_range(FIND_STRUCTURES, 1, source_flag.pos),
                               lambda s: s.structureType == STRUCTURE_CONTAINER)
            if container:
                self.memory.container_pos = container.pos.x | (container.pos.y << 6)
            else:
                biggest_pile = _.max(self.room.find_in_range(FIND_DROPPED_RESOURCES, 1, source_flag.pos),
                                     lambda e: e.amount)
                if biggest_pile != -Infinity:
                    self.memory.container_pos = biggest_pile.pos.x | (biggest_pile.pos.y << 6)
                else:
                    self.memory.container_pos = None
        if Game.time % 10 == 0 and self.memory.container_pos is not None:
            this_pos_to_check = self.pos.x | self.pos.y << 6  # Transcrypt does this incorrectly in an if statement.
            if this_pos_to_check != self.memory.container_pos:
                pos = __new__(RoomPosition(self.memory.container_pos & 0x3F,
                                           self.memory.container_pos >> 6 & 0x3F, self.pos.roomName))
                if _.find(self.room.look_at(LOOK_CREEPS, pos),
                          lambda c: c.my and c.memory.role == role_support_miner and c.ticksToLive > 15):
                    self.memory.container_pos = self.pos.x | self.pos.y << 6
                else:
                    self.basic_move_to(pos)

        sources_list = source_flag.pos.lookFor(LOOK_SOURCES)
        if not len(sources_list):
            self.log("Remote mining source flag {} has no sources under it!", source_flag.name)
            return False
        source = sources_list[0]

        # if Game.time % 3 == 2:
        #     ideal_work = source.energyCapacity / ENERGY_REGEN_TIME / HARVEST_POWER
        #     current_work = self.creep.getActiveBodyparts(WORK)
        #     extra_work = current_work - ideal_work
        #     if extra_work != 0:
        #         if extra_work < 0:
        #             current_work = _.sum(self.room.find_in_range(FIND_MY_CREEPS, 1, source_flag.pos),
        #                                  lambda c: c.memory.role == role_miner and c.getActiveBodyparts(WORK))
        #         if current_work > source.energy / (source.ticksToRegeneration - 1) / HARVEST_POWER:
        #             return False  # skip a tick, to spread it out
        result = self.creep.harvest(source)
        if result != OK and result != ERR_NOT_ENOUGH_RESOURCES:
            self.log("Unknown result from mining-creep.harvest({}): {}", source, result)

        if self.creep.carryCapacity:
            if 'link' in self.memory:
                if self.memory.link is None:
                    return False
                else:
                    link = Game.getObjectById(self.memory.link)
                    if link is None or not self.pos.isNearTo(link):
                        del self.memory.link
                        return False
            else:
                all_possible_links = _.filter(
                    self.room.find(FIND_MY_STRUCTURES),
                    lambda s: (s.structureType == STRUCTURE_LINK or s.structureType == STRUCTURE_STORAGE
                               ) and abs(s.pos.x - source_flag.pos.x) <= 2 and abs(s.pos.y - source_flag.pos.y) <= 2)
                best_priority = 0  # 1-3
                best_spot = None
                link = None
                for x in range(source_flag.pos.x - 1, source_flag.pos.x + 2):
                    for y in range(source_flag.pos.y - 1, source_flag.pos.y + 2):
                        if movement.is_block_empty(self.room, x, y):
                            link_here = _.find(all_possible_links, lambda s: abs(s.pos.x - x) <= 1
                                                                             and abs(s.pos.y - y) <= 1)
                            if link_here:
                                if not flags.look_for(self.room, __new__(RoomPosition(x, y, self.pos.roomName)),
                                                      UPGRADER_SPOT):
                                    if _.find(self.room.look_at(LOOK_STRUCTURES, x, y),
                                              lambda s: s.structureType == STRUCTURE_RAMPART):
                                        priority_here = 3
                                    else:
                                        priority_here = 2
                                else:
                                    priority_here = 1
                                if priority_here > best_priority:
                                    best_priority = priority_here
                                    best_spot = x | y << 6
                                    link = link_here
                                if best_priority >= 3:
                                    break
                    if best_priority >= 3:
                        break
                if link:
                    self.memory.link = link.id
                    self.memory.container_pos = best_spot
                else:
                    self.memory.link = None
                return False
            if self.creep.carry.energy + self.creep.getActiveBodyparts(WORK) > self.creep.carryCapacity:
                if link.structureType == STRUCTURE_LINK:
                    self.home.links.register_target_deposit(link, self, self.creep.carry.energy, 1)
                self.creep.transfer(link, RESOURCE_ENERGY)

        return False

    def should_pickup(self, resource_type=None):
        return 'container_pos' in self.memory and RoleBase.should_pickup(resource_type)

    def _calculate_time_to_replace(self):
        source = self.targets.get_existing_target(self, target_support_miner_mine)
        if not source:
            return -1
        path_length = self.hive.honey.find_path_length(self.home.spawn, source)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, source_pos)
        moves_every = (len(self.creep.body) - self.creep.getActiveBodyparts(MOVE)) / self.creep.getActiveBodyparts(MOVE)
        moves_every = math.ceil(moves_every)
        return path_length / moves_every + _.size(self.creep.body) * CREEP_SPAWN_TIME + 15


class SupportHauler(TransportPickup):
    def run(self):
        pickup = self.targets.get_existing_target(self, target_support_hauler_mine)
        if not pickup:
            if not self.memory.idle_for:
                self.log("WARNING: Support hauler has no target.")
                self.memory.idle_for = 1
            else:
                self.memory.idle_for += 1
                if self.memory.idle_for >= 10:
                    self.log("Support hauler idle for 10 ticks, committing suicide.")
                    self.creep.suicide()
            return

        if not pickup:
            self.memory.role = role_recycling
            self.memory.last_role = role_support_hauler
            return

        fill_id = self.targets._get_existing_target_id(target_support_hauler_fill, self.name)
        builders = self.targets.creeps_now_targeting(target_support_builder_wall, fill_id)
        builder = _(builders).map(lambda name: Game.creeps[name]).filter() \
            .max(lambda c: c.carryCapacity / _.sum(c.carry) + c.ticksToLive / 1500)
        if builder is -Infinity:
            builder = None
            self.log("support hauler can't find builder!")
        fill = builder or self.targets.get_existing_target(self, target_support_hauler_fill)
        if fill == undefined:
            self.log('WARNING: Support hauler has no fill target.')
            return

        return self.transport(pickup, fill, False)

    def _calculate_time_to_replace(self):
        source = self.targets.get_existing_target(self, target_support_hauler_mine)
        if not source:
            return -1
        path_length = self.hive.honey.find_path_length(self.home.spawn, source)
        # TODO: find a good time here by calculating exactly how many trips we'll make before we drop.
        return path_length * 1.7 + _.size(self.creep.body) * CREEP_SPAWN_TIME + 15


class SupportBuilder(TransportPickup):
    def recalc(self, target_flag):
        del self.memory.container_pos
        helping = target_flag.memory.owner

        def best_struct(s):
            if s.pos.inRangeTo(target_flag, 10):
                return s.hits * (1 + 0.05 * s.pos.getRangeTo(target_flag))
            else:
                return s.hits * 100

        def best_construction_site(s):
            if s.pos.inRangeTo(target_flag, 10):
                return (s.progressTotal - s.progress) * (1 + 0.05 * s.pos.getRangeTo(target_flag))
            else:
                return Infinity

        if target_flag.memory.build:
            build_target = _(self.room.find(FIND_CONSTRUCTION_SITES)) \
                .filter(lambda s: (s.owner == helping or not s.owner)).min(best_construction_site)
            if build_target != Infinity:
                target_flag.setPosition(build_target)

        repair_target = _(self.room.find(FIND_STRUCTURES)) \
            .filter(lambda s: (s.owner == helping or not s.owner) and s.hits < s.hitsMax
                              and (s.structureType != STRUCTURE_ROAD)).min(best_struct)
        if repair_target != Infinity:
            target_flag.setPosition(repair_target)

    def run(self):
        target_flag = self.targets.get_existing_target(self, target_support_builder_wall)
        if not target_flag:
            if not self.memory.idle_for:
                self.log("WARNING: Support builder has no target.")
                self.memory.idle_for = 1
            else:
                self.memory.idle_for += 1
                if self.memory.idle_for >= 10:
                    self.log("Support builder idle for 10 ticks, committing suicide.")
                    self.creep.suicide()
            return

        if self.creep.hits < self.creep.hitsMax:
            if not len(flags.find_flags(self, RANGED_DEFENSE)) \
                    or not _.some(self.room.find(FIND_CREEPS), lambda creep: creep.hasActiveBodyparts(HEAL)):
                if self.home.defense.healing_capable() and (self.pos.roomName != self.home.name
                                                            or self.pos.x > 40 or self.pos.y > 40
                                                            or self.pos.x < 10 or self.pos.y < 10):
                    self.follow_energy_path(target_flag, self.home.spawn)
                    return
                elif not self.creep.getActiveBodyparts(WORK):
                    self.creep.suicide()
                    return
        if self.memory.container_pos:
            sitting_target = positions.deserialize_xy_to_pos(self.memory.container_pos,
                                                             target_flag.pos.roomName)
        else:
            sitting_target = target_flag.pos
        distance_away = self.pos.getRangeTo(target_flag)
        if distance_away > 2:
            if self.pos.roomName == target_flag.pos.roomName:
                if distance_away <= 3:
                    total_mass = self.home.mining.get_ideal_miner_workmass_for(target_flag)
                    if self.creep.getActiveBodyparts(WORK) >= total_mass:
                        other_miner = _.find(self.room.look_for_in_area_around(LOOK_CREEPS, target_flag.pos, 1),
                                             lambda c: c.creep.my and c.creep.memory.role == role_support_builder
                                                       and c.creep.ticksToLive < self.creep.ticksToLive)
                        if other_miner:
                            other_miner.creep.suicide()
                            del self.memory._move
                self.move_to(sitting_target)
            else:
                self.follow_energy_path(self.home.spawn, sitting_target)
            return False
        elif distance_away > 1:
            creep = _.find(self.room.look_at(LOOK_CREEPS, sitting_target), lambda c: c.my)
            if creep and creep.memory.role == role_support_builder and creep.ticksToLive > 100:
                self.memory.container_pos = None
                sitting_target = target_flag.pos
            self.move_to(sitting_target)
            return False
        if 'container_pos' not in self.memory:
            container = _.find(self.room.find_in_range(FIND_STRUCTURES, 1, target_flag.pos),
                               lambda s: s.structureType == STRUCTURE_CONTAINER)
            if container:
                self.memory.container_pos = container.pos.x | (container.pos.y << 6)
            else:
                biggest_pile = _.max(self.room.find_in_range(FIND_DROPPED_RESOURCES, 1, target_flag.pos),
                                     lambda e: e.amount)
                if biggest_pile != -Infinity:
                    self.memory.container_pos = biggest_pile.pos.x | (biggest_pile.pos.y << 6)
                else:
                    self.memory.container_pos = None
        if Game.time % 10 == 0 and self.memory.container_pos is not None:
            this_pos_to_check = self.pos.x | self.pos.y << 6  # Transcrypt does this incorrectly in an if statement.
            if this_pos_to_check != self.memory.container_pos:
                pos = __new__(RoomPosition(self.memory.container_pos & 0x3F,
                                           self.memory.container_pos >> 6 & 0x3F, self.pos.roomName))
                if _.find(self.room.look_at(LOOK_CREEPS, pos),
                          lambda c: c.my and c.memory.role == role_support_builder and c.ticksToLive > 15):
                    self.memory.container_pos = self.pos.x | self.pos.y << 6
                else:
                    self.basic_move_to(pos)

        wall = _.find(target_flag.pos.lookFor(LOOK_STRUCTURES), lambda s: s.structureType != STRUCTURE_ROAD)
        if wall:
            result = self.creep.repair(wall)
        else:
            site = _.find(target_flag.pos.lookFor(LOOK_CONSTRUCTION_SITES))
            if not site:
                self.log("Remote mining source flag {} has no wall under it!", target_flag.name)
                self.recalc(target_flag)
                return False
            result = self.creep.build(site)

        if Game.time % 50 == 5:
            self.recalc(target_flag)

        if result != OK and result != ERR_NOT_ENOUGH_RESOURCES:
            self.log("Unknown result from mining-creep.repair|build({}): {}", wall, result)
            if result == ERR_NOT_IN_RANGE:
                self.recalc(target_flag)
        return False

    def should_pickup(self, resource_type=None):
        return 'container_pos' in self.memory and RoleBase.should_pickup(resource_type)

    def _calculate_time_to_replace(self):
        source = self.targets.get_existing_target(self, target_support_builder_wall)
        if not source:
            return -1
        path_length = self.hive.honey.find_path_length(self.home.spawn, source)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, source_pos)
        moves_every = (len(self.creep.body) - self.creep.getActiveBodyparts(MOVE)) / self.creep.getActiveBodyparts(MOVE)
        if self.home.paving():
            moves_every /= 2
        moves_every = math.ceil(moves_every)
        return path_length / moves_every + _.size(self.creep.body) * CREEP_SPAWN_TIME + 15
