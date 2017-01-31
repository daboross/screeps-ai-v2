from cache import global_cache
from constants import *
from creep_management import spawning
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def reassign_room_roles(room):
    """
    :type room: rooms.room_mind.RoomMind
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
    :type room: rooms.room_mind.RoomMind
    """
    smallest_ticks_to_live = 500
    closest_replacement_time = Game.time + 100  # reset spawn at a minimum of every 100 ticks.
    targets = room.hive.targets
    for name, memory in _.pairs(Memory.creeps):
        home = memory.home
        if home != room.name and home:
            continue
        creep = Game.creeps[name]
        if not creep:
            targets.untarget_all({'name': name})

            del Memory.creeps[name]
        else:
            if creep.ticksToLive < smallest_ticks_to_live:
                smallest_ticks_to_live = creep.ticksToLive
            replacement_time = room.replacement_time_of(creep)
            if Game.time < replacement_time < closest_replacement_time:
                closest_replacement_time = replacement_time
    dead_next = Game.time + smallest_ticks_to_live
    room.mem[rmem_key_metadata].clear_next = dead_next + 1
    room.mem[rmem_key_metadata].reset_spawn_on = closest_replacement_time + 1


def get_next_replacement_time(room):
    """
    :type room: rooms.room_mind.RoomMind
    """
    closest_replacement_time = Game.time + 100
    for creep in room.creeps:
        replacement_time = room.replacement_time_of(creep)
        if Game.time < replacement_time < closest_replacement_time:
            closest_replacement_time = replacement_time
    return closest_replacement_time


def clear_cache():
    for name, mem in _.pairs(Memory.rooms):
        if rmem_key_cache in mem:
            for key in Object.keys(mem.cache):
                cache = mem.cache[key]
                if Game.time > cache.dead_at or (cache.ttl_after_use
                                                 and Game.time > cache.last_used + cache.ttl_after_use):
                    del mem.cache[key]
            if len(Object.keys(mem.cache)) <= 0:
                del mem.cache
        if rmem_key_room_reserved_up_until_tick in mem and mem.rea <= Game.time:
            del mem.rea
        if _.isEmpty(mem):
            del Memory.rooms[name]
    for name, mem in _.pairs(Memory.flags):
        if _.isEmpty(mem):
            del Memory.flags[name]
        elif name not in Game.flags and \
                ((not name.includes('_') and name.includes('Flag'))
                 or name.includes('local_mine') or name.startsWith('21_')):
            del Memory.flags[name]
            print('[consistency] Clearing flag {}\'s memory: {}'.format(name, JSON.stringify(mem)))
    global_cache.cleanup()


def complete_refresh(hive):
    """
    :type hive: empire.hive.HiveMind
    """
    # Run all regular clear functions:
    for room in hive.my_rooms:
        clear_memory(room)
        room.recalculate_roles_alive()
        room.reset_planned_role()
    # Double check for creeps in memory that aren't alive (maybe in rooms which are no longer owned?)
    for name in Object.keys(Memory.creeps):
        if name not in Game.creeps:
            mem = Memory.creeps[name]
            print('[consistency] Clearing rouge creep: {} ({})'.format(name, mem.home))
            del Memory.creeps[name]
    # Double check for creeps in TargetMind which aren't alive:
    target_mem = _.get(Memory, 'targets.targeters_using')
    for name in Object.keys(target_mem):
        if name not in Game.creeps:
            targets = target_mem[name]
            print('[consistency] Clearing rouge targets for creep: {} ({})'.format(name, Object.keys(targets)))
            hive.targets.untarget_all({'name': name})
    # Remove deprecated Memory paths that are no longer in use:
    for key in ['cpu_usage', 'profiler', '_debug', 'x']:
        if key in Memory:
            print('[consistency] Removing deprecated memory path: {}'.format(key))
            del Memory[key]
    for key in ['enable_profiling', 'auto_enable_profiling']:
        if key in Memory.meta:
            print('[consistency] Removing deprecated memory path: meta.{}'.format(key))
            del Memory.meta[key]
    for name in Object.keys(Memory.rooms):
        mem = Memory.rooms[name]
        if '_ly' in mem:
            del mem['_ly']
        if 'attack_until' in mem:
            del mem['attack_until']
        if 'alert' in mem:
            del mem['alert']
        if not len(mem):
            del Memory.rooms[name]
    for name in Object.keys(Memory.flags):
        mem = Memory.flags[name]
        if 'remote_miner_targeting' in mem:
            del mem['remote_miner_targeting']
        if not len(mem):
            del Memory.flags[name]
