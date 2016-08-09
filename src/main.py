import constants
import context
import flags
import spawning
import speech
import tower
from constants import *
from control import hivemind
from control.hivemind import TargetMind, HiveMind
from creep_wrappers import wrap_creep
from role_base import RoleBase
from tools import profiling
from utilities import consistency
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

require("perf")()


def main():
    if not Memory.meta:
        Memory.meta = {"pause": False, "quiet": False, "friends": []}
    if Memory.meta.pause:
        return

    flags.move_flags()

    PathFinder.use(True)

    target_mind = TargetMind()
    hive_mind = HiveMind(target_mind)
    context.set_targets(target_mind)
    context.set_hive(hive_mind)

    hive_mind.poll_all_creeps()
    hive_mind.poll_hostiles()

    if not Memory.creeps:
        Memory.creeps = {}
        for name in Object.keys(Game.creeps):
            Memory.creeps[name] = {}

    time = Game.time
    if not Memory.meta or Memory.meta.clear_now or \
            not Memory.meta.clear_next or time > Memory.meta.clear_next:
        print("[main] Clearing memory")
        consistency.clear_memory(target_mind)
        for room in hive_mind.my_rooms:
            room.recalculate_roles_alive()
            consistency.reassign_room_roles(room)
            # Recalculate spawning - either because a creep death just triggered our clearing memory, or we haven't
            # recalculated in the last 500 ticks.
            # TODO: do we really need to recalculate every 500 ticks? even though it really isn't expensive
            room.reset_planned_role()
        Memory.meta.clear_now = False

    for room in hive_mind.my_rooms:
        context.set_room(room)
        for creep in room.creeps:
            try:
                if creep.spawning and creep.memory.role != role_temporary_replacing:
                    continue
                if not creep.memory.base:
                    creep.memory.base = spawning.find_base_type(creep)
                instance = wrap_creep(creep)
                if not instance:
                    if creep.memory.role:
                        print("[{}][{}] Couldn't find role-type wrapper for role {}!".format(
                            creep.memory.home, creep.name, creep.memory.role))
                    else:
                        print("[{}][{}] Couldn't find this creep's role.".format(creep.memory.home, creep.name))
                    role = default_roles[creep.memory.base]
                    if not role:
                        base = RoleBase(target_mind, creep)
                        base.go_to_depot()
                        base.report(speech.base_no_role)
                        continue
                    creep.memory.role = role
                    instance = wrap_creep(creep)
                    room.register_to_role(instance)
                rerun = instance.run()
                if rerun:
                    rerun = instance.run()
                if rerun:
                    rerun = instance.run()
                if rerun:
                    print("[{}][{}: {}] Tried to rerun three times!".format(instance.home.room_name, creep.name,
                                                                            creep.memory.role))
            except Error as e:
                Game.notify("Error running role {}! Creep {} from room {} not run this tick.\n{}".format(
                    creep.memory.role if creep.memory.role else "<no role>", creep.name, creep.memory.home, e.stack
                ), 10)
                print("[{}][{}] Error running role {}!".format(creep.memory.home, creep.name,
                                                               role if role else "<no role>"))
                print(e.stack)

    for name in Object.keys(Game.spawns):
        spawn = Game.spawns[name]
        room = hive_mind.get_room(spawn.pos.roomName)
        spawning.run(room, spawn)

    tower.run()


module.exports.loop = profiling.wrap_main(main)

__pragma__('js', 'global').py = {
    "context": context,
    "consistency": consistency,
    "movement": movement,
    "hivemind": hivemind,
    "flags": flags,
    "constants": constants,
}

RoomPosition.prototype.createFlag2 = lambda flag_type: flags.create_flag(this, flag_type)
RoomPosition.prototype.cfms = lambda main, sub: flags.create_ms_flag(this, main, sub)
