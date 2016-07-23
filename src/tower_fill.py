import creep_utils
import harvesting


def run(creep):
    if creep.memory.harvesting and creep.carry.energy >= creep.carryCapacity:
        creep.memory.harvesting = False
        creep_utils.finished_energy_harvest(creep)
    elif not creep.memory.harvesting and creep.carry.energy <= 0:
        creep.memory.harvesting = True

    if creep.memory.harvesting:
        creep_utils.harvest_energy(creep)
    else:
        target = get_new_target(creep)
        if target:
            result = creep.transfer(target, RESOURCE_ENERGY)
            if result == ERR_NOT_IN_RANGE:
                creep_utils.move_to_path(creep, target)
            elif result != OK:
                print("[{}] Unknown result from creep.transfer({}): {}".format(
                    creep.name, target, result
                ))
        else:
            harvesting.run(creep)


def get_new_target(creep):
    def find_list():
        return [Game.getObjectById(id) for id in Memory.tower.towers]

    return creep_utils.get_spread_out_target(creep, "harvester_deposit", find_list)
