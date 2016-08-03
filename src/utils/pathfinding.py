# Currently disabled / unused, since PathFinder.search is as-it-seems broken.
import flags
from utils.screeps_constants import *

__pragma__('noalias', 'name')

# Keys _cost_cache[use_roads][ignore_all_creeps] = matrix
_cost_cache = {
    True: {
        True: {
            True: {},
            False: {},
        },
        False: {
            True: {},
            False: {},
        },
    },
    False: {
        True: {
            True: {},
            False: {},
        },
        False: {
            True: {},
            False: {},
        },
    }
}
_last_refreshed = {
    True: {
        True: {
            True: {},
            False: {},
        },
        False: {
            True: {},
            False: {},
        },
    },
    False: {
        True: {
            True: {},
            False: {},
        },
        False: {
            True: {},
            False: {},
        },
    }
}


def _get_matrix(room, game_defined_matrix, use_roads, ignore_all_creeps, avoid_all_creeps, room_name):
    time = Game.time
    global last_tick
    # don't look up Game.rooms[] if we have a cache
    if _cost_cache[use_roads][ignore_all_creeps][avoid_all_creeps][room_name] and \
                    time <= _last_refreshed[use_roads][ignore_all_creeps][avoid_all_creeps][room_name]:
        return _cost_cache[room_name]
    if game_defined_matrix:
        matrix = game_defined_matrix
    else:
        matrix = __new__(PathFinder.CostMatrix)

    for struct in room.find(FIND_STRUCTURES):
        if struct.stuctureType is STRUCTURE_ROAD:
            matrix.set(struct.pos.x, struct.pos.y, 1)
        elif struct.structureType is not STRUCTURE_CONTAINER \
                and struct.structureType is not STRUCTURE_RAMPART:
            matrix.set(struct.pos.x, struct.pos.y, 0xff)

    for flag in flags.get_flags(room, flags.PATH_FINDING_AVOID):
        matrix.set(flag.pos.x, flag.pos.y, 0xff)

    if not ignore_all_creeps:
        for creep in room.find(FIND_CREEPS):
            if not creep.my or creep.memory.stationary or avoid_all_creeps:
                matrix.set(creep.pos.x, creep.pos.y, 0xff)
            else:
                matrix.set(creep.pos.x, creep.pos.y, 1)  # just slightly avoid - not too much?

    # for x in range(0, 50):
    #     for y in range(0, 50):
    #         for terrain in room.lookForAt(LOOK_TERRAIN, x, y):
    #             if terrain.type | TERRAIN_MASK_WALL == TERRAIN_MASK_WALL:
    #                 matrix.set(x, y, 0xff)

    _cost_cache[use_roads][ignore_all_creeps][avoid_all_creeps][room_name] = matrix
    _last_refreshed[use_roads][ignore_all_creeps][avoid_all_creeps][room_name] = time

    return matrix


def _new_callback(use_roads, ignore_all_creeps, avoid_all_creeps):
    def _callback(room_name, game_defined_matrix):
        room = Game.rooms[room_name]
        if room:
            return _get_matrix(room, game_defined_matrix, use_roads, ignore_all_creeps, avoid_all_creeps, room_name)
        else:
            print("[pathfinding] No matrix found for {}".format(room_name))
            return None

    return _callback


_USE_PURE_PATHFINDER = False

_DEFAULT_OPTIONS = {
    "use_roads": False,
    "ignore_all_creeps": False,
    "avoid_all_creeps": False,
    "range": 1
}


def find_path(room, from_pos, to_pos, options):
    if not options:
        options = _DEFAULT_OPTIONS
    else:
        for key, value in _DEFAULT_OPTIONS.items():
            if key not in options:
                options[key] = value

    if _USE_PURE_PATHFINDER:
        range = options["range"]
        opts = {
            "maxRooms": 1,
            "range": range,
            "roomCallback": _new_callback(options["use_roads"], options["ignore_all_creeps"],
                                          options["avoid_all_creeps"]),
            "maxOps": 5000,
        }
        if options["use_roads"]:
            opts["plainCost"] = 2
            opts["spawmpCost"] = 10
        path = PathFinder.search(from_pos, to_pos, opts)
        if not path:
            return None
        else:
            return path.path  # it's an object
    else:
        opts = {
            "ignoreCreeps": not options["avoid_all_creeps"],  # in any case, we'll do our own creep matrix additions
            "ignoreRoads": not options["use_roads"],
            "maxRooms": 1,
            "costCallback": _new_callback(options["use_roads"], options["ignore_all_creeps"],
                                          options["avoid_all_creeps"]),
        }
        path = room.findPath(from_pos, to_pos, opts)
        if not path:
            return None
        else:
            return path
