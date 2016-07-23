import building
import creep_utils
import harvesting
import harvesting_big
import spawning
import tower
import tower_fill
import upgrading

require("perf")()

role_functions = {
    "upgrader": upgrading.run,
    "harvester": harvesting.run,
    "big_harvester": harvesting_big.run,
    "builder": building.run,
    "tower_fill": tower_fill.run,
}


def main():
    time = Game.time
    if time % 100 == 0 or Memory.needs_clearing:
        creep_utils.clear_memory()
        creep_utils.recheck_targets_used()
    elif (time + 50) % 100:
        creep_utils.count_roles()
    elif (time + 75) % 200:
        creep_utils.reassign_roles()

    creeps_needing_attention = []
    for name in Object.keys(Game.creeps):
        creep = Game.creeps[name]
        if creep.spawning:
            continue
        role = creep.memory.role
        if role in role_functions:
            role_functions[role](creep)
        else:
            creeps_needing_attention.push(creep)

    if creeps_needing_attention:
        for creep in creeps_needing_attention:
            role = creep_utils.get_role_name()
            creep.memory.role = role
            Memory.role_counts[role] += 1
            role_functions[role](creep)

    for name in Object.keys(Game.spawns):
        spawning.run(Game.spawns[name])

    tower.run()


module.exports.loop = main
