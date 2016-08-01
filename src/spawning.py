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

    if filled < energy:
        print("Room doesn't have enough energy! {} < {}!".format(filled, energy))
        return

    descriptive_level = None

    if base is creep_base_big_harvester:
        if energy < 150:
            print("[{}][spawning] Too few extensions to build a dedicated miner!".format(room.room_name))
        parts = [MOVE, MOVE]
        num_sections = min(int(floor((energy - 100) / 100)), 5)
        for i in range(0, num_sections):
            parts.append(WORK)
        if num_sections < 5:
            descriptive_level = num_sections
    elif base is creep_base_worker:
        if energy >= 500:
            parts = []
            part_idea = [MOVE, MOVE, CARRY, WORK]
            num_sections = min(int(floor(energy / 250)), 4)
            for i in range(0, num_sections):
                for part in part_idea:
                    parts.append(part)
        elif energy >= 400:
            parts = [MOVE, MOVE, MOVE, CARRY, WORK, WORK]
            descriptive_level = "basic-2"
        elif energy >= 250:
            parts = [MOVE, MOVE, CARRY, WORK]
            descriptive_level = "basic-1"
        else:
            print("[{}][spawning] Too few extensions to build a worker!".format(room.room_name))
            return
    elif base is creep_base_full_miner:
        if energy < 550:
            print("[{}][spawning] Too few extensions to build a remote miner!".format(room.room_name))
            return
        parts = []
        num_move = min(int(floor((energy - 500) / 50)), 5)
        num_work = 5
        for i in range(0, num_move - 1):    parts.append(MOVE)
        for i in range(0, num_work):        parts.append(WORK)
        parts.append(MOVE)
        if num_move < 5:
            descriptive_level = num_move
    elif base is creep_base_hauler:
        parts = []
        num_sections = min(int(floor(energy / 100)), 5)
        for i in range(0, num_sections - 1):    parts.append(MOVE)
        for i in range(0, num_sections):        parts.append(CARRY)
        parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_small_hauler:
        parts = []
        num_sections = min(int(floor(energy / 100)), 3)
        for i in range(0, num_sections - 1):    parts.append(MOVE)
        for i in range(0, num_sections):        parts.append(CARRY)
        parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_reserving:
        if energy >= 1300:
            parts = [MOVE, CLAIM, CLAIM, MOVE]
            descriptive_level = 2
        elif energy >= 650:
            parts = [MOVE, CLAIM]
            descriptive_level = 1
        else:
            print("[{}][spawning] Too few extensions to build a remote creep!".format(room.room_name))
            return
    elif base is creep_base_defender:
        parts = []
        # MOVE, MOVE, ATTACK, TOUCH = one section = 190
        num_sections = min(int(floor(energy / 190)), 6)
        for i in range(0, num_sections):        parts.append(TOUGH)
        for i in range(0, num_sections - 1):    parts.append(MOVE)
        for i in range(0, num_sections):        parts.append(ATTACK)
        parts.append(MOVE)
        descriptive_level = num_sections
    else:
        print("[{}][spawning] Unknown creep base {}!".format(room.room_name, base))
        return

    name = random_four_digits()
    home = room.room_name
    if descriptive_level:
        print("[{}][spawning] Choose role {} level {}.".format(room.room_name, role, descriptive_level))
    else:
        print("[{}][spawning] Chose role {}.".format(room.room_name, role))
    result = spawn.createCreep(parts, name, {"role": role, "base": base, "home": home})
    if result != OK and not Game.creeps[result]:
        print("[{}][spawning] Invalid response from createCreep: {}".format(room.room_name, result))
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
