import random

from constants import INVADER_USERNAME
from tools import profiling
from utilities import movement
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
        if len(damaged):
            towers = _.filter(room.find(FIND_MY_STRUCTURES), {'structureType': STRUCTURE_TOWER})
            if not len(towers):
                return
            if len(damaged) > 1 and len(towers) > 1:
                for creep in _.sortBy(damaged, 'hits'):  # heal the highest health creeps first.
                    if len(towers) == 1:
                        towers[0].heal(creep)
                        break
                    elif len(towers) < 1:
                        break
                    else:
                        closest_distance = Infinity
                        closest_index = -1
                        for i in range(0, len(towers)):
                            distance = movement.distance_squared_room_pos(creep.pos, towers[i].pos)
                            if distance < closest_distance:
                                closest_index = i
                                closest_distance = distance
                        tower = towers.splice(closest_index, 1)[0]
                        tower.heal(creep)
            elif len(damaged) > 1:
                towers[0].heal(_.min(damaged, lambda c: movement.distance_squared_room_pos(c, towers[0])))
            else:
                towers[0].heal(damaged[0])
        return

    if 'alert_for' in room.mem:
        room.mem.alert_for += 1
    else:
        room.mem.alert_for = 0

    if not len(room.find(FIND_HOSTILE_CREEPS)):
        for rampart in _.filter(room.find(FIND_STRUCTURES), {"structureType": STRUCTURE_RAMPART}):
            # don't set ramparts over storage/roads to public.
            if not _.find(room.find_at(FIND_STRUCTURES, rampart.pos),
                          lambda s: s.structureType != STRUCTURE_RAMPART
                          and s.structureType != STRUCTURE_ROAD):
                rampart.setPublic(True)
        del room.mem.alert
        del room.mem.alert_for
        return

    towers = _.filter(room.find(FIND_MY_STRUCTURES), {'structureType': STRUCTURE_TOWER})
    hostiles = room.find(FIND_HOSTILE_CREEPS)

    if room.mem.alert_for >= 50:
        hostiles = _.filter(hostiles, lambda c: c.owner.username == INVADER_USERNAME)
        if not len(hostiles):
            return

    for tower in towers:
        hostile = hostiles[random.randint(0, len(hostiles) - 1)]
        tower.attack(hostile)


run = profiling.profiled(run, "tower.run")
