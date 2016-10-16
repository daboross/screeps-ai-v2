from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


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
                min_last_use = Game.time - 10000
            else:
                min_last_use = Game.time - 1500
            if r[key].l < min_last_use:
                del r[key]
