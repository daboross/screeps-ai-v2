import context
from constants import *
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def reassign_roles():
    for room in context.hive().my_rooms:
        reassign_room_roles(room)


def reassign_room_roles(room):
    if room.role_count(role_spawn_fill) < 4 and room.role_count(role_dedi_miner) < room.get_target_dedi_miner_count():
        num = 0
        for creep in room.creeps:
            memory = creep.memory
            if memory.base == creep_base_worker:
                memory.role = role_spawn_fill
            num += 1
            if num > 5:
                break
        room.recalculate_roles_alive()


def clear_memory(target_mind):
    """
    :type target_mind: hivemind.TargetMind
    """
    smallest_ticks_to_live = 500
    for name in Object.keys(Memory.creeps):
        creep = Game.creeps[name]
        if not creep:
            role = Memory.creeps[name].role
            if role:
                print("[{}] {} died".format(name, role))

            if role == role_dedi_miner:
                source_id = target_mind._get_existing_target_id(target_big_source, name)
                if source_id:
                    del Memory.dedicated_miners_stationed[source_id]
                else:
                    print("[{}] WARNING! clear_memory couldn't find placed source for big harvester!".format(name))
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
        elif creep.ticksToLive < smallest_ticks_to_live:
            smallest_ticks_to_live = creep.ticksToLive
    Memory.meta.clear_next = Game.time + smallest_ticks_to_live + 1  # some leeway
