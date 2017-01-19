from empire.honey import _path_cached_data_key_full_path, _path_cached_data_key_length, _path_cached_data_key_metadata
from jstools.screeps import *

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


def cache_stats():
    total_path_v1 = 0
    total_path_v2 = 0
    total_path_v3 = 0
    total_path_other = 0
    total_cost_matrix = 0
    total_other = 0
    for key in Object.keys(Memory.cache):
        if key.startswith('path_'):
            value = Memory.cache[key].v
            if _path_cached_data_key_full_path in value:
                total_path_v1 += 1
            elif _path_cached_data_key_length in value:
                total_path_v2 += 1
            elif _path_cached_data_key_metadata in value:
                total_path_v3 += 1
            else:
                total_path_other += 1
        elif key.includes('cost_matrix'):
            total_cost_matrix += 1
        else:
            total_other += 1
    result = ["Cache Stats:"]
    if total_path_v1 > 0:
        result.append('Version 1 Paths: {}'.format(total_path_v1))
    if total_path_v2 > 0:
        result.append('Version 2 Paths: {}'.format(total_path_v2))
    if total_path_v3 > 0:
        result.append('Version 3 Paths: {}'.format(total_path_v3))
    if total_path_other > 0:
        result.append('Other Paths: {}'.format(total_path_other))
    if total_cost_matrix > 0:
        result.append('Cost Matrices: {}'.format(total_cost_matrix))
    if total_other > 0:
        result.append('Other: {}'.format(total_other))
    return '\n'.join(result)
