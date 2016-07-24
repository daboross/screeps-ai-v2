from base import *

__pragma__('noalias', 'name')


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


def reassign_roles():
    # TODO: hardcoded 2 here
    if role_count("harvester") < 4 and role_count("big_harvester") < 2:
        for name in Object.keys(Memory.creeps):
            memory = Memory.creeps[name]
            if memory.role != "big_harvester":
                memory.role = "harvester"
        count_roles()


def clear_memory(target_mind):
    """
    :type target_mind: hivemind.TargetMind
    """
    for name in Object.keys(Memory.creeps):
        if not Game.creeps[name]:
            role = Memory.creeps[name].role
            if role:
                print("[{}] {} died".format(name, role))

            if role == "big_harvester":
                del Memory.big_harvesters_placed[Memory.creeps[name].targets["big_source"]]

            target_mind._unregister_all(name)

            del Memory.creeps[name]
