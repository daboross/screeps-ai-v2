import autoactions
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
        if Memory.meta.waiting_for_bucket:
            if Game.cpu.bucket >= 10000:
                print("[paused] Bucket full, resuming next tick.")
                Memory.meta.pause = False
                del Memory.meta.waiting_for_bucket
            else:
                print("[paused] Bucket accumulated: {} (used loading code: {})".format(Game.cpu.bucket,
                                                                                       int(Game.cpu.getUsed())))
        elif Game.cpu.bucket <= 5000:
            Memory.meta.waiting_for_bucket = True
        return

    flags.move_flags()

    PathFinder.use(True)

    target_mind = TargetMind()
    hive_mind = HiveMind(target_mind)
    context.set_targets(target_mind)
    context.set_hive(hive_mind)

    if Game.time % 300 == 50:
        for room in hive_mind.visible_rooms:
            consistency.clear_caches(room)

    hive_mind.poll_all_creeps()
    hive_mind.poll_hostiles()

    if Game.time % 20 == 7:
        for room in hive_mind.visible_rooms:
            room.building.place_remote_mining_roads()

    if not Memory.creeps:
        Memory.creeps = {}
        for name in Object.keys(Game.creeps):
            Memory.creeps[name] = {}

    def run_creep(creeps_skipped, room, creep):
        if Game.cpu.getUsed() > Game.cpu.limit * 0.5 and Game.cpu.bucket < 3000:
            if creeps_skipped[room.room_name]:
                creeps_skipped[room.room_name].append(creep.name)
            else:
                creeps_skipped[room.room_name] = [creep.name]
            return
        try:
            if creep.spawning and creep.memory.role != role_temporary_replacing:
                return
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
                    return
                creep.memory.role = role
                instance = wrap_creep(creep)
                room.register_to_role(instance)
            canceled_via_instict = autoactions.instinct_check(instance)
            if canceled_via_instict:
                return
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
                role if role else "[no role]", creep.name, creep.memory.home, e.stack if e else "e == null??"
            ), 10)
            print("[{}][{}] Error running role {}!".format(creep.memory.home, creep.name,
                                                           role if role else "[no role]"))
            print(e.stack if e else "e == null??")

    total_creeps = 0
    creeps_skipped = {}
    if Memory.skipped_last_turn:
        print("[main] Running {} creeps skipped last tick, to save CPU.".format(
            _.sum(Memory.skipped_last_turn, 'length')))
        for room_name in Object.keys(Memory.skipped_last_turn):
            room = hive_mind.get_room(room_name)
            if not room:
                print("[{}] Room no longer visible? skipping re-running creeps skipped last turn from this room."
                      .format(room_name))
                continue
            context.set_room(room)
            room.precreep_tick_actions()
            total_creeps += len(Memory.skipped_last_turn[room_name])
            for creep_name in Memory.skipped_last_turn[room_name]:
                if not Game.creeps[creep_name]:
                    continue
                run_creep(creeps_skipped, room, Game.creeps[creep_name])
        del Memory.skipped_last_turn
    else:
        for room in hive_mind.my_rooms:
            context.set_room(room)
            room.precreep_tick_actions()
            total_creeps += len(room.creeps)
            for creep in room.creeps:
                run_creep(creeps_skipped, room, creep)
    skipped_count = 0
    for room_name in creeps_skipped.keys():
        skipped_count += len(creeps_skipped[room_name])
    if skipped_count:
        print("[main] Skipped {}/{} creeps, to save CPU.".format(skipped_count, total_creeps))
        print("[main] Total CPU used: {}. Bucket: {}.".format(int(Game.cpu.getUsed()), Game.cpu.bucket))
        Memory.skipped_last_turn = creeps_skipped

    for name in Object.keys(Game.spawns):
        spawn = Game.spawns[name]
        room = hive_mind.get_room(spawn.pos.roomName)
        spawning.run(room, spawn)

    tower.run(hive_mind)


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
RoomPosition.prototype.cfms = lambda main_type, sub_type: flags.create_ms_flag(this, main_type, sub_type)
