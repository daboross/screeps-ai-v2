from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def start_main_loop():
    volatile_cache.volatile().set("main_loop_start_cpu", Game.cpu.getUsed())


def clean_and_prepare_memory_array(name):
    array = Memory.cpu_usage[name]
    if array is undefined:
        Memory.cpu_usage[name] = []
    elif len(array) > 1200:
        Memory.cpu_usage[name] = array.slice(len(array) - 1000)


def end_main_loop():
    if not Memory.cpu_usage:
        Memory.cpu_usage = {}
    clean_and_prepare_memory_array("with-cl")
    clean_and_prepare_memory_array("without-cl")
    clean_and_prepare_memory_array("creep-count")
    Memory.cpu_usage["without-cl"].push(Game.cpu.getUsed() - volatile_cache.volatile().get("main_loop_start_cpu"))
    Memory.cpu_usage["with-cl"].push(Game.cpu.getUsed())
    Memory.cpu_usage["creep-count"].push(_.size(Game.creeps))


def get_average(name, count=None):
    tick_array = Memory.cpu_usage and Memory.cpu_usage[name] or []
    if count and count < len(tick_array):
        tick_array = tick_array.slice(len(tick_array) - count)
    if len(tick_array):
        sum = 0
        for x in tick_array:
            sum += x
        return sum / len(tick_array)


def get_average_visual():
    # TODO: do this better
    with_cl = get_average("with-cl")
    without_cl = get_average("without-cl")
    creeps = get_average("creep-count")
    with_cl50 = get_average("with-cl", 50)
    without_cl50 = get_average("without-cl", 50)
    creeps50 = get_average("creep-count", 50)
    return (
        "\nReport:"
        "\n1000 ticks:"
        "\nAvg CPU: {}"
        "\nAvg Runtime: {}"
        "\nAvg creep #: {}"
        "\nAvg CPU/creep: {}"
        "\n50 ticks:"
        "\nAvg CPU: {}"
        "\nAvg Runtime: {}"
        "\nAvg creep #: {}"
        "\nAvg CPU/creep: {}".format(
            with_cl,
            without_cl,
            creeps,
            with_cl / creeps,
            with_cl50,
            without_cl50,
            creeps50,
            with_cl50 / creeps50
        )
    )
