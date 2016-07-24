import harvesting
from base import *

__pragma__('noalias', 'name')


class TowerFill(harvesting.Harvester):
    def run(self, second_run=False):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.untarget_spread_out_target("tower_fill")
            self.untarget_spread_out_target("harvester_deposit")

        if self.memory.harvesting:
            self.harvest_energy()
        else:
            target = self.get_new_tower_target()
            if target:
                result = self.creep.transfer(target, RESOURCE_ENERGY)
                if result == ERR_NOT_IN_RANGE:
                    self.move_to(target)
                elif result == ERR_FULL:
                    self.untarget_spread_out_target("tower_fill")
                    if not second_run:
                        self.run(True)
                elif result != OK:
                    print("[{}] Unknown result from creep.transfer({}): {}".format(
                        self.name, target, result
                    ))
            else:
                # print("[{}] No tower found.".format(self.name))
                harvesting.Harvester.run(self)

    def get_new_tower_target(self):
        def find_list():
            tower_list = []
            for id in Memory.tower.towers:
                tower = Game.getObjectById(id)
                if tower.energy < tower.energyCapacity:
                    tower_list.append(tower)
            return tower_list

        return self.get_spread_out_target("tower_fill", find_list)
