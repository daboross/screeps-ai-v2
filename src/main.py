import building
import creep_utils
import harvesting
import harvesting_big
import spawning
import tower
import tower_fill
import upgrading
from base import *

__pragma__('noalias', 'name')
require("perf")()

role_functions = {
    "upgrader": upgrading.run,
    "harvester": harvesting.run,
    "big_harvester": harvesting_big.run,
    "builder": building.run,
    "tower_fill": tower_fill.run,
}


class Profiler:
    def __init__(self):
        self.last = Game.cpu.getUsed()

    def check(self, name, *args):
        time = Game.cpu.getUsed()
        if time - self.last > 1.5:
            print("Used up {} time with `{}`!".format(time - self.last, name.format(*args)))
        self.last = time


def main():
    p = Profiler()
    time = Game.time
    print("Game time: {}".format(time))
    if time % 100 == 0 or Memory.needs_clearing:
        print("Clearing memory")
        creep_utils.clear_memory()
        p.check("clear_memory")
        creep_utils.recheck_targets_used()
        p.check("recheck_targets_used")
        creep_utils.count_roles()
        p.check("count_roles")
        Memory.needs_clearing = False
    elif (time + 75) % 200 == 0:
        print("Reassigning roles")
        creep_utils.reassign_roles()
        p.check("reassign_roles")

    creeps_needing_attention = []
    for name in Object.keys(Game.creeps):
        creep = Game.creeps[name]
        if creep.spawning:
            continue
        role = creep.memory.role
        if role in role_functions:
            role_functions[role](creep)
        else:
            creeps_needing_attention.append(creep)
        p.check("creep {} ({})", name, role)

    if creeps_needing_attention:
        print("Assigning roles to unassigned creeps")
        for creep in creeps_needing_attention:
            role = creep_utils.get_role_name()
            creep.memory.role = role
            Memory.role_counts[role] += 1
            role_functions[role](creep)
    p.check("creeps_needing_attention")

    print("Performing spawns")
    for name in Object.keys(Game.spawns):
        spawning.run(Game.spawns[name])
        p.check("spawn {}", name)

    print("Performing tower")
    tower.run()
    p.check("tower")


module.exports.loop = main
