_memory_init = None


def init_memory():
    start = Game.cpu.getUsed()
    x = Memory
    end = Game.cpu.getUsed()
    global _memory_init
    _memory_init = end - start


init_memory()

# noinspection PyUnboundLocalVariable
__pragma__('skip')
from utilities.screeps_constants import *

__pragma__('noskip')
_start_of_compile = Game.cpu.getUsed()

# Have this inside an if() statement so that if customizations.js and main.js are concatenated together, the resulting
# code works correctly.
__pragma__('js', '{}', """
if (!global.__customizations_active) {
    require("customizations");
}""")

import math

import autoactions
import constants
import context
import flags
import locations
import spawning
from constants import *
from control import defense
from control import hivemind
from control.hivemind import HiveMind
from control.targets import TargetMind
from creep_wrappers import wrap_creep
from role_base import RoleBase
from tools import memory_info
from utilities import consistency, deathwatch, global_cache, hostile_utils, movement, records, volatile_cache, \
    walkby_move

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

walkby_move.apply_move_prototype()


def run_creep(hive, targets, creeps_skipped, room, creep):
    """
    :type hive: control.hivemind.HiveMind
    :type targets: control.targets.TargetMind
    :type creeps_skipped: dict[str, list[str]]
    :type room: control.hivemind.RoomMind
    :type creep: Creep
    """
    if Game.cpu.getUsed() > Game.cpu.limit * 0.5 and (Game.cpu.bucket < 3000 and
                                                          (Game.gcl.level > 1 or Game.cpu.bucket < 1000)):
        role = creep.memory.role
        if not (role == role_spawn_fill or role == role_tower_fill
                or role == role_link_manager or role == role_hauler or role == role_miner
                or role == role_ranged_offense or role == role_wall_defender):
            if creeps_skipped[room.name]:
                creeps_skipped[room.name].append(creep.name)
            else:
                creeps_skipped[room.name] = [creep.name]
            return
    try:
        if creep.spawning and creep.memory.role != role_temporary_replacing:
            return
        if creep.defense_override:
            return
        records.start_record()
        instance = wrap_creep(hive, targets, room, creep)
        if not instance:
            if creep.memory.role:
                print("[{}][{}] Couldn't find role-type wrapper for role {}!".format(
                    creep.memory.home, creep.name, creep.memory.role))
            else:
                print("[{}][{}] Couldn't find this creep's role.".format(creep.memory.home, creep.name))
            role = default_roles[spawning.find_base_type(creep)]
            if role:
                creep.memory.role = role
                instance = wrap_creep(hive, targets, room, creep)
                room.register_to_role(instance)
            else:
                instance = RoleBase(hive, targets, room, creep)
                instance.go_to_depot()
        records.finish_record('hive.wrap-creep')
        creep.wrapped = instance
        records.start_record()
        bef = Game.cpu.getUsed()
        rerun = instance.run()
        if Game.cpu.bucket >= 7000 or Game.cpu.getUsed() - bef < 0.3:
            if rerun:
                rerun = instance.run()
            if rerun:
                rerun = instance.run()
            if rerun:
                print("[{}][{}: {}] Tried to rerun three times!".format(instance.home.name, creep.name,
                                                                        creep.memory.role))
        records.finish_record(creep.memory.role)
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


def run_room(targets, creeps_skipped, room):
    """
    :type targets: control.targets.TargetMind
    :type creeps_skipped: dict
    :type room: control.hivemind.RoomMind
    """
    try:
        if room.mem.pause:
            return
        records.start_record()
        room.defense.tick()
        records.finish_record('defense.tick')
        if 'skipped_last_turn' in Memory and room.name in Memory.skipped_last_turn:
            for creep in room.creeps:
                role = creep.memory.role
                if role == role_spawn_fill or role == role_tower_fill \
                        or role == role_link_manager or role == role_hauler or role == role_miner \
                        or role == role_ranged_offense or role == role_wall_defender:
                    run_creep(room.hive, targets, creeps_skipped, room, creep)
            for name in Memory.skipped_last_turn[room.name]:
                creep = Game.creeps[name]
                if creep:
                    run_creep(room.hive, targets, creeps_skipped, room, creep)

        else:
            records.start_record()
            room.precreep_tick_actions()
            records.finish_record('room.tick')
            for creep in room.creeps:
                run_creep(room.hive, targets, creeps_skipped, room, creep)
            records.start_record()
            room.building.place_remote_mining_roads()
            records.finish_record('building.roads')
            records.start_record()
            room.building.place_home_ramparts()
            records.finish_record('building.ramparts')
            for spawn in room.spawns:
                records.start_record()
                spawning.run(room, spawn)
                records.finish_record('spawn.tick')
        records.start_record()
        room.links.tick_links()
        records.finish_record('links.tick')
        if Game.time % 25 == 17:
            records.start_record()
            room.mining.poll_flag_energy_sitting()
            records.finish_record('mining.flags')
        records.start_record()
        room.minerals.tick_terminal()
        records.finish_record('terminal.tick')
    except:
        e = __except0__
        Game.notify("Error running room {}!\n{}".format(
            room.name, e.stack if e else "e == null??"
        ), 10)
        print("[{}] Error running room {}!".format(room.name, room.name))
        print(e.stack if e else "e == null?? {}".format(e))
        if not e:
            raise e


def main():
    global _memory_init
    # This check is here in case it's a global reset, and we've already initiated memory.
    if _memory_init is None:
        init_memory()

    records.prep_recording()
    records.start_main_record()
    records.record_memory_amount(_memory_init)
    _memory_init = None

    records.start_record()

    if 'meta' not in Memory:
        Memory.meta = {"pause": False, "quiet": False, "friends": []}

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
                hive = HiveMind(TargetMind())
                for room in hive.my_rooms:
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
    records.finish_record('bucket.check')

    records.start_record()
    flags.move_flags()
    records.finish_record('flags.move')

    records.start_record()
    locations.init()
    if Game.time % 320 == 94:
        locations.clean_old_positions()
    records.finish_record('locations.init')

    records.start_record()

    PathFinder.use(True)

    targets = TargetMind()
    hive = HiveMind(targets)
    context.set_hive(hive)

    records.finish_record('hive.init')

    if Game.time % 320 == 53:
        records.start_record()
        consistency.clear_cache()
        records.finish_record('cache.clean')

    records.start_record()
    hive.poll_all_creeps()
    records.finish_record('hive.poll-creeps')
    if Game.time % 5 == 1 or not _.isEmpty(Memory.hostiles):
        records.start_record()
        deathwatch.start_of_tick_check()
        records.finish_record('deathwatch.check')
        records.start_record()
        # NOTE: this also runs running-away checks and deathwatch checks!
        defense.poll_hostiles(hive, autoactions.running_check_room)
        records.finish_record('defense.poll-hostiles')
    if Game.time % 25 == 7:
        records.start_record()
        defense.cleanup_stored_hostiles()
        records.finish_record('defense.clean-hostiles')

    if not Memory.creeps:
        Memory.creeps = {}
        for name in Object.keys(Game.creeps):
            Memory.creeps[name] = {}

    records.start_record()
    hive.find_my_rooms()
    records.finish_record('hive.poll-rooms')

    creeps_skipped = {}
    if 'skipped_last_turn' in Memory:
        print("[main] Running {} creeps skipped last tick, to save CPU.".format(
            _.sum(Memory.skipped_last_turn, 'length')))
        for room_name in Object.keys(Memory.skipped_last_turn):
            room = hive.get_room(room_name)
            if not room:
                print("[{}] Room no longer visible? skipping re-running creeps skipped last turn from this room."
                      .format(room_name))
                continue
            run_room(targets, creeps_skipped, room)
        del Memory.skipped_last_turn
    else:
        rooms = hive.my_rooms
        if Game.gcl.level > 1 and Game.cpu.bucket <= 4000:
            rooms = sorted(rooms, lambda r: -r.rcl - r.room.controller.progress / r.room.controller.progressTotal)
            rooms = rooms[:len(rooms) - 1]
        used_start = Game.cpu.getUsed()
        for room in rooms:
            run_room(targets, creeps_skipped, room)
            if Game.cpu.getUsed() - used_start >= 400:
                print("[main] Used >= 400 CPU this tick! Skipping everything else.")
                return

    records.start_record()
    for room in hive.visible_rooms:
        autoactions.pickup_check_room(room)
    records.finish_record('auto.pickup')
    if Game.time % 50 == 40:
        records.start_record()
        autoactions.cleanup_running_memory()
        records.finish_record('auto.running-memory-cleanup')

    if Game.time % 10000 == 367:
        records.start_record()
        hive.balance_rooms()
        records.finish_record('hive.balance_rooms')

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

    if Game.cpu.bucket is undefined or Game.cpu.bucket >= 6000 and not Memory.meta.quiet:
        records.start_record()
        hive.sing()
        records.finish_record('hive.sing')

    records.finish_main_record()


module.exports.loop = main

__pragma__('js', 'global').py = {
    "context": context,
    "consistency": consistency,
    "autoactions": autoactions,
    "locations": locations,
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
    "get_creep": lambda name: wrap_creep(context.hive(), context.hive().targets,
                                         context.hive().get_room(Memory.creeps[name].home), Game.creeps[name])
    if name in Game.creeps else None,
    "cc": global_cache.clear_values_matching,
    "full_refresh": lambda: consistency.complete_refresh(context.hive()),
    "analyse_mem": lambda path: memory_info.analyse_memory(path),
    "records": {
        'start': records.start_recording,
        'stop': records.stop_recording,
        'start_sub': records.start_sub_recording,
        'output': records.output_records,
        'output_sub': records.output_sub_records,
        'reset': records.reset_records,
    }
}

RoomPosition.prototype.createFlag2 = lambda flag_type: flags.create_flag(this, flag_type)
RoomPosition.prototype.cfms = lambda main_type, sub_type: flags.create_ms_flag(this, main_type, sub_type)

records.prep_recording()
records.record_compile_amount(Game.cpu.getUsed() - _start_of_compile)
