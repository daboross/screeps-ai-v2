import creep_utils
from base import *

__pragma__('noalias', 'name')


def run(creep):
    source = creep_utils.get_spread_out_target(creep, "big_source", lambda: creep.room.find(FIND_SOURCES))
    if not source:
        print("[{}] No sources found.".format(creep.name))

    result = creep.harvest(source)
    if result == ERR_NOT_IN_RANGE:
        creep_utils.move_to_path(creep, source)
    elif result == OK:
        if Memory.big_harvesters_placed:
            Memory.big_harvesters_placed[source.id] = creep.name
        else:
            Memory.big_harvesters_placed = {
                source.id: creep.name
            }
    else:
        print("[{}] Unknown result from creep.harvest({}): {}".format(
            creep.name, source, result
        ))
