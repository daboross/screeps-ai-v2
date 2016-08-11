from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_hive = None
_targets = None
_room = None


def hive():
    """
    :rtype: control.hivemind.HiveMind
    :return: The current HiveMind in use.
    """
    return _hive


def targets():
    """
    :rtype: control.targets.TargetMind
    :return: The current TargetMind in use.
    """
    return _targets


def room():
    """
    :rtype: control.hivemind.RoomMind
    :return: The current Room being processed.
    """
    return _room


def set_hive(new_hive):
    """
    :type new_hive: control.hivemind.HiveMind
    """
    global _hive
    _hive = new_hive


def set_targets(new_targets):
    """
    :type new_targets: control.targets.TargetMind
    """
    global _targets
    _targets = new_targets


def set_room(new_room):
    """
    :type new_room: control.hivemind.RoomMind
    """
    global _room
    _room = new_room


def clear():
    global _hive
    global _targets
    global _room
    _hive = None
    _targets = None
    _room = None
