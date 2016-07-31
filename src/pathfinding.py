# Currently disabled / unused, since PathFinder.search is as-it-seems broken.

from screeps_constants import *

# Keys _cost_cache[use_roads][ignore_all_creeps] = matrix
_cost_cache = {
    True: {
        True: {},
        False: {}
    },
    False: {
        True: {},
        False: {},
    }
}
# sometimes the script is kept between multiple ticks. Use this to keep track of what
# game tick to refresh each room cache.
_refresh_by = {
    True: {
        True: {},
        False: {}
    },
    False: {
        True: {},
        False: {},
    }
}

# how often to refresh caches
_refresh_every_ticks = 10


def _get_matrix(room, use_roads, ignore_all_creeps, room_name):
    time = Game.time
    # don't look up Game.rooms[] if we have a cache
    if _cost_cache[use_roads][ignore_all_creeps][room_name] and \
                    time < _refresh_by[use_roads][ignore_all_creeps][room_name]:
        return _cost_cache[room_name]
    matrix = __new__(PathFinder.CostMatrix)

    for struct in room.find(FIND_STRUCTURES):
        if struct.stuctureType is STRUCTURE_ROAD:
            if use_roads:
                matrix.set(struct.pos.x, struct.pos.y, 1)
        elif struct.structureType is not STRUCTURE_CONTAINER \
                and struct.structureType is not STRUCTURE_RAMPART:
            matrix.set(struct.pos.x, struct.pos.y, 0xff)

    if not ignore_all_creeps:
        for creep in room.find(FIND_CREEPS):
            if not creep.my or creep.memory.stationary:
                matrix.set(creep.pos.x, creep.pos.y, 0xff)
            else:
                matrix.set(creep.pos.x, creep.pos.y, 5)  # just slightly avoid - not too much?

    for x in range(0, 50):
        for y in range(0, 50):
            for terrain in room.lookForAt(LOOK_TERRAIN, x, y):
                if terrain.type | TERRAIN_MASK_WALL == TERRAIN_MASK_WALL:
                    matrix.set(x, y, 0xff)

    _cost_cache[use_roads][ignore_all_creeps][room_name] = matrix
    _refresh_by[use_roads][ignore_all_creeps][room_name] = Game.time + _refresh_every_ticks

    return matrix


def _new_callback(use_roads, ignore_all_creeps):
    def _callback(room_name):
        room = Game.rooms[room_name]
        if room:
            return _get_matrix(room, use_roads, ignore_all_creeps, room_name)
        else:
            print("[pathfinding] No matrix found for {}".format(room_name))
            return None

    return _callback


def find_path(from_pos, to_pos, options):
    use_roads = not not options and not not options["use_roads"]
    ignore_all_creeps = not not options and not not options["ignore_all_creeps"]
    range = options["range"] if options and options["range"] else 1
    opts = {
        "maxRooms": 16,
        "range": range,
        "roomCallback": _new_callback(use_roads, ignore_all_creeps),
        "maxOps": 5000,
    }
    if use_roads:
        opts["plainCost"] = 2
        opts["spawmCost"] = 10
    path = PathFinder.search(from_pos, to_pos, opts)
    print("Finding path from {} to {}: {}".format(from_pos, to_pos, JSON.stringify(path, None, 4)))
    if not path:
        return None
    else:
        return path.path  # it's an object
