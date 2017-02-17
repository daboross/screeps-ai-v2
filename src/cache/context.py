from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

_hive = None


def hive():
    """
    :rtype: empire.hive.HiveMind
    :return: The current HiveMind in use.
    """
    return _hive


def set_hive(new_hive):
    """
    :type new_hive: empire.hive.HiveMind
    """
    global _hive
    _hive = new_hive
