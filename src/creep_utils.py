__pragma__('noalias', 'name')


# ***
# MOVING
# ***

def get_path_to(creep, target, same_position_ok=False):
    if not creep.memory.path:
        creep.memory.path = {}

    id = target.id
    if not id:
        id = target.pos.x + "_" + target.pos.y + "_" + target.pos.roomName

    if creep.pos == target.pos:
        return None

    if creep.memory.path[id]:
        if not same_position_ok:
            if (creep.memory.last_pos and
                        creep.memory.last_pos.x == creep.pos.x and
                        creep.memory.last_pos.y == creep.pos.y):
                if not creep.memory.same_place_ticks:
                    creep.memory.same_place_ticks = 1
                elif creep.memory.same_place_ticks < 3:
                    creep.memory.same_place_ticks += 1
                else:
                    print("[{}] Regenerating path from {} to {}".format(
                        creep.name, creep.pos, target.pos
                    ))
                    path = creep.pos.findPathTo(target)
                    creep.memory.path[id] = Room.serializePath(path)
                    creep.memory.same_place_ticks = 0
                    return path
            else:
                del creep.memory.same_place_ticks
                creep.memory.last_pos = creep.pos
        try:
            return Room.deserializePath(creep.memory.path[id])
        except:
            del creep.memory.path[id]

    path = creep.pos.findPathTo(target)
    creep.memory.path[id] = Room.serializePath(path)
    return path


def move_to_path(creep, target, same_position_ok=False, times_tried=0):
    if creep.fatigue <= 0:
        result = creep.moveByPath(get_path_to(creep, target, same_position_ok))

        if result != OK:
            if result != ERR_NOT_FOUND:
                console.log("[{}] Unknown result from creep.moveByPath: {}".format(
                    creep.name, result
                ))

            id = target.id
            if not id:
                id = target.pos.x + "_" + target.pos.y + "_" + target.pos.roomName
            del creep.memory.path[id]
            if not times_tried:
                times_tried = 0
            if times_tried < 3:
                move_to_path(creep, target, False, times_tried + 1)
            else:
                console.log("[{}] Continually failed to move from {} to {}!".format(creep.pos, target.pos))


def get_spread_out_target(creep, resource, find_list, limit_by=None, true_limit=False):
    if not creep.memory.targets:
        creep.memory.targets = {}

    if creep.memory.targets[resource]:
        target = Game.getObjectById(creep.memory.targets[resource])
        if target:
            # don't return null targets
            return target
        else:
            print("[{}] Retargetting {}!".format(creep.name, resource))
            id = creep.memory.targets[resource]
            del creep.memory.targets[resource]
            del Memory.targets_used[resource][id]

    if not Memory.targets_used:
        Memory.targets_used = {
            resource: {}
        }
    elif not Memory.targets_used[resource]:
        Memory.targets_used[resource] = {}

    list = find_list()
    min_count = 8000
    min_target = None
    min_target_id = None
    for prop in Object.keys(list):
        possible_target = list[prop]
        id = possible_target.id
        if not id:
            print("No ID on possible target {}".format(possible_target))
            id = possible_target.name

        if not Memory.targets_used[resource][id]:
            creep.memory.targets[resource] = id
            Memory.targets_used[resource][id] = 1
            return possible_target
        elif limit_by:
            if typeof(limit_by) == "number":
                limit = limit_by
            else:
                limit = limit_by(possible_target)
            if Memory.targets_used[resource][id] < limit:
                min_target_id = id
                min_target = possible_target
                break

        if not limit_by or not true_limit:
            if Memory.targets_used[resource][id] < min_count:
                min_count = Memory.targets_used[resource][id]
                min_target = possible_target
                min_target_id = id

    if not min_target:
        return None
    else:
        Memory.targets_used[resource][min_target_id] += 1
        creep.memory.targets[resource] = min_target_id
        return min_target


def get_possible_spread_out_target(creep, resource):
    if creep.memory.targets and creep.memory.targets[resource]:
        target = Game.getObjectById(creep.memory.targets[resource])
        if target:
            return target
        else:
            id = creep.memory.targets[resource]
            del creep.memory.targets[resource]
            del Memory.targets_used[resource][id]

    return None


def untarget_spread_out_target(creep, resource):
    if creep.memory.targets:
        id = creep.memory.targets[resource]
        if id:
            if (Memory.targets_used and Memory.targets_used[resource] and
                    Memory.targets_used[resource][id]):
                Memory.targets_used[resource][id] -= 1

            del creep.memory.targets[resource]


def recheck_targets_used():
    old_targets = Memory.targets_used
    targets_used = {}

    for name in Object.keys(Memory.creeps):
        memory = Memory.creeps[name]
        if not memory.targets:
            continue
        for resource in Object.keys(memory.targets):
            id = memory.targets[resource]
            if not targets_used[resource]:
                targets_used[resource] = {}
            if not targets_used[resource][id]:
                targets_used[resource][id] = 1
            else:
                targets_used[resource][id] += 1

    if old_targets:
        for resource in targets_used.keys():
            for id in targets_used[resource].keys():
                if old_targets[resource][id] != targets_used[resource][id]:
                    print("Target {}:{} didn't match. {} != {}".format(
                        resource, id, old_targets[resource][id], targets_used[resource][id]
                    ))
            if old_targets[type]:
                for id in Object.keys(old_targets[type]):
                    if not targets_used[type][id] and old_targets[type][id]:
                        print("Target {}:{} didn't match. {} != {}".format(
                            resource, id, old_targets[resource][id], 0
                        ))

    Memory.targets_used = targets_used


def harvest_energy(creep):
    # def filter(source):
    #     if not Memory.big_harvesters_placed or not Memory.big_harvesters_placed[source.id]:
    #         return True
    #
    #     harvester = Game.getObjectById(Memory.big_harvesters_placed[source.id])
    #     if harvester:
    #         pos = harvester.pos
    #         energy_piles = pos.look(LOOK_ENERGY)
    #         return energy_piles.length > 0 and energy_piles[0].amount > 20
    #
    #     return True

    def find_list():
        list = creep.room.find(FIND_SOURCES)
        # for name in Object.keys(Game.flags):
        #     flag = Game.flags[name]
        #     if flag.memory.harvesting_spot:
        #         list.extend(flag.pos.lookFor(LOOK_SOURCES))
        return list

    source = get_spread_out_target(creep, "source", find_list)

    if not source:
        print("[{}] Wasn't able to find source {}".format(
            creep.name, creep.memory.targets["source"]
        ))
        finished_energy_harvest(creep)
        go_to_depot(creep)
        return

    piles = source.pos.findInRange(FIND_DROPPED_ENERGY, 3)
    if len(piles) > 0:
        result = creep.pickup(piles[0])
        if result == ERR_NOT_IN_RANGE:
            move_to_path(creep, piles[0])
        elif result != OK:
            print("[{}] Unknown result from creep.pickup({}): {}".format(
                creep.name, piles[0], result))
        return

    containers = source.pos.findInRange(FIND_STRUCTURES, 3, {"filter": lambda struct: (
        (struct.structureType == STRUCTURE_CONTAINER
         or struct.structureType == STRUCTURE_STORAGE)
        and struct.store >= 0
    )})
    if containers.length > 0:
        result = creep.withdraw(containers[0], RESOURCE_ENERGY)
        if result == ERR_NOT_IN_RANGE:
            move_to_path(creep, containers[0])
        elif result != OK:
            print("[{}] Unknown result from creep.withdraw({}): {}".format(
                creep.name, containers[0], result))
        return

    # at this point, there is no energy and no container filled.
    # we should ensure that if there's a big harvester, it hasn't died!
    if (Memory.big_harvesters_placed
        and Memory.big_harvesters_placed[source.id]
        and not Game.creeps[Memory.big_harvesters_placed[source.id]]):
        Memory.needs_clearing = True
        del Memory.big_harvesters_placed[source.id]
        move_to_path(creep, source)
    else:
        # TODO: Hardcoded 2 here!
        if role_count("big_harvester") < 2:
            result = creep.harvest(source)

            if result == ERR_NOT_IN_RANGE:
                move_to_path(creep, source)
            elif result != OK:
                print("[{}] Unknown result from creep.harvest({}): {}".format(
                    creep.name, source, result))
        else:
            go_to_depot(creep)


def finished_energy_harvest(creep):
    untarget_spread_out_target(creep, "source")


# ***
# SPAWNING
# ***

def role_count(role):
    if not Memory.role_counts:
        count_roles()
    count = Memory.role_counts[role]
    return count if count else 0


def get_role_name(new_spawn=False):
    harvester_count = role_count("harvester")
    upgrader_count = role_count("upgrader")
    builder_count = role_count("builder")
    big_harvester_count = role_count("big_harvester")
    tower_fill_count = role_count("tower_fill")
    print("Getting role: assuming {} harvesters exist, {} big harvesters exist, {} upgraders exist,"
          "{} tower_fillers exist, {} builders exist, and this {} a new spawn.".format(
        harvester_count, big_harvester_count, upgrader_count, tower_fill_count, builder_count,
        "is" if new_spawn else "isn't"))

    if harvester_count < 2:
        return "harvester"
    elif big_harvester_count < 2 and new_spawn:
        # TODO: 2 is currently hardcoded for our map section.
        return "big_harvester"
    elif harvester_count < 4:
        return "harvester"
    elif upgrader_count < 1:
        return "upgrader"
    elif tower_fill_count < 2:
        return "tower_fill"
    elif upgrader_count < 2:
        return "upgrader"
    elif harvester_count * 2 < builder_count:
        return "harvester"
    else:
        # these builders will repurpose as upgraders if need be
        return "builder"


# ***
# CONSISTENCY
# ***

def count_roles():
    old_roles = Memory.role_counts
    role_counts = {}

    for name in Object.keys(Memory.creeps):
        role = Memory.creeps[name].role
        if not role:
            continue
        if not role_counts[role]:
            role_counts[role] = 1
        else:
            role_counts[role] += 1

    if old_roles:
        for name in role_counts:
            if role_counts[name] != old_roles[name]:
                print("Role {} didn't match. {} != {}".format(name, old_roles[name], role_counts[name]))

    Memory.role_counts = role_counts


def reassign_roles():
    # TODO: hardcoded 2 here
    if role_count("harvester") < 4 and role_count("big_harvester") < 2:
        for name in Object.keys(Memory.creeps):
            memory = Memory.creeps[name]
            if memory.role != "big_harvester":
                memory.role = "harvester"
        count_roles()


def clear_memory():
    for name in Object.keys(Memory.creeps):
        if not Game.creeps[name]:
            role = Memory.creeps[name].role
            if role:
                print("[{}] {} died".format(name, role))

            if role == "big_harvester":
                del Memory.big_harvesters_placed[Memory.creeps[name].targets["big_source"]]

            for resource in Memory.creeps[name].targets:
                untarget_spread_out_target(creep, resource)

            del Memory.creeps[name]


# ***
# UTILITY
# ***

def is_next_block_clear(creep, target):
    next_pos = __new__(RoomPosition(target.pos.x, target.pos.y, target.pos.roomName))
    creep_pos = creep.pos

    # Apparently, I thought it would be best if we start at the target position, and continue looking for open spaces
    # until we get to the origin position. Thus, if we encounter an obstacle, we use "continue", and if the result is
    # that we've reached the creep position, we return false.
    while True:
        if next_pos.x == creep_pos.x and next_pos.y == creep_pos.y:
            return False

        dir = next_pos.getDirectionTo(creep_pos)

        if dir == TOP:
            next_pos.y -= 1
        elif dir == TOP_RIGHT:
            next_pos.x += 1
            next_pos.y -= 1
        elif dir == RIGHT:
            next_pos.x += 1
        elif dir == BOTTOM_RIGHT:
            next_pos.x += 1
            next_pos.y -= 1
        elif dir == BOTTOM:
            next_pos.x -= 1
            next_pos.y += 1
        elif dir == BOTTOM_LEFT:
            next_pos.x -= 1
            next_pos.y += 1
        elif dir == LEFT:
            next_pos.x -= 1
        elif dir == TOP_LEFT:
            next_pos.y -= 1
            next_pos.x -= 1
        else:
            print("Unknown result from pos.getDirectionTo(): {}".format(dir))
            return False

        creeps = next_pos.lookFor(LOOK_CREEPS)
        if len(creeps):
            continue
        terrain = next_pos.lookFor(LOOK_TERRAIN)
        if (terrain[0].type & TERRAIN_MASK_WALL == TERRAIN_MASK_WALL
            or terrain[0].type & TERRAIN_MASK_LAVA == TERRAIN_MASK_LAVA):
            continue

        structures = next_pos.lookFor(LOOK_STRUCTURES)
        if len(structures):
            continue

        return True


def go_to_depot(creep):
    flag = Game.flags["depot"]
    if flag:
        move_to_path(creep, flag, True)
    else:
        move_to_path(creep, Game.spawns[0], True)
