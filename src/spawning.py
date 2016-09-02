from math import floor

import context
from constants import *
from tools import profiling
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

initial_section = {
    creep_base_work_full_move_hauler: [WORK, MOVE],
    creep_base_work_half_move_hauler: [CARRY, WORK, MOVE],
    creep_base_goader: [ATTACK, MOVE, TOUGH],
    creep_base_full_move_goader: [ATTACK, MOVE],
    creep_base_full_upgrader: [MOVE, CARRY, CARRY],
    creep_base_full_miner: [WORK, WORK, WORK, WORK, WORK],
}

# TODO: limit goader and healer in RoomMind
scalable_sections = {
    creep_base_worker: [MOVE, MOVE, MOVE, MOVE, CARRY, CARRY, CARRY, WORK],
    creep_base_hauler: [MOVE, CARRY],
    creep_base_work_full_move_hauler: [MOVE, CARRY],
    creep_base_work_half_move_hauler: [MOVE, CARRY, CARRY],
    creep_base_reserving: [MOVE, CLAIM],
    creep_base_defender: [CARRY, MOVE, ATTACK],
    creep_base_full_miner: [MOVE],
    creep_base_goader: [MOVE, TOUGH, TOUGH],
    creep_base_full_move_goader: [CARRY],
    creep_base_half_move_healer: [MOVE, HEAL, HEAL],
    creep_base_full_move_healer: [MOVE, HEAL],
    creep_base_dismantler: [WORK, MOVE],
    creep_base_full_upgrader: [MOVE, WORK, WORK],
    creep_base_scout: [MOVE],
}

low_energy_sections = {
    creep_base_worker: [MOVE, MOVE, CARRY, WORK],
}
known_no_energy_limit = [creep_base_mammoth_miner]


def emergency_conditions(room):
    return room.carry_mass_of(role_spawn_fill) < room.get_target_spawn_fill_mass() / 2 \
           and (room.room.energyAvailable >= max(100 * room.work_mass, 250)
                or (room.carry_mass_of(role_spawn_fill)
                    + room.carry_mass_of(role_spawn_fill_backup)
                    + room.carry_mass_of(role_tower_fill)) <= 0)


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
    role_obj = room.get_next_role()
    # This is what is represented by "role_obj"
    # return {
    #     "role": role_needed,
    #     "base": self.get_variable_base(role_needed),
    #     "replacing": self.get_next_replacement_name(role_needed),
    #     "num_sections": self.get_max_sections_for_role(role_needed),
    # }
    if not role_obj:
        # TODO: at this point, figure out how long until the next replacement is needed!
        # if not room.mem.spawning_already_reported_no_next_role:
        #     print("[{}][spawning] All roles are good, no need to spawn more!".format(room.room_name))
        #     room.mem.spawning_already_reported_no_next_role = True
        return
    role = role_obj.role
    base = role_obj.base
    num_sections = role_obj.num_sections
    replacing = role_obj.replacing

    ubos_cache = volatile_cache.mem("energy_used_by_other_spawns")
    if ubos_cache.has(room.room_name):
        filled = spawn.room.energyAvailable - ubos_cache.get(room.room_name)
    else:
        filled = spawn.room.energyAvailable
        # If we have very few harvesters, try to spawn a new one! But don't make it too small, if we already have a big
    # harvester. 150 * work_mass will make a new harvester somewhat smaller than the existing one, but it shouldn't be
    # too bad. We *can* assume that all work_mass at this point is in harvesters, since consistency.reassign_roles()
    # will reassign everyone to harvester if there are fewer than 2 harvesters existing.
    if emergency_conditions(room):
        print("[{}] WARNING: Bootstrapping room!".format(room.room_name))
        energy = filled
    elif num_sections is not None:
        cost = initial_section_cost(base) + num_sections * energy_per_section(base)
        if cost > spawn.room.energyCapacityAvailable:
            # This is just a double check, for as we move into the new role_obj-based system
            new_size = max_sections_of(room, base)
            print("[{}][spawning] Adjusted creep size from {} to {} to match available energy."
                  .format(room.room_name, num_sections, new_size))
            # Since the literal memory object is returned, this mutation will stick for until this creep has been spawned,
            # or the target creep has been refreshed
            num_sections = role_obj.num_sections = new_size
            cost = initial_section_cost(base) + new_size * energy_per_section(base)
        energy = cost
    else:
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
            move_energy = 50
            parts = [MOVE]
        else:
            move_energy = 100
            parts = [MOVE, MOVE]

        num_sections = min(int(floor((energy - move_energy) / 100)), 5)
        for i in range(0, num_sections):
            parts.append(WORK)
        if num_sections < 5:
            if move_energy == 50:
                descriptive_level = "slow-med-{}".format(num_sections)
            else:
                descriptive_level = "med-{}".format(num_sections)
        elif energy >= 650:  # we can fit an extra move
            parts.append(MOVE)
            descriptive_level = "full-8"
        elif move_energy == 50:
            descriptive_level = "slow-6"
        else:
            descriptive_level = "full-7"
    elif base is creep_base_full_miner:
        if energy < 550:
            print("[{}][spawning] Too few extensions to build a remote miner!".format(room.room_name))
            return
        parts = []
        num_move = num_sections
        num_work = 5
        for i in range(0, num_move - 1):
            parts.append(MOVE)
        for i in range(0, num_work):
            parts.append(WORK)
        parts.append(MOVE)
        if num_move < 5:
            descriptive_level = num_move
    elif base is creep_base_reserving:
        parts = []
        for i in range(0, num_sections):
            parts.append(CLAIM)
        for i in range(0, num_sections):
            parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_hauler:
        parts = []
        for i in range(0, num_sections):
            parts.append(CARRY)
        for i in range(0, num_sections):
            parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_work_full_move_hauler:
        parts = []
        for part in initial_section[base]:
            parts.append(part)
        for i in range(0, num_sections):
            parts.append(CARRY)
        for i in range(0, num_sections):
            parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_work_half_move_hauler:
        parts = []
        for part in initial_section[base]:
            parts.append(part)
        for i in range(0, num_sections * 2):
            parts.append(CARRY)
        for i in range(0, num_sections):
            parts.append(MOVE)
        descriptive_level = num_sections * 2 + 1
    elif base is creep_base_worker:
        if energy >= 450:
            parts = []
            for i in range(0, num_sections):
                parts.append(CARRY)
                parts.append(CARRY)
                parts.append(WORK)
                parts.append(CARRY)
            for i in range(0, num_sections * 4):
                parts.append(MOVE)
            descriptive_level = "carry:{}-work:{}".format(num_sections * 3, num_sections)
        elif energy >= 400:
            parts = [MOVE, MOVE, MOVE, CARRY, CARRY, WORK]
            descriptive_level = "carry:2-work:1"
        elif energy >= 250:
            parts = [MOVE, MOVE, CARRY, WORK]
            descriptive_level = "carry:1-work:1"
        else:
            print("[{}][spawning] Too few extensions to build a worker!".format(room.room_name))
            return
    elif base is creep_base_defender:
        parts = []
        # # MOVE, MOVE, ATTACK, TOUCH = one section = 190
        # MOVE, ATTACK, CARRY = one section = 180
        for i in range(0, num_sections):
            parts.append(CARRY)
        for i in range(0, num_sections):
            parts.append(ATTACK)
            parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_mammoth_miner:
        parts = [MOVE]
        energy_counter = 50
        part_counter = 1
        move_counter = 0
        # TODO: this would be a lot nicer if it had calculations, but this is honestly a lot easier to write it like
        # this for now.
        for i in range(0, 2):
            if part_counter >= 50:
                break
            if energy_counter >= energy - 50:
                break
            parts.append(CARRY)
            energy_counter += 50
            part_counter += 1
            move_counter += 0.25
            for j in range(0, 25):
                if move_counter >= 1:
                    if part_counter >= 50:
                        break
                    if energy_counter >= energy - 50:
                        break
                    parts.append(MOVE)
                    energy_counter += 50
                    part_counter += 1
                    move_counter -= 1
                if part_counter >= 50:
                    break
                if energy_counter >= energy - 100:
                    break
                parts.append(WORK)
                energy_counter += 100
                part_counter += 1
                move_counter += 0.25
    elif base is creep_base_goader:
        parts = []
        for i in range(0, num_sections * 2 + 1):  # extra tough in initial section
            parts.append(TOUGH)
        parts.append(ATTACK)
        for i in range(0, num_sections + 1):  # extra move in initial section
            parts.append(MOVE)
    elif base is creep_base_full_move_goader:
        parts = []
        for i in range(0, num_sections * 2 + 1):  # extra tough in initial section
            parts.append(CARRY)
        parts.append(ATTACK)
        parts.append(MOVE)
    elif base is creep_base_half_move_healer:
        parts = []
        for i in range(0, num_sections):
            parts.append(HEAL)
        for i in range(0, num_sections):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(HEAL)
    elif base is creep_base_full_move_healer:
        parts = []
        for i in range(0, num_sections):
            parts.append(HEAL)
            parts.append(MOVE)
    elif base is creep_base_dismantler:
        parts = []
        for i in range(0, num_sections):
            parts.append(WORK)
        for i in range(0, num_sections):
            parts.append(MOVE)
    elif base is creep_base_full_upgrader:
        parts = []
        for part in initial_section[base]:
            parts.append(part)
        for i in range(0, num_sections * 2):
            parts.append(WORK)
        for i in range(0, num_sections):
            parts.append(MOVE)
    elif base is creep_base_scout:
        parts = [MOVE]
    else:
        print("[{}][spawning] Unknown creep base {}! Role object: {}".format(room.room_name, base,
                                                                             JSON.stringify(role_obj)))
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

    if replacing:
        memory = {
            "role": role_temporary_replacing, "base": base, "home": home,
            "replacing": replacing, "replacing_role": role, "carry": carry, "work": work,
        }
    else:
        memory = {"role": role, "base": base, "home": home, "carry": carry, "work": work}

    if role_obj.memory:
        # Add whatever memory seems to be necessary
        _.extend(memory, role_obj.memory)

    if descriptive_level:
        if replacing:
            print("[{}][spawning] Spawning {}, a {} with body {} level {}, live-replacing {}.".format(
                room.room_name, name, role, base, descriptive_level, replacing))
        else:
            print("[{}][spawning] Spawning {}, a {} with body {} level {}.".format(
                room.room_name, name, role, base, descriptive_level))
    else:
        if replacing:
            print("[{}][spawning] Spawning {}, a {} with body {}, live-replacing {}.".format(
                room.room_name, name, role, base, replacing))
        else:
            print("[{}][spawning] Spawning {}, a {} with body {}.".format(room.room_name, name, role, base))
    result = spawn.createCreep(parts, name, memory)
    if result not in Game.creeps:
        print("[{}][spawning] Invalid response from createCreep: {}".format(room.room_name, result))
        if result == ERR_NOT_ENOUGH_RESOURCES:
            print("[{}][spawning] Couldn't create body {} with energy {}!".format(room.room_name, parts, energy))
    else:
        ubos_cache.set(room.room_name, postspawn_calculate_cost_of(parts))
        room.reset_planned_role()
        if role_obj.targets:
            for target_type, target_id in role_obj.targets:
                room.hive_mind.target_mind._register_new_targeter(target_type, name, target_id)
        if role_obj.run_after:
            role_obj.run_after(name)
        if replacing:
            room.register_new_replacing_creep(role, replacing, result)
        else:
            room.register_to_role(Game.creeps[result])


def random_four_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)


def find_base_type(creep):
    part_counts = _.countBy(creep.body, lambda p: p.type)
    total = _.sum(part_counts)
    if part_counts[WORK] == part_counts[CARRY] == part_counts[MOVE] / 2 == total / 4:
        base = creep_base_worker
    elif not part_counts[CARRY] and part_counts[MOVE] < part_counts[WORK] <= 5:
        base = creep_base_local_miner
    elif part_counts[WORK] == part_counts[MOVE] == total / 2 <= 5:
        base = creep_base_full_miner
    elif part_counts[CARRY] == part_counts[MOVE] == total / 2:
        base = creep_base_hauler
    elif part_counts[WORK] == 1 and part_counts[MOVE] == part_counts[CARRY] + 1 == total / 2:
        base = creep_base_work_full_move_hauler
    elif part_counts[WORK] == 1 and part_counts[MOVE] == (part_counts[CARRY] + 1) / 2 == total / 3:
        base = creep_base_work_half_move_hauler
    elif part_counts[CLAIM] == part_counts[MOVE] == total / 2:
        base = creep_base_reserving
    elif part_counts[ATTACK] == part_counts[TOUGH] == part_counts[MOVE] == total / 3:
        base = creep_base_defender
    elif part_counts[MOVE] == total / 3 and part_counts[CARRY] == 2 and \
                                    part_counts[WORK] + part_counts[MOVE] + part_counts[CARRY] == total:
        base = creep_base_full_upgrader
    elif part_counts[MOVE] == total == 1:
        base = creep_base_scout
    else:
        print("[{}][{}] Creep has unknown body! {}".format(
            context.room().room_name, creep.name, JSON.stringify(part_counts)))
        return None
    print("[{}][{}] Re-assigned unknown body creep as {}.".format(
        context.room().room_name, creep.name, base))
    return base


def postspawn_calculate_cost_of(parts):
    cost = 0
    for part in parts:
        cost += BODYPART_COST[part]
    return cost


def energy_per_section(base):
    # TODO: use this to create scalable sections for remote mining ops
    if base in scalable_sections:
        cost = 0
        for part in scalable_sections[base]:
            cost += BODYPART_COST[part]
        return cost
    else:
        return None


def lower_energy_per_section(base):
    if base in low_energy_sections:
        cost = 0
        for part in scalable_sections[base]:
            cost += BODYPART_COST[part]
        return cost
    else:
        return energy_per_section(base)


def initial_section_cost(base):
    cost = 0
    if base in initial_section:
        for part in initial_section[base]:
            cost += BODYPART_COST[part]
    return cost


def max_sections_of(room, base):
    if emergency_conditions(room):
        energy = room.room.energyAvailable
    else:
        energy = room.room.energyCapacityAvailable
    max_by_cost = floor((energy - initial_section_cost(base)) / energy_per_section(base))
    if max_by_cost == 0:
        max_by_cost = floor((energy - initial_section_cost(base)) / lower_energy_per_section(base))
    initial_base_parts = len(initial_section[base]) if base in initial_section else 0
    max_by_parts = floor((50 - initial_base_parts) / len(scalable_sections[base]))
    return min(max_by_cost, max_by_parts)


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
