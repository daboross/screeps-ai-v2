from math import floor

import context
from constants import *
from screeps_constants import *

__pragma__('noalias', 'name')

bases_max_energy = {
    creep_base_worker: 250,
    creep_base_big_harvester: 600,
    creep_base_full_miner: 750,
    creep_base_small_hauler: 300,
    creep_base_hauler: 500,
    creep_base_reserving: 1300,
    creep_base_defender: 190 * 5,
}


def run(room, spawn):
    """
    Activates the spawner, spawning what's needed, as determined by the RoomManager.

    Manages deciding what parts belong on what creep base as well.
    :type room: hivemind.RoomMind
    :type spawn: StructureSpawn
    :type
    """
    if spawn.spawning:
        return
    role = room.get_next_role()
    if not role:
        print("Room didn't have next role!")
        return
    base = role_bases[role]
    filled = spawn.room.energyAvailable
    # If we have very few harvesters, try to spawn a new one! But don't make it too small, if we already have a big
    # harvester. 150 * work_mass will make a new harvester somewhat smaller than the existing one, but it shouldn't be
    # too bad. We *can* assume that all work_mass at this point is in harvesters, since creep_utils.reassign_roles()
    # will reassign everyone to harvester if there are fewer than 2 harvesters existing.
    if room.role_count(role_spawn_fill) < 3 and filled >= max(150 * room.work_mass, 250):
        energy = filled
    else:
        energy = min(spawn.room.energyCapacityAvailable, max(bases_max_energy[base], filled))

    if spawn.room.energyAvailable >= energy:
        if base is creep_base_big_harvester:
            parts = [MOVE, MOVE]
            num_sections = min(int(floor((energy - 100) / 100)), 5)
            for i in range(0, num_sections):
                parts.append(WORK)
        elif base is creep_base_worker:
            if energy >= 500:
                parts = []
                part_idea = [MOVE, MOVE, CARRY, WORK]
                num_sections = int(floor(energy / 250))
                for i in range(0, num_sections):
                    for part in part_idea:
                        parts.append(part)
            elif energy >= 400:
                parts = [MOVE, MOVE, MOVE, CARRY, WORK, WORK]
            elif energy >= 250:
                parts = [MOVE, MOVE, CARRY, WORK]
            elif energy >= 200:
                parts = [MOVE, CARRY, WORK]
            else:
                return
        elif base is creep_base_full_miner:
            if energy < 550:
                print("[spawning] Not enough energy to create a remote miner!"
                      " This WILL block spawning until it is fixed!")
                return
            parts = []
            num_move = min(int(floor((energy - 500) / 50)), 5)
            num_work = 5
            for i in range(0, num_move - 1):    parts.append(MOVE)
            for i in range(0, num_work):        parts.append(WORK)
            parts.append(MOVE)
        elif base is creep_base_hauler:
            parts = []
            num_sections = min(int(floor(energy / 100)), 5)
            for i in range(0, num_sections - 1):    parts.append(MOVE)
            for i in range(0, num_sections):        parts.append(CARRY)
            parts.append(MOVE)
        elif base is creep_base_small_hauler:
            parts = []
            num_sections = min(int(floor(energy / 100)), 3)
            for i in range(0, num_sections - 1):    parts.append(MOVE)
            for i in range(0, num_sections):        parts.append(CARRY)
            parts.append(MOVE)
        elif base is creep_base_reserving:
            if energy >= 1300:
                parts = [MOVE, CLAIM, CLAIM, MOVE]
            elif energy >= 650:
                parts = [MOVE, CLAIM]
            else:
                print("[spawning] Not enough energy to create remote reserve creep!"
                      " This WILL block spawning until it is fixed!")
                return
        elif base is creep_base_defender:
            parts = []
            # MOVE, MOVE, ATTACK, TOUCH = one section = 190
            num_sections = min(int(floor(energy / 190)), 5)
            for i in range(0, num_sections):        parts.append(TOUGH)
            for i in range(0, num_sections - 1):    parts.append(MOVE)
            for i in range(0, num_sections):        parts.append(ATTACK)
            parts.append(MOVE)
        else:
            print("[spawning] Unknown creep base {}!".format(base))
            return
        spawn_with_array(room, spawn, role, base, parts)


def spawn_with_array(room, spawn, role, base, parts):
    name = random_four_digits()
    home = room.room_name
    print("[spawning] Choosing role {} with parts {}".format(role, parts))
    result = spawn.createCreep(parts, name, {"role": role, "base": base, "home": home})
    if result != OK and not Game.creeps[result]:
        print("[spawning] Invalid response from createCreep: {}".format(result))
    else:
        room.add_to_role(role)
        room.reset_planned_role()


def random_four_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)


def find_base_type(creep):
    part_counts = _.countBy(creep.body, lambda p: p.type)
    if part_counts[WORK] == part_counts[CARRY] and part_counts[WORK] == part_counts[MOVE] / 2:
        base = creep_base_worker
    elif part_counts[CARRY] == 0 and part_counts[MOVE] < part_counts[WORK] <= 5:
        base = creep_base_big_harvester
    elif part_counts[CARRY] == 0 and part_counts[WORK] == part_counts[MOVE] <= 5:
        base = creep_base_full_miner
    elif part_counts[WORK] == 0 and part_counts[CARRY] == part_counts[MOVE] <= 3:
        base = creep_base_small_hauler
    elif part_counts[WORK] == 0 and part_counts[CARRY] == part_counts[MOVE]:
        base = creep_base_hauler
    elif part_counts[WORK] == part_counts[CARRY] == 0 and part_counts[CLAIM] == part_counts[MOVE] <= 2:
        base = creep_base_reserving
    elif part_counts[ATTACK] == part_counts[TOUGH] == part_counts[MOVE]:
        base = creep_base_defender
    else:
        print("[room: {}][{}] Creep has unknown body! {}".format(
            context.room().room_name, creep.name, JSON.stringify(part_counts)))
        return None
    print("[room: {}][{}] Re-assigned unknown body creep as {}.".format(
        context.room().room_name, creep.name, base))
    return base
