import random

from tools import profiling
from utilities.screeps_constants import *

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
        for tower_id in Object.keys(Game.structures):
            struct = Game.structures[tower_id]
            if struct.structureType == STRUCTURE_TOWER and struct.my:
                towers.append(tower_id)

        Memory.tower.towers = towers

    new_alert_rooms = set()
    no_longer_alert_rooms = set()
    for tower_id in Memory.tower.towers:
        tower = Game.getObjectById(tower_id)
        if not Memory.tower.towers_memory[tower_id]:
            Memory.tower.towers_memory[tower_id] = {}

        tower.memory = Memory.tower.towers_memory[tower_id]

        if tower.memory.alert:
            if tower.memory.alert_for is undefined:
                tower.memory.alert_for = 0
            tower.memory.alert_for += random.randint(0, 2)
            if Memory.meta.friends and len(Memory.meta.friends):
                target = tower.pos.findClosestByRange(FIND_HOSTILE_CREEPS, {
                    "filter": lambda c: c.owner.username not in Memory.meta.friends
                })
            else:
                target = tower.pos.findClosestByRange(FIND_HOSTILE_CREEPS)
                if random.random() < 0.5 - tower.memory.alert_for / 5.0 and tower.pos.getRangeTo(target) > 7:
                    target = None
            if not target:
                if tower.memory.alert_for >= 20:
                    tower.memory.alert = False
                    no_longer_alert_rooms.add(tower.room)

            if tower.memory.alert_for >= 50 or not target:
                targets = tower.room.find(FIND_MY_CREEPS, {
                    "filter": lambda creep: creep.hits < creep.hitsMax
                })
                if len(targets):
                    tower.heal(targets[0])
                continue
            elif target:
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
                tower.memory.alert_for = 0
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


run = profiling.profiled(run, "tower.run")
