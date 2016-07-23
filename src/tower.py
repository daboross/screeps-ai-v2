import creep_utils


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
                towers.push(id)

        Memory.tower.towers = towers

    for id in Memory.tower.towers:
        tower = Game.getObjectById(id)
        if not Memory.tower.towers_memory[id]:
            Memory.tower.towers_memory[id] = {}

        tower.memory = Memory.tower.towers_memory[id]

        if tower.memory.alert:
            target = tower.pos.findClosestByRange(FIND_HOSTILE_CREEPS)
            if not target:
                tower.memory.alert = false
                continue
            tower.attack(target)
        else:
            targets = tower.room.find(FIND_HOSTILE_CREEPS)
            if targets:
                tower.memory.alert = true
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

    return creep_utils.get_spread_out_target(tower, "structure_repair", find_list)


def execute_repair_target(tower, target):
    if not target or target.hits >= target.hitsMax or target.hits >= 400000:
        creep_utils.untarget_spread_out_target(tower, "structure_repair")
