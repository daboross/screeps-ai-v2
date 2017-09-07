from typing import Any, Optional

from constants import global_cache_mining_paths_suffix, max_repath_mine_roads_every
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def root():
    # type: () -> Any
    if not Memory.cache:
        Memory.cache = {}
    return Memory.cache


def get(key):
    # type: (str) -> Optional[_MemoryValue]
    r = root()
    if key in r and r[key].d > Game.time:
        r[key].l = Game.time
        return r[key].v
    else:
        return None


def get_100_slack(key):
    # type: (str) -> Optional[_MemoryValue]
    r = root()
    if key in r and r[key].d > Game.time + 100:
        r[key].l = Game.time
        return r[key].v
    else:
        return None


def has(key):
    # type: (str) -> bool
    r = root()
    return key in r


# noinspection PyShadowingBuiltins
def set(key, value, ttl):
    # type: (str, Any, int) -> None
    r = root()
    r[key] = {'v': value, 'd': Game.time + ttl, 'l': Game.time}


def rem(key):
    # type: (str) -> None
    r = root()
    del r[key]


def cleanup():
    # type: () -> None
    r = root()
    for key in Object.keys(r):
        if r[key].d <= Game.time:
            del r[key]
        else:
            if key.includes("cost_matrix"):
                min_last_use = Game.time - max_repath_mine_roads_every * 1.2
            elif key.endswith(global_cache_mining_paths_suffix):
                min_last_use = Game.time - max_repath_mine_roads_every
            else:
                min_last_use = Game.time - CREEP_LIFE_TIME
            if r[key].l < min_last_use:
                del r[key]


def clear_values_matching(name):
    # type: (str) -> None
    if not name:
        return
    for key in Object.keys(Memory.cache):
        if key.includes(name):
            del Memory.cache[key]
            print("[clear_global_cache] cleared memory value: {}".format(key))
