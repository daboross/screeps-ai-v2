import speech
from constants import target_tower_fill, target_harvester_deposit
from roles import spawn_fill
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class TowerFill(spawn_fill.SpawnFill):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.target_mind.untarget_all(self.creep)
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget_all(self.creep)

        if self.memory.harvesting:
            return self.harvest_energy()
        else:
            target = self.target_mind.get_new_target(self.creep, target_tower_fill)
            if target:
                self.pick_up_available_energy()
                if not self.creep.pos.isNearTo(target.pos):
                    self.move_to(target)
                    self.report(speech.tower_fill_moving_to_tower)
                    return False
                result = self.creep.transfer(target, RESOURCE_ENERGY)
                if result == OK:
                    self.report(speech.tower_fill_ok)
                elif result == ERR_FULL:
                    self.target_mind.untarget(self.creep, target_tower_fill)
                    return True
                else:
                    print("[{}] Unknown result from creep.transfer({}): {}".format(
                        self.name, target, result
                    ))
                    self.target_mind.untarget(self.creep, target_tower_fill)
                    self.report(speech.tower_fill_unknown_result)
            else:
                return spawn_fill.SpawnFill.run(self)

        return False
