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

    new_alert_rooms = set()
    no_longer_alert_rooms = set()
    for id in Memory.tower.towers:
        tower = Game.getObjectById(id)
        if not Memory.tower.towers_memory[id]:
            Memory.tower.towers_memory[id] = {}

        tower.memory = Memory.tower.towers_memory[id]

        if tower.memory.alert:
            if Memory.meta.friends and len(Memory.meta.friends):
                target = tower.pos.findClosestByRange(FIND_HOSTILE_CREEPS, {
                    "filter": lambda c: c.owner.username not in Memory.meta.friends
                })
            else:
                target = tower.pos.findClosestByRange(FIND_HOSTILE_CREEPS)
            if not target:
                tower.memory.alert = False
                no_longer_alert_rooms.add(tower.room)
                continue
            tower.attack(target)
        else:
            if Memory.meta.friends and len(Memory.meta.friends):
                targets = tower.room.find(FIND_HOSTILE_CREEPS, {
                    "filter": lambda c: c.owner.username not in Memory.meta.friends
                })
            else:
                targets = tower.room.find(FIND_HOSTILE_CREEPS)
            if len(targets):
                tower.memory.alert = True
                tower.attack(targets[0])
                new_alert_rooms.add(tower.room)
                continue

            targets = tower.room.find(FIND_MY_CREEPS, {
                "filter": lambda creep: creep.hits < creep.hitsMax
            })
            if len(targets):
                tower.heal(targets[0])

    for room in no_longer_alert_rooms:
        for rampart in room.find(FIND_STRUCTURES, {"filter": {"structureType": STRUCTURE_RAMPART}}):
            rampart.setPublic(True)

    for room in new_alert_rooms:
        for rampart in room.find(FIND_STRUCTURES, {"filter": {"structureType": STRUCTURE_RAMPART}}):
            rampart.setPublic(False)
