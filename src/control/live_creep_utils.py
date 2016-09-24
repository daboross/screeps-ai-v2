import context
import creep_wrappers
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def replacement_time(creep):
    if 'get_replacement_time' not in creep:
        if 'wrapped' in creep:
            creep = creep.wrapped
        else:
            room = context.room()
            creep = creep_wrappers.wrap_creep(room.hive_mind, room.hive_mind.target_mind, room, creep)
            if not creep:
                return Infinity
    return creep.get_replacement_time()
