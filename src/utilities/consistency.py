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
    if room.spawn and room.role_count(role_spawn_fill) + room.role_count(role_spawn_fill_backup) \
            + room.role_count(role_tower_fill) < 1 \
            and room.role_count(role_dedi_miner) < room.get_target_local_miner_count():
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

    pass
    # # Don't make all local haulers suicide if we have stopped making more because of economy failure!
    # # We should be keeping them alive if that's the case!
    # if room.get_target_local_hauler_mass() and room.carry_mass_of(role_local_hauler) \
    #         > room.get_target_local_hauler_mass():
    #     extra_local_haulers = room.extra_creeps_with_carry_in_role(role_local_hauler,
    #                                                                room.get_target_local_hauler_mass())
    #     if len(extra_local_haulers):
    #         for name in extra_local_haulers:
    #             if name in Memory.creeps:
    #                 room.hive_mind.target_mind.untarget_all({"name": name})
    #                 Memory.creeps[name].role = role_cleanup
    #         room.recalculate_roles_alive()


def clear_memory(room):
    """
    Clears memory for all creeps belonging to room.
    :type room: control.hivemind.RoomMind
    """
    smallest_ticks_to_live = 500
    closest_replacement_time = Game.time + 100  # reset spawn at a minimum of every 100 ticks.
    target_mind = room.hive_mind.target_mind
    for name in Object.keys(Memory.creeps):
        memory = Memory.creeps[name]
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


def clear_cache():
    for name in Object.keys(Memory.rooms):
        mem = Memory.rooms[name]
        if mem.cache:
            for key in Object.keys(mem.cache):
                cache = mem.cache[key]
                if Game.time > cache.dead_at or (cache.ttl_after_use
                                                 and Game.time > cache.last_used + cache.ttl_after_use):
                    del mem.cache[key]
            if len(Object.keys(mem.cache)) <= 0:
                del mem.cache
        if len(Object.keys(mem)) <= 0:
            del Memory.rooms[mem]
    global_cache.cleanup()


reassign_room_roles = profiling.profiled(reassign_room_roles, "consistency.reassign_room_roles")

clear_memory = profiling.profiled(clear_memory, "consistency.clear_memory")

clear_cache = profiling.profiled(clear_cache, "consistency.clear_cache")
