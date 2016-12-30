from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def start_of_tick_check():
    if Memory.deathwatch:
        for name, room_name in Memory.deathwatch:
            if name not in Game.creeps:
                print('[death][{}] {}, a {}, died.'.format(name, _.get(Memory, ['creeps', name, 'role'], 'creep'),
                                                           room_name))
                meta = _.get(Memory, ['rooms', room_name, 'meta'])
                if meta:
                    meta.clear_next = 0

    Memory.deathwatch = []


def mark_creeps(room):
    """
    :type room: control.hivemind.RoomMind
    """
    hostiles = room.defense.dangerous_hostiles()
    count = len(hostiles)
    if count > 3:
        for creep in room.find(FIND_MY_CREEPS):
            Memory.deathwatch.append([creep.name, creep.memory.home])
    else:
        for creep in room.find(FIND_MY_CREEPS):
            if _.some(hostiles, lambda h: movement.chebyshev_distance_room_pos(h, creep) < 4):
                Memory.deathwatch.append([creep.name, creep.memory.home])
