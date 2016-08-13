import random

from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def run(hive):
    """
    :type hive: control.hivemind.HiveMind
    """
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

        mem = Memory.tower.towers_memory[tower_id]

        room = hive.get_room(tower.room.name)

        if mem.alert:
            if mem.alert_for is undefined:
                mem.alert_for = 0
            mem.alert_for += random.randint(0, 2)
            target = room.find_closest_by_range(FIND_HOSTILE_CREEPS, tower.pos)
            if random.random() < 0.5 - mem.alert_for / 5.0 and tower.pos.getRangeTo(target) > 7:
                target = None
            if not target:
                if mem.alert_for >= 20:
                    mem.alert = False
                    no_longer_alert_rooms.add(room)

            if mem.alert_for >= 50 or not target:
                targets = _.filter(room.find(FIND_MY_CREEPS), lambda creep: creep.hits < creep.hitsMax)
                if len(targets):
                    tower.heal(targets[0])
                continue
            elif target:
                tower.attack(target)
        else:
            targets = room.find(FIND_HOSTILE_CREEPS)
            if len(targets):
                mem.alert = True
                mem.alert_for = 0
                tower.attack(targets[0])
                new_alert_rooms.add(room)
                continue

            targets = _.filter(room.find(FIND_MY_CREEPS), lambda creep: creep.hits < creep.hitsMax)
            if len(targets):
                tower.heal(targets[0])

    for room in no_longer_alert_rooms:
        for rampart in _.filter(room.find(FIND_STRUCTURES), {"structureType": STRUCTURE_RAMPART}):
            # don't set ramparts over storage/roads to public.
            if not _.find(room.find_at(FIND_STRUCTURES, rampart.pos), lambda s: s.structureType != STRUCTURE_RAMPART \
                    and s.structureType != STRUCTURE_ROAD):
                rampart.setPublic(True)

    for room in new_alert_rooms:
        for rampart in _.filter(room.find(FIND_STRUCTURES), {"structureType": STRUCTURE_RAMPART}):
            rampart.setPublic(False)


run = profiling.profiled(run, "tower.run")
