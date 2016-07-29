from screeps_constants import *

DEPOT = "depot"
EXIT_NORTH = "exit_north"
EXIT_EAST = "exit_east"
EXIT_SOUTH = "exit_south"
EXIT_WEST = "exit_west"
REMOTE_MINE = "harvest"

DIR_TO_EXIT_FLAG = {
    TOP: EXIT_NORTH,
    LEFT: EXIT_WEST,
    BOTTOM: EXIT_SOUTH,
    RIGHT: EXIT_WEST,
}

flag_definitions = {
    DEPOT: (COLOR_BLUE, COLOR_BLUE),
    EXIT_NORTH: (COLOR_WHITE, COLOR_RED),
    EXIT_EAST: (COLOR_WHITE, COLOR_PURPLE),
    EXIT_SOUTH: (COLOR_WHITE, COLOR_BLUE),
    EXIT_WEST: (COLOR_WHITE, COLOR_CYAN),
    REMOTE_MINE: (COLOR_GREEN, COLOR_CYAN),
}


def is_def(flag, type):
    flag_def = flag_definitions[type]
    return flag.color == flag_def[0] and flag.secondaryColor == flag_def[1]


_room_flag_cache = {}


def get_flags(room, type):
    if room.name:
        room_name = room.name
    else:
        room_name = room
    if _room_flag_cache[room_name] and _room_flag_cache[room_name][type]:
        return _room_flag_cache[room_name][type]
    flag_def = flag_definitions[type]
    if room.name is room_name:
        # this is a room object
        list = room.find(FIND_FLAGS, {
            "filter": {"color": flag_def[0], "secondaryColor": flag_def[1]}
        })
    elif Game.rooms[room_name]:
        list = Game.rooms[room_name].find(FIND_FLAGS, {
            "filter": {"color": flag_def[0], "secondaryColor": flag_def[1]}
        })
    else:
        list = []
        for name in Object.keys(Game.flags):
            flag = Game.flags[name]
            if flag.pos.roomName == room_name and flag.color == flag_def[0] \
                    and flag.secondaryColor == flag_def[1]:
                list.append(flag)
    if _room_flag_cache[room_name]:
        _room_flag_cache[room_name][type] = list
    else:
        _room_flag_cache[room_name] = {type: list}
    return list


_global_flag_cache = {}


def get_global_flags(type, reload=False):
    if _global_flag_cache[type] and not reload:
        return _global_flag_cache[type]
    flag_def = flag_definitions[type]
    flag_list = []
    for name in Object.keys(Game.flags):
        flag = Game.flags[name]
        if flag.color == flag_def[0] and flag.secondaryColor == flag_def[1]:
            flag_list.append(flag)
    _global_flag_cache[type] = flag_list
    return flag_list


def create_flag(position, type):
    flag_def = flag_definitions[type]
    name = "{}_{}".format(type, random_digits())
    position.createFlag(name, flag_def[0], flag_def[1])


def random_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
