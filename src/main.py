import math
from typing import Dict, List, Optional

import constants
import creeps.roles.squads
from cache import consistency, context, global_cache, volatile_cache
from consoletools import client_scripts, visuals
from constants import default_roles, rmem_key_pause_all_room_operations, role_hauler, role_link_manager, role_miner, \
    role_ranged_offense, role_spawn_fill, role_squad_init, role_temporary_replacing, role_tower_fill, role_wall_defender
from creep_management import autoactions, deathwatch, mining_paths, spawning, walkby_move
from creep_management.creep_wrappers import wrap_creep
from creeps.base import RoleBase
from empire import honey, shard_check, stored_data
from empire.hive import HiveMind
from empire.targets import TargetMind
from jstools import errorlog, memory_info, records
from jstools.screeps import *
from position_management import flags, locations
from rooms import building, defense, minerals, squads
from rooms.room_mind import RoomMind
from utilities import hostile_utils, movement, rndrs

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

# Have this inside an if() statement so that if customizations.js and main.js are concatenated together, the resulting
# code works correctly.
if not js_global.__customizations_active:
    require("customizations")
if not js_global.__metadata_active:
    require("metadata")

walkby_move.apply_move_prototype()

__pragma__('js', '{}', """
Object.defineProperty([].__proto__, 'azdef', {
    enumerable: false,
    writable: true,
    configurable: true,
    value: "uh-oh, this still leaks",
});
""")


def _calc_early_exit_cpu():
    # type: () -> int
    if Game.cpu.tickLimit == 500:
        return 450
    else:
        return max(Game.cpu.limit, Game.cpu.tickLimit - 50, int((Game.cpu.limit + Game.cpu.tickLimit) / 2))


_early_exit_cpu = _calc_early_exit_cpu()

_memory_init = None  # type: Optional[int]


def init_memory():
    # type: () -> None
    start = Game.cpu.getUsed()
    # noinspection PyUnusedLocal
    x = Memory
    end = Game.cpu.getUsed()
    global _memory_init
    _memory_init = end - start


@errorlog.wrapped(
    "main",
    lambda hive, targets, creeps_skipped, room, creep: (
            "Error running role {}, creep {} at {} from room {} not run this tick.".format(
                creep.memory.role, creep.name, creep.pos, creep.memory.home
            )
    )
)
def run_creep(hive, targets, creeps_skipped, room, creep):
    # type: (HiveMind, TargetMind, Dict[str, List[str]], RoomMind, Creep) -> None
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

    if creep.spawning and creep.memory.role != role_temporary_replacing \
            and creep.memory.role != role_squad_init:
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


@errorlog.wrapped(
    "main",
    lambda targets, creeps_skipped, room: "Error running room {}".format(room.name)
)
def run_room(targets, creeps_skipped, room):
    # type: (TargetMind, Dict[str, List[str]], RoomMind) -> None
    if room.mem[rmem_key_pause_all_room_operations]:
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
                if Game.cpu.getUsed() > _early_exit_cpu:
                    return

    else:
        records.start_record()
        room.precreep_tick_actions()
        records.finish_record('room.tick')
        for creep in room.creeps:
            run_creep(room.hive, targets, creeps_skipped, room, creep)
            if Game.cpu.getUsed() > _early_exit_cpu:
                return
        if Game.cpu.bucket >= 4500 and (Game.time + room.get_unique_owned_index()) % 50 == 0:
            records.start_record()
            actually_did_anything = errorlog.try_exec(
                "main",
                room.building.build_most_needed_road,
                lambda: "Error running road building in {}.".format(room.name)
            )
            if actually_did_anything:
                records.finish_record('building.roads.check-pavement')
            else:
                records.finish_record('building.roads.cache-checks-only')
            if (Game.time + room.get_unique_owned_index()) % 150 == 0:
                records.start_record()
                room.building.reset_inactive_mines()
                records.finish_record('building.roads.reset-inactive-mines')

        records.start_record()
        room.building.place_home_ramparts()
        records.finish_record('building.ramparts')
        records.start_record()
        room.building.bubble_wrap()
        records.finish_record('building.bubble-wrap')
        records.start_record()
        room.squads.run()
        records.finish_record('squads.run')
        for spawn in room.spawns:
            records.start_record()
            spawning.run(room, spawn)
            records.finish_record('spawn.tick')
    records.start_record()
    room.links.tick_links()
    records.finish_record('links.tick')
    if Game.time % 525 == 17:
        records.start_record()
        room.mining.cleanup_old_flag_sitting_values()
        records.finish_record('mining.cleanup_flags')
    records.start_record()
    room.minerals.tick_terminal()
    records.finish_record('terminal.tick')
    records.start_record()
    room.tick_observer()
    records.finish_record('observer.tick')


@errorlog.wrapped("main", lambda: "error running main")
def main():
    global _memory_init, _early_exit_cpu
    # This check is here in case it's a global reset, and we've already initiated memory.
    if _memory_init is None:
        init_memory()

    records.prep_recording()
    records.start_main_record()
    records.record_memory_amount(_memory_init)
    _memory_init = None  # type: Optional[int]

    _early_exit_cpu = _calc_early_exit_cpu()

    records.start_record()
    stored_data.initial_modification_check()
    records.finish_sub_record('stored_data.initial-modification-check')

    records.start_record()

    if 'meta' not in Memory:
        Memory.meta = {"pause": False, "quiet": True, "friends": []}

    bucket_tier = math.floor((Game.cpu.bucket - 1) / 1000)  # -1 so we don't count max bucket as a separate tier
    if bucket_tier != Memory.meta.last_bucket and bucket_tier:  # and bucket_tier to avoid problems in simulation
        if bucket_tier > Memory.meta.last_bucket:
            print("[main][bucket] Reached a tier {} bucket.".format(bucket_tier))
        else:
            print("[main][bucket] Down to a tier {} bucket.".format(bucket_tier))
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
    client_scripts.injection_check()
    records.finish_record('client-scripts.check')

    records.start_record()
    flags.move_flags()
    records.finish_record('flags.move')

    records.start_record()
    locations.init()
    if Game.time % 320 == 94:
        locations.clean_old_positions()
    records.finish_record('locations.init')

    records.start_record()

    targets = TargetMind()
    hive = HiveMind(targets)
    context.set_hive(hive)

    records.finish_record('hive.init')

    records.start_record()
    pause_by_shard = shard_check.tick_shard_limit_check(hive)
    records.finish_record('shard-check.check')

    if pause_by_shard:
        return

    if Game.time % 320 == 53:
        records.start_record()
        consistency.clear_cache()
        records.finish_record('cache.clean')

    if Game.time % 100000 == 6798:
        records.start_record()
        consistency.complete_refresh(hive)
        records.finish_record('cache.complete-refresh')

    if Game.time % 600 == 550:
        records.start_record()
        mining_paths.cleanup_old_values(hive)
        records.finish_record('mining-paths.cleanup')
    # vv purposefully one tick after the above ^^
    if Game.time % 600 == 551:
        records.start_record()
        building.clean_up_all_road_construction_sites()
        records.finish_record('building.clean-up-road-construction-sites')
    if Game.time % 600 == 200:
        records.start_record()
        building.clean_up_owned_room_roads(hive)
        records.finish_record('building.clean-up-owned-room-roads')

    records.start_record()
    hive.poll_all_creeps()
    records.finish_record('hive.poll-creeps')
    if Game.time % 5 == 1 or not _.isEmpty(Memory.hostiles):
        records.start_record()
        # NOTE: this also runs running-away checks and deathwatch checks!
        defense.poll_hostiles(hive, autoactions.running_check_room)
        records.finish_record('defense.poll-hostiles')
    records.start_record()
    deathwatch.start_of_tick_check()
    for room in hive.visible_rooms:
        deathwatch.mark_creeps(room)
    records.finish_record('deathwatch.check')

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

    if Game.time % 50 == 40:
        records.start_record()
        hive.states.calculate_room_states()
        records.finish_record('hive.calc-states')

    if Game.cpu.getUsed() > _early_exit_cpu:
        print("[main] used >= {} CPU - exiting. completed 0 rooms".format(_early_exit_cpu))
        records.finish_main_record()
        return
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
        if Game.cpu.bucket <= 4000 and len(rooms) > 1:
            rooms = _.sortBy(rooms, lambda r: -r.rcl - r.room.controller.progress / r.room.controller.progressTotal)
            rooms = rooms[0:len(rooms) - 1]
        for room in rooms:
            run_room(targets, creeps_skipped, room)
            if Game.cpu.getUsed() > _early_exit_cpu:
                print("[main] used >= {} CPU - exiting. completed {}/{} rooms".format(
                    _early_exit_cpu, __pragma__('js', '__index0__'), len(rooms)
                ))
                records.finish_main_record()
                return

    records.start_record()
    for room in hive.visible_rooms:
        autoactions.pickup_check_room(room)
    records.finish_record('auto.pickup')
    if Game.time % 50 == 40:
        records.start_record()
        autoactions.cleanup_running_memory()
        records.finish_record('auto.running-memory-cleanup')

    if Game.time % 30 == 10:
        records.start_record()
        stored_data.update_old_structure_data_for_visible_rooms()
        records.finish_record('stored_data.update-visible-rooms')

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

    records.start_record()
    any_visualized_rooms = False
    options_mem = Memory['nyxr_options']
    if options_mem:
        for room_name in Object.keys(options_mem):
            if room_name[0] == '_':
                continue
            any_visualized_rooms = True
            visuals.visualize_room(hive, room_name)
            records.finish_record('visuals.visualize-room')
            records.start_record()
    if not any_visualized_rooms:
        records.finish_record('visuals.empty-check')

    records.start_record()
    stored_data.final_modification_save()
    records.finish_sub_record('stored_data.final-modification-save')

    records.finish_main_record()


module.exports.loop = main

__pragma__('js', 'global').py = {
    "context": context,
    "consistency": consistency,
    "autoactions": autoactions,
    "locations": locations,
    "defense": defense,
    "movement": movement,
    "flags": flags,
    "constants": constants,
    "spawning": spawning,
    "volatile": volatile_cache,
    "cache": global_cache,
    "hostile_utils": hostile_utils,
    "building": building,
    "mining_paths": mining_paths,
    "meminfo": memory_info,
    "minerals": minerals,
    "stored_data": stored_data,
    "rndrs": rndrs,
    "honey": honey,
    "squads": squads,
    "roles_squads": creeps.roles.squads,
    "hive": lambda: context.hive(),
    "get_room": lambda name: context.hive().get_room(name),
    "get_creep": lambda name: wrap_creep(context.hive(), context.hive().targets,
                                         context.hive().get_room(Memory.creeps[name].home), Game.creeps[name])
    if name in Game.creeps else None,
    "repave": building.repave,
    "cc": global_cache.clear_values_matching,
    "full_refresh": lambda: consistency.complete_refresh(context.hive()),
    "analyse_mem": lambda path: memory_info.analyse_memory(path),
    "cache_stats": lambda: memory_info.cache_stats(),
    "records": {
        'start': records.start_recording,
        'stop': records.stop_recording,
        'start_sub': records.start_sub_recording,
        'output': records.output_records,
        'output_sub': records.output_sub_records,
        'reset': records.reset_records,
    }
}
