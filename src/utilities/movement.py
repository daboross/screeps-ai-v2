import math
from typing import Callable, Iterable, List, Optional, TYPE_CHECKING, Tuple, TypeVar, Union, cast

from jstools.screeps import *
from utilities import positions

if TYPE_CHECKING:
    from rooms.room_mind import RoomMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

room_regex = __new__(RegExp("^(W|E)([0-9]{1,3})(N|S)([0-9]{1,3})$"))


def squared_distance(xy1, xy2):
    # type: (Tuple[int, int], Tuple[int, int]) -> int
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
    # type: (str) -> Tuple[int, int]
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


def room_diff(room_1, room_2):
    # type: (str, str) -> Tuple[int, int]
    x1, y1 = parse_room_to_xy(room_1)
    x2, y2 = parse_room_to_xy(room_2)
    return x2 - x1, y2 - y1


def is_room_exact_center_of_sector(room_name):
    # type: (str) -> bool

    rx, ry = parse_room_to_xy(room_name)
    # `-1` in order to undo the adjustment parse_room_to_xy() does for there being both E0S0 and W0N0
    rrx = (-rx - 1 if rx < 0 else rx) % 10
    rry = (-ry - 1 if ry < 0 else ry) % 10

    return rrx == 5 and rry == 5


def sector_centers_near(room_name):
    # type: (str) -> List[str]
    rx, ry = parse_room_to_xy(room_name)
    # `-1` in order to undo the adjustment parse_room_to_xy() does for there being both E0S0 and W0N0
    rrx = (-rx - 1 if rx < 0 else rx) % 10
    rry = (-ry - 1 if ry < 0 else ry) % 10
    if rrx == 5:
        xs = [rx]
    else:
        offset = 5 - rrx
        if rx < 0:
            new_x = rx - offset
        else:
            new_x = rx + offset
        if (rrx > 5) == (rx < 0):
            xs = [new_x, new_x - 10]
        else:
            xs = [new_x, new_x + 10]

    if rry == 5:
        ys = [ry]
    else:
        offset = 5 - rry
        if ry < 0:
            new_y = ry - offset
        else:
            new_y = ry + offset
        if (rry > 5) == (ry < 0):
            ys = [new_y, new_y - 10]
        else:
            ys = [new_y, new_y + 10]

    if abs(ry) < 10:
        for i in range(0, len(ys)):
            if (ys[i] < 0) != (ry < 0):
                if ry < 0:
                    ys[i] += 1
                else:
                    ys[i] -= 1
    if abs(rx) < 10:
        for i in range(0, len(xs)):
            if (xs[i] < 0) != (rx < 0):
                if rx < 0:
                    xs[i] += 1
                else:
                    xs[i] -= 1

    result = []
    for x in xs:
        for y in ys:
            result.append(room_xy_to_name(x, y))
    return result


def is_room_inner_circle_of_sector(room_name):
    # type: (str) -> bool

    rx, ry = parse_room_to_xy(room_name)
    # `-1` in order to undo the adjustment parse_room_to_xy() does for there being both E0S0 and W0N0
    rrx = (-rx - 1 if rx < 0 else rx) % 10
    rry = (-ry - 1 if ry < 0 else ry) % 10

    return (
        (rrx == 4 or rrx == 5 or rrx == 6)
        and (rry == 4 or rry == 5 or rry == 6)
        and not (rrx == 5 and rry == 5)
    )


def is_room_highway(room_name):
    # type: (str) -> bool

    rx, ry = parse_room_to_xy(room_name)
    # `-1` in order to undo the adjustment parse_room_to_xy() does for there being both E0S0 and W0N0
    rrx = (-rx - 1 if rx < 0 else rx) % 10
    rry = (-ry - 1 if ry < 0 else ry) % 10

    return rrx == 0 or rry == 0


def room_chebyshev_distance(room_1, room_2):
    # type: (str, str) -> int
    xdiff, ydiff = room_diff(room_1, room_2)
    return max(abs(xdiff), abs(ydiff))


def is_valid_room_name(room_name):
    # type: (str) -> bool
    matches = room_regex.exec(room_name)
    return not not matches


def room_xy_to_name(room_x, room_y):
    # type: (int, int) -> str
    return "{}{}{}{}".format(
        "E" if room_x > 0 else "W",
        - room_x - 1 if room_x < 0 else room_x,
        "S" if room_y > 0 else "N",
        - room_y - 1 if room_y < 0 else room_y,
    )


def center_pos(room_name):
    # type: (str) -> RoomPosition
    if not room_name or not _.isString(room_name):
        msg = '[movement] WARNING: Non-string room name passed in to center_pos: {}!'.format(room_name)
        print(msg)
        Game.notify(msg)
    return __new__(RoomPosition(25, 25, room_name))


__pragma__('skip')
_T = TypeVar('_T')
__pragma__('noskip')


def do_a_50x50_spiral(func):
    # type: (Callable[[int, int], _T]) -> Optional[_T]
    x = 0
    y = 0
    dx = 0
    dy = -1
    for i in range(0, 50 * 50):
        result = func(x, y)  # type: _T
        if result:
            return result
        if x == y or (x < 0 and x == -y) or (x > 0 and x == -y + 1):
            dx, dy = -dy, dx
        x += dx
        y += dy
    return None


def find_an_open_space(room_name):
    # type: (str) -> RoomPosition
    def test(x_diff, y_diff):
        if Game.map.getTerrainAt(24 + x_diff, 24 + y_diff, room_name) != 'wall':
            return __new__(RoomPosition(24 + x_diff, 24 + y_diff, room_name))

    result = do_a_50x50_spiral(test)  # type: Optional[RoomPosition]
    if result:
        return result
    else:
        print("[movement] WARNING: Could not find open space in {}".format(room_name))
        return __new__(RoomPosition(25, 25, room_name))


def find_an_open_space_around(room_name, center_x, center_y, min_x = 1, min_y = 1, max_x = 48, max_y = 48, cond = None):
    # type: (str, int, int, int, int, int, int, Callable[[int, int], bool]) -> RoomPosition
    def test(x_diff, y_diff):
        x = center_x + x_diff
        y = center_y + y_diff
        if min_x <= x <= max_x and min_y <= y <= max_y and Game.map.getTerrainAt(x, y, room_name) != 'wall' \
                and (cond is None or cond(x, y)):
            return __new__(RoomPosition(x, y, room_name))

    result = do_a_50x50_spiral(test)
    if result:
        return result
    else:
        print("[movement] WARNING: Could not find open space in {} with boundaries [{}-{},{}-{}]"
              .format(room_name, min_x, max_x, min_y, max_y))
        return __new__(RoomPosition(25, 25, room_name))


def find_clear_inbetween_spaces(room, pos1, pos2):
    # type: (RoomMind, RoomPosition, RoomPosition) -> List[int]
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
    # type: (RoomMind, RoomPosition, List[int]) -> Optional[RoomPosition]
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
        if here_pos.x == x and here_pos.y == y:
            closest_length = -Infinity
            closest = xy
        elif distance < closest_length and is_block_clear(room, x, y):
            closest_length = distance
            closest = xy
    if closest is not None:
        return positions.deserialize_xy_to_pos(closest, room_name)
    else:
        return None


def distance_squared_room_pos(room_position_1, room_position_2):
    # type: (RoomPosition, RoomPosition) -> int
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


def chebyshev_distance_room_pos(pos1, pos2):
    # type: (RoomPosition, RoomPosition) -> int
    if pos1.x == undefined or pos2.x == undefined or pos1.roomName == undefined or pos2.roomName == undefined:
        raise AssertionError('chebyshev_distance_room_pos called with non-RoomPosition: ({}, {})'
                             .format(pos1, pos2))
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
    # type: (int, int, int, int) -> int
    return max(abs(x1 - x2), abs(y1 - y2))


def minimum_chebyshev_distance(comparison_pos, targets):
    # type: (RoomPosition, Iterable[Union[RoomPosition, RoomObject]]) -> int
    min_distance = Infinity
    for target in targets:
        pos = cast(RoomObject, target).pos or cast(RoomPosition, target)
        distance = chebyshev_distance_room_pos(comparison_pos, pos)
        if distance < min_distance:
            min_distance = distance
    if min_distance is Infinity:
        return 0
    else:
        return min_distance


def distance_room_pos(room_pos_1, room_pos_2):
    # type: (RoomPosition, RoomPosition) -> float
    """
    Gets the distance between two RoomPositions, taking into account room difference by parsing room names into x, y
    coords. This method is equivalent to `math.sqrt(distance_squared_room_pos(pos1, pos2))`
    :return:
    """
    return math.sqrt(distance_squared_room_pos(room_pos_1, room_pos_2))


def is_block_clear(room, x, y):
    # type: (RoomMind, int, int) -> bool
    """
    Checks if a block is not a wall, has no non-walkable structures, and has no creeps.
    """
    if x > 49 or y > 49 or x < 0 or y < 0:
        return False
    if Game.map.getTerrainAt(x, y, room.room.name) == 'wall':
        return False
    if len(room.look_at(LOOK_CREEPS, x, y)) != 0:
        return False
    for struct in cast(List[Structure], room.look_at(LOOK_STRUCTURES, x, y)):
        if (struct.structureType != STRUCTURE_RAMPART or
                not cast(StructureRampart, struct).my) \
                and struct.structureType != STRUCTURE_CONTAINER and struct.structureType != STRUCTURE_ROAD:
            return False
    for site in cast(List[ConstructionSite], room.look_at(LOOK_CONSTRUCTION_SITES, x, y)):
        if site.my and site.structureType != STRUCTURE_RAMPART \
                and site.structureType != STRUCTURE_CONTAINER and site.structureType != STRUCTURE_ROAD:
            return False
    return True


def is_block_empty(room, x, y):
    # type: (RoomMind, int, int) -> bool
    """
    Checks if a block is not a wall, and has no non-walkable structures. (does not check creeps)
    """
    if x > 49 or y > 49 or x < 0 or y < 0:
        return False
    if Game.map.getTerrainAt(x, y, room.room.name) == 'wall':
        return False
    for struct in cast(List[Structure], room.look_at(LOOK_STRUCTURES, x, y)):
        if (struct.structureType != STRUCTURE_RAMPART or
                not cast(STRUCTURE_RAMPART, struct).my) \
                and struct.structureType != STRUCTURE_CONTAINER and struct.structureType != STRUCTURE_ROAD:
            return False
    for site in cast(List[ConstructionSite], room.look_at(LOOK_CONSTRUCTION_SITES, x, y)):
        if site.my and site.structureType != STRUCTURE_RAMPART \
                and site.structureType != STRUCTURE_CONTAINER and site.structureType != STRUCTURE_ROAD:
            return False
    return True


def get_entrance_for_exit_pos(exit_pos):
    # type: (RoomPosition) -> Union[RoomPosition, int]
    room_xy = parse_room_to_xy(exit_pos.roomName)
    return get_entrance_for_exit_pos_with_room(exit_pos, room_xy)


def get_entrance_for_exit_pos_with_room(exit_pos, current_room_xy):
    # type: (RoomPosition, Tuple[int, int]) -> Union[RoomPosition, int]
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
    # type: (int, int) -> Optional[int]
    """
    Gets the screeps direction constant from a given dx and dy.
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
        print("[movement][direction] ERROR: Unknown dx/dy: {},{}!".format(dx, dy))
        return None
    else:
        return direction


def apply_direction(pos, direction):
    # type: (RoomPosition, int) -> Optional[RoomPosition]
    dxdy = js_global.__movement_use_directionToDxDy(direction)
    if dxdy:
        return __new__(RoomPosition(pos.x + dxdy[0], pos.y + dxdy[1], pos.roomName))
    else:
        return None


def diff_as_direction(origin, destination):
    # type: (RoomPosition, RoomPosition) -> Optional[int]
    if origin.roomName and destination.roomName and origin.roomName != destination.roomName:
        origin_room_pos = parse_room_to_xy(origin.roomName)
        destination_room_pos = parse_room_to_xy(destination.roomName)
        direction = dxdy_to_direction(destination_room_pos[0] * 50 + destination.x
                                      - origin_room_pos[0] * 50 - origin.x,
                                      destination_room_pos[1] * 50 + destination.y
                                      - origin_room_pos[1] * 50 - origin.y)
    else:
        direction = dxdy_to_direction(destination.x - origin.x, destination.y - origin.y)
    if direction is None:
        print("[movement] No direction found for diff_as_direction({}, {})."
              .format(origin, destination))
    return direction


def next_pos_in_direction_to(origin, destination):
    # type: (RoomPosition, RoomPosition) -> RoomPosition
    if origin.roomName and destination.roomName and origin.roomName != destination.roomName:
        origin_room_pos = parse_room_to_xy(origin.roomName)
        destination_room_pos = parse_room_to_xy(destination.roomName)
        dx = destination_room_pos[0] * 50 + destination.x - origin_room_pos[0] * 50 - origin.x
        dy = destination_room_pos[1] * 50 + destination.y - origin_room_pos[1] * 50 - origin.y
    else:
        dx = destination.x - origin.x
        dy = destination.y - origin.y
    new_x = origin.x + Math.sign(dx)
    new_y = origin.y + Math.sign(dy)
    if new_x > 49 or new_x < 0 or new_y > 49 or new_y < 0:
        room_x, room_y = parse_room_to_xy(origin.roomName)
        if new_x > 49:
            new_x -= 50
            room_x += 1
        elif new_x < 0:
            new_x += 50
            room_x -= 1
        if new_y > 49:
            new_y -= 50
            room_y += 1
        elif new_y < 0:
            new_y += 50
            room_y -= 1
        return __new__(RoomPosition(new_x, new_y, room_xy_to_name(room_x, room_y)))
    else:
        return __new__(RoomPosition(new_x, new_y, origin.roomName))


def is_edge_position(pos):
    # type: (RoomPosition) -> bool
    return pos.x == 49 or pos.y == 49 or pos.x == 0 or pos.y == 0
