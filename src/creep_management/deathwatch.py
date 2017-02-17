from constants import INVADER_USERNAME
from jstools.screeps import *
from utilities import movement

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def start_of_tick_check():
    if Memory.deathwatch:
        for name, home_name, threats, room_name in Memory.deathwatch:
            if name not in Game.creeps:
                if not _.every(threats, lambda t: t == INVADER_USERNAME or t == 'unknown'):
                    threats = ['an invader' if t == INVADER_USERNAME else t for t in threats]
                    msg = '[death][{}] {}, a {} of {}, died in {}, likely at the hands of {}.'.format(
                        Game.time,
                        name,
                        _.get(Memory, ['creeps', name, 'role'], 'creep'),
                        home_name,
                        room_name or "the universe",
                        ("{} or {}".format(', '.join(threats[:len(threats) - 1]),
                                           threats[len(threats) - 1])
                         if len(threats) > 1 else threats[0])
                    )
                    print(msg)
                    Game.notify(msg)
                meta = _.get(Memory, ['rooms', home_name, 'meta'])
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
                _(hostiles).map(lambda h: _.get(h, ['owner', 'username'], 'unknown')).uniq().value(),
                room.name,
            ])
    elif count > 0:
        for creep in room.find(FIND_MY_CREEPS):
            if _.some(hostiles, lambda h: movement.chebyshev_distance_room_pos(h, creep) < 4):
                Memory.deathwatch.append([
                    creep.name, creep.memory.home,
                    _(hostiles).filter(lambda h: movement.chebyshev_distance_room_pos(h, creep) < 4)
                        .map(lambda h: _.get(h, ['owner', 'username'], 'unknown')).uniq().value(),
                    room.name,
                ])
