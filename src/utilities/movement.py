import math

import context
import flags
from utilities.screeps_constants import *

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
    return x2 - x1, y2 - y1


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
    dir1 = direction
    flag_list = flags.find_flags(room_name, flags.DIR_TO_EXIT_FLAG[direction])
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
        flag_list = flags.find_flags(room_name, flags.DIR_TO_EXIT_FLAG[direction])
    if not len(flag_list):
        no_exit_flag = flags.find_flags(room_name, flags.DIR_TO_NO_EXIT_FLAG[direction])
        if not len(no_exit_flag):
            flags.find_flags(room_name, flags.DIR_TO_NO_EXIT_FLAG[dir1])
        if not len(no_exit_flag):
            print("[movement] Couldn't find exit flag in room {} to direction {}!"
                  " [targeting room {} from room {}] ({}, {})".format(
                room_name, flags.DIR_TO_EXIT_FLAG[direction], to_room, room_name, difference[0], difference[1]))
        return None, direction

    return flag_list[0].pos, direction


def get_no_exit_flag_and_direction(room_name, to_room, difference):
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

    flag_list = flags.find_flags(room_name, flags.DIR_TO_NO_EXIT_FLAG[direction])
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
        flag_list = flags.find_flags(room_name, flags.DIR_TO_EXIT_FLAG[direction])
    if not len(flag_list):
        print("[movement] Couldn't find exit flag in room {} to direction {}!"
              " [targeting room {} from room {}] ({}, {})".format(
            room_name, flags.DIR_TO_EXIT_FLAG[direction], to_room, room_name, difference[0], difference[1]))
        return None, direction

    return flag_list[0].pos, direction


def get_exit_flag_to(from_room, to_room):
    difference = inter_room_difference(from_room, to_room)
    if not difference:
        return None
    return get_exit_flag_and_direction(from_room, to_room, difference)[0]


def get_no_exit_flag_to(from_room, to_room):
    difference = inter_room_difference(from_room, to_room)
    if not difference:
        return None
    return get_no_exit_flag_and_direction(from_room, to_room, difference)[0]


def path_distance(here, target, non_roads_two_movement=False):
    if here == target:
        return 0
    current = __new__(RoomPosition(here.x, here.y, here.roomName))

    path_len = 0
    x = 0
    rooms_looked_at = []

    target_room_xy = parse_room_to_xy(target.roomName)

    while current.roomName != target.roomName and x < 6:
        rooms_looked_at.append(current.roomName)
        x += 1
        room = Game.rooms[current.roomName]
        current_room_xy = parse_room_to_xy(current.roomName)
        difference = (target_room_xy[0] - current_room_xy[0], target_room_xy[1] - current_room_xy[1])
        exit_pos, exit_direction = get_exit_flag_and_direction(current.roomName, target.roomName, difference)
        if not exit_pos:
            print("[path_distance] Couldn't find exit flag from {} to {} (exit {})!".format(current.roomName,
                                                                                            target.roomName,
                                                                                            exit_direction))
            return -1

        path = context.hive().honey.find_path(current, exit_pos)
        if path:
            if not non_roads_two_movement:
                path_len += len(path) + 1  # one to accommodate moving to the other room.
            elif room:
                for pos in path:
                    if _.find(room.lookForAt(pos, LOOK_STRUCTURES), lambda s: s.structureType == STRUCTURE_ROAD):
                        path_len += 1
                    else:
                        path_len += 2
                path_len += 1
            else:
                # we can't see room but we have a cached path, so let's just assume path is no-roads
                path_len += len(path) * 2 + 1
        else:
            if room:
                if not path:
                    print("[path_distance] pathfinding couldn't find path to exit {} in room {}!".format(
                        exit_direction, current.roomName))
                    return -1
            else:
                # TODO: use PathFinder here!
                print("[path_distance] Couldn't find view to room {}! Using linear distance.".format(current.roomName))
                if not non_roads_two_movement:
                    path_len += math.sqrt(distance_squared_room_pos(current, exit_pos)) + 1
                else:
                    path_len += 2 * math.sqrt(distance_squared_room_pos(current, exit_pos)) + 1

        current = get_entrance_for_exit_pos_with_room(exit_pos, current_room_xy)

    if x >= 6:
        rooms_looked_at.append(current.roomName)
        print("[path_distance] Looked at 6 rooms when pathfinding from {} to {}: {}".format(
            here, target, JSON.stringify(rooms_looked_at)))
    room = Game.rooms[current.roomName]

    path = context.hive().honey.find_path(current, target)
    if path:
        if not non_roads_two_movement:
            path_len += len(path)
        elif room:
            for pos in path:
                if _.find(room.lookForAt(pos, LOOK_STRUCTURES), lambda s: s.structureType == STRUCTURE_ROAD):
                    path_len += 1
                else:
                    path_len += 2
            path_len += 1
        else:
            # we can't see room but we have a cached path, so let's just assume path is no-roads
            path_len += len(path) * 2 + 1
    else:
        if room:
            if not path:
                print("[path_distance] pathfinding couldn't find path to {} from {}!".format(target, current))
                return -1
        else:
            print("[path_distance] Couldn't find view to room {}! Using linear distance.".format(current.roomName))
            if not non_roads_two_movement:
                path_len += math.sqrt(distance_squared_room_pos(current, target))
            else:
                path_len += 2 * math.sqrt(distance_squared_room_pos(current, target))

    return path_len


def is_block_clear(room, x, y):
    if len(room.lookForAt(LOOK_CREEPS, x, y)) != 0:
        return False
    for struct in room.lookForAt(LOOK_STRUCTURES, x, y):
        if struct.structureType != STRUCTURE_RAMPART and struct.structureType != STRUCTURE_EXTENSION \
                and struct.structureType != STRUCTURE_CONTAINER:
            return False
    for terrain in room.lookForAt(LOOK_TERRAIN, x, y):
        # TODO: there are no constants for this value, and TERRAIN_MASK_* constants seem to be useless...
        if terrain == 'wall':
            return False
    return True


def get_entrance_for_exit_pos(exit_pos):
    if exit_pos.pos:
        exit_pos = exit_pos.pos
    room_xy = parse_room_to_xy(exit_pos.roomName)
    return get_entrance_for_exit_pos_with_room(exit_pos, room_xy)


def get_entrance_for_exit_pos_with_room(exit_pos, current_room_xy):
    if exit_pos.pos:
        exit_pos = exit_pos.pos
    entrance_pos = __new__(RoomPosition(exit_pos.x, exit_pos.y, exit_pos.roomName))
    room_x, room_y = current_room_xy
    if exit_pos.y == 0:
        entrance_pos.y = 49
        room_y -= 1
    elif exit_pos.y == 49:
        entrance_pos.y = 0
        room_y += 1
    elif exit_pos.x == 0:
        entrance_pos.x = 49
        room_x -= 1
    elif exit_pos.x == 49:
        entrance_pos.x = 0
        room_x += 1
    else:
        print("[movement][get_entrance_for_exit_pos] Exit position given ({}) is not an exit position.".format(
            JSON.stringify(exit_pos)
        ))
        return -1
    entrance_pos.roomName = "{}{}{}{}".format(
        "E" if room_x > 0 else "W",
        abs(room_x),
        "S" if room_y > 0 else "N",
        abs(room_y),
    )
    return entrance_pos


def average_pos_same_room(targets):
    if not targets or not len(targets):
        return None
    sum_x, sum_y = 0, 0
    room_name = None
    for target in targets:
        if "pos" in target:
            target = target.pos  # get the position
        room_name = target.roomName
        sum_x += target.x
        sum_y += target.y
    x_avg = sum_x / len(targets)
    y_avg = sum_y / len(targets)
    return __new__(RoomPosition(x_avg, y_avg, room_name))
