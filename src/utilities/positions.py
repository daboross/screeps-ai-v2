from typing import Optional, Tuple, Union, cast

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
        return cast(int, pos), optional_y, None
    else:
        if cast(RoomObject, pos).pos:
            return cast(RoomObject, pos).pos.x, cast(RoomObject, pos).pos.y, cast(RoomObject, pos).pos.roomName
        else:
            return cast(RoomPosition, pos).x, cast(RoomPosition, pos).y, cast(RoomPosition, pos).roomName


def clamp_room_x_or_y(coord):
    # type: (int) -> int
    return (coord if coord < 49 else 49) if coord > 0 else 0


def serialize_xy(x, y):
    # type: (int, int) -> int
    return x | y << 6


def serialize_pos_xy(pos):
    # type: (Union[RoomPosition, StoredObstacle, _PathPos]) -> int
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
