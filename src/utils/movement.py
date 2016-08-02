import math

import flags
from utils import pathfinding
from utils.screeps_constants import *

__pragma__('noalias', 'name')

room_regex = __new__(RegExp("(W|E)([0-9]{1,2})(N|S)([0-9]{1,2})"))


def inter_room_difference(from_room, to_room):
    """
    :param from_room: The name of the room to get from.
    :param to_room: The name of the room to get to.
    :return: (x_difference, y_difference)
    :type from_room: Room
    :type to_room: Room
    :rtype: (int, int)
    """
    # example room string: W47N26 or E1S1 or E1N1
    pos1 = parse_room_to_xy(from_room)
    pos2 = parse_room_to_xy(to_room)
    if not pos1 or not pos2:
        return None
    x1, y1 = pos1
    x2, y2 = pos2
    return (x2 - x1, y2 - y1)


def squared_distance(xy1, xy2):
    """
    Gets the squared distance between two x, y positions
    :param xy1: a tuple (x, y)
    :param xy2: a tuple (x, y)
    :return: an integer, the squared linear distance
    """
    x_diff = (xy1[0] - xy2[0])
    y_diff = (xy1[1] - xy2[1])
    return x_diff * x_diff + y_diff * y_diff


def parse_room_to_xy(room_name):
    matches = room_regex.exec(room_name)
    if not matches:
        return None
    if matches[1] == "W":
        x = -int(matches[2])
    else:
        x = +int(matches[2])
    if matches[3] == "N":
        y = -int(matches[4])
    else:
        y = +int(matches[4])
    return x, y


def distance_squared_room_pos(room_position_1, room_position_2):
    """
    Gets the squared distance between two RoomPositions, taking into account room difference by parsing room names to
    x, y coords and counting each room difference at 50 position difference.
    :param room_position_1: The first RoomPosition
    :param room_position_2: The second RoomPosition
    :return: The squared distance as an int
    """
    if room_position_1.roomName == room_position_2.roomName:
        return squared_distance((room_position_1.x, room_position_1.y), (room_position_2.x, room_position_2.y))
    room_1_pos = parse_room_to_xy(room_position_1.roomName)
    room_2_pos = parse_room_to_xy(room_position_2.roomName)
    full_pos_1 = (
        room_1_pos[0] * 50 + room_position_1.x,
        room_1_pos[1] * 50 + room_position_1.y
    )
    full_pos_2 = (
        room_2_pos[0] * 50 + room_position_2.x,
        room_2_pos[1] * 50 + room_position_2.y
    )
    return squared_distance(full_pos_1, full_pos_2)


def get_exit_flag_and_direction(room_name, to_room, difference):
    if abs(difference[0]) > abs(difference[1]):
        if difference[0] > 0:
            direction = RIGHT
        else:
            direction = LEFT
    else:
        if difference[1] > 0:
            direction = BOTTOM
        else:
            direction = TOP

    flag_list = flags.get_flags(room_name, flags.DIR_TO_EXIT_FLAG[direction])
    if not len(flag_list):
        # If we have another direction (if path is diagonal), try another way?
        if abs(difference[0]) > abs(difference[1]):
            if difference[1] > 0:
                direction = BOTTOM
            elif difference[1] < 0:
                direction = TOP
        else:
            if difference[0] > 0:
                direction = RIGHT
            elif difference[0] < 0:
                direction = LEFT
        flag_list = flags.get_flags(room_name, flags.DIR_TO_EXIT_FLAG[direction])
    if not len(flag_list):
        print("Couldn't find exit flag in room {} to direction {}! [targetting room {} from room {}]"
              .format(room_name, flags.DIR_TO_EXIT_FLAG[direction], to_room, room_name))
        return None, direction

    return flag_list[0].pos, direction


def path_distance(here, target):
    if here == target:
        return 0
    current = __new__(RoomPosition(here.x, here.y, here.roomName))

    path_len = 0
    x = 1

    while current.roomName != target.roomName and x < 6:
        x += 1
        print("Now calculating {} to {}".format(current.roomName, target.roomName))
        room = Game.rooms[current.roomName]
        difference = inter_room_difference(current.roomName, target.roomName)
        if not difference:
            print("[path_distance] Couldn't find room pos difference between {} and {}!".format(current.roomName,
                                                                                                target.roomName))
            return -1
        new_pos, exit_direction = get_exit_flag_and_direction(current.roomName, target.roomName, difference)
        if not new_pos:
            print("[path_distance] Couldn't find exit flag from {} to {} (exit {})!".format(current.roomName,
                                                                                            target.roomName,
                                                                                            exit_direction))
            return -1

        if room:
            path = pathfinding.find_path(room, current, new_pos, None)
            if not path:
                print("[path_distance] pathfinding couldn't find path to exit {} in room {}!".format(exit_direction,
                                                                                                     current.roomName))
                return -1
            path_len += len(path) + 1  # one to accommodate moving to the other room.
        else:
            print("[path_distance] Couldn't find view to room {}! Using linear distance.")
            path_len += math.sqrt(distance_squared_room_pos(current, new_pos)) + 1

        print("[path_distance] Adding {} to {}. New len: {}".format(current, new_pos, path_len))

        if exit_direction == TOP:
            new_pos.y = 49
        elif exit_direction == BOTTOM:
            new_pos.y = 0
        elif exit_direction == LEFT:
            new_pos.x = 49
        elif exit_direction == RIGHT:
            new_pos.x = 0
        else:
            print("[path_distance] get_exit_flag_and_direction returned unknown direction! {}".format(exit_direction))
            return -1
        current = new_pos

    room = Game.rooms[current.roomName]
    if room:
        path = pathfinding.find_path(room, current, target, None)
        if not path:
            print("[path_distance] pathfinding couldn't find path from {} to {} in room {}!".format(current,
                                                                                                    target,
                                                                                                    current.roomName))
        path_len += len(path)
    else:
        print("[path_distance] Couldn't find view to room {}! Using linear distance.")
        path_len += math.sqrt(distance_squared_room_pos(current, target)) + 1
        print("[path_distance] Adding {} to {}. New len: {}".format(current, target, path_len))

    return path_len
