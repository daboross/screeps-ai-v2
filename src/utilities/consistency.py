import math

import context
from constants import *
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def reassign_roles():
    for room in context.hive().my_rooms:
        reassign_room_roles(room)


def reassign_room_roles(room):
    """
    :type room: control.hivemind.RoomMind
    """
    if room.role_count(role_spawn_fill) + room.role_count(role_spawn_fill_backup) < 4 \
            and room.role_count(role_dedi_miner) < room.get_target_local_miner_count():
        num = 0
        for creep in room.creeps:
            memory = creep.memory
            if memory.base == creep_base_worker:
                memory.role = role_spawn_fill_backup
                num += 1
            elif memory.base == creep_base_hauler:
                memory.role = role_spawn_fill
                num += 1
            if num >= 5:
                break
        room.recalculate_roles_alive()

    if room.carry_mass_of(role_local_hauler) > room.get_target_local_hauler_carry_mass():
        # The creep with the lowest lifetime left should die.
        next_to_die = room.next_x_to_die_of_role(
            role_local_hauler,
            max(1, (room.carry_mass_of(role_local_hauler) - room.get_target_local_hauler_carry_mass())
                / room.get_max_sections_for_role(role_local_hauler)))
        changed = False
        for name in next_to_die:
            if Memory.creeps[name]:
                Memory.creeps[name].role = role_cleanup
                changed = True
        if changed:
            room.recalculate_roles_alive()


def clear_memory(room):
    """
    Clears memory for all creeps belonging to room.
    :type room: control.hivemind.RoomMind
    """
    smallest_ticks_to_live = 500
    closest_replacement_time = math.pow(2, 30)
    target_mind = room.hive_mind.target_mind
    for name in Object.keys(Memory.creeps):
        memory = Memory.creeps[name]
        home = memory.home
        if home != room.room_name and home:
            continue
        creep = Game.creeps[name]
        if not creep:
            role = Memory.creeps[name].role
            if role:
                print("[{}][{}] {} died".format(home, name, role))
            if role == role_dedi_miner:
                source_id = target_mind._get_existing_target_id(target_big_source, name)
                if source_id:
                    del Memory.dedicated_miners_stationed[source_id]
                else:
                    print("[{}][{}] WARNING! clear_memory couldn't find placed source for big harvester!".format(
                        home, name))
            elif role == role_remote_miner:
                flag = target_mind._get_existing_target_from_name(name, target_remote_mine_miner)
                if flag and flag.memory and flag.memory.remote_miner_targeting == name:
                    del flag.memory.remote_miner_targeting
                    del flag.memory.remote_miner_death_tick
            elif role == role_remote_mining_reserve:
                controller = target_mind._get_existing_target_from_name(name, target_remote_reserve)
                if controller and controller.room.memory.controller_remote_reserve_set == name:
                    del controller.room.memory.controller_remote_reserve_set
            target_mind._unregister_all(name)

            del Memory.creeps[name]
        else:
            if creep.ticksToLive < smallest_ticks_to_live:
                smallest_ticks_to_live = creep.ticksToLive
            replacement_time = creep.memory.calculated_replacement_time
            if replacement_time and Game.time < replacement_time < closest_replacement_time:
                closest_replacement_time = creep.memory.calculated_replacement_time
    dead_next = Game.time + smallest_ticks_to_live
    room.mem.meta.clear_next = dead_next + 1
    room.mem.meta.reset_spawn_on = closest_replacement_time + 1


def clear_caches(room):
    if room.mem.cache:
        for key in room.mem.cache:
            cache = room.mem.cache[key]
            if Game.time > cache.dead_at or (cache.ttl_after_use and Game.time > cache.last_used + cache.ttl_after_use):
                del room.mem.cache[key]


reassign_room_roles = profiling.profiled(reassign_room_roles, "consistency.reassign_room_roles")

clear_memory = profiling.profiled(clear_memory, "consistency.clear_memory")
