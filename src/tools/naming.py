from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def random_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
