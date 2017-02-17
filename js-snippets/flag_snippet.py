
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

reverse_definitions = {}
for name in Object.keys(flag_definitions):
    primary, secondary = flag_definitions[name]
    if primary in reverse_definitions:
        reverse_definitions[primary][secondary] = name
    else:
        reverse_definitions[primary] = {secondary: name}

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
    refresh_time = Game.time + _REFRESH_EVERY
    _room_flag_cache = new_map()
    _room_flag_refresh_time = refresh_time
    _global_flag_cache = new_map()
    _global_flag_refresh_time = refresh_time
    _last_flag_len = _.size(Game.flags)


def __check_new_flags():
    global _last_flag_len, _last_checked_flag_len
    global _room_flag_cache, _room_flag_refresh_time
    global _global_flag_refresh_time, _global_flag_cache
    if _last_checked_flag_len < Game.time:
        length = _.size(Game.flags)
        if _last_flag_len != length:
            refresh_flag_caches()


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

def squared_distance(x1, y1, x2, y2):
    """
    TODO: this is duplicated in movement.py - currently necessary to avoid circular imports though.
    Gets the squared distance between two x, y positions
    :return: an integer, the squared linear distance
    """
    x_diff = (x1 - x2)
    y_diff = (y1 - y2)
    return x_diff * x_diff + y_diff * y_diff


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


def _flag_hint():
    reverse_primary = reverse_definitions[this.color]
    if reverse_primary:
        if this.secondaryColor in reverse_primary:
            return reverse_primary[this.secondaryColor]
    return None


Flag.prototype.hint = _flag_hint
