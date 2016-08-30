import flags
import speech
from constants import target_spawn_deposit, recycle_time, role_recycling, role_spawn_fill, role_tower_fill, \
    role_spawn_fill_backup, role_builder
from roles import building
from tools import profiling
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class SpawnFill(building.Builder):
    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_spawn_fill
            return False
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.target_mind.untarget_all(self)
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget_all(self)

        if self.memory.harvesting:
            return self.harvest_energy()
        else:
            target = self.target_mind.get_new_target(self, target_spawn_deposit)
            if target:
                if target.color:  # it's a spawn fill wait flag
                    rwc_cache = volatile_cache.mem("sfrwc")
                    if not rwc_cache.has(self.pos.roomName):
                        rwc_cache.set(self.pos.roomName, not not _.find(
                            self.room.find(FIND_MY_STRUCTURES),
                            lambda s: (s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN)
                                      and s.energy < s.energyCapacity))
                    if rwc_cache.get(self.pos.roomName):
                        self.target_mind.untarget(self, target_spawn_deposit)
                        return True
                    if self.memory.role == role_spawn_fill or self.memory.role == role_tower_fill:
                        del self.memory.filling_now
                        if self.creep.carry.energy < self.creep.carryCapacity:
                            self.memory.harvesting = True
                            return True
                        if not self.creep.pos.isEqualTo(target.pos):
                            if self.creep.pos.isNearTo(target.pos):
                                self.basic_move_to(target)
                            else:
                                self.move_to(target)
                        return False
                else:
                    del self.memory.filling_now
                    if target.energy >= target.energyCapacity:
                        self.target_mind.untarget(self, target_spawn_deposit)
                        return True
                    else:
                        if not self.creep.pos.isNearTo(target.pos):
                            self.move_to(target)
                            self.report(speech.spawn_fill_moving_to_target)
                            return False

                        result = self.creep.transfer(target, RESOURCE_ENERGY)

                        if result == OK:
                            self.report(speech.spawn_fill_ok)
                            if self.creep.carry.energy > target.energyCapacity - target.energy:
                                volatile_cache.mem("extensions_filled").set(target.id, True)
                                if self.creep.carry.energy + target.energy - target.energyCapacity > 0:
                                    self.target_mind.untarget(self, target_spawn_deposit)
                                    new_target = self.target_mind.get_new_target(self, target_spawn_deposit)
                                    if new_target and not self.creep.pos.isNearTo(new_target.pos):
                                        self.move_to(new_target)
                                else:
                                    self.harvest_energy()  # Get a head start on this too!
                        elif result == ERR_FULL:
                            self.target_mind.untarget(self, target_spawn_deposit)
                            return True
                        else:
                            self.log("Unknown result from spawn_fill-creep.transfer({}): {}", target, result)
                            self.target_mind.untarget(self, target_spawn_deposit)
                            self.report(speech.spawn_fill_unknown_result)
                            return True
                        return False

            if self.memory.role == role_spawn_fill_backup and self.home.carry_mass_of(role_tower_fill) \
                    + self.home.carry_mass_of(role_spawn_fill) >= self.home.get_target_spawn_fill_mass():
                self.memory.role = role_builder
                return building.Builder.run(self)

            if self.home.room.controller.level > 4 and self.home.spawn:
                # We have links, let's not do this manually - unless we're rebuilding a spawn!
                if self.creep.carry.energy < self.creep.carryCapacity * 0.8:
                    self.memory.harvesting = True
                    return True
                target = flags.find_closest_in_room(self.creep.pos, flags.SPAWN_FILL_WAIT)
                if target:
                    if not self.creep.pos.isNearTo(target):
                        self.move_to(target)
                else:
                    self.go_to_depot()
                return False

            if not self.memory.filling_now and self.__name__ == SpawnFill.__name__ \
                    and self.creep.carry.energy < self.creep.carryCapacity * 0.4:
                self.memory.harvesting = True
                return True
            target = self.room.find_closest_by_range(FIND_MY_CREEPS, self.creep.pos,
                                                     # > 1 to avoid 1-work remote haulers
                                                     lambda c: c.getActiveBodyparts(WORK) > 1
                                                               and c.getActiveBodyparts(CARRY) > 1
                                                               and c.carry.energy < c.carryCapacity * 0.75
                                                               and not c.memory.emptying)
            if not target:
                target = self.room.find_closest_by_range(FIND_MY_CREEPS, self.creep.pos,
                                                         lambda c: c.getActiveBodyparts(WORK) > 1
                                                                   and c.getActiveBodyparts(CARRY) > 1
                                                                   and c.carry.energy < c.carryCapacity
                                                                   and not c.memory.emptying)
            if not target:
                self.go_to_depot()
                return False
            self.memory.filling_now = True
            if not self.creep.pos.isNearTo(target.pos):
                self.move_to(target)
                return False
            self.creep.transfer(target, RESOURCE_ENERGY)

        return False


profiling.profile_whitelist(SpawnFill, ["run"])
