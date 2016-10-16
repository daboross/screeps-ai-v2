import spawning
from constants import *
from control import live_creep_utils
from tools import profiling
from utilities import global_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def reassign_room_roles(room):
    """
    :type room: control.hivemind.RoomMind
    """
    if room.spawn and not room.role_count(role_spawn_fill) and not room.role_count(role_spawn_fill_backup) \
            and not room.role_count(role_tower_fill) and len(room.creeps):
        for creep in room.creeps:
            memory = creep.memory
            base = spawning.find_base_type(creep)
            if base == creep_base_worker:
                memory.role = role_spawn_fill_backup
                break
            elif base == creep_base_hauler:
                memory.role = role_spawn_fill
                break
        room.recalculate_roles_alive()
    if not room.under_siege() and room.spawn and not room.role_count(role_miner) \
            and not room.work_mass_of(role_spawn_fill) and not room.work_mass_of(role_spawn_fill_backup) \
            and not room.work_mass_of(role_tower_fill) and len(room.creeps) \
            and ((not room.role_count(role_spawn_fill) and not room.role_count(role_tower_fill))
                 or (room.room.storage and not room.room.storage.storeCapacity)):
        for creep in room.creeps:
            memory = creep.memory
            base = spawning.find_base_type(creep)
            if base == creep_base_worker:
                memory.role = role_spawn_fill_backup


def clear_memory(room):
    """
    Clears memory for all creeps belonging to room, and sets room.mem.meta.(clear_next & reset_spawn_on)
    :type room: control.hivemind.RoomMind
    """
    smallest_ticks_to_live = 500
    closest_replacement_time = Game.time + 100  # reset spawn at a minimum of every 100 ticks.
    target_mind = room.hive_mind.target_mind
    for name, memory in _.pairs(Memory.creeps):
        home = memory.home
        if home != room.room_name and home:
            continue
        creep = Game.creeps[name]
        if not creep:
            role = Memory.creeps[name].role
            if role and role != role_recycling:
                print("[{}][{}] {} died.".format(home, name, role))
            target_mind._unregister_all(name)

            del Memory.creeps[name]
        else:
            if creep.ticksToLive < smallest_ticks_to_live:
                smallest_ticks_to_live = creep.ticksToLive
            replacement_time = live_creep_utils.replacement_time(creep)
            if Game.time < replacement_time < closest_replacement_time:
                closest_replacement_time = replacement_time
    dead_next = Game.time + smallest_ticks_to_live
    room.mem.meta.clear_next = dead_next + 1
    room.mem.meta.reset_spawn_on = closest_replacement_time + 1


def get_next_replacement_time(room):
    """
    :type room: control.hivemind.RoomMind
    """
    closest_replacement_time = Game.time + 100
    for creep in room.creeps:
        replacement_time = live_creep_utils.replacement_time(creep)
        if Game.time < replacement_time < closest_replacement_time:
            closest_replacement_time = replacement_time
    return closest_replacement_time


def clear_cache():
    for name, mem in _.pairs(Memory.rooms):
        if mem.cache:
            for key in Object.keys(mem.cache):
                cache = mem.cache[key]
                if Game.time > cache.dead_at or (cache.ttl_after_use
                                                 and Game.time > cache.last_used + cache.ttl_after_use):
                    del mem.cache[key]
            if len(Object.keys(mem.cache)) <= 0:
                del mem.cache
        if len(Object.keys(mem)) <= 0:
            del Memory.rooms[name]
    global_cache.cleanup()


reassign_room_roles = profiling.profiled(reassign_room_roles, "consistency.reassign_room_roles")

clear_memory = profiling.profiled(clear_memory, "consistency.clear_memory")

clear_cache = profiling.profiled(clear_cache, "consistency.clear_cache")
