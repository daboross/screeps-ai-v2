import math
from typing import List, Optional, TYPE_CHECKING, cast

from constants import RANGED_DEFENSE, UPGRADER_SPOT, role_hauler, role_miner, \
    role_recycling, role_spawn_fill, target_energy_hauler_mine, target_energy_miner_mine
from creeps.base import RoleBase
from creeps.behaviors.refill import Refill
from creeps.behaviors.transport import TransportPickup
from creeps.roles.spawn_fill import SpawnFill
from empire import stored_data
from jstools.screeps import *
from position_management import flags
from utilities import movement, positions

if TYPE_CHECKING:
    from empire.targets import TargetMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


class EnergyMiner(TransportPickup):
    def run(self):
        source_flag = cast(Flag, self.targets.get_existing_target(self, target_energy_miner_mine))
        if not source_flag:
            self.log("WARNING: Getting new remote mine for remote miner!")
            source_flag = cast(Flag, self.targets.get_new_target(self, target_energy_miner_mine))
        if not source_flag:
            self.log("Remote miner can't find any sources! Flag: {}".format(source_flag))
            self.memory.role = role_recycling
            self.memory.last_role = role_miner
            return False
        if Game.time % 10 == 7 and flags.flag_sponsor(source_flag) != self.home.name:
            self.memory.home = flags.flag_sponsor(source_flag)

        if self.creep.hits < self.creep.hitsMax:
            if not len(flags.find_flags(self.room.name, RANGED_DEFENSE)) \
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
                                             lambda c: c.creep.my and c.creep.memory.role == role_miner
                                                       and c.creep.ticksToLive < self.creep.ticksToLive)
                        if other_miner:
                            cast(Creep, other_miner[LOOK_CREEPS]).suicide()
                            del self.memory._move
                self.move_to(sitting_target)
            else:
                self.follow_energy_path(self.home.spawn, sitting_target)
            return False
        elif distance_away > 1:
            creep = cast(Creep, _.find(self.room.look_at(LOOK_CREEPS, sitting_target), lambda c: c.my))
            if creep and creep.memory.role == role_miner and creep.ticksToLive > 100:
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
                          lambda c: c.my and c.memory.role == role_miner and c.ticksToLive > 15):
                    self.memory.container_pos = self.pos.x | self.pos.y << 6
                else:
                    self.basic_move_to(pos)

        sources_list = cast(List[Source], source_flag.pos.lookFor(LOOK_SOURCES))
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
                    link = cast(OwnedStructure, Game.getObjectById(self.memory.link))
                    if link is None or not self.pos.isNearTo(link):
                        del self.memory.link
                        return False
            else:
                all_possible_links = _.filter(
                    cast(List[OwnedStructure], self.room.find(FIND_MY_STRUCTURES)),
                    lambda s: (s.structureType == STRUCTURE_LINK or s.structureType == STRUCTURE_STORAGE
                               ) and abs(s.pos.x - source_flag.pos.x) <= 2 and abs(s.pos.y - source_flag.pos.y) <= 2)
                best_priority = 0  # 1-3
                best_spot = None
                link = None  # type: Optional[OwnedStructure]
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
            if self.creep.carry[RESOURCE_ENERGY] + self.creep.getActiveBodyparts(WORK) > self.creep.carryCapacity:
                if link.structureType == STRUCTURE_LINK:
                    self.home.links.register_target_deposit(cast(StructureLink, link), self,
                                                            self.creep.carry[RESOURCE_ENERGY], 1)
                self.creep.transfer(link, RESOURCE_ENERGY)

        return False

    def should_pickup(self, resource_type = None):
        return 'container_pos' in self.memory and RoleBase.should_pickup(resource_type)

    def _calculate_time_to_replace(self):
        source = self.targets.get_new_target(self, target_energy_miner_mine)
        if not source:
            return -1
        path_length = self.hive.honey.find_path_length(self.home.spawn.pos, source)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, source_pos)
        moves_every = (len(self.creep.body) - self.creep.getActiveBodyparts(MOVE)) / self.creep.getActiveBodyparts(MOVE)
        if self.home.paving():
            moves_every /= 2
        moves_every = math.ceil(moves_every)
        return path_length / moves_every + _.size(self.creep.body) * CREEP_SPAWN_TIME + 15


def find_new_energy_miner_target_mine(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    best_id = None
    closest_flag = Infinity
    for flag in creep.home.mining.available_mines:
        flag_id = "flag-{}".format(flag.name)
        miners = targets.targets[target_energy_miner_mine][flag_id]
        if not miners or miners < 1:
            distance = movement.distance_squared_room_pos(flag.pos, creep.creep.pos)
            if distance < closest_flag:
                closest_flag = distance
                best_id = flag_id

    return best_id


class EnergyHauler(TransportPickup, SpawnFill, Refill):
    def run_local_refilling(self, pickup, fill):
        if not self.memory.filling:
            if self.creep.getActiveBodyparts(WORK) and Game.cpu.bucket >= 4000:
                construction_sites = cast(List[ConstructionSite],
                                          self.room.find_in_range(FIND_MY_CONSTRUCTION_SITES, 3, self.pos))
                if len(construction_sites):
                    self.creep.build(_.max(construction_sites, 'progress'))
                else:
                    repair_sites = cast(List[Structure],
                                        _.filter(self.room.find_in_range(FIND_STRUCTURES, 3, self.pos),
                                                 lambda s: s.hits < s.hitsMax
                                                           and s.hits < self.home.get_min_sane_wall_hits))
                    if len(repair_sites):
                        self.creep.repair(_.min(repair_sites, 'hits'))
                    else:
                        self.repair_nearby_roads()
            if self.memory.running == 'refill':
                return self.refill_creeps()
            elif self.memory.running == role_spawn_fill or self.memory.running == 'spawn_wait':
                return SpawnFill.run(self)
            else:
                if _.find(self.home.find(FIND_MY_STRUCTURES), lambda s:
                        (s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN)
                and s.energy < s.energyCapacity):
                    self.memory.running = role_spawn_fill
                    return SpawnFill.run(self)
                else:
                    self.memory.running = 'refill'
                    return self.refill_creeps()
        elif self.creep.ticksToLive < 200 and self.creep.ticksToLive < self.path_length(fill, pickup) * 2:
            if self.creep.carry[RESOURCE_ENERGY] > 0:
                self.memory.filling = False
                return self.refill_creeps()
            else:
                self.memory.last_role = self.memory.role
                self.memory.role = role_recycling
                return False

    def run(self):
        pickup = cast(Flag, self.targets.get_existing_target(self, target_energy_hauler_mine))
        if not pickup:
            self.log("WARNING: Getting new remote mine for remote hauler!")
            pickup = cast(Flag, self.targets.get_new_target(self, target_energy_hauler_mine))

        if not pickup:
            self.memory.role = role_recycling
            self.memory.last_role = role_hauler
            return

        if _.size(self.creep.carry) > 1:
            fill = self.home.room.storage or self.home.spawn
        else:
            fill = self.home.mining.closest_deposit_point_to_mine(pickup)

        if fill == undefined:
            self.log('WARNING: Energy hauler in room without storage nor spawn. Repurposing as spawn fill.')
            self.memory.role = role_spawn_fill
            return

        if fill.id == self.home.spawn.id:
            if not self.memory.filling and self.pos.roomName == fill.pos.roomName:
                return self.run_local_refilling(pickup, fill)
            elif 'running' in self.memory:
                del self.memory.running

        return self.transport(pickup, fill, self.home.paving())

    def _calculate_time_to_replace(self):
        source = cast(Flag, self.targets.get_new_target(self, target_energy_hauler_mine))
        if not source:
            return -1
        path_length = self.hive.honey.find_path_length(self.home.spawn.pos, source.pos)
        # TODO: find a good time here by calculating exactly how many trips we'll make before we drop.
        return path_length * 1.7 + _.size(self.creep.body) * CREEP_SPAWN_TIME + 15


def find_new_energy_hauler_target_mine(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    best_id = None
    # don't go to any rooms with 100% haulers in use.
    smallest_percentage = 1
    for flag in creep.home.mining.active_mines:
        flag_id = "flag-{}".format(flag.name)
        if not creep.home.mining.haulers_can_target_mine(flag):
            continue
        hauler_mass = targets.workforce_of(target_energy_hauler_mine, flag_id)
        hauler_percentage = float(hauler_mass) / creep.home.mining.calculate_current_target_mass_for_mine(flag)
        too_long = creep.creep.ticksToLive < 2.2 * creep.home.mining.distance_to_mine(flag)
        if too_long:
            if hauler_percentage < 0.5:
                hauler_percentage *= 2
            else:
                hauler_percentage = 0.99
        if not hauler_mass or hauler_percentage < smallest_percentage:
            smallest_percentage = hauler_percentage
            best_id = flag_id

    return best_id


class RemoteReserve(TransportPickup):
    def find_claim_room(self):
        claim_room = self.memory.claiming
        if claim_room:
            if Game.time % 100 == 49:
                if Memory.reserving[claim_room] != self.name:
                    if Memory.reserving[claim_room] in Game.creeps:
                        creep = Game.creeps[Memory.reserving[claim_room]]
                        if not creep.spawning:
                            if self.creep.ticksToLive > creep.ticksToLive:
                                Memory.reserving[claim_room] = self.name
                            elif self.pos.roomName != claim_room or \
                                            creep.pos.getRangeTo(self.creep.room.controller.pos) < 4:
                                self.creep.suicide()
                    else:
                        Memory.reserving[claim_room] = self.name
            return claim_room
        self.log("WARNING: Calculating new reserve target for remote mining reserver!")
        if not Memory.reserving:
            Memory.reserving = {}

        lowest_time = Infinity
        best = None
        for op_flag in self.home.mining.active_mines:
            creep = Game.creeps[Memory.reserving[op_flag.pos.roomName]]
            if creep and creep.ticksToLive > 200:
                continue
            if Memory.no_controller and Memory.no_controller[op_flag.pos.roomName]:
                continue
            room = Game.rooms[op_flag.pos.roomName]
            if room and not room.controller:
                if Memory.no_controller:
                    Memory.no_controller[op_flag.pos.roomName] = True
                else:
                    Memory.no_controller = {op_flag.pos.roomName: True}
                continue
            time = room and room.controller.reservation and room.controller.reservation.ticksToEnd or 0
            if creep:
                time += creep.ticksToLive * (creep.getActiveBodyparts(CLAIM) - 1)
            if time >= 4999:
                continue
            if time < lowest_time:
                lowest_time = time
                best = op_flag.pos.roomName

        if best:
            Memory.reserving[best] = self.name
            self.memory.claiming = best
        return best

    def check_move_parts(self):
        if not self.creep.hasActiveBodyparts(MOVE) \
                and not len(flags.find_flags(self.room.name, RANGED_DEFENSE)) \
                and not _.some(self.room.find(FIND_CREEPS), lambda creep: creep.hasActiveBodyparts(HEAL)):
            self.creep.suicide()
            self.home.check_all_creeps_next_tick()
            return False

    def run(self):
        claim_room = self.find_claim_room()
        if not claim_room:
            self.creep.suicide()
            return

        if self.pos.roomName != claim_room:
            if Game.rooms[claim_room]:
                target = Game.rooms[claim_room].controller.pos
            else:
                target = movement.find_an_open_space(claim_room)
            self.follow_energy_path(self.home.spawn, target)
            self.check_move_parts()
            return

        controller = self.room.room.controller

        if not controller:
            del self.memory.claiming
            return True

        if controller.reservation and controller.reservation.ticksToEnd > 4999:
            if self.pos.isNearTo(controller):
                self.creep.suicide()
                return False
            else:
                del self.memory.claiming
                return True

        if not self.pos.isNearTo(controller):
            self.move_to(controller)
            self.check_move_parts()
            return False

        if controller.reservation and controller.reservation.username != self.creep.owner.username:
            self.log("Remote reserve creep target owned by another player! {} has taken our reservation!",
                     controller.reservation.username)
        else:
            self.creep.reserveController(controller)
            if Game.time % 5 == 2 and controller.reservation:
                stored_data.set_reservation_time(self.pos.roomName, controller.reservation.ticksToEnd)

    def _calculate_time_to_replace(self):
        room = self.find_claim_room()
        if not room:
            return -1
        if Game.rooms[room]:
            target_pos = Game.rooms[room].controller.pos
        else:
            return -1
        path_length = self.hive.honey.find_path_length(self.home.spawn.pos, target_pos)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, target_pos)
        return path_length + _.size(self.creep.body) * CREEP_SPAWN_TIME + 15
