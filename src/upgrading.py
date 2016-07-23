import creep_utils
from base import *
__pragma__('noalias', 'name')


def run(creep):
    if creep.memory.harvesting and creep.carry.energy >= creep.carryCapacity:
        creep.memory.harvesting = False
        creep_utils.finished_energy_harvest(creep)
    elif not creep.memory.harvesting and creep.carry.energy <= 0:
        creep.memory.harvesting = True

    if creep.memory.harvesting:
        creep_utils.harvest_energy(creep)
    elif not creep.room.controller.my:
        creep_utils.go_to_depot(creep)
    else:
        result = creep.upgradeController(creep.room.controller)
        if result == ERR_NOT_IN_RANGE:
            creep_utils.move_to_path(creep, creep.room.controller)
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            creep.memory.harvesting = True
        elif result == OK:
            creep_utils.move_to_path(creep, creep.room.controller, True)
        else:
            print("[{}] Unknown result from upgradeController({}): {}".format(
                creep.name, creep.room.controller, result
            ))

            if creep.carry.energy < creep.carryCapacity:
                creep.memory.harvesting = True
            else:
                creep_utils.go_to_depot(creep)
