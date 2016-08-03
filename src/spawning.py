from math import floor

import context
from constants import *
from utils.screeps_constants import *

__pragma__('noalias', 'name')

bases_max_energy = {
    creep_base_worker: 250 * 5,
    creep_base_big_harvester: 100 + 100 * 5,
    creep_base_full_miner: 750,
    creep_base_small_hauler: 300,
    creep_base_hauler: 500,
    creep_base_reserving: 650 * 2,
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
        # TODO: at this point, figure out how long until the next replacement is needed!
        if not room.mem.spawning_already_reported_no_next_role:
            print("[{}][spawning] All roles are good, no need to spawn more!".format(room.room_name))
            room.mem.spawning_already_reported_no_next_role = True
        return
    elif room.mem.spawning_already_reported_no_next_role:
        room.mem.spawning_already_reported_no_next_role = False
    base = role_bases[role]

    filled = spawn.room.energyAvailable
    # If we have very few harvesters, try to spawn a new one! But don't make it too small, if we already have a big
    # harvester. 150 * work_mass will make a new harvester somewhat smaller than the existing one, but it shouldn't be
    # too bad. We *can* assume that all work_mass at this point is in harvesters, since consistency.reassign_roles()
    # will reassign everyone to harvester if there are fewer than 2 harvesters existing.
    if room.role_count(role_spawn_fill) < 3 and filled >= max(150 * room.work_mass, 250):
        energy = filled
    else:
        energy = min(spawn.room.energyCapacityAvailable, max(bases_max_energy[base], filled))

    if filled < energy:
        # print("Room doesn't have enough energy! {} < {}!".format(filled, energy))
        return

    descriptive_level = None

    if base is creep_base_big_harvester:
        if energy < 200:
            print("[{}][spawning] Too few extensions to build a dedicated miner!".format(room.room_name))
        parts = [MOVE, MOVE]
        num_sections = min(int(floor((energy - 100) / 100)), 5)
        for i in range(0, num_sections):
            parts.append(WORK)
        if num_sections < 5:
            descriptive_level = num_sections
        elif energy >= 650:  # we can fit an extra work
            parts.append(MOVE)
            descriptive_level = "full-8"
        else:
            descriptive_level = "full-7"
    elif base is creep_base_worker:
        if energy >= 500:
            parts = []
            part_idea = [MOVE, MOVE, CARRY, WORK]
            num_sections = min(int(floor(energy / 250)), 5)
            for i in range(0, num_sections):
                for part in part_idea:
                    parts.append(part)
            descriptive_level = "full-{}".format(num_sections)
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
        for i in range(0, num_move - 1):
            parts.append(MOVE)
        for i in range(0, num_work):
            parts.append(WORK)
        parts.append(MOVE)
        if num_move < 5:
            descriptive_level = num_move
    elif base is creep_base_hauler:
        parts = []
        num_sections = min(int(floor(energy / 100)), 5)
        for i in range(0, num_sections - 1):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(CARRY)
        parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_small_hauler:
        parts = []
        num_sections = min(int(floor(energy / 100)), 3)
        for i in range(0, num_sections - 1):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(CARRY)
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
        for i in range(0, num_sections):
            parts.append(TOUGH)
        for i in range(0, num_sections - 1):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(ATTACK)
        parts.append(MOVE)
        descriptive_level = num_sections
    else:
        print("[{}][spawning] Unknown creep base {}!".format(room.room_name, base))
        return

    name = random_four_digits()
    home = room.room_name

    replacing = room.get_next_replacement_name(role)

    if replacing:
        memory = {
            "role": role_temporary_replacing, "base": base, "home": home,
            "replacing": replacing, "replacing_role": role,
        }
    else:
        memory = {"role": role, "base": base, "home": home}

    if descriptive_level:
        if replacing:
            print("[{}][spawning] Choose role {} with body {} level {}, live-replacing {}.".format(
                room.room_name, role, base, descriptive_level, replacing))
        else:
            print("[{}][spawning] Choose role {} with body {} level {}.".format(
                room.room_name, role, base, descriptive_level))
    else:
        if replacing:
            print("[{}][spawning] Choose role {} with body {}, live-replacing {}.".format(
                room.room_name, role, base, replacing))
        else:
            print("[{}][spawning] Choose role {} with body {}.".format(room.room_name, role, base))
    result = spawn.createCreep(parts, name, memory)
    if result not in Game.creeps:
        print("[{}][spawning] Invalid response from createCreep: {}".format(room.room_name, result))
    else:
        if replacing:
            room.register_new_replacing_creep(role, replacing, result)
        else:
            room.register_to_role(Game.creeps[result])
        room.reset_planned_role()


def random_four_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)


def find_base_type(creep):
    part_counts = _.countBy(creep.body, lambda p: p.type)
    if part_counts[WORK] == part_counts[CARRY] and part_counts[WORK] == part_counts[MOVE] / 2:
        base = creep_base_worker
    elif not part_counts[CARRY] and part_counts[MOVE] < part_counts[WORK] <= 5:
        base = creep_base_big_harvester
    elif not part_counts[WORK] and part_counts[CARRY] == part_counts[MOVE] <= 3:
        base = creep_base_small_hauler
    elif not part_counts[CARRY] and part_counts[WORK] == part_counts[MOVE] <= 5:
        base = creep_base_full_miner
    elif not part_counts[WORK] and part_counts[CARRY] == part_counts[MOVE]:
        base = creep_base_hauler
    elif not part_counts[WORK] and not part_counts[CARRY] and part_counts[CLAIM] == part_counts[MOVE] <= 2:
        base = creep_base_reserving
    elif part_counts[ATTACK] == part_counts[TOUGH] == part_counts[MOVE]:
        base = creep_base_defender
    else:
        print("[{}][{}] Creep has unknown body! {}".format(
            context.room().room_name, creep.name, JSON.stringify(part_counts)))
        return None
    print("[{}][{}] Re-assigned unknown body creep as {}.".format(
        context.room().room_name, creep.name, base))
    return base
