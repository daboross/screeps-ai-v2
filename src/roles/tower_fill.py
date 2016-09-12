import speech
from constants import target_tower_fill, recycle_time, role_recycling, role_tower_fill
from roles import spawn_fill
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


class TowerFill(spawn_fill.SpawnFill):
    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_tower_fill
            return False
        if self.memory.filling and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.filling = False
            self.targets.untarget_all(self)
        elif not self.memory.filling and self.creep.carry.energy <= 0:
            self.memory.filling = True
            self.targets.untarget_all(self)

        if self.memory.filling:
            return self.harvest_energy()
        else:
            target = self.targets.get_new_target(self, target_tower_fill)
            if target:
                if not self.creep.pos.isNearTo(target.pos):
                    self.move_to(target)
                    self.report(speech.tower_fill_moving_to_tower)
                    return False
                result = self.creep.transfer(target, RESOURCE_ENERGY)
                if result == OK:
                    self.report(speech.tower_fill_ok)
                elif result == ERR_FULL:
                    self.targets.untarget(self, target_tower_fill)
                    return True
                else:
                    self.log("Unknown result from tower_fill-creep.transfer({}): {}", target, result)
                    self.targets.untarget(self, target_tower_fill)
                    self.report(speech.tower_fill_unknown_result)
            else:
                return spawn_fill.SpawnFill.run(self)

        return False


profiling.profile_whitelist(TowerFill, ["run"])
