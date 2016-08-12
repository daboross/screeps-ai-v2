import math

from utilities.screeps_constants import *

__pragma__('noalias', 'name')

DEPOT = "depot"
EXIT_NORTH = "exit_north"
EXIT_EAST = "exit_east"
EXIT_SOUTH = "exit_south"
EXIT_WEST = "exit_west"
REMOTE_MINE = "harvest"
CLAIM_LATER = "claim_later"
PATH_FINDING_AVOID = "avoid_moving_through"
SOURCE_QUEUE_START = "source_stop"
MAIN_DESTRUCT = "destruct"
MAIN_BUILD = "build"
SUB_WALL = "wall"
SUB_RAMPART = "rampart"
SUB_EXTENSION = "extension"
SUB_SPAWN = "spawn"
SUB_TOWER = "tower"
SUB_STORAGE = "storage"
SUB_LINK = "link"

DIR_TO_EXIT_FLAG = {
    TOP: EXIT_NORTH,
    LEFT: EXIT_WEST,
    BOTTOM: EXIT_SOUTH,
    RIGHT: EXIT_EAST,
}

flag_definitions = {
    DEPOT: (COLOR_BLUE, COLOR_BLUE),
    PATH_FINDING_AVOID: (COLOR_BLUE, COLOR_RED),
    EXIT_NORTH: (COLOR_WHITE, COLOR_RED),
    EXIT_EAST: (COLOR_WHITE, COLOR_PURPLE),
    EXIT_SOUTH: (COLOR_WHITE, COLOR_BLUE),
    EXIT_WEST: (COLOR_WHITE, COLOR_CYAN),
    REMOTE_MINE: (COLOR_GREEN, COLOR_CYAN),
    CLAIM_LATER: (COLOR_GREEN, COLOR_PURPLE),
    SOURCE_QUEUE_START: (COLOR_BLUE, COLOR_RED)
}

main_to_flag_primary = {
    MAIN_DESTRUCT: COLOR_RED,
    MAIN_BUILD: COLOR_PURPLE,
}
sub_to_flag_secondary = {
    SUB_WALL: COLOR_RED,
    SUB_RAMPART: COLOR_PURPLE,
    SUB_EXTENSION: COLOR_BLUE,
    SUB_SPAWN: COLOR_CYAN,
    SUB_TOWER: COLOR_GREEN,
    SUB_STORAGE: COLOR_YELLOW,
    SUB_LINK: COLOR_ORANGE,
}
flag_secondary_to_sub = {
    COLOR_RED: SUB_WALL,
    COLOR_PURPLE: SUB_RAMPART,
    COLOR_BLUE: SUB_EXTENSION,
    COLOR_CYAN: SUB_SPAWN,
    COLOR_GREEN: SUB_TOWER,
    COLOR_YELLOW: SUB_STORAGE,
    COLOR_ORANGE: SUB_LINK,
}

_last_flag_len = 0
_last_checked_flag_len = 0


def __check_new_flags():
    global _last_flag_len, _last_checked_flag_len
    global _room_flag_cache, _room_flag_refresh_time
    global _global_flag_refresh_time, _global_flag_cache
    global _closest_flag_refresh_time, _closest_flag_cache
    if _last_checked_flag_len < Game.time:
        length = Object.keys(Game.flags).length
        if _last_flag_len < length:
            # TODO: make 50 here a constant, to agree with refresh times set below
            refresh_time = Game.time + 50
            _room_flag_cache = __new__(Map())
            _room_flag_refresh_time = refresh_time
            _global_flag_cache = __new__(Map())
            _global_flag_refresh_time = refresh_time
            _closest_flag_cache = __new__(Map())
            _closest_flag_refresh_time = refresh_time
            _last_flag_len = length
        _last_checked_flag_len = Game.time


def move_flags():
    if Memory.flags_to_move:
        for name, pos in Memory.flags_to_move:
            pos = __new__(RoomPosition(pos.x, pos.y, pos.roomName))
            result = Game.flags[name].setPosition(pos)
            print("[flags] Moving flag {} to {}. Result: {}".format(name, pos, result))
        del Memory.flags_to_move


def is_def(flag, flag_type):
    flag_def = flag_definitions[flag_type]
    return flag.color == flag_def[0] and flag.secondaryColor == flag_def[1]


_room_flag_cache = __new__(Map())
_room_flag_refresh_time = Game.time + 50


def __get_room_and_name(room):
    if room.room:
        room = room.room
    if room.name:
        return room, room.name
    else:
        return Game.rooms[room], room


def __get_cache(room_name, flag_type):
    global _room_flag_refresh_time, _room_flag_cache
    __check_new_flags()
    if Game.time > _room_flag_refresh_time:
        _room_flag_refresh_time = Game.time + 50
        _room_flag_cache = __new__(Map())
    if room_name in _room_flag_cache and flag_type in _room_flag_cache[room_name]:
        return _room_flag_cache[room_name][flag_type]
    else:
        return None


def find_flags(room, flag_type):
    room, room_name = __get_room_and_name(room)
    cached = __get_cache(room_name, flag_type)
    if cached:
        return cached
    flag_def = flag_definitions[flag_type]
    if room:
        flag_list = room.find(FIND_FLAGS, {
            "filter": {"color": flag_def[0], "secondaryColor": flag_def[1]}
        })
    else:
        flag_list = []
        for flag_name in Object.keys(Game.flags):
            flag = Game.flags[flag_name]
            if flag.pos.roomName == room_name and flag.color == flag_def[0] \
                    and flag.secondaryColor == flag_def[1]:
                flag_list.append(flag)
    if room_name in _room_flag_cache:
        _room_flag_cache[room_name][flag_type] = flag_list
    else:
        _room_flag_cache[room_name] = {flag_type: flag_list}
    return flag_list


def find_by_main_with_sub(room, main_type):
    room, room_name = __get_room_and_name(room)
    # we're assuming that no MAIN type has the same identity as any full type
    cached = __get_cache(room_name, main_type)
    if cached:
        return cached

    flag_primary = main_to_flag_primary[main_type]

    if room:
        flag_list = []
        for flag in room.find(FIND_FLAGS, {"filter": {"color": flag_primary}}):
            flag_list.append((flag, flag_secondary_to_sub[flag.secondaryColor]))
    else:
        flag_list = []
        for name in Object.keys(Game.flags):
            flag = Game.flags[name]
            if flag.pos.roomName == room_name and flag.color == flag_primary:
                secondary = flag_secondary_to_sub[flag.secondaryColor]
                if secondary:  # don't pick flags which don't match any of the secondary colors
                    flag_list.append([flag, secondary])

    if room_name in _room_flag_cache:
        _room_flag_cache[room_name][main_type] = flag_list
    else:
        _room_flag_cache[room_name] = {main_type: flag_list}

    return flag_list


def find_ms_flag(room, main_type, sub_type):
    type_name = "{}_{}".format(main_type, sub_type)
    room, room_name = __get_room_and_name(room)
    cached = __get_cache(room_name, "{}_{}".format(main_type, sub_type))
    if cached:
        return cached
    primary = main_to_flag_primary[main_type]
    secondary = sub_to_flag_secondary[sub_type]
    if room:
        flag_list = room.find(FIND_FLAGS, {
            "filter": {"color": primary, "secondaryColor": secondary}
        })
    else:
        flag_list = []
        for flag_name in Object.keys(Game.flags):
            flag = Game.flags[flag_name]
            if flag.pos.roomName == room_name and flag.color == primary \
                    and flag.secondaryColor == secondary:
                flag_list.append(flag)
    if room_name in _room_flag_cache:
        _room_flag_cache[room_name][type_name] = flag_list
    else:
        _room_flag_cache[room_name] = {type_name: flag_list}
    return flag_list


_global_flag_cache = __new__(Map())
_global_flag_refresh_time = Game.time + 50


def find_flags_global(flag_type, reload=False):
    global _global_flag_refresh_time, _global_flag_cache
    __check_new_flags()
    if Game.time > _global_flag_refresh_time:
        _global_flag_refresh_time = Game.time + 50
        _global_flag_cache = __new__(Map())
    if _global_flag_cache[flag_type] and not reload:
        return _global_flag_cache[flag_type]
    flag_def = flag_definitions[flag_type]
    flag_list = []
    for name in Object.keys(Game.flags):
        flag = Game.flags[name]
        if flag.color == flag_def[0] and flag.secondaryColor == flag_def[1]:
            flag_list.append(flag)
    _global_flag_cache[flag_type] = flag_list
    return flag_list


_closest_flag_cache = __new__(Map())
_closest_flag_refresh_time = Game.time + 50


def squared_distance(x1, y1, x2, y2):
    """
    TODO: this is duplicated in movement.py - currently necessary to avoid circular imports though.
    Gets the squared distance between two x, y positions
    :return: an integer, the squared linear distance
    """
    x_diff = (x1 - x2)
    y_diff = (y1 - y2)
    return x_diff * x_diff + y_diff * y_diff


def find_closest_in_room(pos, flag_type):
    global _closest_flag_refresh_time, _closest_flag_cache
    __check_new_flags()
    if Game.time > _closest_flag_refresh_time:
        _closest_flag_refresh_time = Game.time + 50
        _closest_flag_cache = __new__(Map())
    key = "{}_{}_{}_{}".format(pos.roomName, pos.x, pos.y, flag_type)
    if key in _closest_flag_cache:
        return _closest_flag_cache[key]
    closest_distance = math.pow(2, 30)
    closest_flag = None
    for flag in find_flags(pos.roomName, flag_type):
        distance = squared_distance(pos.x, pos.y, flag.pos.x, flag.pos.y)
        if distance < closest_distance:
            closest_distance = distance
            closest_flag = flag
    _closest_flag_cache[key] = closest_flag

    return closest_flag


def __create_flag(position, flag_type, primary, secondary):
    name = "{}_{}".format(flag_type, random_digits())
    # TODO: Make some sort of utility for finding a visible position, so we can do this
    # even if all our spawns are dead!
    known_position = Game.spawns[Object.keys(Game.spawns)[0]].pos
    flag_name = known_position.createFlag(name, primary, secondary)
    if Memory.flags_to_move:
        Memory.flags_to_move.push((flag_name, position))
    else:
        Memory.flags_to_move = [(flag_name, position)]
    return flag_name


def create_flag(position, flag_type):
    flag_def = flag_definitions[flag_type]
    __create_flag(position, flag_type, flag_def[0], flag_def[1])


def create_ms_flag(position, main, sub):
    __create_flag(position, "{}_{}".format(main, sub), main_to_flag_primary[main], sub_to_flag_secondary[sub])


def random_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
