import creep_utils
import upgrading

__pragma__('noalias', 'name')


def run(creep):
    if creep.memory.harvesting and creep.carry.energy >= creep.carryCapacity:
        creep.memory.harvesting = False
        creep_utils.finished_energy_harvest(creep)
        creep_utils.untarget_spread_out_target(creep, "structure_repair")
        creep_utils.untarget_spread_out_target(creep, "structure_build")
        creep_utils.untarget_spread_out_target(creep, "structure_repair_big")
    elif not creep.memory.harvesting and creep.carry.energy <= 0:
        creep.memory.harvesting = True

    if creep.memory.harvesting:
        creep_utils.harvest_energy(creep)
    else:
        target = creep_utils.get_possible_spread_out_target(creep, "structure_repair")
        if target:
            execute_repair_target(creep, target, 350000, "structure_repair")
        target = creep_utils.get_possible_spread_out_target(creep, "structure_build")
        if target:
            execute_construction_target(creep, target)
            return

        target = get_new_repair_target(creep, 350000, "structure_repair")
        if target:
            creep_utils.untarget_spread_out_target(creep, "structure_repair_big")
            execute_repair_target(creep, target, 350000, "structure_repair")
            return

        target = get_new_construction_target(creep)
        if target:
            creep_utils.untarget_spread_out_target(creep, "structure_repair_big")
            execute_construction_target(creep, target)
            return

        for max_energy in range(400000, 600000, 50000):
            target = get_new_repair_target(creep, max_energy, "structure_repair_big")
            if target:
                execute_repair_target(creep, target, max_energy, "structure_repair_big")
                return

        upgrading.run(creep)


def get_new_repair_target(creep, max_hits, type):
    def find_list():
        return creep.room.find(FIND_STRUCTURES, {"filter": lambda structure: (
            structure.my != False and
            structure.hits < structure.hitsMax and
            structure.hits < max_hits
        )})

    def max_builders(structure):
        return min((1 + (structure.hitsMax - min(structure.hits, max_hits)) / creep.carryCapacity), 3)

    return creep_utils.get_spread_out_target(creep, type, find_list, max_builders, True)


def get_new_construction_target(creep):
    def find_list():
        return creep.room.find(FIND_CONSTRUCTION_SITES)

    return creep_utils.get_spread_out_target(creep, "structure_build", find_list, 3, True)


def execute_repair_target(creep, target, max_hits, type):
    if target.hits >= target.hitsMax or target.hits >= max_hits:
        creep_utils.untarget_spread_out_target(creep, type)
        return

    result = creep.repair(target)
    if result == OK:
        if creep_utils.is_next_block_clear(creep, target):
            creep_utils.move_to_path(creep, target, True)
    elif result == ERR_NOT_IN_RANGE:
        creep_utils.move_to_path(creep, target)
    else:
        print("[{}] Unknown result from creep.repair({}): {}".format(
            creep.name, target, result
        ))
        if result == ERR_INVALID_TARGET:
            creep_utils.untarget_spread_out_target(creep, type)


def execute_construction_target(creep, target):
    result = creep.build(target)
    if result == OK:
        if creep_utils.is_next_block_clear(creep, target):
            creep_utils.move_to_path(creep, target, True)
    elif result == ERR_NOT_IN_RANGE:
        creep_utils.move_to_path(creep, target)
    else:
        print("[{}] Unknown result from creep.build({}): {}".format(
            creep.name, target, result
        ))
        if result == ERR_INVALID_TARGET:
            creep_utils.untarget_spread_out_target(creep, "structure_build")
