import speech
from constants import target_spawn_deposit, recycle_time, role_recycling, role_spawn_fill, role_tower_fill, \
    role_spawn_fill_backup, role_builder, role_upgrader
from goals.refill import Refill
from role_base import RoleBase
from roles import building
from roles import upgrading
from tools import profiling
from utilities import movement
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


class SpawnFill(building.Builder, Refill):
    def run(self):
        if self.creep.ticksToLive < recycle_time and not self.home.under_siege():
            self.memory.role = role_recycling
            self.memory.last_role = role_spawn_fill
            return False
        if self.memory.filling and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.filling = False
            if self.memory.role == role_spawn_fill or self.memory.role == role_tower_fill:
                self.targets.untarget_all(self)
            else:
                return True
        elif not self.memory.filling and (self.creep.carry.energy <= 0 or
                                              (self.creep.carry.energy <= 20
                                               and self.home.room.storage and movement.chebyshev_distance_room_pos(
                                                  self.pos, self.home.room.storage) < 5)):
            self.memory.filling = True
            del self.memory.running
            if self.memory.role == role_spawn_fill or self.memory.role == role_tower_fill:
                self.targets.untarget_all(self)
            else:
                return True

        if self.memory.filling:
            return self.harvest_energy()
        else:
            if 'running' in self.memory:
                if self.memory.running == role_upgrader:
                    return upgrading.Upgrader.run(self)
                elif self.memory.running == role_builder:
                    return building.Builder.run(self)
                elif self.memory.running == "refill":
                    return self.refill_creeps()
                elif self.memory.running != role_spawn_fill:
                    self.log("WARNING: Unknown running value: {}", self.memory.running)
                    del self.memory.running
            elif self.home.room.energyCapacityAvailable < 550 and self.home.room.energyAvailable < 300 \
                    and self.home.next_role is None:
                if self.creep.hasActiveBodyparts(WORK):
                    self.memory.running = role_builder
                    return building.Builder.run(self)
                else:
                    self.memory.running = "refill"
                    return self.refill_creeps()
            target = self.targets.get_new_target(self, target_spawn_deposit)
            if target:
                if target.color:  # it's a spawn fill wait flag
                    rwc_cache = volatile_cache.mem("sfrwc")
                    if not rwc_cache.has(self.pos.roomName):
                        rwc_cache.set(self.pos.roomName, not not _.find(
                            self.room.find(FIND_MY_STRUCTURES),
                            lambda s: (s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN)
                                      and s.energy < s.energyCapacity))
                    if rwc_cache.get(self.pos.roomName):
                        self.targets.untarget(self, target_spawn_deposit)
                        return True
                    if self.creep.carry.energy < self.creep.carryCapacity:
                        self.memory.filling = True
                        return True
                    if not self.home.room.storage:
                        self.memory.running = "refill"
                        return self.refill_creeps()
                    if not self.creep.pos.isEqualTo(target.pos):
                        if self.creep.pos.isNearTo(target.pos):
                            self.basic_move_to(target)
                        else:
                            self.move_to(target)
                    return False
                else:
                    if target.energy >= target.energyCapacity:
                        self.targets.untarget(self, target_spawn_deposit)
                        return True
                    else:
                        if not self.creep.pos.isNearTo(target.pos):
                            self.report(speech.spawn_fill_moving_to_target)
                            if movement.chebyshev_distance_room_pos(self.pos, target) < 5 \
                                    and 'nbm' not in self.memory:
                                if self.force_basic_move_to(target, lambda c: (c.memory.role != role_spawn_fill
                                and c.memory.role != role_tower_fill) or not c.carry.energy):
                                    return False
                                else:
                                    self.memory.nbm = True
                            self.move_to(target)
                            return False
                        del self.memory.nbm

                        result = self.creep.transfer(target, RESOURCE_ENERGY)

                        if result == OK:
                            self.report(speech.spawn_fill_ok)
                            if self.creep.carry.energy > target.energyCapacity - target.energy:
                                volatile_cache.mem("extensions_filled").set(target.id, True)
                                if self.creep.carry.energy + target.energy - target.energyCapacity > 0:
                                    self.targets.untarget(self, target_spawn_deposit)
                                    new_target = self.targets.get_new_target(self, target_spawn_deposit)
                                    if new_target and not self.creep.pos.isNearTo(new_target.pos):
                                        self.move_to(new_target)
                                else:
                                    self.harvest_energy()  # Get a head start on this too!
                        elif result == ERR_FULL:
                            self.targets.untarget(self, target_spawn_deposit)
                            return True
                        else:
                            self.log("Unknown result from spawn_fill-creep.transfer({}): {}", target, result)
                            self.targets.untarget(self, target_spawn_deposit)
                            self.report(speech.spawn_fill_unknown_result)
                            return True
                        return False

            if self.home.full_storage_use and self.memory.role == role_spawn_fill_backup \
                    and self.home.carry_mass_of(role_tower_fill) + self.home.carry_mass_of(role_spawn_fill) \
                            >= self.home.get_target_total_spawn_fill_mass():
                self.memory.role = role_builder
                return building.Builder.run(self)
            elif self.memory.role == role_spawn_fill_backup:
                if _.find(self.room.building.next_priority_construction_targets(), lambda s:
                        s.structureType == STRUCTURE_EXTENSION) or self.home.upgrading_deprioritized():
                    self.memory.running = role_builder
                    return building.Builder.run(self)
                else:
                    self.memory.running = role_upgrader
                    return upgrading.Upgrader.run(self)
            elif not self.home.room.storage or self.home.room.storage.storeCapacity <= 0:
                self.memory.running = "refill"
                return self.refill_creeps()
            elif self.creep.carry.energy < self.creep.carryCapacity:
                self.memory.filling = True
                return self.harvest_energy()
        return False

    def should_pickup(self, resource_type=None):
        if 'running' in self.memory:
            if self.memory.running == role_upgrader:
                return upgrading.Upgrader.should_pickup(self, resource_type)
            elif self.memory.running == role_builder:
                return building.Builder.should_pickup(self, resource_type)
        return RoleBase.should_pickup(self, resource_type)


profiling.profile_whitelist(SpawnFill, ["run"])
