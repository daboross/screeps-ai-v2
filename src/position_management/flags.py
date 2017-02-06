"""
Flag colors:

Red:
    Red: DESTRUCT_WALL
    Purple: DESTRUCT_RAMPART
    Blue: DESTRUCT_EXTENSION
    Cyan: DESTRUCT_SPAWN
    Green: DESTRUCT_TOWER
    Yellow: DESTRUCT_STORAGE
    Orange: DESTRUCT_LINK
    Brown: DESTRUCT_EXTRACTOR
    Grey: DESTRUCT_TERMINAL
    White: DESTRUCT_ROAD
Purple:
    Red: CONSTRUCT_WALL
    Purple: CONSTRUCT_RAMPART
    Blue: CONSTRUCT_EXTENSION
    Cyan: CONSTRUCT_SPAWN
    Green: CONSTRUCT_TOWER
    Yellow: CONSTRUCT_STORAGE
    Orange: CONSTRUCT_LINK
    Brown: CONSTRUCT_EXTRACTOR
    Grey: CONSTRUCT_TERMINAL
    White: CONSTRUCT_ROAD
Blue:
    Red:
    Purple: LOCAL_MINE
    Blue: DEPOT
    Cyan: SPAWN_FILL_WAIT
    Green: UPGRADER_SPOT
    Yellow:
    Orange:
    Brown:
    Grey: SLIGHTLY_AVOID
    White: SK_LAIR_SOURCE_NOTED
Cyan:
    Red: TD_H_H_STOP        - TowerDrain Healing Healer Stop
    Purple: TD_H_D_STOP     - Tower Drain Healing Damaged Stop
    Blue: TD_D_GOAD         - Tower Drain Goading Stop
    Cyan: RANGED_DEFENSE    - Kiting defender spot (optional memory: { size: numRangedAttackParts })
    Green: ATTACK_DISMANTLE - Dismantler Spot (optional memory: { size: numWorkParts })
    Yellow: RAID_OVER       - Raid Over Notice (unused)
    Orange: ENERGY_GRAB     - Energy grab spot (optional memory: { size: numCarryParts })
    Brown: SCOUT            - Scout Here
    Grey: ATTACK_POWER_BANK - Power bank attacker spot
    White: REAP_POWER_BANK  - Power bank carrier spot
Green:
    Red:
    Purple: CLAIM_LATER     - Controller to claim
    Blue:
    Cyan: REMOTE_MINE       - Remote mine source (set memory: { active: true }, optional: { do_reserve: true } )
    Green:
    Yellow:
    Orange:
    Brown:
    Grey: RESERVE_NOW       - Controller to reserve (not that optimized at the moment)
    White:
Yellow:
    Red:
    Purple:
    Blue:
    Cyan:
    Green:
    Yellow:
    Orange:
    Brown:
    Grey:
    White:
Orange:
    Red:
    Purple:
    Blue:
    Cyan:
    Green:
    Yellow:
    Orange:
    Brown:
    Grey:
    White:
Brown:
    Red:
    Purple:
    Blue:
    Cyan:
    Green:
    Yellow:
    Orange:
    Brown:
    Grey:
    White:
Grey:
    Red:
    Purple:
    Blue:
    Cyan:
    Green:
    Yellow:
    Orange:
    Brown:
    Grey:
    White:
White:
    Red:
    Purple:
    Blue:
    Cyan:
    Green: REROUTE              - Portal marked for current use (hardcoded name: `reroute`)
    Yellow: REROUTE_DESTINATION - Destination of a reroute (hardcoded name: `reroute_destination`)
    Orange:
    Brown:
    Grey:
    White:
"""

from constants import ATTACK_DISMANTLE, ATTACK_POWER_BANK, CLAIM_LATER, DEPOT, ENERGY_GRAB, LOCAL_MINE, RAID_OVER, \
    RAMPART_DEFENSE, RANGED_DEFENSE, REAP_POWER_BANK, REMOTE_MINE, REROUTE, REROUTE_DESTINATION, RESERVE_NOW, SCOUT, \
    SK_LAIR_SOURCE_NOTED, SLIGHTLY_AVOID, SPAWN_FILL_WAIT, TD_D_GOAD, TD_H_D_STOP, TD_H_H_STOP, UPGRADER_SPOT
from jstools.js_set_map import new_map
from jstools.screeps import *
from utilities import naming

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

# Building main: 10*
MAIN_BUILD = 100
MAIN_DESTRUCT = 101
# Building owned structures: 11*
SUB_RAMPART = 110
SUB_SPAWN = 111
SUB_EXTENSION = 112
SUB_TOWER = 113
SUB_STORAGE = 114
SUB_LINK = 115
SUB_EXTRACTOR = 116
SUB_TERMINAL = 117
# Building unowned structures: 12*
SUB_WALL = 120
SUB_ROAD = 121
SUB_CONTAINER = 122

flag_definitions = {
    LOCAL_MINE: (COLOR_BLUE, COLOR_PURPLE),
    DEPOT: (COLOR_BLUE, COLOR_BLUE),
    SPAWN_FILL_WAIT: (COLOR_BLUE, COLOR_CYAN),
    UPGRADER_SPOT: (COLOR_BLUE, COLOR_GREEN),
    SLIGHTLY_AVOID: (COLOR_BLUE, COLOR_GREY),
    SK_LAIR_SOURCE_NOTED: (COLOR_BLUE, COLOR_WHITE),
    TD_H_H_STOP: (COLOR_CYAN, COLOR_RED),
    TD_H_D_STOP: (COLOR_CYAN, COLOR_PURPLE),
    TD_D_GOAD: (COLOR_CYAN, COLOR_BLUE),
    ATTACK_DISMANTLE: (COLOR_CYAN, COLOR_GREEN),
    RAID_OVER: (COLOR_CYAN, COLOR_YELLOW),
    ENERGY_GRAB: (COLOR_CYAN, COLOR_ORANGE),
    SCOUT: (COLOR_CYAN, COLOR_BROWN),
    RANGED_DEFENSE: (COLOR_CYAN, COLOR_CYAN),
    ATTACK_POWER_BANK: (COLOR_CYAN, COLOR_GREY),
    REAP_POWER_BANK: (COLOR_CYAN, COLOR_WHITE),
    REMOTE_MINE: (COLOR_GREEN, COLOR_CYAN),
    CLAIM_LATER: (COLOR_GREEN, COLOR_PURPLE),
    RESERVE_NOW: (COLOR_GREEN, COLOR_GREY),
    RAMPART_DEFENSE: (COLOR_GREEN, COLOR_GREEN),
    REROUTE: (COLOR_WHITE, COLOR_GREEN),
    REROUTE_DESTINATION: (COLOR_WHITE, COLOR_YELLOW),
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
    SUB_EXTRACTOR: COLOR_BROWN,
    SUB_CONTAINER: COLOR_BROWN,  # Dual flags, but container can only be used for destruct.
    SUB_ROAD: COLOR_WHITE,
    SUB_TERMINAL: COLOR_GREY,
}
flag_secondary_to_sub = {
    COLOR_RED: SUB_WALL,
    COLOR_PURPLE: SUB_RAMPART,
    COLOR_BLUE: SUB_EXTENSION,
    COLOR_CYAN: SUB_SPAWN,
    COLOR_GREEN: SUB_TOWER,
    COLOR_YELLOW: SUB_STORAGE,
    COLOR_ORANGE: SUB_LINK,
    COLOR_BROWN: SUB_EXTRACTOR,
    COLOR_GREY: SUB_TERMINAL,
    COLOR_WHITE: SUB_ROAD,
}
flag_sub_to_structure_type = {
    SUB_SPAWN: STRUCTURE_SPAWN,
    SUB_EXTENSION: STRUCTURE_EXTENSION,
    SUB_RAMPART: STRUCTURE_RAMPART,
    SUB_WALL: STRUCTURE_WALL,
    SUB_STORAGE: STRUCTURE_STORAGE,
    SUB_TOWER: STRUCTURE_TOWER,
    SUB_LINK: STRUCTURE_LINK,
    SUB_EXTRACTOR: STRUCTURE_EXTRACTOR,
    SUB_CONTAINER: STRUCTURE_CONTAINER,
    SUB_ROAD: STRUCTURE_ROAD,
    SUB_TERMINAL: STRUCTURE_TERMINAL,
}
structure_type_to_flag_sub = {
    STRUCTURE_SPAWN: SUB_SPAWN,
    STRUCTURE_EXTENSION: SUB_EXTENSION,
    STRUCTURE_RAMPART: SUB_RAMPART,
    STRUCTURE_WALL: SUB_WALL,
    STRUCTURE_STORAGE: SUB_STORAGE,
    STRUCTURE_TOWER: SUB_TOWER,
    STRUCTURE_LINK: SUB_LINK,
    STRUCTURE_EXTRACTOR: SUB_EXTRACTOR,
    STRUCTURE_CONTAINER: SUB_CONTAINER,
    STRUCTURE_ROAD: SUB_ROAD,
    STRUCTURE_TERMINAL: SUB_TERMINAL,
}

_REFRESH_EVERY = 50

_last_flag_len = 0
_last_checked_flag_len = 0


def refresh_flag_caches():
    global _last_flag_len, _last_checked_flag_len
    global _room_flag_cache, _room_flag_refresh_time
    global _global_flag_refresh_time, _global_flag_cache
    global _closest_flag_refresh_time, _closest_flag_cache
    refresh_time = Game.time + _REFRESH_EVERY
    _room_flag_cache = new_map()
    _room_flag_refresh_time = refresh_time
    _global_flag_cache = new_map()
    _global_flag_refresh_time = refresh_time
    _closest_flag_cache = new_map()
    _closest_flag_refresh_time = refresh_time
    _last_flag_len = _.size(Game.flags)


def __check_new_flags():
    global _last_flag_len, _last_checked_flag_len
    global _room_flag_cache, _room_flag_refresh_time
    global _global_flag_refresh_time, _global_flag_cache
    global _closest_flag_refresh_time, _closest_flag_cache
    if _last_checked_flag_len < Game.time:
        length = _.size(Game.flags)
        if _last_flag_len != length:
            refresh_flag_caches()


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


_room_flag_cache = new_map()
_room_flag_refresh_time = Game.time + _REFRESH_EVERY


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
        _room_flag_refresh_time = Game.time + _REFRESH_EVERY
        _room_flag_cache = new_map()

    if _room_flag_cache.has(room_name) and _room_flag_cache.get(room_name).has(flag_type):
        return _room_flag_cache.get(room_name).get(flag_type)
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
    if _room_flag_cache.has(room_name):
        _room_flag_cache.get(room_name).set(flag_type, flag_list)
    else:
        _room_flag_cache.set(room_name, new_map([[flag_type, flag_list]]))
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

    if _room_flag_cache.has(room_name):
        _room_flag_cache.get(room_name).set(main_type, flag_list)
    else:
        _room_flag_cache.set(room_name, new_map([[main_type, flag_list]]))
    return flag_list


def find_ms_flags(room, main_type, sub_type):
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
    if _room_flag_cache.has(room_name):
        _room_flag_cache.get(room_name).set(type_name, flag_list)
    else:
        _room_flag_cache.set(room_name, new_map([[type_name, flag_list]]))
    return flag_list


_global_flag_cache = new_map()
_global_flag_refresh_time = Game.time + _REFRESH_EVERY


def find_flags_global(flag_type, reload=False):
    global _global_flag_refresh_time, _global_flag_cache
    __check_new_flags()
    if Game.time > _global_flag_refresh_time:
        _global_flag_refresh_time = Game.time + _REFRESH_EVERY
        _global_flag_cache = new_map()
    if _global_flag_cache.has(flag_type) and not reload:
        return _global_flag_cache.get(flag_type)
    flag_def = flag_definitions[flag_type]
    flag_list = []
    for name in Object.keys(Game.flags):
        flag = Game.flags[name]
        if flag.color == flag_def[0] and flag.secondaryColor == flag_def[1]:
            flag_list.append(flag)
    _global_flag_cache.set(flag_type, flag_list)
    return flag_list


def find_flags_ms_global(main_type, sub_type, reload=False):
    type_name = "{}_{}".format(main_type, sub_type)
    global _global_flag_refresh_time, _global_flag_cache
    __check_new_flags()
    if Game.time > _global_flag_refresh_time:
        _global_flag_refresh_time = Game.time + _REFRESH_EVERY
        _global_flag_cache = new_map()
    if _global_flag_cache.has(type_name) and not reload:
        return _global_flag_cache.get(type_name)
    primary = main_to_flag_primary[main_type]
    secondary = sub_to_flag_secondary[sub_type]
    flag_list = []
    for name in Object.keys(Game.flags):
        flag = Game.flags[name]
        if flag.color == primary and flag.secondaryColor == secondary:
            flag_list.append(flag)
    _global_flag_cache.set(type_name, flag_list)
    return flag_list


def find_by_main_with_sub_global(main_type, reload=False):
    global _global_flag_refresh_time, _global_flag_cache
    __check_new_flags()
    if Game.time > _global_flag_refresh_time:
        _global_flag_refresh_time = Game.time + _REFRESH_EVERY
        _global_flag_cache = new_map()
    # we're assuming that no MAIN type has the same identity as any full type
    if _global_flag_cache.has(main_type) and not reload:
        return _global_flag_cache.get(main_type)
    primary = main_to_flag_primary[main_type]
    flag_list = []
    for name in Object.keys(Game.flags):
        flag = Game.flags[name]
        if flag.color == primary:
            secondary = flag_secondary_to_sub[flag.secondaryColor]
            if secondary:  # don't pick flags which don't match any of the secondary colors
                flag_list.append([flag, secondary])
    _global_flag_cache.set(main_type, flag_list)
    return flag_list


_closest_flag_cache = new_map()
_closest_flag_refresh_time = Game.time + _REFRESH_EVERY


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
        _closest_flag_cache = new_map()
    key = "{}_{}_{}_{}".format(pos.roomName, pos.x, pos.y, flag_type)
    if _closest_flag_cache.has(key):
        return _closest_flag_cache.get(key)
    closest_distance = Infinity
    closest_flag = None
    for flag in find_flags(pos.roomName, flag_type):
        distance = squared_distance(pos.x, pos.y, flag.pos.x, flag.pos.y)
        if distance < closest_distance:
            closest_distance = distance
            closest_flag = flag
    _closest_flag_cache.set(key, closest_flag)

    return closest_flag


def __create_flag(position, flag_type, primary, secondary):
    if position.pos:
        position = position.pos
    name = "{}_{}".format(flag_type, naming.random_digits())
    # TODO: Make some sort of utility for finding a visible position, so we can do this
    # even if all our spawns are dead!
    room = Game.rooms[position.roomName]
    if room:
        flag_name = room.createFlag(position, name, primary, secondary)
        print("[flags] Created flag at {}: {}".format(position, flag_name))
        return flag_name
    else:
        known_position = Game.spawns[Object.keys(Game.spawns)[0]].pos
        flag_name = known_position.createFlag(name, primary, secondary)
        if Memory.flags_to_move:
            Memory.flags_to_move.push((flag_name, position))
        else:
            Memory.flags_to_move = [(flag_name, position)]
        return flag_name


def create_flag(position, flag_type):
    flag_def = flag_definitions[flag_type]
    return __create_flag(position, flag_type, flag_def[0], flag_def[1])


def create_ms_flag(position, main, sub):
    return __create_flag(position, "{}_{}".format(main, sub), main_to_flag_primary[main], sub_to_flag_secondary[sub])


def rename_flags():
    refresh_flag_caches()
    for name in Object.keys(flag_definitions):
        for flag in find_flags_global(name):
            if Game.cpu.getUsed() > 400:
                refresh_flag_caches()
                return "Used too much CPU!"
            if Game.rooms[flag.pos.roomName] and (flag.name.startswith("Flag") or not flag.name.includes('_')) \
                    and flag.name not in Memory.flags:
                new_name = create_flag(flag.pos, name)
                if Memory.flags[flag.name]:
                    if len(Memory.flags[flag.name]):
                        Memory.flags[new_name] = Memory.flags[flag.name]
                    del Memory.flags[flag.name]
                flag.remove()
    for main in Object.keys(main_to_flag_primary):
        for flag, sub in find_by_main_with_sub_global(main):
            if Game.cpu.getUsed() > 400:
                refresh_flag_caches()
                return "Used too much CPU!"
            if Game.rooms[flag.pos.roomName] and (flag.name.startswith("Flag") or not flag.name.includes('_')) \
                    and flag.name not in Memory.flags:
                new_name = create_ms_flag(flag.pos, main, sub)
                if Memory.flags[flag.name]:
                    if len(Memory.flags[flag.name]):
                        Memory.flags[new_name] = Memory.flags[flag.name]
                    del Memory.flags[flag.name]
                flag.remove()
    refresh_flag_caches()


def look_for(room, position, main, sub=None):
    """
    :type room: rooms.room_mind.RoomMind
    """
    if not room.look_at:
        raise ValueError("Invalid room argument")
    if position.pos:
        position = position.pos
    if sub:
        return _.find(room.look_at(LOOK_FLAGS, position),
                      lambda f: f.color == main_to_flag_primary[main] and
                                f.secondaryColor == sub_to_flag_secondary[sub])
    else:
        flag_def = flag_definitions[main]
        if not flag_def:
            # TODO: This is a hack because a common pattern is
            # look_for(room, pos, flags.MAIN_DESTRUCT, flags.structure_type_to_flag_sub[structure_type])
            # if there is no flag for a given structure, sub will be undefined, and thus this side will be called
            # and not the above branch.
            return []
        return _.find(room.look_at(LOOK_FLAGS, position),
                      lambda f: f.color == flag_def[0] and f.secondaryColor == flag_def[1])


_flag_sponsor_regex = __new__(RegExp("^(W|E)([0-9]{1,3})(N|S)([0-9]{1,3})"))


def flag_sponsor(flag, backup_search_by=None):
    """
    :type backup_search_by: empire.hive.HiveMind
    :param flag: Flag to find the sponsor of
    :param backup_search_by: The hive to search for backup, if any
    :return:
    """
    if flag.name in Memory.flags:
        sponsor = flag.memory.sponsor
        if sponsor:
            return sponsor
    sponsor_match = _flag_sponsor_regex.exec(flag.name)
    if sponsor_match:
        return sponsor_match[0]
    elif backup_search_by:
        room = backup_search_by.get_closest_owned_room(flag.pos.roomName)
        if room:
            return room.name
        else:
            return None
    else:
        return None
