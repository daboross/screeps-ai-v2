import hivemind
from base import *

__pragma__('noalias', 'name')

# ***
# SPAWNING
# ***

creep_base_worker = "worker"
creep_base_big_harvester = "big_harvester"

# TODO: the third argument of each subarray isn't used at all.
role_requirements = [
    ["harvester", 2, creep_base_worker],
    # TODO: 2 is currently hardcoded for my map.
    ["big_harvester", 2, creep_base_big_harvester],
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
# CONSISTENCY
# ***

def reassign_roles():
    # TODO: hardcoded 2 here
    if role_count("harvester") < 4 and role_count("big_harvester") < 2:
        num = 0
        for name in Object.keys(Memory.creeps):
            memory = Memory.creeps[name]
            if memory.role != "big_harvester":
                memory.role = "harvester"
            num += 1
            if num > 4:
                break
        count_roles()


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


def clear_memory(target_mind):
    """
    :type target_mind: hivemind.TargetMind
    """
    smallest_ticks_to_live = 2000
    for name in Object.keys(Memory.creeps):
        creep = Game.creeps[name]
        if not creep:
            # Do spawn more now! If we had reached max creeps.
            del Memory.no_more_spawning
            role = Memory.creeps[name].role
            if role:
                print("[{}] {} died".format(name, role))

            if role == "big_harvester":
                source_id = target_mind._get_existing_target_id(hivemind.target_big_source, name)
                if source_id:
                    del Memory.big_harvesters_placed[source_id]
                else:
                    print("[{}] WARNING! clear_memory couldn't find placed source for big harvester!".format(name))
            target_mind._unregister_all(name)

            del Memory.creeps[name]
        elif creep.ticksToLive < smallest_ticks_to_live:
            smallest_ticks_to_live = creep.ticksToLive
    Memory.meta.clear_next = Game.time + smallest_ticks_to_live + 3  # some leeway
