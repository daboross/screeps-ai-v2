import building
import creep_utils
import harvesting
import harvesting_big
import profiling
import spawning
import tower
import tower_fill
import upgrading
from base import *
from hivemind import TargetMind

__pragma__('noalias', 'name')

require("perf")()

# Needs to be below require("perf") and all other imports
profiling.init()

role_classes = {
    "upgrader": upgrading.Upgrader,
    "harvester": harvesting.Harvester,
    "big_harvester": harvesting_big.BigHarvester,
    "builder": building.Builder,
    "tower_fill": tower_fill.TowerFill,
}


class Profiler:
    def __init__(self):
        self.last = 0

    def check(self, name, *args):
        time = Game.cpu.getUsed()
        if time - self.last > 4:
            print("Used up {} time with `{}`!".format(time - self.last, name.format(*args)))
        if time > 30:
            print("Already used up {} time! (just finished `{}`)".format(time, name.format(*args)))
        self.last = time


def main():
    if Memory.did_not_finish:
        if Memory.last_creep:
            print("Didn't finish! Last creep run: {}: {}".format(
                Memory.last_creep, Game.creeps[Memory.last_creep].saying))
            del Memory.last_creep
        return
    Memory.did_not_finish = True
    p = Profiler()
    p.check("initial_load")
    target_mind = TargetMind()

    p.check("create_target_mind")
    time = Game.time
    if time % 100 == 0 or Memory.needs_clearing:
        print("Clearing memory")
        creep_utils.clear_memory(target_mind)
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

    for name in Object.keys(Game.creeps):
        Memory.last_creep = name
        creep = Game.creeps[name]
        if creep.spawning:
            continue
        role = creep.memory.role
        if role in role_classes:
            creep_wrapper = role_classes[role](target_mind, creep)
        else:
            role = creep_utils.get_role_name()
            creep.memory.role = role
            Memory.role_counts[role] += 1
            creep_wrapper = role_classes[role](target_mind, creep)

        rerun = creep_wrapper.run()
        if rerun:
            rerun = creep_wrapper.run()
        if rerun:
            print("[{}] Tried to rerun twice!".format(name))
        p.check("creep {} ({})", name, role)
        Memory.last_creep_saying = creep.saying

    del Memory.last_creep

    for name in Object.keys(Game.spawns):
        spawning.run(Game.spawns[name])
        p.check("spawn {}", name)

    tower.run()
    p.check("tower")
    del Memory.did_not_finish


module.exports.loop = profiling.profiler.wrap(main)
