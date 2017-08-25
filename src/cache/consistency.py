from typing import TYPE_CHECKING, cast

from cache import global_cache
from constants import *
from creep_management import spawning
from empire import stored_data
from jstools.screeps import *
from position_management import locations

if TYPE_CHECKING:
    from rooms.room_mind import RoomMind
    from empire.hive import HiveMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def reassign_room_roles(room):
    # type: (RoomMind) -> None
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
    # type: (RoomMind) -> None
    """
    Clears memory for all creeps belonging to room, and sets room.mem.meta.(clear_next & reset_spawn_on)
    :type room: rooms.room_mind.RoomMind
    """
    game_time = Game.time
    smallest_ticks_to_live = 500
    closest_replacement_time = game_time + 100  # reset spawn at a minimum of every 100 ticks.
    targets = room.hive.targets
    for name, memory in _.pairs(Memory.creeps):
        home = memory.home
        if home != room.name and home:
            continue
        creep = Game.creeps[name]
        if not creep:
            targets.untarget_all(cast(Creep, {'name': name}))

            del Memory.creeps[name]
        else:
            if creep.ticksToLive < smallest_ticks_to_live:
                smallest_ticks_to_live = creep.ticksToLive
            replacement_time = room.replacement_time_of(creep)
            if Game.time < replacement_time < closest_replacement_time:
                closest_replacement_time = replacement_time
        move_memory = memory['_move']
        if move_memory:
            time = move_memory.time
            if not time or game_time > time + basic_reuse_path:
                del memory['_move']
    dead_next = Game.time + smallest_ticks_to_live
    if rmem_key_metadata not in room.mem:
        print("[consistency] warning: no metadata key in room {} memory. Creating.".format(room.name))
        room.mem[rmem_key_metadata] = {}
    room.mem[rmem_key_metadata].clear_next = dead_next + 1
    room.mem[rmem_key_metadata].reset_spawn_on = closest_replacement_time + 1
    squad_mem = room.mem[rmem_key_squad_memory]
    if squad_mem:
        for key in Object.keys(squad_mem):
            if not locations.get(key):
                del squad_mem[key]


def get_next_replacement_time(room):
    # type: (RoomMind) -> int
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
    # type: () -> None
    for name, mem in _.pairs(Memory.rooms):
        if rmem_key_cache in mem:
            for key in Object.keys(mem.cache):
                cache = mem.cache[key]
                if not cache.dead_at or Game.time > cache.dead_at:
                    del mem.cache[key]
            if len(Object.keys(mem.cache)) <= 0:
                del mem.cache
        if rmem_key_room_reserved_up_until_tick in mem and mem[rmem_key_room_reserved_up_until_tick] <= Game.time:
            del mem[rmem_key_room_reserved_up_until_tick]
        if _.isEmpty(mem):
            del Memory.rooms[name]
        if mem[rmem_key_metadata] and (not _.get(Game.rooms, [name, 'controller', 'my'])):
            if mem[rmem_key_metadata].clear_next < Game.time - 600 * 1000:
                # we've been dead for a long while, and haven't been cleaned up..
                Game.notify("[consistency] Cleaning up memory for dead room {}".format(name))
                console.log("[consistency] Cleaning up memory for dead room {}".format(name))
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
    # type: (HiveMind) -> None
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
            hive.targets.untarget_all(cast(Creep, {'name': name}))
    # Remove deprecated Memory paths that are no longer in use:
    for key in ['cpu_usage', 'profiler', '_debug', 'x', '_ij_timeout', '_visuals_till', '_inject_timeout']:
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
        for true_only_key in [rmem_key_focusing_home, rmem_key_upgrading_paused, rmem_key_building_paused,
                              rmem_key_storage_use_enabled]:
            if true_only_key in mem and not mem[true_only_key]:
                del mem[true_only_key]
        if 'oss' in mem:
            del mem['oss']
        for key in Object.keys(mem):
            if key.startsWith('oss-'):
                del mem[key]
        if rmem_key_mineral_mind_storage in mem:
            mineral_mind_mem = mem[rmem_key_mineral_mind_storage]
            for sub_key in Object.keys(mineral_mind_mem):
                sub_mem = mineral_mind_mem[sub_key]
                if (_.isObject(sub_mem) and _.isEmpty(sub_mem)) or sub_mem is 0:
                    print('[consistency] Deleting empty memory path Memory.rooms.{}.{}.{}'
                          .format(name, rmem_key_mineral_mind_storage, sub_key))
                    del mineral_mind_mem[sub_key]
                if sub_key == 'mineral_hauler' and sub_mem not in Game.creeps:
                    print('[consistency] Deleting empty memory path Memory.rooms.{}.{}.{}'
                          .format(name, rmem_key_mineral_mind_storage, sub_key))
                    del mineral_mind_mem[sub_key]
            if _.isEmpty(mineral_mind_mem):
                print('[consistency] Deleting empty memory path Memory.rooms.{}.{}'
                      .format(name, rmem_key_mineral_mind_storage))
                del mem[rmem_key_mineral_mind_storage]
        if _.isEmpty(mem):
            print('[consistency] Deleting empty memory path Memory.rooms.{}'.format(name))
            del Memory.rooms[name]
    if Memory.reserving:
        for name in Object.keys(Memory.reserving):
            if Memory.reserving[name] not in Game.creeps:
                del Memory.reserving[name]
    if Memory.flags:
        for name in Object.keys(Memory.flags):
            mem = Memory.flags[name]
            if 'remote_miner_targeting' in mem:
                del mem['remote_miner_targeting']
            if _.isEmpty(mem):
                del Memory.flags[name]
    if Memory.spawns:
        for name in Object.keys(Memory.spawns):
            if _.isEmpty(Memory.spawns[name]):
                del Memory.spawns[name]
        if _.isEmpty(Memory.spawns):
            del Memory.spawns
    if '_owned_rooms_index' in Memory.meta:
        to_remove = []
        for room_name in Memory.meta['_owned_rooms_index']:
            room_data = hive.get_room(room_name)
            if not room_data or not room_data.my:
                to_remove.append(room_name)
        _.pull(Memory.meta['_owned_rooms_index'], to_remove)
    stored_data.cleanup_old_data(hive)
