import building
import creep_utils
import flags
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

role_classes = {
    "upgrader": upgrading.Upgrader,
    "harvester": harvesting.Harvester,
    "big_harvester": harvesting_big.BigHarvester,
    "builder": building.Builder,
    "tower_fill": tower_fill.TowerFill,
}


def main():
    if Memory.meta and Memory.meta.pause:
        return

    target_mind = TargetMind()

    if not Memory.creeps:
        Memory.creeps = {}
        for name in Object.keys(Game.creeps):
            Memory.creeps[name] = {}

    time = Game.time
    if not Memory.meta or Memory.meta.clear_now or \
            not Memory.meta.clear_next or time > Memory.meta.clear_next:
        if not Memory.meta:
            Memory.meta = {"pause": False, "quiet": False}
        print("Clearing memory")
        creep_utils.clear_memory(target_mind)
        creep_utils.count_roles()
        creep_utils.reassign_roles()
        Memory.meta.clear_now = False

    for name in Object.keys(Game.creeps):
        creep = Game.creeps[name]
        if creep.spawning:
            continue
        if not creep.memory.base:
            creep.memory.base = creep_utils.find_base(creep)
        role = creep.memory.role
        if role in role_classes:
            creep_instance = role_classes[role](target_mind, creep)
        else:
            role = creep_utils.get_role_name(creep.memory.base)[1]
            creep.memory.role = role
            if Memory.role_counts[role]:
                Memory.role_counts[role] += 1
            else:
                Memory.role_counts[role] = 1
            creep_instance = role_classes[role](target_mind, creep)
        rerun = creep_instance.run()
        if rerun:
            rerun = creep_instance.run()
        if rerun:
            print("[{}] Tried to rerun twice!".format(name))

    for name in Object.keys(Game.spawns):
        spawning.run(Game.spawns[name])

    tower.run()


module.exports.loop = profiling.wrap_main(main)

RoomPosition.prototype.createFlag2 = lambda pos: flags.create_flag(this, pos)
