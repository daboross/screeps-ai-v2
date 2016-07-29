import building
import context
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
from hivemind import TargetMind, HiveMind

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
    hive_mind = HiveMind(target_mind)
    context.set_targets(target_mind)
    context.set_hive(hive_mind)

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
        # just deassign this even if we didn't find any dead creeps - if there weren't any dead creep it means
        # this has reached the maximum wait time of 2000 ticks, in which case if we had any alive creeps, at least one
        # of them *should* have died - so we probably are completely dead due to some bug. If that happens, it'd
        # probably be best to start spawning more!
        Memory.meta.no_more_spawning = False

    for room in hive_mind.my_rooms:
        context.set_room(room)
        for creep in room.creeps:
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
                print("[{}] Tried to rerun twice!".format(creep.name))

    for name in Object.keys(Game.spawns):
        spawn = Game.spawns[name]
        context.set_room(hive_mind.get_room(spawn.pos.roomName))
        spawning.run(spawn)

    tower.run()
    context.clear()


module.exports.loop = profiling.wrap_main(main)

RoomPosition.prototype.createFlag2 = lambda pos: flags.create_flag(this, pos)
