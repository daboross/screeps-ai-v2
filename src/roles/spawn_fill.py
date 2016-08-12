import speech
from constants import target_harvester_deposit
from roles import building
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class SpawnFill(building.Builder):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.target_mind.untarget_all(self)
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget_all(self)

        if self.memory.harvesting:
            return self.harvest_energy()
        else:
            target = self.target_mind.get_new_target(self, target_harvester_deposit)
            if target:
                if target.energy >= target.energyCapacity:
                    self.target_mind.untarget(self, target_harvester_deposit)
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
                        self.target_mind.untarget(self, target_harvester_deposit)
                        return True
                    else:
                        self.log("Unknown result from creep.transfer({}): {}", target, result)
                        self.target_mind.untarget(self, target_harvester_deposit)
                        self.report(speech.spawn_fill_unknown_result)
                        return True
            else:
                if self.creep.getActiveBodyparts(WORK):
                    return building.Builder.run(self)
                target = self.creep.pos.findClosestByRange(FIND_MY_CREEPS, {
                    "filter": lambda c: c.getActiveBodyparts(WORK) and
                                        c.getActiveBodyparts(CARRY) and c.carry.energy < c.carryCapacity
                })
                if target:
                    if not self.creep.pos.isNearTo(target.pos):
                        self.move_to(target)
                        return False
                    self.creep.transfer(target, RESOURCE_ENERGY)
                else:
                    if self.creep.carry.energy < self.creep.carryCapacity:
                        self.memory.harvesting = True
                        return True
                    else:
                        self.report((["No one", "to give", "this to."], False))
                        self.go_to_depot()
        return False


profiling.profile_whitelist(SpawnFill, ["run"])
