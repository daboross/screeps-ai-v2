from base import *
from tools import decorate

__pragma__('noalias', 'name')

profiler = require("screeps-profiler")


def profile_method(cls, func_name):
    """
    Sets up profiling on a class method with the name func_name.

    :param cls: The class to profile
    :param func_name: The name of the function to profile
    """
    name = "{}.{}".format(cls.__name__, func_name)
    decorate(cls, func_name, _profiled(name))


_DEFAULT_IGNORED = []
ROLE_BASE_IGNORE = ["harvesting", "name"]


def profile_class(cls, ignored=None):
    """
    Sets up profiling on all methods in a given class.

    :param cls: The class to profile
    :param ignored: List of names to ignore
    """
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

    def deco(func):
        return profiler.registerFN(func, name)

    return deco


def init():
    profiler.enable()
