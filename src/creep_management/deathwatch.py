from constants import INVADER_USERNAME
from jstools.screeps_constants import *
from utilities import movement

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def start_of_tick_check():
    if Memory.deathwatch:
        for name, room_name, threats in Memory.deathwatch:
            if name not in Game.creeps:
                if not _.every(threats, lambda t: t == INVADER_USERNAME or t == 'unknown'):
                    threats = ['an invader' if t == INVADER_USERNAME else t for t in threats]
                    msg = '[death] {}, a {} of {}, died, likely at the hands of {}.'.format(
                        name, _.get(Memory, ['creeps', name, 'role'], 'creep'),
                        room_name,
                        ("{} or {}".format(', '.join(threats[:len(threats) - 1]),
                                           threats[len(threats) - 1])
                         if len(threats) > 1 else threats[0])
                    )
                    print(msg)
                    Game.notify(msg)
                meta = _.get(Memory, ['rooms', room_name, 'meta'])
                if meta:
                    meta.clear_next = 0

    Memory.deathwatch = []


def mark_creeps(room):
    """
    :type room: rooms.room_mind.RoomMind
    """
    all_hostiles = room.room.find(FIND_HOSTILE_CREEPS)
    hostiles = []
    for creep in all_hostiles:
        if creep.hasActiveOffenseBodyparts():
            hostiles.append(creep)
    count = len(hostiles)
    if count > 3:
        for creep in room.find(FIND_MY_CREEPS):
            Memory.deathwatch.append([
                creep.name, creep.memory.home,
                _(hostiles).map(lambda h: _.get(h, ['owner', 'username'], 'unknown')).uniq().value()
            ])
    elif count > 0:
        for creep in room.find(FIND_MY_CREEPS):
            if _.some(hostiles, lambda h: movement.chebyshev_distance_room_pos(h, creep) < 4):
                Memory.deathwatch.append([
                    creep.name, creep.memory.home,
                    _(hostiles).filter(lambda h: movement.chebyshev_distance_room_pos(h, creep) < 4)
                        .map(lambda h: _.get(h, ['owner', 'username'], 'unknown')).uniq().value()
                ])
