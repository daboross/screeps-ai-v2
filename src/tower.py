from screeps_constants import *

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

            targets = tower.room.find(FIND_MY_CREEPS, {
                "filter": lambda creep: (
                    creep.hits < creep.hitsMax
                )
            })
            if len(targets):
                tower.heal(targets[0])
