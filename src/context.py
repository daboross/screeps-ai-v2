from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_hive = None


def hive():
    """
    :rtype: control.hivemind.HiveMind
    :return: The current HiveMind in use.
    """
    return _hive


def set_hive(new_hive):
    """
    :type new_hive: control.hivemind.HiveMind
    """
    global _hive
    _hive = new_hive
