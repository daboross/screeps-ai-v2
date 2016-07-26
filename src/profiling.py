from base import *

__pragma__('noalias', 'name')

profiler = require("screeps-profiler")

decorated = []


def printem():
    print("Decorated {}".format(JSON.stringify(decorated)))


def profile(name):
    def decorator(func):
        decorated.append(name)
        return profiler.registerFN(func, name)

    return decorator


def profile_func(func, name):
    decorated.append(name)
    return profiler.registerFN(func, name)


def init():
    profiler.enable()
