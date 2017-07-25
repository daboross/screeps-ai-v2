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
    Cyan: REMOTE_MINE       - Remote mine source (optional memory: { do_reserve: true } )
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
    Red: SQUAD_KITING_HEALER    - Marks a location for a kiting attacker and healer squad.
    Purple: SQUAD_DUAL_SCOUTS   - Marks a location for two scouts.
    Blue: SQUAD_4_SCOUTS        - Marks a location for four scouts.
    Cyan: SQUAD_DUAL_ATTACK     - Marks a location for one attack and one heal squad.
    Green: SQUAD_DISMANTLE_RANGED - Marks a location for one ranged, one dismantle and two healer squad.
    Yellow: SQUAD_TOWER_DRAIN   - Marks a location for three healers.
    Orange:
    Brown: SQUAD_SIGN_CLEAR     - Marks a location to clear a controller sign.
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
    Red: SUPPORT_MINE           - Marker for where a mine should be for supporting
    Purple: SUPPORT_WALL        - Marker for what wall the supporting creeps are repairing currently
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
from typing import Dict, List, Optional, TYPE_CHECKING, Tuple, Union, cast

from constants import ATTACK_DISMANTLE, ATTACK_POWER_BANK, CLAIM_LATER, DEPOT, ENERGY_GRAB, LOCAL_MINE, RAID_OVER, \
    RAMPART_DEFENSE, RANGED_DEFENSE, REAP_POWER_BANK, REMOTE_MINE, REROUTE, REROUTE_DESTINATION, RESERVE_NOW, SCOUT, \
    SK_LAIR_SOURCE_NOTED, SLIGHTLY_AVOID, SPAWN_FILL_WAIT, SQUAD_4_SCOUTS, SQUAD_DISMANTLE_RANGED, SQUAD_DUAL_ATTACK, \
    SQUAD_DUAL_SCOUTS, SQUAD_KITING_PAIR, SQUAD_SIGN_CLEAR, SQUAD_TOWER_DRAIN, SUPPORT_MINE, SUPPORT_WALL, TD_D_GOAD, \
    TD_H_D_STOP, TD_H_H_STOP, UPGRADER_SPOT
from jstools.js_set_map import new_map
from jstools.screeps import *
from utilities import naming

if TYPE_CHECKING:
    from rooms.room_mind import RoomMind
    from empire.hive import HiveMind
    from rooms.defense import RoomDefense

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

# Building main: 10*
MAIN_BUILD = 100
MAIN_DESTRUCT = 101
MAIN_SQUAD = 102
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
    SQUAD_KITING_PAIR: (COLOR_ORANGE, COLOR_RED),
    SQUAD_DUAL_SCOUTS: (COLOR_ORANGE, COLOR_PURPLE),
    SQUAD_4_SCOUTS: (COLOR_ORANGE, COLOR_BLUE),
    SQUAD_DUAL_ATTACK: (COLOR_ORANGE, COLOR_CYAN),
    SQUAD_DISMANTLE_RANGED: (COLOR_ORANGE, COLOR_GREEN),
    SQUAD_SIGN_CLEAR: (COLOR_ORANGE, COLOR_BROWN),
    SQUAD_TOWER_DRAIN: (COLOR_ORANGE, COLOR_YELLOW),
    SUPPORT_MINE: (COLOR_GREY, COLOR_RED),
    SUPPORT_WALL: (COLOR_GREY, COLOR_PURPLE),
}

reverse_definitions = {}  # type: Dict[str, Dict[str, int]]

main_to_flag_primary = {
    MAIN_DESTRUCT: COLOR_RED,
    MAIN_BUILD: COLOR_PURPLE,
    MAIN_SQUAD: COLOR_ORANGE,
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
flag_secondary_to_sub = {}

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
structure_type_to_flag_sub = {}


def define_reverse_maps():
    # type: () -> None
    for flag_type in Object.keys(flag_definitions):
        primary, secondary = flag_definitions[flag_type]
        if primary in reverse_definitions:
            reverse_definitions[primary][secondary] = int(flag_type)
        else:
            reverse_definitions[primary] = {secondary: int(flag_type)}
    for sub_type in Object.keys(sub_to_flag_secondary):
        if sub_type != SUB_CONTAINER:
            flag_secondary_to_sub[sub_to_flag_secondary[sub_type]] = int(sub_type)
    for sub_type in Object.keys(flag_sub_to_structure_type):
        structure_type_to_flag_sub[flag_sub_to_structure_type[sub_type]] = int(sub_type)


define_reverse_maps()

_REFRESH_EVERY = 50

_last_flag_len = 0
_last_checked_flag_len = 0

_cache_refresh_time = 0

_flag_type_to_flags = new_map()
_flag_color_to_flag_secondary_color_to_flags = new_map()
_room_name_to_flag_type_to_flags = new_map()
_room_name_to_color_to_secondary_to_flags = new_map()

_ALL_OF_PRIMARY = '__all__'


def refresh_flag_caches():
    # type: () -> None
    global _last_flag_len, _last_checked_flag_len, _cache_refresh_time, \
        _room_name_to_flag_type_to_flags, _flag_type_to_flags, _flag_color_to_flag_secondary_color_to_flags

    game_flag_names = Object.keys(Game.flags)

    _cache_refresh_time = Game.time + _REFRESH_EVERY
    _last_flag_len = len(game_flag_names)

    _room_name_to_flag_type_to_flags = new_map()
    _flag_type_to_flags = new_map()
    _flag_color_to_flag_secondary_color_to_flags = new_map()

    possible_flag_mains = _.values(main_to_flag_primary)

    for flag_name in game_flag_names:
        flag = Game.flags[flag_name]
        if possible_flag_mains.includes(flag.color):
            if _flag_color_to_flag_secondary_color_to_flags.has(flag.color):
                flag_secondary_to_flags = _flag_color_to_flag_secondary_color_to_flags.get(flag.color)
            else:
                flag_secondary_to_flags = new_map()
                _flag_color_to_flag_secondary_color_to_flags.set(flag.color, flag_secondary_to_flags)
            if flag_secondary_to_flags.has(flag.secondaryColor):
                flag_secondary_to_flags.get(flag.secondaryColor).push(flag)
            else:
                flag_secondary_to_flags.set(flag.secondaryColor, [flag])

            if flag_secondary_to_flags.has(_ALL_OF_PRIMARY):
                flag_secondary_to_flags.get(_ALL_OF_PRIMARY).push(flag)
            else:
                flag_secondary_to_flags.set(_ALL_OF_PRIMARY, [flag])

            if _room_name_to_color_to_secondary_to_flags.has(flag.pos.roomName):
                in_room_color_to_secondary_to_flags = _room_name_to_color_to_secondary_to_flags.get(flag.pos.roomName)
            else:
                in_room_color_to_secondary_to_flags = new_map()
                _room_name_to_color_to_secondary_to_flags.set(flag.pos.roomName, in_room_color_to_secondary_to_flags)

            if in_room_color_to_secondary_to_flags.has(flag.color):
                in_room_flag_secondary_to_flags = in_room_color_to_secondary_to_flags.get(flag.color)
            else:
                in_room_flag_secondary_to_flags = new_map()
                in_room_color_to_secondary_to_flags.set(flag.color, in_room_flag_secondary_to_flags)
            if in_room_flag_secondary_to_flags.has(flag.secondaryColor):
                in_room_flag_secondary_to_flags.get(flag.secondaryColor).push(flag)
            else:
                in_room_flag_secondary_to_flags.set(flag.secondaryColor, [flag])

            if in_room_flag_secondary_to_flags.has(_ALL_OF_PRIMARY):
                in_room_flag_secondary_to_flags.get(_ALL_OF_PRIMARY).push(flag)
            else:
                in_room_flag_secondary_to_flags.set(_ALL_OF_PRIMARY, [flag])

        if _flag_type_to_flags.has(flag.hint):
            _flag_type_to_flags.get(flag.hint).push(flag)
        else:
            _flag_type_to_flags.set(flag.hint, [flag])

        if _room_name_to_flag_type_to_flags.has(flag.pos.roomName):
            in_room_flag_type_to_flags = _room_name_to_flag_type_to_flags.get(flag.pos.roomName)
        else:
            in_room_flag_type_to_flags = new_map()
            _room_name_to_flag_type_to_flags.set(flag.pos.roomName, in_room_flag_type_to_flags)
        if in_room_flag_type_to_flags.has(flag.hint):
            in_room_flag_type_to_flags.get(flag.hint).push(flag)
        else:
            in_room_flag_type_to_flags.set(flag.hint, [flag])


def __check_new_flags():
    # type: () -> None
    global _last_flag_len, _last_checked_flag_len
    if _last_checked_flag_len < Game.time:
        _last_checked_flag_len = Game.time + 1  # check every 2 ticks
        length = _.size(Game.flags)
        if _last_flag_len != length:
            refresh_flag_caches()
        elif _cache_refresh_time < Game.time:
            refresh_flag_caches()


def move_flags():
    # type: () -> None
    if Memory.flags_to_move:
        for name, pos in Memory.flags_to_move:
            pos = __new__(RoomPosition(pos.x, pos.y, pos.roomName))
            result = Game.flags[name].setPosition(pos)
            print("[flags] Moving flag {} to {}. Result: {}".format(name, pos, result))
        del Memory.flags_to_move


_HasRoom = Union[Room, RoomMind, RoomDefense]
_IsRoom = Union[_HasRoom, str]


def __get_room_name(room_arg):
    # type: (_IsRoom) -> str
    if cast(Union[RoomMind, RoomDefense], room_arg).room:
        room = cast(Union[RoomMind, RoomDefense], room_arg).room
    else:
        room = cast(Room, room_arg)
    if room.name:
        return room.name
    else:
        return str(room)


def find_flags(room, flag_type):
    # type: (_IsRoom, int) -> List[Flag]
    room_name = __get_room_name(room)

    __check_new_flags()

    flag_type_to_flags = _room_name_to_flag_type_to_flags.get(room_name)
    if flag_type_to_flags is undefined:
        return []
    flags = flag_type_to_flags.get(flag_type)
    if flags:
        return flags
    else:
        return []


def find_by_main_with_sub(room, main_type):
    # type: (_IsRoom, int) -> List[Tuple[Flag, int]]
    room_name = __get_room_name(room)

    __check_new_flags()

    in_room_color_to_secondary_to_flags = _room_name_to_color_to_secondary_to_flags.get(room_name)
    if not in_room_color_to_secondary_to_flags:
        return []

    of_this_main = in_room_color_to_secondary_to_flags.get(main_to_flag_primary[main_type])
    if not of_this_main:
        return []

    result = []
    for flag in of_this_main.get(_ALL_OF_PRIMARY):
        sub_type = flag_secondary_to_sub[flag.secondaryColor]
        if sub_type:
            result.append((flag, sub_type))

    return result


def find_ms_flags(room, main_type, sub_type):
    # type: (_IsRoom, int, int) -> List[Flag]
    room_name = __get_room_name(room)

    __check_new_flags()

    in_room_color_to_secondary_to_flags = _room_name_to_color_to_secondary_to_flags.get(room_name)
    if not in_room_color_to_secondary_to_flags:
        return []

    of_this_main = in_room_color_to_secondary_to_flags.get(main_to_flag_primary[main_type])
    if not of_this_main:
        return []

    result = of_this_main.get(sub_to_flag_secondary[sub_type])

    if result:
        return result
    else:
        return []


def find_flags_global(flag_type):
    # type: (int) -> List[Flag]
    __check_new_flags()

    result = _flag_type_to_flags.get(flag_type)

    if result:
        return result
    else:
        return []


def find_flags_global_multitype_shared_primary(flag_types):
    # type: (List[int]) -> List[Flag]
    __check_new_flags()

    shared_primary_color = None
    secondary_colors = []
    for flag_type in flag_types:
        definition = flag_definitions[flag_type]
        if shared_primary_color is None:
            shared_primary_color = definition[0]
        elif shared_primary_color != definition[0]:
            print('[flags][find_flags_global_multitype_shared_first] Called with diverse firsts! {}'.format(flag_types))
            return None
        secondary_colors.append(definition[1])

    result = []

    of_this_main = _flag_color_to_flag_secondary_color_to_flags.get(shared_primary_color)

    if not of_this_main:
        return result

    for flag in of_this_main.get(_ALL_OF_PRIMARY):
        if secondary_colors.includes(flag.secondaryColor):
            result.append(flag)
    return result


def find_flags_ms_global(main_type, sub_type):
    # type: (int, int) -> List[Flag]
    __check_new_flags()

    of_this_main = _flag_color_to_flag_secondary_color_to_flags.get(main_to_flag_primary[main_type])
    if not of_this_main:
        return []

    result = of_this_main.get(sub_to_flag_secondary[sub_type])

    if result:
        return result
    else:
        return []


def find_by_main_with_sub_global(main_type):
    # type: (int) -> List[Tuple[Flag, int]]
    __check_new_flags()

    of_this_main = _flag_color_to_flag_secondary_color_to_flags.get(main_to_flag_primary[main_type])
    if not of_this_main:
        return []

    result = []
    for flag in of_this_main.get(_ALL_OF_PRIMARY):
        sub_type = flag_secondary_to_sub[flag.secondaryColor]
        if sub_type:
            result.append((flag, sub_type))

    return result


def __create_flag(position, flag_type, primary, secondary, name_prefix):
    # type: (RoomPosition, Union[str, int], int, int, Optional[str]) -> Union[str, int]
    name = "{}_{}".format(flag_type, naming.random_digits())
    if name_prefix:
        name = "{}_{}".format(name_prefix, name)
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


def create_flag(position, flag_type, sponsor=None):
    # type: (RoomPosition, int, Optional[str]) -> Union[str, int]
    flag_def = flag_definitions[flag_type]
    return __create_flag(position, flag_type, flag_def[0], flag_def[1], sponsor)


def create_ms_flag(position, main, sub):
    # type: (RoomPosition, int, int) -> Union[str, int]
    return __create_flag(position, "{}_{}".format(main, sub), main_to_flag_primary[main], sub_to_flag_secondary[sub],
                         None)


def rename_flags():
    # type: () -> Optional[str]
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
    # type: (RoomMind, RoomPosition, int, Optional[int]) -> Optional[Flag]
    """
    :type room: rooms.room_mind.RoomMind
    :type position: RoomPosition
    :type main: int
    :type sub: int
    """
    if not room.look_at:
        raise ValueError("Invalid room argument")
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
            return None
        return cast(Optional[Flag], _.find(room.look_at(LOOK_FLAGS, position),
                                           lambda f: f.color == flag_def[0] and f.secondaryColor == flag_def[1]))


_flag_sponsor_regex = __new__(RegExp("^(W|E)([0-9]{1,3})(N|S)([0-9]{1,3})"))


def flag_sponsor(flag, backup_search_by=None):
    # type: (Flag, Optional[HiveMind]) -> Optional[str]
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


def _flag_hint():
    # type: () -> Optional[int]
    reverse_primary = reverse_definitions[this.color]
    result = None
    if reverse_primary:
        if this.secondaryColor in reverse_primary:
            result = reverse_primary[this.secondaryColor]
    Object.defineProperty(this, 'hint', {
        'value': result,
        'enumerable': True,
        'configurable': True,
    })
    return result


Object.defineProperty(Flag.prototype, 'hint', {
    'get': _flag_hint,
    'enumerable': True,
    'configurable': True,
})
