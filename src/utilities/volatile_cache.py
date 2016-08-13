from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_volatile_memory = None
_tick_stored_for = 0


def volatile():
    global _tick_stored_for
    global _volatile_memory
    if _tick_stored_for < Game.time:
        _tick_stored_for = Game.time
        _volatile_memory = new_map()
    return _volatile_memory


def mem(key):
    v = volatile()
    if key not in v:
        v[key] = new_map()
    return v[key]


def submem(key1, key2):
    v = volatile()
    if key1 not in v:
        v[key1] = new_map([[key2, new_map()]])
        v[key1][key2] = new_map()
    elif key2 not in v[key1]:
        v[key1][key2] = new_map()
    return v[key1][key2]
