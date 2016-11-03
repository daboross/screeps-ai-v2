_memory_init = None


def init_memory():
    start = Game.cpu.getUsed()
    x = Memory
    end = Game.cpu.getUsed()
    global _memory_init
    _memory_init = end - start


init_memory()
import math

import autoactions
import constants
import context
import flags
import spawning
import speech
from constants import *
from control import hivemind, defense
from control.hivemind import HiveMind
from control.targets import TargetMind
from creep_wrappers import wrap_creep
from role_base import RoleBase
from tools import profiling, memory_info
from utilities import averages, consistency, global_cache, hostile_utils, movement, volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

require("perf")()


def run_creep(hive_mind, target_mind, creeps_skipped, room, creep):
    if Game.cpu.getUsed() > Game.cpu.limit * 0.5 and (Game.cpu.bucket < 3000 and
                                                          (Game.gcl.level > 1 or Game.cpu.bucket < 1000)):
        role = creep.memory.role
        if not (role == role_spawn_fill or role == role_tower_fill
                or role == role_link_manager or role == role_hauler or role == role_miner
                or role == role_ranged_offense or role == role_wall_defender):
            if creeps_skipped[room.room_name]:
                creeps_skipped[room.room_name].append(creep.name)
            else:
                creeps_skipped[room.room_name] = [creep.name]
            return
    try:
        if creep.spawning and creep.memory.role != role_temporary_replacing:
            return
        if creep.defense_override:
            return
        averages.start_record()
        instance = wrap_creep(hive_mind, target_mind, room, creep)
        if not instance:
            if creep.memory.role:
                print("[{}][{}] Couldn't find role-type wrapper for role {}!".format(
                    creep.memory.home, creep.name, creep.memory.role))
            else:
                print("[{}][{}] Couldn't find this creep's role.".format(creep.memory.home, creep.name))
            role = default_roles[spawning.find_base_type(creep)]
            if role:
                creep.memory.role = role
                instance = wrap_creep(hive_mind, target_mind, room, creep)
                room.register_to_role(instance)
            else:
                instance = RoleBase(hivemind, target_mind, room, creep)
                instance.go_to_depot()
                instance.report(speech.base_no_role)
        averages.finish_record('hive.wrap-creep')
        creep.wrapped = instance
        averages.start_record()
        rerun = instance.run()
        if Game.cpu.bucket >= 7000:
            if rerun:
                rerun = instance.run()
            if rerun:
                rerun = instance.run()
            if rerun:
                print("[{}][{}: {}] Tried to rerun three times!".format(instance.home.room_name, creep.name,
                                                                        creep.memory.role))
        averages.finish_record(creep.memory.role)
    except:
        e = __except0__
        role = creep.memory.role
        Game.notify("Error running role {}! Creep {} from room {} not run this tick.\n{}".format(
            role if role else "[no role]", creep.name, creep.memory.home, e.stack if e else "e == null??"
        ), 10)
        print("[{}][{}] Error running role {}!".format(creep.memory.home, creep.name,
                                                       role if role else "[no role]"))
        print(e.stack if e else "e == null?? {}".format(e))
        if not e:
            raise e


run_creep = profiling.profiled(run_creep, "main.run_creep")


def run_room(target_mind, creeps_skipped, room):
    """
    :type target_mind: control.targets.TargetMind
    :type creeps_skipped: dict
    :type room: control.hivemind.RoomMind
    """
    try:
        if room.mem.pause:
            return
        context.set_room(room)
        averages.start_record()
        room.defense.tick()
        averages.finish_record('defense.tick')
        if 'skipped_last_turn' in Memory and room.room_name in Memory.skipped_last_turn:
            for creep in room.creeps:
                role = creep.memory.role
                if role == role_spawn_fill or role == role_tower_fill \
                        or role == role_link_manager or role == role_hauler or role == role_miner \
                        or role == role_ranged_offense or role == role_wall_defender:
                    run_creep(room.hive_mind, target_mind, creeps_skipped, room, creep)
            for name in Memory.skipped_last_turn[room.room_name]:
                creep = Game.creeps[name]
                if creep:
                    run_creep(room.hive_mind, target_mind, creeps_skipped, room, creep)

        else:
            averages.start_record()
            room.precreep_tick_actions()
            averages.finish_record('room.tick')
            for creep in room.creeps:
                run_creep(room.hive_mind, target_mind, creeps_skipped, room, creep)
            averages.start_record()
            room.building.place_remote_mining_roads()
            averages.finish_record('building.roads')
            averages.start_record()
            room.building.place_home_ramparts()
            averages.finish_record('building.ramparts')
            for spawn in room.spawns:
                averages.start_record()
                spawning.run(room, spawn)
                averages.finish_record('spawn.tick')
        averages.start_record()
        room.links.tick_links()
        averages.finish_record('links.tick')
        if Game.time % 25 == 17:
            averages.start_record()
            room.mining.poll_flag_energy_sitting()
            averages.finish_record('mining.flags')
        averages.start_record()
        room.minerals.tick_terminal()
        averages.finish_record('terminal.tick')
    except:
        e = __except0__
        Game.notify("Error running room {}!\n{}".format(
            room.room_name, e.stack if e else "e == null??"
        ), 10)
        print("[{}] Error running room {}!".format(room.room_name, room.room_name))
        print(e.stack if e else "e == null?? {}".format(e))
        if not e:
            raise e


run_room = profiling.profiled(run_room, "main.run_room")


def main():
    global _memory_init
    # This check is here in case it's a global reset, and we've already initiated memory.
    if _memory_init is None:
        init_memory()

    averages.start_main_loop()

    if 'meta' not in Memory:
        Memory.meta = {"pause": False, "quiet": False, "friends": []}
    averages.prep_recording()
    averages.start_main_record()
    averages.record_memory_amount(_memory_init)
    _memory_init = None

    bucket_tier = math.floor((Game.cpu.bucket - 1) / 1000)  # -1 so we don't count max bucket as a separate tier
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
                hive_mind = HiveMind(TargetMind())
                for room in hive_mind.my_rooms:
                    room.defense.set_ramparts(True)
    Memory.meta.last_bucket = bucket_tier

    if Memory.meta.pause:
        if Memory.meta.waiting_for_bucket:
            if Game.gcl.level <= 2 and Game.cpu.bucket > 2000 or Game.cpu.bucket >= 10000:
                print("[paused] Bucket full, resuming next tick.")
                del Memory.meta.pause
                del Memory.meta.waiting_for_bucket
            else:
                print("[paused] Bucket accumulated: {} (used loading code: {})".format(Game.cpu.bucket,
                                                                                       math.floor(Game.cpu.getUsed())))
        elif Game.cpu.bucket <= 5000:
            Memory.meta.waiting_for_bucket = True
        return

    flags.move_flags()

    averages.start_record()

    PathFinder.use(True)

    target_mind = TargetMind()
    hive_mind = HiveMind(target_mind)
    context.set_targets(target_mind)
    context.set_hive(hive_mind)

    averages.finish_record('hive.init')

    if Game.time % 320 == 53:
        averages.start_record()
        consistency.clear_cache()
        averages.finish_record('cache.clean')

    averages.start_record()
    hive_mind.poll_all_creeps()
    averages.finish_record('hive.poll-creeps')
    if Game.time % 5 == 1 or not _.isEmpty(Memory.hostiles):
        averages.start_record()
        defense.poll_hostiles(hive_mind)
        averages.finish_record('defense.poll-hostiles')
    if Game.time % 25 == 7:
        averages.start_record()
        defense.cleanup_stored_hostiles()
        averages.finish_record('defense.clean-hostiles')

    if not Memory.creeps:
        Memory.creeps = {}
        for name in Object.keys(Game.creeps):
            Memory.creeps[name] = {}

    averages.start_record()
    hive_mind.find_my_rooms()
    averages.finish_record('hive.poll-rooms')

    averages.start_record()
    try:
        for room in hive_mind.visible_rooms:
            autoactions.running_check_room(room)
    except:
        e = __except0__
        Game.notify("Error executing run-away-checks!\n{}".format(
            e.stack if e else "e: {}".format(e)
        ), 10)
        print("[hive] Error running run-away-checks!")
        print(e.stack if e else "e: {}".format(e))

    averages.finish_record('auto.runaway')

    creeps_skipped = {}
    if 'skipped_last_turn' in Memory:
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
        if Game.gcl.level > 1 and Game.cpu.bucket <= 4000:
            rooms = sorted(rooms, lambda r: -r.rcl - r.room.controller.progress / r.room.controller.progressTotal)
            rooms = rooms[:len(rooms) - 1]
        for room in rooms:
            run_room(target_mind, creeps_skipped, room)
    averages.start_record()
    for room in hive_mind.visible_rooms:
        autoactions.pickup_check_room(room)
    averages.finish_record('auto.pickup')
    if Game.time % 50 == 40:
        averages.start_record()
        autoactions.cleanup_running_memory()
        averages.finish_record('auto.running-memory-cleanup')
    if not _.isEmpty(creeps_skipped):
        skipped_count = _.sum(creeps_skipped, 'length')
        if skipped_count:
            if Memory.skipped_last_turn:
                all_creeps = _.sum(Memory.skipped_last_turn, 'length')
            else:
                all_creeps = len(Object.keys(Game.creeps))
            print("[main] Skipped {}/{} creeps, to save CPU.".format(skipped_count, all_creeps))
            print("[main] Total CPU used: {}. Bucket: {}.".format(math.floor(Game.cpu.getUsed()), Game.cpu.bucket))
            Memory.skipped_last_turn = creeps_skipped

    averages.finish_main_record()
    averages.end_main_loop()


module.exports.loop = profiling.wrap_main(main)


def clear_global_cache(name):
    if not name:
        return
    for key in Object.keys(Memory.cache):
        if key.includes(name):
            del Memory.cache[key]
            print("[clear_global_cache] Cleared {}.".format(key))


__pragma__('js', 'global').py = {
    "context": context,
    "consistency": consistency,
    "autoactions": autoactions,
    "defense": defense,
    "movement": movement,
    "hivemind": hivemind,
    "flags": flags,
    "constants": constants,
    "spawning": spawning,
    "volatile": volatile_cache,
    "cache": global_cache,
    "hostile_utils": hostile_utils,
    "hive": lambda: context.hive(),
    "get_room": lambda name: context.hive().get_room(name),
    "get_creep": lambda name: wrap_creep(context.hive(), context.targets(),
                                         context.hive().get_room(Memory.creeps[name].home), Game.creeps[name])
    if name in Game.creeps else None,
    "cpu_avg": averages.get_average_visual,
    "cc": clear_global_cache,
    "analyse_mem": lambda path: memory_info.analyse_memory(path),
    "records": {
        'start': averages.start_recording,
        'stop': averages.stop_recording,
        'output': averages.output_records,
        'reset': averages.reset_records,
    }
}

RoomPosition.prototype.createFlag2 = lambda flag_type: flags.create_flag(this, flag_type)
RoomPosition.prototype.cfms = lambda main_type, sub_type: flags.create_ms_flag(this, main_type, sub_type)

averages.finish_record("")
