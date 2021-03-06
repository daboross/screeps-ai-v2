import math
from math import floor
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union, cast

from cache import volatile_cache
from constants import *
from jstools.screeps import *
from utilities import naming

if TYPE_CHECKING:
    from rooms.room_mind import RoomMind
    from creeps.base import RoleBase

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

initial_section = {
    creep_base_work_full_move_hauler: [WORK, WORK, MOVE, MOVE],
    creep_base_work_half_move_hauler: [WORK, WORK, MOVE],  # for swamp roads.
    # TODO: separate "repair station" creeps triggered by lookFor during moveByPath
    creep_base_goader: [ATTACK, MOVE, TOUGH],
    creep_base_full_move_goader: [ATTACK, MOVE],
    creep_base_full_upgrader: [MOVE, CARRY, CARRY],
    creep_base_1500miner: [WORK, WORK, WORK],
    creep_base_3000miner: [WORK, WORK, WORK, WORK, WORK],
    creep_base_4000miner: [WORK, WORK, WORK, WORK, WORK, WORK, WORK],
    creep_base_carry3000miner: [CARRY, WORK, WORK, WORK, WORK, WORK],
    creep_base_mammoth_miner: [MOVE, CARRY, WORK, WORK, WORK],
    creep_base_ranged_offense: [MOVE, HEAL],
    creep_base_3h: [MOVE, MOVE, MOVE, HEAL, HEAL, HEAL],
}

# TODO: limit goader and healer in RoomMind
scalable_sections = {
    creep_base_worker: [MOVE, MOVE, MOVE, MOVE, CARRY, CARRY, CARRY, WORK],
    creep_base_hauler: [MOVE, CARRY],
    creep_base_work_full_move_hauler: [MOVE, CARRY],
    creep_base_work_half_move_hauler: [MOVE, CARRY, CARRY],
    creep_base_reserving: [MOVE, CLAIM],
    creep_base_defender: [TOUGH, MOVE, MOVE, MOVE, ATTACK, ATTACK],
    creep_base_rampart_defense: [MOVE, ATTACK, ATTACK],
    creep_base_ranged_offense: [MOVE, RANGED_ATTACK],
    creep_base_3h: [MOVE, RANGED_ATTACK],
    creep_base_1500miner: [MOVE],
    creep_base_3000miner: [MOVE],
    creep_base_4000miner: [MOVE],
    creep_base_carry3000miner: [MOVE],
    creep_base_goader: [MOVE, TOUGH, TOUGH],
    creep_base_full_move_goader: [MOVE, TOUGH, CARRY, CARRY],
    creep_base_half_move_healer: [MOVE, HEAL, HEAL],
    creep_base_full_move_healer: [MOVE, HEAL],
    creep_base_squad_healer: [MOVE, HEAL],
    creep_base_squad_ranged: [MOVE, RANGED_ATTACK],
    creep_base_squad_dismantle: [MOVE, WORK],
    creep_base_dismantler: [WORK, WORK, MOVE],
    creep_base_full_move_dismantler: [WORK, MOVE],
    creep_base_full_upgrader: [MOVE, WORK, WORK],
    creep_base_scout: [MOVE],
    creep_base_mammoth_miner: [MOVE, WORK, WORK, WORK, WORK],
    creep_base_full_move_attack: [MOVE, ATTACK],
    creep_base_power_attack: [MOVE, MOVE, TOUGH, ATTACK, ATTACK, ATTACK],
    creep_base_half_move_hauler: [MOVE, CARRY, CARRY],
    creep_base_claiming: [MOVE, MOVE, MOVE, MOVE, MOVE, MOVE, CLAIM, MOVE],
    creep_base_claim_attack: [MOVE, MOVE, MOVE, MOVE, MOVE, CLAIM, CLAIM, CLAIM, CLAIM, CLAIM],
}

half_sections = {
    creep_base_worker: [WORK, MOVE],
    creep_base_work_half_move_hauler: [MOVE, CARRY],
    creep_base_half_move_hauler: [MOVE, CARRY],
    creep_base_full_upgrader: [MOVE, WORK],
    creep_base_defender: [ATTACK, MOVE],
    creep_base_rampart_defense: [ATTACK, MOVE],
    creep_base_goader: [TOUGH, MOVE],
    creep_base_half_move_healer: [MOVE, HEAL],
    creep_base_power_attack: [MOVE, ATTACK],
    creep_base_dismantler: [MOVE, WORK],
    creep_base_claim_attack: [MOVE, MOVE, TOUGH, HEAL],
    creep_base_3h: [MOVE, MOVE, TOUGH, TOUGH],
}

low_energy_sections = {
    creep_base_worker: [MOVE, MOVE, CARRY, WORK],
    creep_base_full_upgrader: [MOVE, CARRY, WORK],
    creep_base_claiming: [MOVE, CLAIM, MOVE],
}

low_energy_dynamic = [creep_base_1500miner, creep_base_3000miner, creep_base_4000miner]


def would_be_emergency(room):
    # type: (RoomMind) -> bool
    """
    :type room: rooms.room_mind.RoomMind
    """
    spawn_mass = (room.carry_mass_of(role_spawn_fill)
                  + room.carry_mass_of(role_spawn_fill_backup)
                  + room.carry_mass_of(role_tower_fill))
    return spawn_mass <= 0 or (spawn_mass < room.get_target_total_spawn_fill_mass() / 2)


def emergency_conditions(room):
    # type: (RoomMind) -> bool
    """
    :type room: rooms.room_mind.RoomMind
    """
    if volatile_cache.mem(room.name).has("emergency_conditions"):
        return volatile_cache.mem(room.name).get("emergency_conditions")
    # The functions we run to determine target mass will in turn call emergency_conditions itself
    # This prevents an infinite loop (we set the actual value at the end of the function)
    volatile_cache.mem(room.name).set("emergency_conditions", False)
    if room.room.energyAvailable >= 300:
        spawn_mass = room.carry_mass_of(role_spawn_fill) \
                     + room.carry_mass_of(role_spawn_fill_backup) \
                     + room.carry_mass_of(role_tower_fill)
        emergency = spawn_mass <= 0 or (
            spawn_mass < room.get_target_total_spawn_fill_mass() / 2
            and room.room.energyAvailable >= 100 * spawn_mass
        )
    else:
        emergency = False
    volatile_cache.mem(room.name).delete("running_emergency_conditions")
    volatile_cache.mem(room.name).set("emergency_conditions", emergency)
    return emergency


def run(room, spawn):
    # type: (RoomMind, StructureSpawn) -> None
    """
    Activates the spawner, spawning what's needed, as determined by the RoomMind.

    Manages deciding what parts belong on what creep base as well.
    :type room: rooms.room_mind.RoomMind
    :type spawn: StructureSpawn
    :type
    """
    if spawn.spawning or room.squads.any_high_priority_renew():
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
        #     print("[{}][spawning] All roles are good, no need to spawn more!".format(room.name))
        #     room.mem.spawning_already_reported_no_next_role = True
        return
    role = role_obj[roleobj_key_role]
    base = role_obj[roleobj_key_base]
    num_sections = role_obj[roleobj_key_num_sections] or 0
    replacing = role_obj[roleobj_key_replacing]

    ubos_cache = volatile_cache.mem("energy_used_by_other_spawns")
    if ubos_cache.has(room.name):
        filled = spawn.room.energyAvailable - ubos_cache.get(room.name)
    else:
        filled = spawn.room.energyAvailable
    # If we have very few harvesters, try to spawn a new one! But don't make it too small, if we already have a big
    # harvester. 150 * work_mass will make a new harvester somewhat smaller than the existing one, but it shouldn't be
    # too bad. We *can* assume that all work_mass at this point is in harvesters, since consistency.reassign_roles()
    # will reassign everyone to harvester if there are fewer than 2 harvesters existing.
    if emergency_conditions(room):
        print("[{}] WARNING: Bootstrapping room!".format(room.name))
        energy = filled
    else:
        energy = spawn.room.energyCapacityAvailable

    half_section = 1 if num_sections % 1 else 0
    num_sections -= num_sections % 1  # This is so as to only create expected behavior with half-sections

    if num_sections is not None and base in scalable_sections:
        if (num_sections <= 0 or not num_sections) and not (num_sections is 0 and half_section):  # Catch NaN here too?
            print("[{}][spawning] Trying to spawn a 0-section {} creep! Changing this to a 1-section creep!"
                  .format(room.name, base))
            num_sections = 1
            role_obj[roleobj_key_num_sections] = 1
        cost = cost_of_sections(base, num_sections, energy) + half_section * half_section_cost(base)
        if not cost:
            print("[{}][spawning] ERROR: Unknown cost retrieved from cost_of_sections({}, {}, {}): {}"
                  .format(room.name, base, num_sections, energy, cost))
            cost = Infinity
        if cost > energy:
            new_size = max_sections_of(room, base)
            if new_size <= 0:
                if low_energy_dynamic.includes(base):
                    cost = energy
                else:
                    print("[{}][spawning] ERROR: Trying to spawn a {}, which we don't have enough energy for even 1"
                          " section of!".format(room.name, base))
                    return
            else:
                print("[{}][spawning] Adjusted creep size from {} to {} to match available energy."
                      .format(room.name, num_sections, new_size))
                # Since the literal memory object is returned, this mutation will stick for until this creep has been
                # spawned, or the target creep has been refreshed
                num_sections = role_obj[roleobj_key_num_sections] = new_size
                half_section = 1 if num_sections % 1 else 0
                num_sections -= num_sections % 1
                cost = cost_of_sections(base, num_sections, energy) + half_section * half_section_cost(base)
        energy = cost

    if filled < energy:
        # print("[{}][spawning] Room doesn't have enough energy! {} < {}!".format(room.name, filled, energy))
        return

    descriptive_level = None  # type: Any

    if base is creep_base_1500miner:
        parts = []
        work_cost = BODYPART_COST[WORK]
        move_cost = BODYPART_COST[MOVE]
        if energy < work_cost * 3 + move_cost:  # 350 on official servers
            print("[{}][spawning] Building sub-optimal dedicated miner!".format(room.name))
            num_work = math.floor((energy - move_cost) / work_cost)
            num_move = math.floor((energy - num_work * work_cost) / move_cost)
        else:
            num_move = num_sections or 3
            num_work = 3
        for i in range(0, num_work):
            parts.append(WORK)
        for i in range(0, num_move):
            parts.append(MOVE)
        descriptive_level = "work:{}-move:{}".format(num_work, num_move)
    elif base is creep_base_3000miner:
        work_cost = BODYPART_COST[WORK]
        move_cost = BODYPART_COST[MOVE]
        parts = []
        if energy < work_cost * 5 + move_cost:  # 550 on offical servers
            print("[{}][spawning] Building sub-optimal dedicated miner!".format(room.name))
            num_work = math.floor((energy - move_cost) / work_cost)
            num_move = math.floor((energy - num_work * work_cost) / move_cost)
        else:
            num_move = num_sections or 5
            num_work = 5
        for i in range(0, num_work):
            parts.append(WORK)
        for i in range(0, num_move):
            parts.append(MOVE)
        descriptive_level = "work:{}-move:{}".format(num_work, num_move)
    elif base is creep_base_4000miner:
        work_cost = BODYPART_COST[WORK]
        move_cost = BODYPART_COST[MOVE]
        parts = []
        if energy < work_cost * 7 + move_cost:  # 750 on official servers
            print("[{}][spawning] Building sub-optimal dedicated miner!".format(room.name))
            num_work = math.floor((energy - move_cost) / work_cost)
            num_move = math.floor((energy - num_work * work_cost) / move_cost)
        else:
            num_move = num_sections or 7
            num_work = 7
        for i in range(0, num_work):
            parts.append(WORK)
        for i in range(0, num_move):
            parts.append(MOVE)
        descriptive_level = "work:{}-move:{}".format(num_work, num_move)
    elif base is creep_base_carry3000miner:
        work_cost = BODYPART_COST[WORK]
        move_cost = BODYPART_COST[MOVE]
        carry_cost = BODYPART_COST[CARRY]
        if energy < work_cost * 5 + move_cost + carry_cost:
            print("[{}][spawning] Too few extensions to build a dedicated 3000 miner with carry!"
                  .format(room.name))
            if Game.time % 30 == 3:
                room.reset_planned_role()
            return
        parts = []
        num_move = num_sections or 5
        num_work = 5
        for i in range(0, num_work):
            parts.append(WORK)
        parts.append(CARRY)
        for i in range(0, num_move):
            parts.append(MOVE)
        descriptive_level = num_move
    elif base is creep_base_reserving:
        parts = []
        for i in range(0, num_sections):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(CLAIM)
        descriptive_level = num_sections
    elif base is creep_base_claiming:
        claim_cost = BODYPART_COST[CLAIM]
        move_cost = BODYPART_COST[MOVE]
        if energy >= claim_cost + move_cost * 7:
            parts = [MOVE, MOVE, MOVE, MOVE, MOVE, MOVE, CLAIM, MOVE]
        elif energy >= claim_cost + move_cost * 4:
            parts = [MOVE, MOVE, MOVE, CLAIM, MOVE]
        elif energy >= claim_cost + move_cost * 2:
            parts = [MOVE, CLAIM, MOVE]
        elif energy > claim_cost + move_cost:
            parts = [CLAIM, MOVE]
        else:
            print("[{}][spawning] Too few extensions to build a claim creep!"
                  .format(room.name))
            if Game.time % 30 == 3:
                room.reset_planned_role()
            return
    elif base is creep_base_claim_attack:
        parts = []
        for i in range(0, half_section):
            parts.append(TOUGH)
        for i in range(0, num_sections * 5):
            parts.append(CLAIM)
        for i in range(0, num_sections * 5 + half_section * 2):
            parts.append(MOVE)
        for i in range(0, half_section):
            parts.append(HEAL)
        if half_section:
            descriptive_level = 'claim:{}-heal:{}'.format(num_sections * 5, half_section)
        else:
            descriptive_level = 'claim:{}'.format(num_sections)
    elif base is creep_base_hauler:
        parts = []
        for i in range(0, num_sections):
            parts.append(CARRY)
        for i in range(0, num_sections):
            parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_half_move_hauler:
        parts = []
        for i in range(0, num_sections * 2 + half_section):
            parts.append(CARRY)
        for i in range(0, num_sections + half_section):
            parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_work_full_move_hauler:
        parts = []
        for i in range(0, num_sections):
            parts.append(CARRY)
        for part in initial_section[base]:
            parts.append(part)
        for i in range(0, num_sections):
            parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_work_half_move_hauler:
        parts = []
        for i in range(0, num_sections * 2 + half_section):
            parts.append(CARRY)
        for part in initial_section[base]:
            parts.append(part)
        for i in range(0, num_sections + half_section):
            parts.append(MOVE)
        descriptive_level = num_sections * 2 + 1
    elif base is creep_base_worker:
        move_cost = BODYPART_COST[MOVE]
        carry_cost = BODYPART_COST[CARRY]
        work_cost = BODYPART_COST[WORK]
        if energy >= move_cost * 4 + carry_cost * 3 + work_cost:  # 450 on official servers
            parts = []
            for i in range(0, num_sections):
                parts.append(CARRY)
                parts.append(CARRY)
                parts.append(CARRY)
                parts.append(MOVE)
            for i in range(0, num_sections + half_section):
                parts.append(WORK)
            for i in range(0, num_sections * 3 + half_section):
                parts.append(MOVE)
            descriptive_level = "carry:{}-work:{}".format(num_sections * 3, num_sections)
        elif energy >= move_cost * 3 + carry_cost * 2 + work_cost:  # 400 on official servers
            parts = [MOVE, MOVE, MOVE, CARRY, CARRY, WORK]
            descriptive_level = "carry:2-work:1"
        elif energy >= move_cost * 2 + carry_cost + work_cost:  # 250 on official servers
            parts = [MOVE, MOVE, CARRY, WORK]
            descriptive_level = "carry:1-work:1"
        else:
            print("[{}][spawning] Too few extensions to build a worker ({}/{} energy)!".format(room.name, energy, 250))
            if Game.time % 30 == 3:
                room.reset_planned_role()
            return
    elif base is creep_base_defender:
        parts = []
        # # MOVE, MOVE, ATTACK, TOUCH = one section = 190
        # MOVE, ATTACK, CARRY = one section = 180 [TOUGH, MOVE, MOVE, MOVE, ATTACK, ATTACK],
        for i in range(0, num_sections):
            parts.append(TOUGH)
        for i in range(0, math.floor(num_sections * 1.5)):
            parts.append(MOVE)
        for i in range(0, num_sections * 2 + half_section):
            parts.append(ATTACK)
        for i in range(0, math.ceil(num_sections * 1.5) + half_section):
            parts.append(MOVE)
        descriptive_level = num_sections
    elif base is creep_base_rampart_defense:
        parts = []
        for i in range(0, num_sections + half_section):
            parts.append(MOVE)
        for i in range(0, num_sections * 2 + half_section):
            parts.append(ATTACK)
        descriptive_level = num_sections * 2 + half_section
    elif base is creep_base_ranged_offense:
        parts = []
        for i in range(0, num_sections):
            parts.append(RANGED_ATTACK)
        for i in range(0, 1 + num_sections):
            parts.append(MOVE)
        parts.append(HEAL)
        descriptive_level = num_sections
    elif base is creep_base_3h:
        parts = []
        for i in range(0, half_section * 2):
            parts.append(TOUGH)
        for i in range(0, num_sections):
            parts.append(RANGED_ATTACK)
        for i in range(0, 3 + 2 * half_section + num_sections):
            parts.append(MOVE)
        for i in range(0, 3):
            parts.append(HEAL)
        descriptive_level = num_sections
    elif base is creep_base_mammoth_miner:
        parts = [MOVE, CARRY]
        move_cost = BODYPART_COST[MOVE]
        carry_cost = BODYPART_COST[CARRY]
        work_cost = BODYPART_COST[WORK]
        energy_counter = move_cost + carry_cost
        part_counter = 2
        move_counter = 0.25
        # TODO: this would be much better if done in constant time.
        for i in range(0, 2):
            if part_counter >= MAX_CREEP_SIZE:
                break
            if energy_counter >= energy - move_cost:
                break
            # parts.append(CARRY)
            # energy_counter += carry_cost
            # part_counter += 1
            # move_counter += 0.25
            for _ignored in range(0, 25):
                if move_counter >= 1:
                    if part_counter >= MAX_CREEP_SIZE:
                        break
                    if energy_counter >= energy - move_cost:
                        break
                    parts.append(MOVE)
                    energy_counter += move_cost
                    part_counter += 1
                    move_counter -= 1
                if part_counter >= MAX_CREEP_SIZE:
                    break
                if energy_counter >= energy - work_cost:
                    break
                parts.append(WORK)
                energy_counter += work_cost
                part_counter += 1
                move_counter += 0.25
    elif base is creep_base_goader:
        parts = []
        for i in range(0, num_sections * 2 + 1 + half_section):  # extra tough in initial section
            parts.append(TOUGH)
        parts.append(ATTACK)
        for i in range(0, num_sections + 1 + half_section):  # extra move in initial section
            parts.append(MOVE)
    elif base is creep_base_full_move_goader:
        parts = []
        for i in range(0, num_sections * 2):
            parts.append(CARRY)
        for i in range(0, num_sections):
            parts.append(TOUGH)
        parts.append(ATTACK)
        for i in range(0, num_sections + 1):  # extra move in initial section
            parts.append(MOVE)
    elif base is creep_base_half_move_healer:
        parts = []
        total_heal = num_sections * 2 + half_section
        total_move = num_sections + half_section
        for i in range(0, math.floor(total_move / 2)):
            parts.append(MOVE)
        for i in range(0, math.floor(total_heal / 2)):
            parts.append(HEAL)
        for i in range(0, math.ceil(total_move / 2)):
            parts.append(MOVE)
        for i in range(0, math.ceil(total_heal / 2)):
            parts.append(HEAL)
    elif base is creep_base_full_move_healer:
        parts = []
        for i in range(0, math.floor(num_sections / 2)):
            parts.append(MOVE)
        for i in range(0, math.floor(num_sections / 2)):
            parts.append(HEAL)
        for i in range(0, math.ceil(num_sections / 2)):
            parts.append(MOVE)
        for i in range(0, math.ceil(num_sections / 2)):
            parts.append(HEAL)
    elif base is creep_base_squad_healer:
        parts = []
        for i in range(0, num_sections):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(HEAL)
    elif base is creep_base_squad_ranged:
        parts = []
        for i in range(0, num_sections):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(RANGED_ATTACK)
    elif base is creep_base_squad_dismantle:
        parts = []
        for i in range(0, math.floor(num_sections / 2)):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(WORK)
        for i in range(0, math.ceil(num_sections / 2)):
            parts.append(MOVE)
    elif base is creep_base_dismantler:
        parts = []
        for i in range(0, num_sections * 2 + half_section):
            parts.append(WORK)
        for i in range(0, num_sections + half_section):
            parts.append(MOVE)
    elif base is creep_base_full_move_dismantler:
        parts = []
        for i in range(0, num_sections):
            parts.append(WORK)
        for i in range(0, num_sections):
            parts.append(MOVE)
    elif base is creep_base_full_upgrader:
        if num_sections > 1 or half_section:
            parts = [CARRY]
            num_work = num_sections * 2 + half_section
            num_move = num_sections + half_section + 1
            for i in range(0, num_work):
                parts.append(WORK)
            if num_work > 15:
                # Technically the initial section always has 2 carry parts,
                #  but let's not include this second one if we don't need to
                parts.append(CARRY)
            elif half_section:
                # we have one fewer CARRY and one fewer work in the half section, so we can afford to have 1 less MOVE.
                num_move -= 1
            for i in range(0, num_move):
                parts.append(MOVE)
            descriptive_level = num_work
        else:
            parts = [MOVE, CARRY, WORK]
            descriptive_level = "min"
    elif base is creep_base_power_attack:
        parts = []
        for i in range(0, num_sections):
            parts.append(TOUGH)
        for i in range(0, num_sections * 2 + half_section):
            parts.append(MOVE)
        for i in range(0, num_sections * 3 + half_section):
            parts.append(ATTACK)
    elif base is creep_base_full_move_attack:
        parts = []
        for i in range(0, num_sections):
            parts.append(MOVE)
        for i in range(0, num_sections):
            parts.append(ATTACK)
    elif base is creep_base_scout:
        parts = [MOVE]
    else:
        print("[{}][spawning] Unknown creep base {}! Role object: {}".format(room.name, base,
                                                                             JSON.stringify(role_obj)))
        room.reset_planned_role()
        return

    name = naming.random_digits()
    if Game.creeps[name]:
        name = naming.random_digits()
    home = room.name

    if replacing:
        memory = {
            "home": home,
            "role": role_temporary_replacing,
            "replacing": replacing,
            "replacing_role": role
        }
    else:
        memory = {"home": home, "role": role}

    if role_obj[roleobj_key_initial_memory]:
        # Add whatever memory seems to be necessary
        _.extend(memory, role_obj[roleobj_key_initial_memory])

    if _.sum(parts, lambda p: BODYPART_COST[p]) > spawn.room.energyAvailable - ubos_cache.get(room.name):
        print("[{}][spawning] Warning: Generated too costly of a body for a {}! Available energy: {}, cost: {}."
              .format(room.name, role, spawn.room.energyAvailable - ubos_cache.get(room.name),
                      _.sum(parts, lambda p: BODYPART_COST[p])))
        room.reset_planned_role()
        return

    # if descriptive_level:
    #     if replacing:
    #         print("[{}][spawning] Spawning {}, a {} with body {} level {}, live-replacing {}.".format(
    #             room.name, name, role, base, descriptive_level, replacing))
    #     else:
    #         print("[{}][spawning] Spawning {}, a {} with body {} level {}.".format(
    #             room.name, name, role, base, descriptive_level))
    # else:
    #     if replacing:
    #         print("[{}][spawning] Spawning {}, a {} with body {}, live-replacing {}.".format(
    #             room.name, name, role, base, replacing))
    #     else:
    #         print("[{}][spawning] Spawning {}, a {} with body {}.".format(room.name, name, role, base))
    result = spawn.createCreep(parts, name, memory)
    if result not in Game.creeps:
        print("[{}][spawning] Invalid response from createCreep: {}".format(room.name, result))
        if result == ERR_NOT_ENOUGH_RESOURCES:
            print("[{}][spawning] Couldn't create body {} with energy {} (target num_sections: {})!"
                  .format(room.name, parts, energy, num_sections))
        elif result == ERR_INVALID_ARGS:
            if descriptive_level:
                print("[{}][spawning] Produced invalid body array for creep type {} level {}: {}"
                      .format(room.name, base, descriptive_level, JSON.stringify(parts)))
            else:
                print("[{}][spawning] Produced invalid body array for creep type {}: {}"
                      .format(room.name, base, JSON.stringify(parts)))
    else:
        result = cast(str, result)
        used = ubos_cache.get(room.name) or 0
        used += postspawn_calculate_cost_of(parts)
        ubos_cache.set(room.name, used)
        room.reset_planned_role()
        if role_obj[roleobj_key_initial_targets]:
            for target_type, target_id in role_obj[roleobj_key_initial_targets]:
                room.hive.targets.manually_register(cast(Creep, {'name': name}), target_type, target_id)
        if role_obj[roleobj_key_request_identifier]:
            room.successfully_spawned_request(role_obj[roleobj_key_request_identifier])
        if role_obj[roleobj_key_run_after_spawning]:
            __pragma__('js', '(eval(role_obj[roleobj_key_run_after_spawning]))')(name)
        if replacing:
            room.register_new_replacing_creep(replacing, result)
        else:
            room.register_to_role(Game.creeps[result])


def validate_role(role_obj):
    # type: (Dict[str, Any]) -> None
    if role_obj is None:
        return
    if not role_obj[roleobj_key_role]:
        raise AssertionError("Invalid role: no .role property")
    if not role_obj[roleobj_key_base]:
        raise AssertionError("Invalid role: no .base property")
    if not role_obj[roleobj_key_num_sections]:
        role_obj[roleobj_key_num_sections] = Infinity
    if roleobj_key_replacing in role_obj and not role_obj[roleobj_key_replacing]:
        del role_obj[roleobj_key_replacing]
    role_obj.num_sections = ceil_sections(role_obj.num_sections, role_obj['base'])


def find_base_type(_creep):
    # type: (Union[Creep, RoleBase]) -> Optional[str]
    if cast(RoleBase, _creep).creep:
        creep = cast(RoleBase, _creep).creep
    else:
        creep = cast(Creep, _creep)
    part_counts = _.countBy(creep.body, lambda p: p.type)
    total = _.sum(part_counts)
    if part_counts[WORK] == part_counts[CARRY] == part_counts[MOVE] / 2 == total / 4 \
            or part_counts[WORK] == part_counts[CARRY] / 3 == part_counts[MOVE] / 4 == total / 8 \
            or part_counts[WORK] - 1 == part_counts[CARRY] / 3 == (part_counts[MOVE] - 1) / 4 == (total - 2) / 8:
        base = creep_base_worker
    elif part_counts[MOVE] + part_counts[WORK] == total and part_counts[MOVE] <= part_counts[WORK] <= 3:
        base = creep_base_1500miner
    elif part_counts[MOVE] + part_counts[WORK] == total and part_counts[MOVE] <= part_counts[WORK] <= 5:
        base = creep_base_3000miner
    elif part_counts[MOVE] + part_counts[WORK] == total and part_counts[MOVE] <= part_counts[WORK] <= 7:
        base = creep_base_4000miner
    elif part_counts[CARRY] == 1 and part_counts[MOVE] + part_counts[WORK] + 1 == total \
            and part_counts[MOVE] <= part_counts[WORK] <= 5:
        base = creep_base_carry3000miner
    elif part_counts[CARRY] == part_counts[MOVE] == total / 2:
        base = creep_base_hauler
    elif part_counts[WORK] == 2 and part_counts[MOVE] == part_counts[CARRY] + 2 == total / 2:
        base = creep_base_work_full_move_hauler
    elif (part_counts[WORK] == 2 and part_counts[MOVE] == (part_counts[CARRY] + 2) / 2 == total / 3) \
            or (part_counts[WORK] == 2 and part_counts[MOVE] - 2 == (part_counts[CARRY]) / 2 == (total - 3) / 3):
        base = creep_base_work_half_move_hauler
    elif part_counts[CLAIM] == part_counts[MOVE] == total / 2:
        base = creep_base_reserving
    elif part_counts[ATTACK] == part_counts[TOUGH] == part_counts[MOVE] == total / 3:
        base = creep_base_defender
    elif (part_counts[MOVE] == total / 3 and part_counts[CARRY] == 2
          and part_counts[WORK] + part_counts[MOVE] + part_counts[CARRY] == total) \
            or (part_counts[MOVE] == (total - 1) / 3 + 1 and part_counts[CARRY] == 2
                and part_counts[WORK] + part_counts[MOVE] + part_counts[CARRY] == total):
        base = creep_base_full_upgrader
    elif part_counts[MOVE] == total == 1:
        base = creep_base_scout
    elif part_counts[ATTACK] / 2 == part_counts[MOVE] == total / 3 \
            or (part_counts[ATTACK] - 1) / 2 == part_counts[MOVE] - 1 == (total - 2) / 3:
        base = creep_base_rampart_defense
    else:
        print("[{}][{}] Creep has unknown body! {}".format(
            creep.memory.home, creep.name, JSON.stringify(part_counts)))
        return None
    return base


def postspawn_calculate_cost_of(parts):
    # type: (List[str]) -> int
    cost = 0
    for part in parts:
        cost += BODYPART_COST[part]
    return cost


def energy_per_section(base):
    # type: (str) -> Optional[int]
    # TODO: use this to create scalable sections for remote mining ops
    if base in scalable_sections:
        cost = 0
        for part in scalable_sections[base]:
            cost += BODYPART_COST[part]
        return cost
    else:
        return None


def lower_energy_per_section(base):
    # type: (str) -> Optional[int]
    if base in low_energy_sections:
        cost = 0
        for part in low_energy_sections[base]:
            cost += BODYPART_COST[part]
        return cost
    else:
        return energy_per_section(base)


def initial_section_cost(base):
    # type: (str) -> int
    cost = 0
    if base in initial_section:
        for part in initial_section[base]:
            cost += BODYPART_COST[part]
    return cost


def half_section_cost(base):
    # type: (str) -> int
    cost = 0
    if base in half_sections:
        for part in half_sections[base]:
            cost += BODYPART_COST[part]
    return cost


def cost_of_sections(base, num_sections, energy_available):
    # type: (str, int, int) -> int
    initial_cost = initial_section_cost(base)
    per_section_energy = energy_per_section(base)
    if initial_cost + per_section_energy > energy_available:
        per_section_energy = lower_energy_per_section(base)
    if num_sections % 1 > 0:
        return initial_cost + int(math.floor(num_sections)) * per_section_energy \
               + half_section_cost(base)
    else:
        return initial_section_cost(base) + num_sections * per_section_energy


def max_sections_of(room, base):
    # type: (RoomMind, str) -> int
    if emergency_conditions(room):
        energy = room.room.energyAvailable
    else:
        energy = room.room.energyCapacityAvailable
    max_by_cost = int(floor((energy - initial_section_cost(base)) / energy_per_section(base)))
    if max_by_cost == 0:
        max_by_cost = floor((energy - initial_section_cost(base)) / lower_energy_per_section(base))
    initial_base_parts = len(initial_section[base]) if base in initial_section else 0
    max_by_parts = floor((MAX_CREEP_SIZE - initial_base_parts) / len(scalable_sections[base]))
    num_sections = min(max_by_cost, max_by_parts)
    if base in half_sections:
        current_parts = initial_base_parts + num_sections * len(scalable_sections[base])
        if current_parts + len(half_sections[base]) <= MAX_CREEP_SIZE:
            current_energy = cost_of_sections(base, num_sections, energy)
            if current_energy + half_section_cost(base) <= energy:
                num_sections += 0.5
    return num_sections


def using_lower_energy_section(room, base):
    # type: (RoomMind, str) -> bool
    if emergency_conditions(room):
        energy = room.room.energyAvailable
    else:
        energy = room.room.energyCapacityAvailable
    max_by_cost = floor((energy - initial_section_cost(base)) / energy_per_section(base))
    if max_by_cost == 0:
        return True
    else:
        return False


def work_count(_creep):
    # type: (Union[Creep, RoleBase]) -> int
    if cast(RoleBase, _creep).creep:
        creep = cast(RoleBase, _creep).creep
    else:
        creep = cast(Creep, _creep)
    work = 0
    for part in creep.body:
        if part.type == WORK:
            work += 1
            if part.boost:
                boost = BOOSTS[WORK][part.boost]
                # rough estimation, we probably don't care about boosts for different
                # functions yet, since we don't even have boosted creeps spawning!
                work += boost[Object.keys(boost)[0]]
    return work


def carry_count(_creep):
    # type: (Union[Creep, RoleBase]) -> int
    if cast(RoleBase, _creep).creep:
        creep = cast(RoleBase, _creep).creep
    else:
        creep = cast(Creep, _creep)
    return int(creep.carryCapacity / CARRY_CAPACITY)


def fit_num_sections(needed, maximum, extra_initial = 0, min_split = 1):
    # type: (float, float, float, int) -> float
    if maximum <= 1:
        return maximum

    num = min_split
    trying = Infinity
    while trying > maximum:
        trying = ceil_sections(needed / num - extra_initial)
        num += 1
    return trying


def ceil_sections(count, base = None):
    # type: (float, Optional[str]) -> float
    if base is not None and base not in half_sections:
        return math.ceil(count)
    return math.ceil(count * 2) / 2
