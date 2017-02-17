var ATTACK_DISMANTLE = __init__ (__world__.constants).ATTACK_DISMANTLE;
var ATTACK_POWER_BANK = __init__ (__world__.constants).ATTACK_POWER_BANK;
var CLAIM_LATER = __init__ (__world__.constants).CLAIM_LATER;
var DEPOT = __init__ (__world__.constants).DEPOT;
var ENERGY_GRAB = __init__ (__world__.constants).ENERGY_GRAB;
var LOCAL_MINE = __init__ (__world__.constants).LOCAL_MINE;
var RAID_OVER = __init__ (__world__.constants).RAID_OVER;
var RAMPART_DEFENSE = __init__ (__world__.constants).RAMPART_DEFENSE;
var RANGED_DEFENSE = __init__ (__world__.constants).RANGED_DEFENSE;
var REAP_POWER_BANK = __init__ (__world__.constants).REAP_POWER_BANK;
var REMOTE_MINE = __init__ (__world__.constants).REMOTE_MINE;
var REROUTE = __init__ (__world__.constants).REROUTE;
var REROUTE_DESTINATION = __init__ (__world__.constants).REROUTE_DESTINATION;
var RESERVE_NOW = __init__ (__world__.constants).RESERVE_NOW;
var SCOUT = __init__ (__world__.constants).SCOUT;
var SK_LAIR_SOURCE_NOTED = __init__ (__world__.constants).SK_LAIR_SOURCE_NOTED;
var SLIGHTLY_AVOID = __init__ (__world__.constants).SLIGHTLY_AVOID;
var SPAWN_FILL_WAIT = __init__ (__world__.constants).SPAWN_FILL_WAIT;
var TD_D_GOAD = __init__ (__world__.constants).TD_D_GOAD;
var TD_H_D_STOP = __init__ (__world__.constants).TD_H_D_STOP;
var TD_H_H_STOP = __init__ (__world__.constants).TD_H_H_STOP;
var UPGRADER_SPOT = __init__ (__world__.constants).UPGRADER_SPOT;
var new_map = __init__ (__world__.jstools.js_set_map).new_map;
var naming = __init__ (__world__.utilities.naming);
var MAIN_BUILD = 100;
var MAIN_DESTRUCT = 101;
var SUB_RAMPART = 110;
var SUB_SPAWN = 111;
var SUB_EXTENSION = 112;
var SUB_TOWER = 113;
var SUB_STORAGE = 114;
var SUB_LINK = 115;
var SUB_EXTRACTOR = 116;
var SUB_TERMINAL = 117;
var SUB_WALL = 120;
var SUB_ROAD = 121;
var SUB_CONTAINER = 122;
var flag_definitions = {[LOCAL_MINE]: [COLOR_BLUE, COLOR_PURPLE], [DEPOT]: [COLOR_BLUE, COLOR_BLUE], [SPAWN_FILL_WAIT]: [COLOR_BLUE, COLOR_CYAN], [UPGRADER_SPOT]: [COLOR_BLUE, COLOR_GREEN], [SLIGHTLY_AVOID]: [COLOR_BLUE, COLOR_GREY], [SK_LAIR_SOURCE_NOTED]: [COLOR_BLUE, COLOR_WHITE], [TD_H_H_STOP]: [COLOR_CYAN, COLOR_RED], [TD_H_D_STOP]: [COLOR_CYAN, COLOR_PURPLE], [TD_D_GOAD]: [COLOR_CYAN, COLOR_BLUE], [ATTACK_DISMANTLE]: [COLOR_CYAN, COLOR_GREEN], [RAID_OVER]: [COLOR_CYAN, COLOR_YELLOW], [ENERGY_GRAB]: [COLOR_CYAN, COLOR_ORANGE], [SCOUT]: [COLOR_CYAN, COLOR_BROWN], [RANGED_DEFENSE]: [COLOR_CYAN, COLOR_CYAN], [ATTACK_POWER_BANK]: [COLOR_CYAN, COLOR_GREY], [REAP_POWER_BANK]: [COLOR_CYAN, COLOR_WHITE], [REMOTE_MINE]: [COLOR_GREEN, COLOR_CYAN], [CLAIM_LATER]: [COLOR_GREEN, COLOR_PURPLE], [RESERVE_NOW]: [COLOR_GREEN, COLOR_GREY], [RAMPART_DEFENSE]: [COLOR_GREEN, COLOR_GREEN], [REROUTE]: [COLOR_WHITE, COLOR_GREEN], [REROUTE_DESTINATION]: [COLOR_WHITE, COLOR_YELLOW]};
var reverse_definitions = {};
var __iterable0__ = Object.keys (flag_definitions);
for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
    var name = __iterable0__ [__index0__];
    var __left0__ = flag_definitions [name];
    var primary = __left0__ [0];
    var secondary = __left0__ [1];
    if ((primary in reverse_definitions)) {
        reverse_definitions [primary] [secondary] = name;
    }
    else {
        reverse_definitions [primary] = {[secondary]: name};
    }
}
var main_to_flag_primary = {[MAIN_DESTRUCT]: COLOR_RED, [MAIN_BUILD]: COLOR_PURPLE};
var sub_to_flag_secondary = {[SUB_WALL]: COLOR_RED, [SUB_RAMPART]: COLOR_PURPLE, [SUB_EXTENSION]: COLOR_BLUE, [SUB_SPAWN]: COLOR_CYAN, [SUB_TOWER]: COLOR_GREEN, [SUB_STORAGE]: COLOR_YELLOW, [SUB_LINK]: COLOR_ORANGE, [SUB_EXTRACTOR]: COLOR_BROWN, [SUB_CONTAINER]: COLOR_BROWN, [SUB_ROAD]: COLOR_WHITE, [SUB_TERMINAL]: COLOR_GREY};
var flag_secondary_to_sub = {[COLOR_RED]: SUB_WALL, [COLOR_PURPLE]: SUB_RAMPART, [COLOR_BLUE]: SUB_EXTENSION, [COLOR_CYAN]: SUB_SPAWN, [COLOR_GREEN]: SUB_TOWER, [COLOR_YELLOW]: SUB_STORAGE, [COLOR_ORANGE]: SUB_LINK, [COLOR_BROWN]: SUB_EXTRACTOR, [COLOR_GREY]: SUB_TERMINAL, [COLOR_WHITE]: SUB_ROAD};
var flag_sub_to_structure_type = {[SUB_SPAWN]: STRUCTURE_SPAWN, [SUB_EXTENSION]: STRUCTURE_EXTENSION, [SUB_RAMPART]: STRUCTURE_RAMPART, [SUB_WALL]: STRUCTURE_WALL, [SUB_STORAGE]: STRUCTURE_STORAGE, [SUB_TOWER]: STRUCTURE_TOWER, [SUB_LINK]: STRUCTURE_LINK, [SUB_EXTRACTOR]: STRUCTURE_EXTRACTOR, [SUB_CONTAINER]: STRUCTURE_CONTAINER, [SUB_ROAD]: STRUCTURE_ROAD, [SUB_TERMINAL]: STRUCTURE_TERMINAL};
var structure_type_to_flag_sub = {[STRUCTURE_SPAWN]: SUB_SPAWN, [STRUCTURE_EXTENSION]: SUB_EXTENSION, [STRUCTURE_RAMPART]: SUB_RAMPART, [STRUCTURE_WALL]: SUB_WALL, [STRUCTURE_STORAGE]: SUB_STORAGE, [STRUCTURE_TOWER]: SUB_TOWER, [STRUCTURE_LINK]: SUB_LINK, [STRUCTURE_EXTRACTOR]: SUB_EXTRACTOR, [STRUCTURE_CONTAINER]: SUB_CONTAINER, [STRUCTURE_ROAD]: SUB_ROAD, [STRUCTURE_TERMINAL]: SUB_TERMINAL};
var _REFRESH_EVERY = 50;
var _last_flag_len = 0;
var _last_checked_flag_len = 0;
var refresh_flag_caches = function () {
    var refresh_time = Game.time + _REFRESH_EVERY;
    _room_flag_cache = new_map ();
    _room_flag_refresh_time = refresh_time;
    _global_flag_cache = new_map ();
    _global_flag_refresh_time = refresh_time;
    _closest_flag_cache = new_map ();
    _closest_flag_refresh_time = refresh_time;
    _last_flag_len = _.size (Game.flags);
};
var __check_new_flags = function () {
    if (_last_checked_flag_len < Game.time) {
        var length = _.size (Game.flags);
        if (_last_flag_len != length) {
            refresh_flag_caches ();
        }
    }
};
var move_flags = function () {
    if (Memory.flags_to_move) {
        var __iterable0__ = Memory.flags_to_move;
        for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
            var __left0__ = __iterable0__ [__index0__];
            var name = __left0__ [0];
            var pos = __left0__ [1];
            var pos = new RoomPosition (pos.x, pos.y, pos.roomName);
            var result = Game.flags [name].setPosition (pos);
            print ('[flags] Moving flag {} to {}. Result: {}'.format (name, pos, result));
        }
        delete Memory.flags_to_move;
    }
};
var is_def = function (flag, flag_type) {
    var flag_def = flag_definitions [flag_type];
    return flag.color == flag_def [0] && flag.secondaryColor == flag_def [1];
};
var _room_flag_cache = new_map ();
var _room_flag_refresh_time = Game.time + _REFRESH_EVERY;
var __get_room_and_name = function (room) {
    if (room.room) {
        var room = room.room;
    }
    if (room.name) {
        return [room, room.name];
    }
    else {
        return [Game.rooms [room], room];
    }
};
var __get_cache = function (room_name, flag_type) {
    __check_new_flags ();
    if (Game.time > _room_flag_refresh_time) {
        _room_flag_refresh_time = Game.time + _REFRESH_EVERY;
        _room_flag_cache = new_map ();
    }
    if (_room_flag_cache.has (room_name) && _room_flag_cache.get (room_name).has (flag_type)) {
        return _room_flag_cache.get (room_name).get (flag_type);
    }
    else {
        return null;
    }
};
var find_flags = function (room, flag_type) {
    var __left0__ = __get_room_and_name (room);
    var room = __left0__ [0];
    var room_name = __left0__ [1];
    var cached = __get_cache (room_name, flag_type);
    if (cached) {
        return cached;
    }
    var flag_def = flag_definitions [flag_type];
    if (room) {
        var flag_list = room.find (FIND_FLAGS, {'filter': {'color': flag_def [0], 'secondaryColor': flag_def [1]}});
    }
    else {
        var flag_list = [];
        var __iterable0__ = Object.keys (Game.flags);
        for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
            var flag_name = __iterable0__ [__index0__];
            var flag = Game.flags [flag_name];
            if (flag.pos.roomName == room_name && flag.color == flag_def [0] && flag.secondaryColor == flag_def [1]) {
                flag_list.append (flag);
            }
        }
    }
    if (_room_flag_cache.has (room_name)) {
        _room_flag_cache.get (room_name).set (flag_type, flag_list);
    }
    else {
        _room_flag_cache.set (room_name, new_map ([[flag_type, flag_list]]));
    }
    return flag_list;
};
var find_by_main_with_sub = function (room, main_type) {
    var __left0__ = __get_room_and_name (room);
    var room = __left0__ [0];
    var room_name = __left0__ [1];
    var cached = __get_cache (room_name, main_type);
    if (cached) {
        return cached;
    }
    var flag_primary = main_to_flag_primary [main_type];
    if (room) {
        var flag_list = [];
        var __iterable0__ = room.find (FIND_FLAGS, {'filter': {'color': flag_primary}});
        for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
            var flag = __iterable0__ [__index0__];
            flag_list.append ([flag, flag_secondary_to_sub [flag.secondaryColor]]);
        }
    }
    else {
        var flag_list = [];
        var __iterable0__ = Object.keys (Game.flags);
        for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
            var name = __iterable0__ [__index0__];
            var flag = Game.flags [name];
            if (flag.pos.roomName == room_name && flag.color == flag_primary) {
                var secondary = flag_secondary_to_sub [flag.secondaryColor];
                if (secondary) {
                    flag_list.append ([flag, secondary]);
                }
            }
        }
    }
    if (_room_flag_cache.has (room_name)) {
        _room_flag_cache.get (room_name).set (main_type, flag_list);
    }
    else {
        _room_flag_cache.set (room_name, new_map ([[main_type, flag_list]]));
    }
    return flag_list;
};
var find_ms_flags = function (room, main_type, sub_type) {
    var type_name = '{}_{}'.format (main_type, sub_type);
    var __left0__ = __get_room_and_name (room);
    var room = __left0__ [0];
    var room_name = __left0__ [1];
    var cached = __get_cache (room_name, '{}_{}'.format (main_type, sub_type));
    if (cached) {
        return cached;
    }
    var primary = main_to_flag_primary [main_type];
    var secondary = sub_to_flag_secondary [sub_type];
    if (room) {
        var flag_list = room.find (FIND_FLAGS, {'filter': {'color': primary, 'secondaryColor': secondary}});
    }
    else {
        var flag_list = [];
        var __iterable0__ = Object.keys (Game.flags);
        for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
            var flag_name = __iterable0__ [__index0__];
            var flag = Game.flags [flag_name];
            if (flag.pos.roomName == room_name && flag.color == primary && flag.secondaryColor == secondary) {
                flag_list.append (flag);
            }
        }
    }
    if (_room_flag_cache.has (room_name)) {
        _room_flag_cache.get (room_name).set (type_name, flag_list);
    }
    else {
        _room_flag_cache.set (room_name, new_map ([[type_name, flag_list]]));
    }
    return flag_list;
};
var _global_flag_cache = new_map ();
var _global_flag_refresh_time = Game.time + _REFRESH_EVERY;
var find_flags_global = function (flag_type, reload) {
    if (typeof reload == 'undefined' || (reload != null && reload .hasOwnProperty ("__kwargtrans__"))) {;
        var reload = false;
    };
    __check_new_flags ();
    if (Game.time > _global_flag_refresh_time) {
        _global_flag_refresh_time = Game.time + _REFRESH_EVERY;
        _global_flag_cache = new_map ();
    }
    if (_global_flag_cache.has (flag_type) && !(reload)) {
        return _global_flag_cache.get (flag_type);
    }
    var flag_def = flag_definitions [flag_type];
    var flag_list = [];
    var __iterable0__ = Object.keys (Game.flags);
    for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
        var name = __iterable0__ [__index0__];
        var flag = Game.flags [name];
        if (flag.color == flag_def [0] && flag.secondaryColor == flag_def [1]) {
            flag_list.append (flag);
        }
    }
    _global_flag_cache.set (flag_type, flag_list);
    return flag_list;
};
var find_flags_ms_global = function (main_type, sub_type, reload) {
    if (typeof reload == 'undefined' || (reload != null && reload .hasOwnProperty ("__kwargtrans__"))) {;
        var reload = false;
    };
    var type_name = '{}_{}'.format (main_type, sub_type);
    __check_new_flags ();
    if (Game.time > _global_flag_refresh_time) {
        _global_flag_refresh_time = Game.time + _REFRESH_EVERY;
        _global_flag_cache = new_map ();
    }
    if (_global_flag_cache.has (type_name) && !(reload)) {
        return _global_flag_cache.get (type_name);
    }
    var primary = main_to_flag_primary [main_type];
    var secondary = sub_to_flag_secondary [sub_type];
    var flag_list = [];
    var __iterable0__ = Object.keys (Game.flags);
    for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
        var name = __iterable0__ [__index0__];
        var flag = Game.flags [name];
        if (flag.color == primary && flag.secondaryColor == secondary) {
            flag_list.append (flag);
        }
    }
    _global_flag_cache.set (type_name, flag_list);
    return flag_list;
};
var find_by_main_with_sub_global = function (main_type, reload) {
    if (typeof reload == 'undefined' || (reload != null && reload .hasOwnProperty ("__kwargtrans__"))) {;
        var reload = false;
    };
    __check_new_flags ();
    if (Game.time > _global_flag_refresh_time) {
        _global_flag_refresh_time = Game.time + _REFRESH_EVERY;
        _global_flag_cache = new_map ();
    }
    if (_global_flag_cache.has (main_type) && !(reload)) {
        return _global_flag_cache.get (main_type);
    }
    var primary = main_to_flag_primary [main_type];
    var flag_list = [];
    var __iterable0__ = Object.keys (Game.flags);
    for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
        var name = __iterable0__ [__index0__];
        var flag = Game.flags [name];
        if (flag.color == primary) {
            var secondary = flag_secondary_to_sub [flag.secondaryColor];
            if (secondary) {
                flag_list.append ([flag, secondary]);
            }
        }
    }
    _global_flag_cache.set (main_type, flag_list);
    return flag_list;
};
var _closest_flag_cache = new_map ();
var _closest_flag_refresh_time = Game.time + _REFRESH_EVERY;
var squared_distance = function (x1, y1, x2, y2) {
    var x_diff = x1 - x2;
    var y_diff = y1 - y2;
    return x_diff * x_diff + y_diff * y_diff;
};
var find_closest_in_room = function (pos, flag_type) {
    __check_new_flags ();
    if (Game.time > _closest_flag_refresh_time) {
        _closest_flag_refresh_time = Game.time + 50;
        _closest_flag_cache = new_map ();
    }
    var key = '{}_{}_{}_{}'.format (pos.roomName, pos.x, pos.y, flag_type);
    if (_closest_flag_cache.has (key)) {
        return _closest_flag_cache.get (key);
    }
    var closest_distance = Infinity;
    var closest_flag = null;
    var __iterable0__ = find_flags (pos.roomName, flag_type);
    for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
        var flag = __iterable0__ [__index0__];
        var distance = squared_distance (pos.x, pos.y, flag.pos.x, flag.pos.y);
        if (distance < closest_distance) {
            var closest_distance = distance;
            var closest_flag = flag;
        }
    }
    _closest_flag_cache.set (key, closest_flag);
    return closest_flag;
};
var __create_flag = function (position, flag_type, primary, secondary) {
    if (position.pos) {
        var position = position.pos;
    }
    var name = '{}_{}'.format (flag_type, naming.random_digits ());
    var room = Game.rooms [position.roomName];
    if (room) {
        var flag_name = room.createFlag (position, name, primary, secondary);
        print ('[flags] Created flag at {}: {}'.format (position, flag_name));
        return flag_name;
    }
    else {
        var known_position = Game.spawns [Object.keys (Game.spawns) [0]].pos;
        var flag_name = known_position.createFlag (name, primary, secondary);
        if (Memory.flags_to_move) {
            Memory.flags_to_move.push ([flag_name, position]);
        }
        else {
            Memory.flags_to_move = [[flag_name, position]];
        }
        return flag_name;
    }
};
var create_flag = function (position, flag_type) {
    var flag_def = flag_definitions [flag_type];
    return __create_flag (position, flag_type, flag_def [0], flag_def [1]);
};
var create_ms_flag = function (position, main, sub) {
    return __create_flag (position, '{}_{}'.format (main, sub), main_to_flag_primary [main], sub_to_flag_secondary [sub]);
};
var rename_flags = function () {
    refresh_flag_caches ();
    var __iterable0__ = Object.keys (flag_definitions);
    for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
        var name = __iterable0__ [__index0__];
        var __iterable1__ = find_flags_global (name);
        for (var __index1__ = 0; __index1__ < __iterable1__.length; __index1__++) {
            var flag = __iterable1__ [__index1__];
            if (Game.cpu.getUsed () > 400) {
                refresh_flag_caches ();
                return 'Used too much CPU!';
            }
            if (Game.rooms [flag.pos.roomName] && (flag.name.startswith ('Flag') || !(flag.name.includes ('_'))) && !(flag.name in Memory.flags)) {
                var new_name = create_flag (flag.pos, name);
                if (Memory.flags [flag.name]) {
                    if (len (Memory.flags [flag.name])) {
                        Memory.flags [new_name] = Memory.flags [flag.name];
                    }
                    delete Memory.flags [flag.name];
                }
                flag.remove ();
            }
        }
    }
    var __iterable0__ = Object.keys (main_to_flag_primary);
    for (var __index0__ = 0; __index0__ < __iterable0__.length; __index0__++) {
        var main = __iterable0__ [__index0__];
        var __iterable1__ = find_by_main_with_sub_global (main);
        for (var __index1__ = 0; __index1__ < __iterable1__.length; __index1__++) {
            var __left0__ = __iterable1__ [__index1__];
            var flag = __left0__ [0];
            var sub = __left0__ [1];
            if (Game.cpu.getUsed () > 400) {
                refresh_flag_caches ();
                return 'Used too much CPU!';
            }
            if (Game.rooms [flag.pos.roomName] && (flag.name.startswith ('Flag') || !(flag.name.includes ('_'))) && !(flag.name in Memory.flags)) {
                var new_name = create_ms_flag (flag.pos, main, sub);
                if (Memory.flags [flag.name]) {
                    if (len (Memory.flags [flag.name])) {
                        Memory.flags [new_name] = Memory.flags [flag.name];
                    }
                    delete Memory.flags [flag.name];
                }
                flag.remove ();
            }
        }
    }
    refresh_flag_caches ();
};
var look_for = function (room, position, main, sub) {
    if (typeof sub == 'undefined' || (sub != null && sub .hasOwnProperty ("__kwargtrans__"))) {;
        var sub = null;
    };
    if (!(room.look_at)) {
        var __except0__ = ValueError ('Invalid room argument');
        __except0__.__cause__ = null;
        throw __except0__;
    }
    if (position.pos) {
        var position = position.pos;
    }
    if (sub) {
        return _.find (room.look_at (LOOK_FLAGS, position), (function __lambda__ (f) {
            return f.color == main_to_flag_primary [main] && f.secondaryColor == sub_to_flag_secondary [sub];
        }));
    }
    else {
        var flag_def = flag_definitions [main];
        if (!(flag_def)) {
            return [];
        }
        return _.find (room.look_at (LOOK_FLAGS, position), (function __lambda__ (f) {
            return f.color == flag_def [0] && f.secondaryColor == flag_def [1];
        }));
    }
};
var _flag_sponsor_regex = new RegExp ('^(W|E)([0-9]{1,3})(N|S)([0-9]{1,3})');
var flag_sponsor = function (flag, backup_search_by) {
    if (typeof backup_search_by == 'undefined' || (backup_search_by != null && backup_search_by .hasOwnProperty ("__kwargtrans__"))) {;
        var backup_search_by = null;
    };
    if ((flag.name in Memory.flags)) {
        var sponsor = flag.memory.sponsor;
        if (sponsor) {
            return sponsor;
        }
    }
    var sponsor_match = _flag_sponsor_regex.exec (flag.name);
    if (sponsor_match) {
        return sponsor_match [0];
    }
    else if (backup_search_by) {
        var room = backup_search_by.get_closest_owned_room (flag.pos.roomName);
        if (room) {
            return room.name;
        }
        else {
            return null;
        }
    }
    else {
        return null;
    }
};
var _flag_hint = function () {
    var reverse_primary = reverse_definitions [this.color];
    if (reverse_primary) {
        if ((this.secondaryColor in reverse_primary)) {
            return reverse_primary [this.secondaryColor];
        }
    }
    return null;
};
Flag.prototype.hint = _flag_hint;