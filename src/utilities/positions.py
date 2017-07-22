from typing import Optional, Tuple, Union

from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def parse_xy_arguments(pos, optional_y):
    # type: (Union[RoomPosition, RoomObject, int], Optional[int]) -> Tuple[int, int, Optional[str]]
    """
    Parses x/optional_y arguments into x, y, and roomName
    :param pos: The first argument
    :param optional_y: The second argument
    :return: (x, y, room_name)
    :rtype: (int, int, str)
    """
    if optional_y is not None and optional_y is not undefined:
        return pos, optional_y, None
    else:
        if pos.pos:
            return pos.pos.x, pos.pos.y, pos.pos.roomName
        else:
            return pos.x, pos.y, pos.roomName


def clamp_room_x_or_y(coord):
    # type: (int) -> int
    return (coord if coord < 49 else 49) if coord > 0 else 0


def serialize_xy(x, y):
    # type: (int, int) -> int
    return x | y << 6


def serialize_pos_xy(pos):
    # type: (RoomPosition) -> int
    return pos.x | pos.y << 6


def deserialize_xy(xy):
    # type: (int) -> Tuple[int, int]
    return (xy & 0x3F), (xy >> 6 & 0x3F)


def deserialize_xy_to_pos(xy, room_name):
    # type: (int, str) -> RoomPosition
    return __new__(RoomPosition(xy & 0x3F, xy >> 6 & 0x3F, room_name))


def serialize_xy_room(x, y, room_name):
    # type: (int, int, str) -> str
    return str(x | y << 6) + '|' + room_name


def serialize_xy_room_pos(pos):
    # type: (RoomPosition) -> str
    return str(pos.x | pos.y << 6) + '|' + pos.roomName
