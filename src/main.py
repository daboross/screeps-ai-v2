import math

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
from utilities import consistency, global_cache, averages
from utilities import movement
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

require("perf")()


def run_creep(hive_mind, target_mind, creeps_skipped, room, creep):
    if Game.cpu.getUsed() > Game.cpu.limit * 0.5 and Game.cpu.bucket < 3000:
        role = creep.memory.role
        if not (role == role_spawn_fill or role == role_local_hauler or role == role_dedi_miner
                or role == role_remote_hauler or role == role_remote_miner or role == role_link_manager):
            if creeps_skipped[room.room_name]:
                creeps_skipped[room.room_name].append(creep.name)
            else:
                creeps_skipped[room.room_name] = [creep.name]
        return
    try:
        if creep.spawning and creep.memory.role != role_temporary_replacing:
            return
        # if Game.cpu.bucket < 6000 and creep.memory.role in [role_remote_hauler, role_remote_miner, role_builder] \
        #         and len(room.sources) >= 2:
        #     if creep.memory.role != role_remote_miner:
        #         RoleBase(hive_mind, target_mind, room, creep).go_to_depot()
        #     return
        instance = wrap_creep(hive_mind, target_mind, room, creep)
        if not instance:
            if creep.memory.role:
                print("[{}][{}] Couldn't find role-type wrapper for role {}!".format(
                    creep.memory.home, creep.name, creep.memory.role))
            else:
                print("[{}][{}] Couldn't find this creep's role.".format(creep.memory.home, creep.name))
            role = default_roles[spawning.find_base_type(creep)]
            if not role:
                base = RoleBase(hive_mind, target_mind, room, creep)
                base.go_to_depot()
                base.report(speech.base_no_role)
                return
            creep.memory.role = role
            instance = wrap_creep(hive_mind, target_mind, room, creep)
            room.register_to_role(instance)
        canceled_via_instict = autoactions.instinct_check(instance)
        if canceled_via_instict:
            return
        rerun = instance.run()
        if Game.cpu.bucket >= 6000:
            if rerun:
                rerun = instance.run()
            if rerun:
                rerun = instance.run()
            if rerun:
                print("[{}][{}: {}] Tried to rerun three times!".format(instance.home.room_name, creep.name,
                                                                        creep.memory.role))
    except:
        e = __except0__
        role = creep.memory.role
        Game.notify("Error running role {}! Creep {} from room {} not run this tick.\n{}".format(
            role if role else "[no role]", creep.name, creep.memory.home, e.stack if e else "e == null??"
        ), 10)
        print("[{}][{}] Error running role {}!".format(creep.memory.home, creep.name,
                                                       role if role else "[no role]"))
        print(e.stack if e else "e == null?? {}".format(e))


def run_room(target_mind, creeps_skipped, room):
    """
    :type target_mind: control.targets.TargetMind
    :type creeps_skipped: dict
    :type room: control.hivemind.RoomMind
    """
    context.set_room(room)
    if not Memory.skipped_last_turn:
        try:
            room.precreep_tick_actions()
        except:
            print("[{}] Error running precreep_tick_actions:\n{}".format(room.room_name, __except0__.stack))
    if Memory.skipped_last_turn and room.room_name in Memory.skipped_last_turn:
        for name in Memory.skipped_last_turn[room.room_name]:
            creep = Game.creeps[name]
            if creep:
                run_creep(room.hive_mind, target_mind, creeps_skipped, room, creep)
        for creep in room.creeps:
            role = creep.memory.role
            if role == role_spawn_fill or role == role_local_hauler or role == role_dedi_miner \
                    or role == role_remote_hauler or role == role_remote_miner or role == role_link_manager:
                run_creep(room.hive_mind, target_mind, creeps_skipped, room, creep)

    else:
        for creep in room.creeps:
            run_creep(room.hive_mind, target_mind, creeps_skipped, room, creep)
    room.links.tick_links()
    if not Memory.skipped_last_turn:
        room.building.place_remote_mining_roads()
        for spawn in room.spawns:
            spawning.run(room, spawn)
    room.mining.poll_flag_energy_sitting()
    tower.run(room)


def main():
    averages.start_main_loop()

    if not Memory.meta:
        Memory.meta = {"pause": False, "quiet": False, "friends": []}

    bucket_tier = math.floor((Game.cpu.bucket - 1) / 1000)  # -1 so we don't count max bucket as a separate teir
    if bucket_tier != Memory.meta.last_bucket and bucket_tier:  # and bucket_tier to avoid problems in simulation
        if bucket_tier > Memory.meta.last_bucket:
            print("[main][bucket] Reached a tier {} bucket.".format(bucket_tier))
            if bucket_tier >= 6:
                Memory.meta.auto_enable_profiling = False
        else:
            print("[main][bucket] Down to a tier {} bucket.".format(bucket_tier))
            if bucket_tier <= 4:
                Memory.meta.auto_enable_profiling = True
            if bucket_tier <= 1:
                Memory.meta.pause = True
    Memory.meta.last_bucket = bucket_tier

    if Memory.meta.pause:
        if Memory.meta.waiting_for_bucket:
            if Game.cpu.bucket >= 10000:
                print("[paused] Bucket full, resuming next tick.")
                Memory.meta.pause = False
                del Memory.meta.waiting_for_bucket
            else:
                print("[paused] Bucket accumulated: {} (used loading code: {})".format(Game.cpu.bucket,
                                                                                       math.floor(Game.cpu.getUsed())))
        elif Game.cpu.bucket <= 5000:
            Memory.meta.waiting_for_bucket = True
        return

    flags.move_flags()

    PathFinder.use(True)

    target_mind = TargetMind()
    hive_mind = HiveMind(target_mind)
    context.set_targets(target_mind)
    context.set_hive(hive_mind)

    if Game.time % 320 == 53:
        consistency.clear_cache()

    hive_mind.poll_all_creeps()
    if Game.time % 5 == 1:
        hive_mind.poll_hostiles()

    if not Memory.creeps:
        Memory.creeps = {}
        for name in Object.keys(Game.creeps):
            Memory.creeps[name] = {}

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
            run_room(target_mind, creeps_skipped, room)
        del Memory.skipped_last_turn
    else:
        rooms = hive_mind.my_rooms
        if Game.cpu.bucket <= 5000:
            rooms = sorted(rooms, lambda r: -r.room.controller.level)
            if Game.cpu.bucket <= 4000:
                rooms = rooms[:len(rooms) - 1]
        for room in rooms:
            run_room(target_mind, creeps_skipped, room)
    skipped_count = _.sum(creeps_skipped, 'length')
    if skipped_count:
        if Memory.skipped_last_turn:
            all_creeps = _.sum(Memory.skipped_last_turn, 'length')
        else:
            all_creeps = len(Object.keys(Game.creeps))
        print("[main] Skipped {}/{} creeps, to save CPU.".format(skipped_count, all_creeps))
        print("[main] Total CPU used: {}. Bucket: {}.".format(math.floor(Game.cpu.getUsed()), Game.cpu.bucket))
        Memory.skipped_last_turn = creeps_skipped

    averages.end_main_loop()


module.exports.loop = profiling.wrap_main(main)

__pragma__('js', 'global').py = {
    "context": context,
    "consistency": consistency,
    "movement": movement,
    "hivemind": hivemind,
    "flags": flags,
    "constants": constants,
    "spawning": spawning,
    "get_room": lambda name: context.hive().get_room(name),
    "volatile": volatile_cache,
    "cache": global_cache,
    "get_creep": lambda name: wrap_creep(context.hive(), context.targets(),
                                         context.hive().get_room(Memory.creeps[name].home), Game.creeps[name])
    if name in Game.creeps else None,
    "cpu_avg": averages.get_average,
}

RoomPosition.prototype.createFlag2 = lambda flag_type: flags.create_flag(this, flag_type)
RoomPosition.prototype.cfms = lambda main_type, sub_type: flags.create_ms_flag(this, main_type, sub_type)
