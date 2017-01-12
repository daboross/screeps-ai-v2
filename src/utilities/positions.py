from jstools.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def parse_xy_arguments(pos, optional_y):
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
    return (coord if coord < 49 else 49) if coord > 0 else 0


def serialize_xy(x, y):
    return x | y << 6


def serialize_pos_xy(pos):
    pos = pos.pos or pos
    return pos.x | pos.y << 6


def deserialize_xy(xy):
    return (xy & 0x3F), (xy >> 6 & 0x3F)


def deserialize_xy_to_pos(xy, room_name):
    return __new__(RoomPosition(xy & 0x3F, xy >> 6 & 0x3F, room_name))
