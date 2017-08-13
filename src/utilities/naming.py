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


def random_digits():
    # type: () -> str
    # JavaScript trickery here - TODO: pythonize
    return __pragma__('js', '{}', 'Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)')
