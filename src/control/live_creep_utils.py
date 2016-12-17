import context
import creep_wrappers
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def replacement_time(creep, room):
    """
    :type creep: Creep
    :type room: control.hivemind.RoomMind
    """
    if 'get_replacement_time' not in creep:
        if 'wrapped' in creep:
            creep = creep.wrapped
        else:
            creep = creep_wrappers.wrap_creep(room.hive_mind, room.hive_mind.target_mind, room, creep)
            if not creep:
                return Infinity
    return creep.get_replacement_time()
