from base import *

__pragma__('noalias', 'name')


def run():
    current_time = Game.time
    if not Memory.tower:
        Memory.tower = {
            "towers_memory": {},
        }

    if not Memory.tower.last_recheck or current_time > Memory.tower.last_recheck + 500:
        Memory.tower.last_recheck = current_time
        towers = []
        for id in Object.keys(Game.structures):
            struct = Game.structures[id]
            if struct.structureType == STRUCTURE_TOWER and struct.my:
                towers.append(id)

        Memory.tower.towers = towers

    for id in Memory.tower.towers:
        tower = Game.getObjectById(id)
        if not Memory.tower.towers_memory[id]:
            Memory.tower.towers_memory[id] = {}

        tower.memory = Memory.tower.towers_memory[id]

        if tower.memory.alert:
            target = tower.pos.findClosestByRange(FIND_HOSTILE_CREEPS)
            if not target:
                tower.memory.alert = False
                continue
            tower.attack(target)
        else:
            targets = tower.room.find(FIND_HOSTILE_CREEPS)
            if len(targets):
                tower.memory.alert = True
                tower.attack(targets[0])
                continue

            if tower.energy < tower.energyCapacity / 2:
                continue

            target = get_new_repair_target(tower)

            if target:
                execute_repair_target(tower, target)
                continue


def get_new_repair_target(tower):
    def find_list():
        return tower.room.find(FIND_STRUCTURES, {
            "filter": lambda structure: (
                (structure.my != False) and (structure.htis < structure.hitsMax) and (structure.hits < 350000) and (
                    structure.pos.inRangeTo(tower.pos, 10))
            )
        })

    return get_spread_out_target(tower, "structure_repair", find_list)


def execute_repair_target(tower, target):
    if not target or target.hits >= target.hitsMax or target.hits >= 400000:
        untarget_spread_out_target(tower, "structure_repair")


def get_spread_out_target(tower, resource, find_list, limit_by=None, true_limit=False):
    if not tower.memory.targets:
        tower.memory.targets = {}

    if tower.memory.targets[resource]:
        target = Game.getObjectById(tower.memory.targets[resource])
        if target:
            # don't return null targets
            return target
        else:
            print("[{}] Retargetting {}!".format(tower.name, resource))
            id = tower.memory.targets[resource]
            del tower.memory.targets[resource]
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
            tower.memory.targets[resource] = id
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
        tower.memory.targets[resource] = min_target_id
        return min_target


def untarget_spread_out_target(tower, resource):
    if tower.memory.targets:
        id = tower.memory.targets[resource]
        if id:
            if (Memory.targets_used and Memory.targets_used[resource] and
                    Memory.targets_used[resource][id]):
                Memory.targets_used[resource][id] -= 1

            del tower.memory.targets[resource]
