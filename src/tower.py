import random

from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def run(room):
    """
    :type room: control.hivemind.RoomMind
    """
    if not room.mem.alert and Game.time % 3 == 1:
        targets = room.find(FIND_HOSTILE_CREEPS)
        if len(targets):
            for rampart in _.filter(room.find(FIND_STRUCTURES), {"structureType": STRUCTURE_RAMPART}):
                rampart.setPublic(False)
            room.mem.alert = True
    if not room.mem.alert:
        damaged = _.filter(room.find(FIND_MY_CREEPS), lambda creep: creep.hits < creep.hitsMax)
        if damaged:
            for tower, target in zip(_.filter(room.find(FIND_MY_STRUCTURES), {'structureType': STRUCTURE_TOWER}),
                                     damaged):
                tower.heal(target)
        return

    room.mem.alert_for = (room.mem.alert_for or 0) + random.randint(0, 2)

    if not len(room.find(FIND_HOSTILE_CREEPS)):
        for rampart in _.filter(room.find(FIND_STRUCTURES), {"structureType": STRUCTURE_RAMPART}):
            # don't set ramparts over storage/roads to public.
            if not _.find(room.find_at(FIND_STRUCTURES, rampart.pos),
                          lambda s: s.structureType != STRUCTURE_RAMPART
                          and s.structureType != STRUCTURE_ROAD):
                rampart.setPublic(True)
        room.mem.alert = False
        del room.mem.alert_for
        return

    towers = _.filter(room.find(FIND_MY_STRUCTURES), {'structureType': STRUCTURE_TOWER})
    hostiles = room.find(FIND_HOSTILE_CREEPS)

    if room.mem.alert_for >= 50:
        hostiles = _.filter(hostiles, lambda c: c.owner.username == "Invader")
        if not len(hostiles):
            return

    for tower in towers:
        index = random.randint(0, len(hostiles))
        hostile = hostiles[index]
        tower.attack()
        print("[{}] Attacking {} (i: {})".format(room.room_name, hostile, index))


run = profiling.profiled(run, "tower.run")
