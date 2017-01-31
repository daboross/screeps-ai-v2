from constants import global_cache_mining_paths_suffix, max_repath_mine_roads_every
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def root():
    if not Memory.cache:
        Memory.cache = {}
    return Memory.cache


def get(key):
    r = root()
    if key in r and r[key].d > Game.time:
        r[key].l = Game.time
        return r[key].v
    else:
        return None


def has(key):
    r = root()
    return key in r


def set(key, value, ttl):
    r = root()
    r[key] = {'v': value, 'd': Game.time + ttl, 'l': Game.time}


def rem(key):
    r = root()
    del r[key]


def cleanup():
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
    if not name:
        return
    for key in Object.keys(Memory.cache):
        if key.includes(name):
            del Memory.cache[key]
            print("[clear_global_cache] Cleared {}.".format(key))
