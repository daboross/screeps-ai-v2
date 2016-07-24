import upgrading
from base import *

__pragma__('noalias', 'name')


class Harvester(upgrading.Upgrader):
    def run(self, second_run=False):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            self.harvest_energy()
        else:
            target = self.get_new_target()

            if target:
                if target.energy >= target.energyCapacity:
                    self.untarget_spread_out_target("harvester_deposit")
                    if not second_run:
                        self.run(True)
                    return
                else:
                    result = self.creep.transfer(target, RESOURCE_ENERGY)
                    if result == ERR_NOT_IN_RANGE:
                        self.move_to(target)
                    elif result == ERR_FULL:
                        self.untarget_spread_out_target("harvester_deposit")
                        if not second_run:
                            self.run(True)
                    elif result != OK:
                        print("[{}] Unknown result from creep.transfer({}): {}".format(
                            self.name, target, result
                        ))
                        self.untarget_spread_out_target("harvester_deposit")
            else:
                upgrading.Upgrader.run(self)

    def get_new_target(self):
        def find_list():
            return self.creep.room.find(FIND_STRUCTURES, {
                "filter": lambda structure: ((structure.structureType == STRUCTURE_EXTENSION
                                              or structure.structureType == STRUCTURE_SPAWN)
                                             and structure.energy < structure.energyCapacity
                                             and structure.my)
            })

        return self.get_spread_out_target("harvester_deposit", find_list)
