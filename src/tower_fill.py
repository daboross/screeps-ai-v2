import harvesting
import hivemind
from base import *

__pragma__('noalias', 'name')


class TowerFill(harvesting.Harvester):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget(self.creep, hivemind.target_tower_fill)
            self.target_mind.untarget(self.creep, hivemind.target_harvester_deposit)

        if self.memory.harvesting:
            return self.harvest_energy()
        else:
            target = self.target_mind.get_new_target(self.creep, hivemind.target_tower_fill)
            if target:
                result = self.creep.transfer(target, RESOURCE_ENERGY)
                if result == ERR_NOT_IN_RANGE:
                    self.creep.say("TF. F. T.")
                    self.move_to(target)
                elif result == ERR_FULL:
                    self.target_mind.untarget(self.creep, hivemind.target_tower_fill)
                    return True
                elif result != OK:
                    print("[{}] Unknown result from creep.transfer({}): {}".format(
                        self.name, target, result
                    ))
                    self.creep.say("TF. ???")
                else:
                    self.creep.say("TF.")
            else:
                # print("[{}] No tower found.".format(self.name))
                self.creep.say("TF. H.")
                return harvesting.Harvester.run(self)

        return False
