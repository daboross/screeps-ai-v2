initial_section = {
    creep_base_work_full_move_hauler: [WORK, WORK, MOVE, MOVE],
    creep_base_work_half_move_hauler: [WORK, WORK, MOVE],
    creep_base_goader: [ATTACK, MOVE, TOUGH],
    creep_base_full_move_goader: [ATTACK, MOVE],
    # etc...
}

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
    # etc...
}

half_sections = {
    creep_base_worker: [WORK, MOVE],
    creep_base_work_half_move_hauler: [MOVE, CARRY],
    creep_base_half_move_hauler: [MOVE, CARRY],
    # etc...
}

low_energy_sections = {
    creep_base_worker: [MOVE, MOVE, CARRY, WORK],
    creep_base_full_upgrader: [MOVE, CARRY, WORK],
    creep_base_claiming: [MOVE, CLAIM, MOVE],
    # etc...
}

low_energy_dynamic = [creep_base_1500miner, creep_base_3000miner, creep_base_4000miner]


def would_be_emergency(room):
    """
    :type room: rooms.room_mind.RoomMind
    """
    spawn_mass = room.carry_mass_of(role_spawn_fill) \
                 + room.carry_mass_of(role_spawn_fill_backup) \
                 + room.carry_mass_of(role_tower_fill)
    return spawn_mass <= 0 or (spawn_mass < room.get_target_total_spawn_fill_mass() / 2)


def emergency_conditions(room):
    """
    :type room: rooms.room_mind.RoomMind
    """
    return volatile_cache.mem(room.name).get("emergency_conditions")


def run(room, spawn):
    """
    Activates the spawner, spawning what's needed, as determined by the RoomMind.

    Manages deciding what parts belong on what creep base as well.
    :type room: rooms.room_mind.RoomMind
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
        #     print("[{}][spawning] All roles are good, no need to spawn more!".format(room.name))
        #     room.mem.spawning_already_reported_no_next_role = True
        return
    role = role_obj.role
    base = role_obj.base
    num_sections = role_obj.num_sections or 0
    replacing = role_obj.replacing

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
            role_obj.num_sections = 1
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
                num_sections = role_obj.num_sections = new_size
                half_section = 1 if num_sections % 1 else 0
                num_sections -= num_sections % 1
                cost = cost_of_sections(base, num_sections, energy) + half_section * half_section_cost(base)
        energy = cost

    if filled < energy:
        return

    descriptive_level = None

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
    # etc...
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
    elif base is creep_base_rampart_defense:
        parts = []
        for i in range(0, num_sections + half_section):
            parts.append(MOVE)
        for i in range(0, num_sections * 2 + half_section):
            parts.append(ATTACK)
        descriptive_level = num_sections * 2 + half_section
    # etc...
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

    if role_obj.memory:
        # Add whatever memory seems to be necessary
        _.extend(memory, role_obj.memory)

    if _.sum(parts, lambda p: BODYPART_COST[p]) > spawn.room.energyAvailable - ubos_cache.get(room.name):
        print("[{}][spawning] Warning: Generated too costly of a body for a {}! Available energy: {}, cost: {}."
              .format(room.name, role, spawn.room.energyAvailable - ubos_cache.get(room.name),
                      _.sum(parts, lambda p: BODYPART_COST[p])))
        room.reset_planned_role()
        return
    result = spawn.createCreep(parts, name, memory)
    # error management / creep registration below
