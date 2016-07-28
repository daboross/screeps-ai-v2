# from base import *
# from tools import decorate
#
# __pragma__('noalias', 'name')
#
# # profiler = require("screeps-profiler")
#
# profiled = []
#
#
# def profile_method(cls, func_name):
#     """
#     Sets up profiling on a class method with the name func_name
#     :param cls: The class to profile
#     :param func_name: The name of the function to profile
#     """
#     # name = "{}.{}".format(cls.__name__, func_name)
#     # profiled.append(name)
#     # decorate(cls, func_name, profile_decorator(name))
#
#
# def profile_decorator(name):
#     def decorator(func):
#         return profiler.registerFN(func, name)
#
#     return decorator
#
#
# def profiled_func(func, name):
#     return profiler.registerFN(func, name)
#
#
# def init():
#     profiler.enable()
#
#
# def print_profiled():
#     print(JSON.stringify(profiled))
#
#
# Game.print_profiled = print_profiled
