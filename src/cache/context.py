from typing import Optional, TYPE_CHECKING

from jstools.screeps import *

if TYPE_CHECKING:
    from empire.hive import HiveMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

_hive = None  # type: Optional[HiveMind]


def hive():
    # type: () -> Optional[HiveMind]
    """
    :rtype: empire.hive.HiveMind
    :return: The current HiveMind in use.
    """
    return _hive


def set_hive(new_hive):
    # type: (Optional[HiveMind]) -> None
    """
    :type new_hive: empire.hive.HiveMind
    """
    global _hive
    _hive = new_hive
