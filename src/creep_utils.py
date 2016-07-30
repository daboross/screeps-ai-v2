import context
from constants import *
from screeps_constants import *

__pragma__('noalias', 'name')

# ***
# SPAWNING
# ***

role_requirements = [
    [role_spawn_fill, 2, creep_base_worker],
    [role_dedi_miner, -10, creep_base_big_harvester],
    [role_spawn_fill, 4, creep_base_worker],
    [role_upgrader, 1, creep_base_worker],
    [role_tower_fill, 2, creep_base_worker],
    [role_remote_miner, -11, creep_base_full_miner],
    # TODO: dynamic creep base based on mining operation!
    [role_remote_hauler, -12, creep_base_hauler],
    [role_upgrader, 2, creep_base_worker],
    [role_spawn_fill, 6, creep_base_worker],
    [role_builder, 6, creep_base_worker],
]


def role_count(role):
    if not Memory.role_counts:
        count_roles()
    count = Memory.role_counts[role]
    if not count and count != 0:
        count = 0
        Memory.role_counts[role] = 0
    return count


def get_role_name(existing_base=None):
    for role, ideal, base in role_requirements:
        if existing_base and existing_base != base:
            continue
        if ideal == -10:
            ideal = context.room().target_big_harvester_count
        elif ideal == -11:
            ideal = context.room().target_remote_miner_count
        elif ideal == -12:
            ideal = context.room().target_remote_hauler_count
        current = role_count(role)
        if current < ideal or (not current and ideal > 0):
            print("[roles] Found role {}! {} < {}".format(role, current, ideal))
            return base, role
        else:
            print("[roles] We're good with {} {}! (ideal={}, actual={})".format(ideal, role, ideal, current))
    if existing_base == creep_base_worker:
        print("[roles] No new roles needed! Existing worker set as builder.")
        return creep_base_worker, "builder"
    elif existing_base == creep_base_big_harvester:
        print("[roles] No new roles needed! Existing big_harvester set as big_harvester")
        return creep_base_big_harvester, "big_harvester"
    else:
        print("[roles] No new roles needed!")
        return None, None


def find_base(creep):
    part_counts = _.countBy(creep.body, lambda p: p.type)
    if part_counts[MOVE] > part_counts[WORK]:
        base = creep_base_worker
    else:
        base = creep_base_big_harvester
    print("[roles] Body {} found to be {}.".format(JSON.stringify(part_counts), base))
    return base


# ***
# RANDOM STUFF
# ***

room_regex = __new__(RegExp("(W|E)([0-9]{1,2})(N|S)([0-9]{1,2})"))


def inter_room_difference(from_room, to_room):
    """
    :param from_room: The name of the room to get from.
    :param to_room: The name of the room to get to.
    :return: (x_difference, y_difference)
    :type from_room: Room
    :type to_room: Room
    :rtype: (int, int)
    """
    # example room string: W47N26 or E1S1 or E1N1
    pos1 = parse_room_to_xy(from_room)
    pos2 = parse_room_to_xy(to_room)
    if not pos1 or not pos2:
        return None
    x1, y1 = pos1
    x2, y2 = pos2
    return (x2 - x1, y2 - y1)


def squared_distance(xy1, xy2):
    """
    Gets the squared distance between two x, y positions
    :param xy1: a tuple (x, y)
    :param xy2: a tuple (x, y)
    :return: an integer, the squared linear distance
    """
    x_diff = (xy1[0] - xy2[0])
    y_diff = (xy1[1] - xy2[1])
    return x_diff * x_diff + y_diff * y_diff


def parse_room_to_xy(room_name):
    matches = room_regex.exec(room_name)
    if not matches:
        return None
    if matches[1] == "W":
        x = -int(matches[2])
    else:
        x = +int(matches[2])
    if matches[3] == "N":
        y = -int(matches[4])
    else:
        y = +int(matches[4])
    return x, y


# ***
# CONSISTENCY
# ***

def reassign_roles():
    for room in context.hive().my_rooms:
        reassign_room_roles(room)


def reassign_room_roles(room):
    if role_count("harvester") < 4 and role_count("big_harvester") < room.target_big_harvester_count:
        num = 0
        for creep in room.creeps:
            memory = creep.memory
            if memory.role != "big_harvester":
                memory.role = "harvester"
            num += 1
            if num > 4:
                break
        count_room_roles(room)


def count_roles():
    for room in context.hive().my_rooms:
        count_room_roles(room)


def count_room_roles(room):
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


def clear_memory(target_mind):
    """
    :type target_mind: hivemind.TargetMind
    """
    smallest_ticks_to_live = 2000
    for name in Object.keys(Memory.creeps):
        creep = Game.creeps[name]
        if not creep:
            role = Memory.creeps[name].role
            if role:
                print("[{}] {} died".format(name, role))

            if role == role_dedi_miner:
                source_id = target_mind._get_existing_target_id(target_big_source, name)
                if source_id:
                    del Memory.big_harvesters_placed[source_id]
                else:
                    print("[{}] WARNING! clear_memory couldn't find placed source for big harvester!".format(name))
            elif role == role_remote_miner:
                flag = target_mind._get_existing_target_from_name(name, target_remote_mine_miner)
                if flag.memory.remote_miner_targeting == name:
                    del flag.memory.remote_miner_targeting
                    del flag.memory.remote_miner_death_tick
            target_mind._unregister_all(name)

            del Memory.creeps[name]
        elif creep.ticksToLive < smallest_ticks_to_live:
            smallest_ticks_to_live = creep.ticksToLive
    Memory.meta.clear_next = Game.time + smallest_ticks_to_live + 3  # some leeway
