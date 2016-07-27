import hivemind
from base import *

__pragma__('noalias', 'name')

# ***
# SPAWNING
# ***

creep_base_base = "base"
creep_base_big_harvester = "big_harvester"

# TODO: the third argument of each subarray isn't used at all.
role_requirements = [
    ["harvester", 2, creep_base_base],
    # TODO: 2 is currently hardcoded for my map.
    ["big_harvester", 2, creep_base_big_harvester],
    ["harvester", 4, creep_base_base],
    ["upgrader", 1, creep_base_base],
    ["tower_fill", 2, creep_base_base],
    ["upgrader", 2, creep_base_base],
    ["harvester", 6, creep_base_base],
    ["builder", 6, creep_base_base]
]


def role_count(role):
    if not Memory.role_counts:
        count_roles()
    count = Memory.role_counts[role]
    if not count and count != 0:
        count = 0
        Memory.role_counts[role] = 0
    return count


def get_role_name():
    for role, count in role_requirements:
        if Memory.role_counts[role] < count:
            return role
    return None


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
    Memory.clear_memory_next = Game.time + smallest_ticks_to_live + 3  # some leeway
