from typing import Any, TYPE_CHECKING

from jstools.js_set_map import new_map, new_set
from jstools.screeps import *

if TYPE_CHECKING:
    from jstools.js_set_map import JSMap, JSSet

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

_volatile_memory = None
_tick_stored_for = 0


def volatile():
    # type: () -> JSMap[str, Any]
    global _tick_stored_for
    global _volatile_memory
    if _volatile_memory is None or _tick_stored_for < Game.time:
        _tick_stored_for = Game.time
        _volatile_memory = new_map()
    return _volatile_memory


def mem(key):
    # type: (str) -> JSMap[Any, Any]
    """
    :rtype: jstools.js_set_map.JSMap
    """
    v = volatile()
    if not v.has(key):
        v.set(key, new_map())
    return v.get(key)


def setmem(key):
    # type: (str) -> JSSet[Any]
    """
    :rtype: jstools.js_set_map.JSSet
    """
    v = volatile()
    if not v.has(key):
        v.set(key, new_set())
    return v.get(key)


def submem(key1, key2):
    # type: (str, str) -> JSMap[Any, Any]
    """
    :rtype: jstools.js_set_map.JSMap
    """
    v = volatile()
    if not v.has(key1):
        v.set(key1, new_map([(key2, new_map())]))
    elif not v.get(key1).has(key2):
        v.get(key1).set(key2, new_map())
    return v.get(key1).get(key2)
