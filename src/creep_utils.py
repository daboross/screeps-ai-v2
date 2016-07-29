import context
from base import *
from constants import creep_base_worker, creep_base_big_harvester, target_big_source

__pragma__('noalias', 'name')

# ***
# SPAWNING
# ***

role_requirements = [
    ["harvester", 2, creep_base_worker],
    ["big_harvester", -5, creep_base_big_harvester],
    ["harvester", 4, creep_base_worker],
    ["upgrader", 1, creep_base_worker],
    ["tower_fill", 2, creep_base_worker],
    ["upgrader", 2, creep_base_worker],
    ["harvester", 6, creep_base_worker],
    ["builder", 6, creep_base_worker]
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
        if ideal == -5:
            # TODO: better way to do this?
            ideal = context.room().target_big_harvester_count
        current = role_count(role)
        if current < ideal or (not current and ideal > 0):
            if (not existing_base) or existing_base == base:
                print("[roles] Found role {}! {} < {}".format(role, current, ideal))
                return base, role
            else:
                print("[roles] Found role {} didn't match existing base {}.".format(role, existing_base))
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


def parse_room_direction_to(room1, room2):
    """
    Parse the general direction from room1 to room2. This only works for directly adjecent rooms - longer paths are a
    TODO.
    :param room1: The room from
    :param room2: The room to
    :return: TOP, RIGHT, BOTTOM, LEFT constants, or None if rooms have the same location
    """
    # example room string: W47N26 or E1S1 or E1N1
    pos1 = parse_room_to_xy(room1)
    pos2 = parse_room_to_xy(room2)
    if not pos1 or not pos2:
        return None
    x1, y1 = pos1
    x2, y2 = pos2
    if x1 > x2:
        # room1 is to the right of room2
        return LEFT
    elif x1 < x2:
        return RIGHT
    elif y1 > y2:
        # room1 is below room2
        return TOP
    elif y2 < y1:
        return BOTTOM
    else:
        return None


def parse_room_to_xy(room_name):
    matches = room_regex.match(room_name)
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

            if role == "big_harvester":
                source_id = target_mind._get_existing_target_id(target_big_source, name)
                if source_id:
                    del Memory.big_harvesters_placed[source_id]
                else:
                    print("[{}] WARNING! clear_memory couldn't find placed source for big harvester!".format(name))
            target_mind._unregister_all(name)

            del Memory.creeps[name]
        elif creep.ticksToLive < smallest_ticks_to_live:
            smallest_ticks_to_live = creep.ticksToLive
    Memory.meta.clear_next = Game.time + smallest_ticks_to_live + 3  # some leeway
