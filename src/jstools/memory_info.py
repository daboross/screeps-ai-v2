from jstools.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def analyse_memory(path=None):
    mem = Memory
    if path is not None:
        mem = _.get(mem, path)
    for key, submem in _.pairs(mem):
        amount = count_total_keys(submem)
        print("Under {}: {}".format(key, amount))


def count_total_keys(mem):
    total_count = 0
    for key, submem in _.pairs(mem):
        total_count += 1
        if _.isObject(submem):
            total_count += count_total_keys(submem)
    return total_count
