from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def root():
    if not Memory.cache:
        Memory.cache = {}
    return Memory.cache


def get(key):
    r = root()
    if key in r and r[key].d > Game.time:
        return r[key].v
    else:
        return None


def set(key, value, ttl):
    r = root()
    r[key] = {'v': value, 'd': Game.time + ttl}


def cleanup():
    r = root()
    for key in Object.keys(r):
        if r[key].d <= Game.time:
            del r[key]
