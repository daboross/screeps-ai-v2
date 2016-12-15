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
        if 'cache' in mem:
            for key in Object.keys(mem.cache):
                cache = mem.cache[key]
                if Game.time > cache.dead_at or (cache.ttl_after_use
                                                 and Game.time > cache.last_used + cache.ttl_after_use):
                    del mem.cache[key]
            if len(Object.keys(mem.cache)) <= 0:
                del mem.cache
        if 'rea' in mem and mem.rea <= Game.time:
            del mem.rea
        if _.isEmpty(mem):
            del Memory.rooms[name]
    for name, mem in _.pairs(Memory.flags):
        if _.isEmpty(mem):
            del Memory.flags[name]
        elif name not in Game.flags and (
                    (not name.includes('_') and name.includes('Flag')) or name.includes('local_mine')):
            del Memory.flags[name]
            print('[consistency] Clearing flag {}\'s memory: {}'.format(name, JSON.stringify(mem)))
    global_cache.cleanup()


def clear_all_dead(hive):
    for room in hive.my_rooms:
        clear_memory(room)
        room.recalculate_roles_alive()
        room.reset_planned_role()

    for name, mem in _.pairs(Memory.creeps):
        if name not in Game.creeps:
            print('[consistency] Clearing rouge creep: {} ({})'.format(name, mem.home))
            del Memory.creeps[name]
    for name, targets in _.pairs(_.get(Memory, 'targets.targeters_using')):
        if name not in Game.creeps:
            print('[consistency] Clearing rouge targets for creep: {} ({})'.format(name, Object.keys(targets)))
            hive.target_mind._unregister_all(name)


reassign_room_roles = profiling.profiled(reassign_room_roles, "consistency.reassign_room_roles")

clear_memory = profiling.profiled(clear_memory, "consistency.clear_memory")

clear_cache = profiling.profiled(clear_cache, "consistency.clear_cache")
