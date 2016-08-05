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
MAIN_DESTRUCT = "destruct"
MAIN_BUILD = "build"
SUB_WALL = "wall"
SUB_RAMPART = "rampart"
SUB_EXTENSION = "extension"

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
}

main_to_flag_primary = {
    MAIN_DESTRUCT: COLOR_RED,
    MAIN_BUILD: COLOR_PURPLE,
}
sub_to_flag_secondary = {
    SUB_WALL: COLOR_RED,
    SUB_RAMPART: COLOR_PURPLE,
    SUB_EXTENSION: COLOR_BLUE,
}
flag_secondary_to_sub = {
    COLOR_RED: SUB_WALL,
    COLOR_PURPLE: SUB_RAMPART,
    COLOR_BLUE: SUB_EXTENSION,
}


def move_flags():
    if Memory.flags_to_move:
        for name, pos in Memory.flags_to_move:
            pos = __new__(RoomPosition(pos.x, pos.y, pos.roomName))
            result = Game.flags[name].setPosition(pos)
            print("Moving flag {} to {}. Result: {}".format(name, pos, result))
        del Memory.flags_to_move


def is_def(flag, flag_type):
    flag_def = flag_definitions[flag_type]
    return flag.color == flag_def[0] and flag.secondaryColor == flag_def[1]


_room_flag_cache = {}
_room_flag_refresh_time = 0


def __get_room_and_name(room):
    if room.name:
        return room, room.name
    else:
        return Game.rooms[room], room


def __get_cache(room_name, flag_type):
    global _room_flag_refresh_time, _room_flag_cache
    if Game.time > _room_flag_refresh_time:
        _room_flag_refresh_time = Game.time + 100
        _room_flag_cache = {}
    if room_name in _room_flag_cache and flag_type in _room_flag_cache[room_name]:
        return _room_flag_cache[room_name][flag_type]
    else:
        return None


def get_flags(room, flag_type):
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
                flag_list.append((flag, flag_secondary_to_sub[flag.secondaryColor]))

    if room_name in _room_flag_cache:
        _room_flag_cache[room_name][main_type] = flag_list
    else:
        _room_flag_cache[room_name] = {main_type: flag_list}

    return flag_list


_global_flag_cache = {}


def get_global_flags(flag_type, reload=False):
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
