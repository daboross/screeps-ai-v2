import math

import context
import flags
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

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
    # Make this work in the simulation, for little to no cost!
    if from_room == to_room:
        return 0, 0

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
        return 0, 0
    if matches[1] == "W":
        x = -int(matches[2])
    else:
        x = +int(matches[2])
    if matches[3] == "N":
        y = -int(matches[4])
    else:
        y = +int(matches[4])
    return x, y


def room_xy_to_name(room_x, room_y):
    return "{}{}{}{}".format(
        "E" if room_x > 0 else "W",
        abs(room_x),
        "S" if room_y > 0 else "N",
        abs(room_y),
    )


def is_room_highway_intersection(room_name):
    x, y = parse_room_to_xy(room_name)
    return x % 10 == 0 and y % 10 == 0


def center_pos(room_name):
    return __new__(RoomPosition(25, 25, room_name))


def distance_squared_room_pos(room_position_1, room_position_2):
    """
    Gets the squared distance between two RoomPositions, taking into account room difference by parsing room names to
    x, y coords and counting each room difference at 50 position difference.
    :param room_position_1: The first RoomPosition
    :param room_position_2: The second RoomPosition
    :return: The squared distance as an int
    """
    if room_position_1.pos: room_position_1 = room_position_1.pos
    if room_position_2.pos: room_position_2 = room_position_2.pos
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


def chebyshev_distance_room_pos(pos1, pos2):
    if pos1.pos: pos1 = pos1.pos
    if pos2.pos: pos2 = pos2.pos
    if pos1.roomName == pos2.roomName:
        return max(abs(pos1.x - pos2.x), abs(pos1.y - pos2.y))
    room_1_pos = parse_room_to_xy(pos1.roomName)
    room_2_pos = parse_room_to_xy(pos2.roomName)
    world_pos_1 = (
        room_1_pos[0] * 50 + pos1.x,
        room_1_pos[1] * 50 + pos1.y
    )
    world_pos_2 = (
        room_2_pos[0] * 50 + pos2.x,
        room_2_pos[1] * 50 + pos2.y
    )
    return max(abs(world_pos_1[0] - world_pos_2[0]), abs(world_pos_1[1] - world_pos_2[1]))


def minimum_chebyshev_distance(comparison_pos, targets):
    return _.min(targets, lambda p: chebyshev_distance_room_pos(comparison_pos, p))


def distance_room_pos(room_pos_1, room_pos_2):
    """
    Gets the distance between two RoomPositions, taking into account room difference by parsing room names into x, y
    coords. This method is equivalent to `math.sqrt(distance_squared_room_pos(pos1, pos2))`
    :param room_pos_1:
    :param room_pos_2:
    :return:
    """
    return math.sqrt(distance_squared_room_pos(room_pos_1, room_pos_2))


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
    if here.pos:
        here = here.pos
    if target.pos:
        target = target.pos
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
        room_mind = context.hive().get_room(current.roomName)
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
            elif room_mind:
                for pos in path:
                    if _.find(room_mind.look_at(LOOK_STRUCTURES, pos), {'structureType': STRUCTURE_ROAD}):
                        path_len += 1
                    else:
                        path_len += 2
                path_len += 1
            else:
                # we can't see room but we have a cached path, so let's just assume path is no-roads
                path_len += len(path) * 2 + 1
        else:
            if room_mind:
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
    room_mind = context.hive().get_room(current.roomName)

    path = context.hive().honey.find_path(current, target)
    if path:
        if not non_roads_two_movement:
            path_len += len(path)
        elif room_mind:
            for pos in path:
                if _.find(room_mind.look_at(LOOK_STRUCTURES, pos), {'structureType': STRUCTURE_ROAD}):
                    path_len += 1
                else:
                    path_len += 2
            path_len += 1
        else:
            # we can't see room but we have a cached path, so let's just assume path is no-roads
            path_len += len(path) * 2 + 1
    else:
        if room_mind:
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
    """
    Checks if a block is not a wall, has no non-walkable structures, and has no creeps.
    :type room: control.hivemind.RoomMind
    """
    if x > 49 or y > 49 or x < 0 or y < 0:
        return False
    if Game.map.getTerrainAt(x, y, room.room.name) == 'wall':
        return False
    if len(room.look_at(LOOK_CREEPS, x, y)) != 0:
        return False
    for struct in room.look_at(LOOK_STRUCTURES, x, y):
        if (struct.structureType != STRUCTURE_RAMPART or not struct.my) \
                and struct.structureType != STRUCTURE_CONTAINER and struct.structureType != STRUCTURE_ROAD:
            return False
    for site in room.look_at(LOOK_CONSTRUCTION_SITES, x, y):
        if site.my and site.structureType != STRUCTURE_RAMPART \
                and site.structureType != STRUCTURE_CONTAINER and site.structureType != STRUCTURE_ROAD:
            return False
    return True


is_block_clear = profiling.profiled(is_block_clear, 'movement.is_block_clear')


def serialized_pos_to_pos_obj(room, xy):
    return {'x': xy & 0x3F, 'y': xy >> 6 & 0x3F, 'roomName': room}


def xy_to_serialized_int(x, y):
    return x | y << 6


def is_block_empty(room, x, y):
    """
    Checks if a block is not a wall, and has no non-walkable structures. (does not check creeps).
    :type room: control.hivemind.RoomMind
    """
    if x > 49 or y > 49 or x < 0 or y < 0:
        return False
    if Game.map.getTerrainAt(x, y, room.room.name) == 'wall':
        return False
    for struct in room.look_at(LOOK_STRUCTURES, x, y):
        if (struct.structureType != STRUCTURE_RAMPART or not struct.my) \
                and struct.structureType != STRUCTURE_CONTAINER and struct.structureType != STRUCTURE_ROAD:
            return False
    for site in room.look_at(LOOK_CONSTRUCTION_SITES, x, y):
        if site.my and site.siteureType != STRUCTURE_RAMPART \
                and site.siteureType != STRUCTURE_CONTAINER and site.siteureType != STRUCTURE_ROAD:
            return False
    return True


is_block_empty = profiling.profiled(is_block_empty, 'movement.is_block_empty')


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
    entrance_pos.roomName = room_xy_to_name(room_x, room_y)
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
    return __new__(RoomPosition(round(x_avg), round(y_avg), room_name))
