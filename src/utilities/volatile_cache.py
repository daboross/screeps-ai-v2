from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

_volatile_memory = None
_tick_stored_for = 0


def volatile():
    global _tick_stored_for
    global _volatile_memory
    if _volatile_memory is None or _tick_stored_for < Game.time:
        _tick_stored_for = Game.time
        _volatile_memory = new_map()
    return _volatile_memory


def mem(key):
    """
    :rtype: utilities.screeps_constants.JSMap
    """
    v = volatile()
    if not v.has(key):
        v.set(key, new_map())
    return v.get(key)


def setmem(key):
    """
    :rtype: utilities.screeps_constants.JSSet
    """
    v = volatile()
    if not v.has(key):
        v.set(key, new_set())
    return v.get(key)


def submem(key1, key2):
    """
    :rtype: utilities.screeps_constants.JSMap
    """
    v = volatile()
    if not v.has(key1):
        v.set(key1, new_map([[key2, new_map()]]))
    elif not v.get(key1).has(key2):
        v.get(key1).set(key2, new_map())
    return v.get(key1).get(key2)
