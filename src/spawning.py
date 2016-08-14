from math import floor

import context
from constants import *
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

bases_max_energy = {
    creep_base_local_miner: 100 + 100 * 5,
    creep_base_full_miner: 150 * 5,
    creep_base_small_hauler: 100 * 3,
    creep_base_reserving: 650 * 2,
    creep_base_defender: 180 * 6,
}

scalable_sections = {
    creep_base_worker: [MOVE, MOVE, CARRY, WORK],
    creep_base_hauler: [MOVE, CARRY],
    creep_base_reserving: [MOVE, CLAIM],
    creep_base_defender: [CARRY, MOVE, ATTACK],
    creep_base_full_miner: [WORK, MOVE],
}


def run(room, spawn):
    """
    Activates the spawner, spawning what's needed, as determined by the RoomManager.

    Manages deciding what parts belong on what creep base as well.
    :type room: control.hivemind.RoomMind
    :type spawn: StructureSpawn
    :type
    """
    if spawn.spawning:
        return
    role = room.get_next_role()
    if not role:
        # TODO: at this point, figure out how long until the next replacement is needed!
        # if not room.mem.spawning_already_reported_no_next_role:
        #     print("[{}][spawning] All roles are good, no need to spawn more!".format(room.room_name))
        #     room.mem.spawning_already_reported_no_next_role = True
        return
    base = role_bases[role]

    filled = spawn.room.energyAvailable
    # If we have very few harvesters, try to spawn a new one! But don't make it too small, if we already have a big
    # harvester. 150 * work_mass will make a new harvester somewhat smaller than the existing one, but it shouldn't be
    # too bad. We *can* assume that all work_mass at this point is in harvesters, since consistency.reassign_roles()
    # will reassign everyone to harvester if there are fewer than 2 harvesters existing.
    if room.role_count(role_spawn_fill) < 3 and filled >= max(150 * room.work_mass, 250):
        energy = filled
    else:
        if base in bases_max_energy:
            # Minimum of actual capacity, and (maximum of needed and how much actual energy we have)
            energy = min(spawn.room.energyCapacityAvailable, max(bases_max_energy[base], filled))
        elif base in scalable_sections:
            # If we are spawning a scalable creep, wait until we're filled the maximum we are going to be filled.
            energy = spawn.room.energyCapacityAvailable - (spawn.room.energyCapacityAvailable
                                                           % energy_per_section(base))
        else:
            print("[{}][spawning] Base {} has neither maximum energy nor scalable section energy!".format(
                room.room_name, base))
            energy = spawn.room.energyCapacityAvailable
    if filled < energy:
        # print("[{}][spawning] Room doesn't have enough energy! {} < {}!".format(room.room_name, filled, energy))
        return

    descriptive_level = None

    if base is creep_base_local_miner:
        if energy < 200:
            print("[{}][spawning] Too few extensions to build a dedicated miner!".format(room.room_name))
            return
        if energy < 600 and energy % 100 != 0:
            work_energy = 50
            parts = [MOVE]
        else:
            work_energy = 100
            parts = [MOVE, MOVE]

        num_sections = min(int(floor((energy - work_energy) / 100)), 5)
        for i in range(0, num_sections):
            parts.append(WORK)
        if num_sections < 5:
            if work_energy == 50:
                descriptive_level = "slow-med-{}".format(num_sections)
            else:
                descriptive_level = "med-{}".format(num_sections)
        elif energy >= 650:  # we can fit an extra work
            parts.append(MOVE)
            descriptive_level = "full-8"
        elif work_energy == 50:
            descriptive_level = "slow-6"
        else:
            descriptive_level = "full-7"
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
    elif base is creep_base_hauler:
        parts = []
        num_sections = min(int(floor(energy / 100)), room.get_max_sections_for_role(role))
        for i in range(0, num_sections - 1):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(CARRY)
        parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_worker:
        if energy >= 500:
            parts = []
            max_sections = int(floor(energy / 250))
            num_sections = min(max_sections, room.get_max_sections_for_role(role))
            for i in range(0, num_sections * 2 - 1):
                parts.append(MOVE)
            for i in range(0, num_sections):
                parts.append(CARRY)
                parts.append(WORK)
            parts.append(MOVE)
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
    elif base is creep_base_defender:
        parts = []
        # # MOVE, MOVE, ATTACK, TOUCH = one section = 190
        # MOVE, ATTACK, CARRY = one section = 180
        num_sections = min(int(floor(energy / 180)), room.get_max_sections_for_role(role))
        for i in range(0, num_sections):
            parts.append(CARRY)
        for i in range(0, num_sections - 1):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(ATTACK)
        parts.append(MOVE)
        descriptive_level = num_sections
    else:
        print("[{}][spawning] Unknown creep base {} (for role {})!".format(room.room_name, base, role))
        room.reset_planned_role()
        return

    carry = 0
    work = 0
    for part in parts:
        if part == CARRY:
            carry += 1
        if part == WORK:
            work += 1

    name = random_four_digits()
    home = room.room_name

    replacing = room.get_next_replacement_name(role)

    if replacing:
        memory = {
            "role": role_temporary_replacing, "base": base, "home": home,
            "replacing": replacing, "replacing_role": role, "carry": carry, "work": work,
        }
    else:
        memory = {"role": role, "base": base, "home": home, "carry": carry, "work": work}

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
        base = creep_base_local_miner
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


def energy_per_section(base):
    # TODO: use this to create scalable sections for remote mining ops
    if base in scalable_sections:
        cost = 0
        for part in scalable_sections[base]:
            cost += BODYPART_COST[part]
        return cost
    else:
        return None


def max_sections_of(room, base):
    if room.room:
        room = room.room
    return floor(room.energyCapacityAvailable / energy_per_section(base))


def work_count(creep):
    if creep.creep:  # support RoleBase
        creep = creep.creep
    if creep.memory.work:
        return creep.memory.work
    work = 0
    for part in creep.body:
        if part.type == WORK:
            work += 1
            if part.boost:
                boost = BOOSTS[WORK][part.boost]
                # rough estimation, we probably don't care about boosts for different
                # functions yet, since we don't even have boosted creeps spawning!
                work += boost[Object.keys(boost)[0]]
    creep.memory.work = work
    return work


def carry_count(creep):
    if creep.creep:  # support RoleBase
        creep = creep.creep
    if creep.memory.carry:
        return creep.memory.carry
    carry = 0
    for part in creep.body:
        if part.type == CARRY:
            carry += 1
            if part.boost:
                boost = BOOSTS[WORK][part.boost]
                # rough estimation, we probably don't care about boosts for different
                # functions yet, since we don't even have boosted creeps spawning!
                if boost.capacity:
                    carry += boost.capacity
    creep.memory.carry = carry
    return carry


run = profiling.profiled(run, "spawning.run")
