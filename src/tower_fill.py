import creep_utils
import harvesting
from base import *

__pragma__('noalias', 'name')


def run(creep, second_run=False):
    if creep.memory.harvesting and creep.carry.energy >= creep.carryCapacity:
        creep.memory.harvesting = False
        creep_utils.finished_energy_harvest(creep)
    elif not creep.memory.harvesting and creep.carry.energy <= 0:
        creep.memory.harvesting = True
        creep_utils.untarget_spread_out_target(creep, "tower_fill")
        creep_utils.untarget_spread_out_target(creep, "harvester_deposit")

    if creep.memory.harvesting:
        creep_utils.harvest_energy(creep)
    else:
        target = get_new_target(creep)
        if target:
            result = creep.transfer(target, RESOURCE_ENERGY)
            if result == ERR_NOT_IN_RANGE:
                creep_utils.move_to_path(creep, target)
            elif result == ERR_FULL:
                creep_utils.untarget_spread_out_target(creep, "tower_fill")
                if not second_run:
                    run(creep, True)
            elif result != OK:
                print("[{}] Unknown result from creep.transfer({}): {}".format(
                    creep.name, target, result
                ))
        else:
            print("[{}] No tower found.".format(creep.name))
            harvesting.run(creep)


def get_new_target(creep):
    def find_list():
        tower_list = []
        for id in Memory.tower.towers:
            tower = Game.getObjectById(id)
            if tower.energy < tower.energyCapacity:
                tower_list.append(tower)
        return tower_list

    return creep_utils.get_spread_out_target(creep, "tower_fill", find_list)
