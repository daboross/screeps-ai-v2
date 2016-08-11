import constants
import context
import flags
import spawning
import speech
import tower
from constants import *
from control import hivemind
from control.hivemind import HiveMind
from control.targets import TargetMind
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

    for room in hive_mind.my_rooms:
        context.set_room(room)
        room.precreep_tick_actions()
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
            except:
                e = __except__
                role = creep.memory.role
                Game.notify("Error running role {}! Creep {} from room {} not run this tick.\n{}".format(
                    role if role else "[no role]", creep.name, creep.memory.home, e.stack
                ), 10)
                print("[{}][{}] Error running role {}!".format(creep.memory.home, creep.name,
                                                               role if role else "[no role]"))
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
    "get_room": lambda name: context.hive().get_room(name)
}

RoomPosition.prototype.createFlag2 = lambda flag_type: flags.create_flag(this, flag_type)
RoomPosition.prototype.cfms = lambda main, sub: flags.create_ms_flag(this, main, sub)
