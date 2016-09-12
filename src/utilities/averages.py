from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def start_main_loop():
    volatile_cache.volatile().set("main_loop_start_cpu", Game.cpu.getUsed())


def end_main_loop():
    if not Memory.cpu_usage:
        Memory.cpu_usage = {"without-cl": [], "with-cl": []}
    no_cl_list = Memory.cpu_usage["without-cl"]
    if no_cl_list is undefined:
        Memory.cpu_usage["without-cl"] = []
    elif len(no_cl_list) > 1200:
        Memory.cpu_usage["without-cl"] = no_cl_list.splice(len(no_cl_list) - 1000, Infinity)
    with_cl_list = Memory.cpu_usage["with-cl"]
    if with_cl_list is undefined:
        Memory.cpu_usage["with-cl"] = []
    elif len(with_cl_list) > 1200:
        Memory.cpu_usage["with-cl"] = with_cl_list.splice(len(with_cl_list) - 1000, Infinity)

    Memory.cpu_usage["without-cl"].push(Game.cpu.getUsed() - volatile_cache.volatile().get("main_loop_start_cpu"))
    Memory.cpu_usage["with-cl"].push(Game.cpu.getUsed())


def get_average(with_cl=True):
    if with_cl:
        cpu_per_tick = Memory.cpu_usage and Memory.cpu_usage["with-cl"] or []
    else:
        cpu_per_tick = Memory.cpu_usage and Memory.cpu_usage["without-cl"] or []
    if len(cpu_per_tick):
        sum = 0
        for x in cpu_per_tick:
            sum += x
        return sum / len(cpu_per_tick)
