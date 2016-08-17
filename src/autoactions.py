import context
from control import pathdef
from tools import profiling
from utilities import volatile_cache, movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def pathfinder_enemy_array_for_room(room_name):
    cache = volatile_cache.mem("enemy_lists")
    if room_name in cache:
        return cache[room_name]

    enemy_positions = []

    for hostile in Memory.hostiles:
        dx, dy = movement.inter_room_difference(room_name, Memory.hostile_last_rooms[hostile])
        if abs(dx) <= 1 and abs(dy) <= 1:
            pos = Memory.hostile_last_positions[hostile]
            pos = __new__(RoomPosition(pos.x, pos.y, pos.roomName))
            enemy_positions.append({"pos": pos, "range": 50})

    cache[room_name] = enemy_positions
    return enemy_positions


def room_hostile(room_name):
    cache = volatile_cache.mem("rua")
    if room_name in cache:
        return cache[room_name]

    room_under_attack = False

    for hostile in Memory.hostiles:
        if Memory.hostile_last_rooms[hostile] == room_name:
            room_under_attack = True
            break

    cache[room_name] = room_under_attack
    return room_under_attack


def get_cost_matrix(room_name):
    cache = volatile_cache.mem("enemy_cost_matrix")
    if room_name in cache:
        return cache[room_name]
    # TODO: some of this is duplicated in pathdef.HoneyTrails

    room = context.hive().get_room(room_name)
    if not room:
        if room_hostile(room_name):
            return False
        else:
            return __new__(PathFinder.CostMatrix())

    cost_matrix = __new__(PathFinder.CostMatrix())

    def wall_at(x, y):
        for t in room.room.lookForAt(LOOK_TERRAIN, x, y):
            # TODO: there are no constants for this value, and TERRAIN_MASK_* constants seem to be useless...
            if t == 'wall':
                return True
        return False

    def set_in_range(pos, drange, value, increase_by_center):
        for x in range(pos.x - drange, pos.x + drange + 1):
            for y in range(pos.y - drange, pos.y + drange + 1):
                if not wall_at(x, y) and cost_matrix.get(x, y) < value:
                    cost_matrix.set(x, y, value)
        if increase_by_center > 0 and drange > 1:
            set_in_range(pos, drange - 1, value + increase_by_center, increase_by_center)

    for struct in room.find(FIND_STRUCTURES):
        if struct.structureType != STRUCTURE_ROAD and struct.structureType != STRUCTURE_CONTAINER:
            if struct.structureType != STRUCTURE_RAMPART or not struct.my:
                cost_matrix.set(struct.pos.x, struct.pos.y, 255)
    for creep in room.find(FIND_HOSTILE_CREEPS):
        set_in_range(creep.pos, 7, 2, 7)
        cost_matrix.set(creep.pos.x, creep.pos.y, 255)
    for creep in room.find(FIND_CREEPS):
        set_in_range(creep.pos, 1, 5, 0)
        cost_matrix.set(creep.pos.x, creep.pos.y, 255)

    cache[room_name] = cost_matrix
    return cost_matrix


def get_path_away(origin):
    # TODO: any path caching here? I don't think it'd be beneficiary, since enemy creeps generally move each tick...
    targets = pathfinder_enemy_array_for_room(origin.roomName)
    # TODO: This current search does avoid enemies, but can very easily lead to creeps getting cornered. I'm thinking
    # a path to the nearest exit might be better.
    # This might have been fixed by setting range to 50 instead of 10, but I'm also unsure if that actually works...
    result = PathFinder.search(origin, targets, {
        "roomCallback": get_cost_matrix,
        "flee": True,
        "maxRooms": 8,
    })

    path = []

    last_x, last_y = origin.x, origin.y
    for origin in result.path:
        dx = origin.x - last_x
        dy = origin.y - last_y
        last_x = origin.x
        last_y = origin.y
        path.append({
            'x': origin.x,
            'y': origin.y,
            'dx': dx,
            'dy': dy,
            'direction': pathdef.get_direction(dx, dy)
        })

    return path
    # return result.path


get_path_away = profiling.profiled(get_path_away, "autoactions.get_path_away")


def run_away_check(creep):
    """
    :type creep: role_base.RoleBase
    """
    if not room_hostile(creep.creep.pos.roomName):
        return
    parts = _.countBy(creep.creep.body, 'type')
    if parts[ATTACK] or parts[RANGED_ATTACK]:
        return  # we're a defender, defenders don't run away!

    path = get_path_away(creep.creep.pos)
    if len(path):
        result = creep.creep.moveByPath(path)
        if result != OK:
            creep.log("Unknown result from moving when running away: {}".format(result))
    return True


run_away_check = profiling.profiled(run_away_check, "autoactions.run_away_check")


def instinct_check(creep):
    """
    :type creep: role_base.RoleBase
    :rtype: bool
    :param creep: Creep to perform an instinct check on.
    :return: True of instinct has taken effect and creep should not run it's original function.
    """
    if run_away_check(creep):
        return True
    return False


instinct_check = profiling.profiled(instinct_check, "autoactions.instinct_check")