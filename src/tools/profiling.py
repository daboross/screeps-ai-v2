from tools import decorate
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

module_profiler = None
enabled = False
initialized = False

if Memory.meta and Memory.meta.enable_profiling:
    enabled = True
else:
    enabled = False


def profile_method(cls, func_name):
    """
    Sets up profiling on a class method with the name func_name.

    :param cls: The class to profile
    :param func_name: The name of the function to profile
    """
    if not enabled:
        return
    if not initialized:
        init()
    name = "{}.{}".format(cls.__name__, func_name)
    decorate(cls, func_name, _profiled(name))


_DEFAULT_IGNORED = []


def profile_class(cls, ignored=None):
    """
    Sets up profiling on all methods in a given class.

    :param cls: The class to profile
    :param ignored: List of names to ignore
    """
    if not enabled:
        return
    if not initialized:
        init()
    if not ignored:
        ignored = _DEFAULT_IGNORED
    for func_name in dir(cls):
        if not func_name.startswith("__") and func_name not in ignored and \
                        typeof(cls[func_name]) == "function":
            profile_method(cls, func_name)


def _profiled(name):
    """
    Profiling decorator function.

    :param name: Name to call function in profiler
    :return: function which takes original_func and returns profiled_func
    """
    if not enabled:
        return lambda func: func
    if not initialized:
        init()

    def deco(func):
        return module_profiler.registerFN(func, name)

    return deco


def init():
    if enabled:
        global module_profiler
        global initialized
        module_profiler = require("screeps-profiler")
        module_profiler.enable()
        initialized = True


def wrap_main(main_func):
    if enabled:
        if not initialized:
            init()
        return module_profiler.wrap(main_func)
    else:
        return main_func
