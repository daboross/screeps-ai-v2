from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_volatile_memory = None
_tick_stored_for = 0


def volatile():
    global _tick_stored_for
    global _volatile_memory
    if _tick_stored_for < Game.time:
        _tick_stored_for = Game.time
        _volatile_memory = __new__(Map())
    return _volatile_memory


def mem(key):
    v = volatile()
    if key not in v:
        v[key] = {}
    return v[key]
