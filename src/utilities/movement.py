import math

from jstools.screeps_constants import *
from utilities import positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

room_regex = __new__(RegExp("(W|E)([0-9]{1,2})(N|S)([0-9]{1,2})"))


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
        x = -int(matches[2]) - 1
    else:
        x = +int(matches[2])
    if matches[3] == "N":
        y = -int(matches[4]) - 1
    else:
        y = +int(matches[4])
    return x, y


def is_valid_room_name(room_name):
    matches = room_regex.exec(room_name)
    return not not matches


def room_xy_to_name(room_x, room_y):
    return "{}{}{}{}".format(
        "E" if room_x > 0 else "W",
        - room_x - 1 if room_x < 0 else room_x,
        "S" if room_y > 0 else "N",
        - room_y - 1 if room_y < 0 else room_y,
    )


def center_pos(room_name):
    return __new__(RoomPosition(25, 25, room_name))


def find_an_open_space(room_name):
    x = 0
    y = 0
    dx = 0
    dy = -1
    for _ in range(0, 50 * 50):
        if Game.map.getTerrainAt(24 + x, 24 + y, room_name) != 'wall':
            return __new__(RoomPosition(24 + x, 24 + y, room_name))
        if x == y or (x < 0 and x == -y) or (x > 0 and x == -y + 1):
            dx, dy = -dy, dx
        x += dx
        y += dy
    print("[movement] WARNING: Could not find open space in {}".format(room_name))
    return __new__(RoomPosition(25, 25, room_name))


def find_clear_inbetween_spaces(room, pos1, pos2):
    if pos1.pos:
        pos1 = pos1.pos
    if pos2.pos:
        pos2 = pos2.pos
    distance = chebyshev_distance_room_pos(pos1, pos2)
    result = []
    if distance > 2 or pos1.roomName != pos2.roomName:
        return result
    for x in range(pos1.x - 1, pos1.x + 2):
        for y in range(pos1.y - 1, pos1.y + 2):
            xdiff = abs(x - pos2.x)
            ydiff = abs(y - pos2.y)
            if xdiff < 2 and ydiff < 2:
                if is_block_empty(room, x, y):
                    result.push(positions.serialize_xy(x, y))
    return result


def room_pos_of_closest_serialized(room, here_pos, list_of_serialized):
    if here_pos.pos:
        here_pos = here_pos.pos
    length = len(list_of_serialized)
    room_name = here_pos.roomName

    if length == 1:
        return positions.deserialize_xy_to_pos(list_of_serialized[0], room_name)
    here_x = here_pos.x
    here_y = here_pos.y
    closest = None
    closest_length = Infinity
    for xy in list_of_serialized:
        x, y = positions.deserialize_xy(xy)
        distance = max(abs(here_x - x), abs(here_y - y))
        if distance < closest_length and is_block_clear(room, x, y):
            closest_length = distance
            closest = xy
    if closest is not None:
        return positions.deserialize_xy_to_pos(closest, room_name)
    else:
        return None

def distance_squared_room_pos(room_position_1, room_position_2):
    """
    Gets the squared distance between two RoomPositions, taking into account room difference by parsing room names to
    x, y coords and counting each room difference at 50 position difference.
    :param room_position_1: The first RoomPosition
    :param room_position_2: The second RoomPosition
    :return: The squared distance as an int
    """
    if room_position_1.pos:
        room_position_1 = room_position_1.pos
    if room_position_2.pos:
        room_position_2 = room_position_2.pos
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
    if pos1.pos:
        pos1 = pos1.pos
    if pos2.pos:
        pos2 = pos2.pos
    if pos1.roomName == pos2.roomName:
        return max(abs(pos1.x - pos2.x), abs(pos1.y - pos2.y))
    room_1_pos = parse_room_to_xy(pos1.roomName)
    room_2_pos = parse_room_to_xy(pos2.roomName)
    world_pos_1 = (
        room_1_pos[0] * 49 + pos1.x,
        room_1_pos[1] * 49 + pos1.y
    )
    world_pos_2 = (
        room_2_pos[0] * 49 + pos2.x,
        room_2_pos[1] * 49 + pos2.y
    )
    return max(abs(world_pos_1[0] - world_pos_2[0]), abs(world_pos_1[1] - world_pos_2[1]))


def chebyshev_distance_xy(x1, y1, x2, y2):
    return max(abs(x1 - x2), abs(y1 - y2))


def minimum_chebyshev_distance(comparison_pos, targets):
    min_distance = Infinity
    for target in targets:
        distance = chebyshev_distance_room_pos(comparison_pos, target)
        if distance < min_distance:
            min_distance = distance
    if min_distance is Infinity:
        return 0
    else:
        return min_distance


def distance_room_pos(room_pos_1, room_pos_2):
    """
    Gets the distance between two RoomPositions, taking into account room difference by parsing room names into x, y
    coords. This method is equivalent to `math.sqrt(distance_squared_room_pos(pos1, pos2))`
    :param room_pos_1:
    :param room_pos_2:
    :return:
    """
    return math.sqrt(distance_squared_room_pos(room_pos_1, room_pos_2))


def is_block_clear(room, x, y):
    """
    Checks if a block is not a wall, has no non-walkable structures, and has no creeps.
    :type room: rooms.room_mind.RoomMind
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


def is_block_empty(room, x, y):
    """
    Checks if a block is not a wall, and has no non-walkable structures. (does not check creeps).
    :type room: rooms.room_mind.RoomMind
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
        if site.my and site.structureType != STRUCTURE_RAMPART \
                and site.structureType != STRUCTURE_CONTAINER and site.structureType != STRUCTURE_ROAD:
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
    entrance_pos.roomName = room_xy_to_name(room_x, room_y)
    return entrance_pos


def dxdy_to_direction(dx, dy):
    """
    Gets the screeps direction constant from a given dx and dy.
    :type dx: int
    :type dy: int
    :rtype: int
    """
    direction = None
    if dx < 0:
        if dy < 0:
            direction = TOP_LEFT
        elif dy == 0:
            direction = LEFT
        elif dy > 0:
            direction = BOTTOM_LEFT
    elif dx == 0:
        if dy < 0:
            direction = TOP
        elif dy > 0:
            direction = BOTTOM
    elif dx > 0:
        if dy < 0:
            direction = TOP_RIGHT
        elif dy == 0:
            direction = RIGHT
        elif dy > 0:
            direction = BOTTOM_RIGHT
    if direction is None:
        print("[honey][direction] ERROR: Unknown dx/dy: {},{}!".format(dx, dy))
        return None
    else:
        return direction


def diff_as_direction(origin, destination):
    if origin.pos is not undefined:
        origin = origin.pos
    if destination.pos is not undefined:
        destination = destination.pos
    direction = dxdy_to_direction(destination.x - origin.x, destination.y - origin.y)
    if direction is None:
        print("[movement][direction_to] No direction found for get_direction({} - {}, {} - {})."
              .format(destination.x, origin.x, destination.y, origin.y))
    return direction
