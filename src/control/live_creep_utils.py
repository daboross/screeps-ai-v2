import creep_wrappers
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def replacement_time(creep):
    if creep.get_replacement_time is undefined:
        creep = creep_wrappers.wrap_creep(creep)
    return creep.get_replacement_time()
