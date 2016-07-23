import creep_utils
import upgrading


def run(creep, second_run=False):
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
            if target.energy >= target.energyCapacity:
                creep_utils.untarget_spread_out_target(creep, "harvester_deposit")
                if not second_run:
                    run(creep, True)
                return
            else:
                result = creep.transfer(target, RESOURCE_ENERGY)
                if result == ERR_NOT_IN_RANGE:
                    creep_utils.move_to_path(creep, target)
                elif result == ERR_FULL:
                    creep_utils.untarget_spread_out_target(creep, "harvester_deposit")
                    if not second_run:
                        run(creep, True)
                elif result != OK:
                    print("[{}] Unknown result from creep.transfer({}): {}".format(
                        creep.name, target, result
                    ))
                    creep_utils.untarget_spread_out_target(creep, "harvester_deposit")
        else:
            upgrading.run(creep)


def get_new_target(creep):
    def find_list():
        return creep.room.find(FIND_STRUCTURES, {
            "filter": lambda structure: ((structure.structureType == STRUCTURE_EXTENSION
                                          or structure.structureType == STRUCTURE_SPAWN)
                                         and structure.energy < structure.energyCapacity
                                         and structure.my)
        })

    return creep_utils.get_spread_out_target(creep, "harvester_deposit", find_list)
