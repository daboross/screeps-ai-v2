import speech
from constants import target_spawn_deposit, recycle_time, role_recycling, role_spawn_fill
from roles import building
from tools import profiling
from utilities import movement
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
                    if self.__name__ == SpawnFill.__name__:
                        del self.memory.filling_now
                        if self.creep.carry.energy < self.creep.carryCapacity:
                            self.memory.harvesting = True
                            return True
                        if not self.creep.pos.isNearTo(target.pos) or \
                                (not self.creep.pos.isEqualTo(target.pos)
                                 and movement.is_block_clear(self.room.room, target.pos.x, target.pos.y)):
                            self.move_to(target)
                        if _.find(self.room.find(FIND_MY_STRUCTURES),
                                  lambda s: (s.structureType == STRUCTURE_EXTENSION
                                             or s.structureType == STRUCTURE_SPAWN)
                                  and s.energy < s.energyCapacity):
                            self.target_mind.untarget(self, target_spawn_deposit)
                            return True
                        return False
                else:
                    del self.memory.filling_now
                    if target.energy >= target.energyCapacity:
                        self.target_mind.untarget(self, target_spawn_deposit)
                        return True
                    else:
                        self.pick_up_available_energy()
                        if not self.creep.pos.isNearTo(target.pos):
                            self.move_to(target)
                            self.report(speech.spawn_fill_moving_to_target)
                            return False

                        result = self.creep.transfer(target, RESOURCE_ENERGY)

                        if result == OK:
                            self.report(speech.spawn_fill_ok)
                        elif result == ERR_FULL:
                            self.target_mind.untarget(self, target_spawn_deposit)
                            return True
                        else:
                            self.log("Unknown result from creep.transfer({}): {}", target, result)
                            self.target_mind.untarget(self, target_spawn_deposit)
                            self.report(speech.spawn_fill_unknown_result)
                            return True
                        return False

            if self.creep.getActiveBodyparts(WORK) and not self.home.upgrading_paused():
                return building.Builder.run(self)
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
