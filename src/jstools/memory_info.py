from typing import Any, Dict, Optional

from empire.honey import _path_cached_data_key_full_path, _path_cached_data_key_length, _path_cached_data_key_metadata
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


def analyse_memory(path = None):
    # type: (Optional[str]) -> None
    mem = Memory
    if path is not None:
        mem = _.get(mem, path)
    total = 0
    for key, submem in _.pairs(mem):
        amount = count_total_keys(submem)
        total += amount
        print("under {}: {}".format(key, amount))
    print("total: {}".format(total))


def count_total_keys(mem):
    # type: (Dict[str, Any]) -> int
    total_count = 0
    for key, submem in _.pairs(mem):
        total_count += 1
        if _.isObject(submem):
            total_count += count_total_keys(submem)
    return total_count


def cache_stats():
    # type: () -> str
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
