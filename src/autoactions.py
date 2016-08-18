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

    for hostile, room_name, pos, owner in Memory.hostiles:
        dx, dy = movement.inter_room_difference(room_name, room_name)
        if abs(dx) <= 1 and abs(dy) <= 1:
            if owner == "Source Keeper":
                enemy_range = 5
            elif owner == "Invader":
                enemy_range = 20
            else:
                enemy_range = 60
            pos = __new__(RoomPosition(pos.x, pos.y, pos.roomName))
            enemy_positions.append({"pos": pos, "range": enemy_range})

    cache[room_name] = enemy_positions
    return enemy_positions


def room_hostile(room_name):
    cache = volatile_cache.mem("rua")
    if room_name in cache:
        return cache[room_name]

    room_under_attack = False

    for hostile, hostile_room, pos, owner in Memory.hostiles:
        if hostile_room == room_name and owner != "Source Keeper":
            room_under_attack = True
            break

    cache[room_name] = room_under_attack
    return room_under_attack


def simple_cost_matrix(room_name, new_to_use_as_base=False):
    cache = volatile_cache.mem("enemy_cost_matrix")
    if room_name in cache and not new_to_use_as_base:
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

    if not new_to_use_as_base:
        cache[room_name] = cost_matrix
    return cost_matrix


def get_path_away(origin, targets):
    # TODO: any path caching here? I don't think it'd be beneficiary, since enemy creeps generally move each tick...
    # TODO: This current search does avoid enemies, but can very easily lead to creeps getting cornered. I'm thinking
    # a path to the nearest exit might be better.
    # This might have been fixed by setting range to 50 instead of 10, but I'm also unsure if that actually works...
    result = PathFinder.search(origin, targets, {
        "roomCallback": simple_cost_matrix,
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


def get_cached_away_path(creep, targets):
    """
    :type creep: role_base.RoleBase
    """

    if '_away_path' in creep.memory and creep.memory._away_path.reset > Game.time:
        return Room.deserializePath(creep.memory._away_path.path)
    else:
        path = get_path_away(creep.creep.pos, targets)
        creep.memory._away_path = {"reset": Game.time + 3, "path": Room.serializePath(path)}
        return path


def instinct_do_heal(creep):
    """
    :type creep: role_base.RoleBase
    """
    damaged = None
    most_damage = 0
    for ally in creep.room.find_in_range(FIND_MY_CREEPS, 1, creep.creep.pos):
        damage = ally.hitsMax - ally.hits
        if damage > most_damage:
            most_damage = damage
            damaged = ally
    if damaged:
        result = creep.creep.heal(damaged)
        if result != OK:
            creep.log("Unknown heal result! {}".format(result))


def instinct_do_attack(creep):
    """
    :type creep: role_base.RoleBase
    """
    damaged = None
    most_damage = 0
    for enemy in creep.room.find_in_range(FIND_MY_CREEPS, 1, creep.creep.pos):
        damage = enemy.hitsMax - enemy.hits
        if damage < most_damage:
            most_damage = damage
            damaged = enemy
        creep.creep.attack(damaged)


def run_away_check(creep):
    """
    :type creep: role_base.RoleBase
    """
    hostile_path_targets = pathfinder_enemy_array_for_room(creep.creep.pos.roomName)
    if not len(hostile_path_targets):
        del creep.memory._away_path
        return False
    if creep.creep.getActiveBodyparts(ATTACK) or creep.creep.getActiveBodyparts(RANGED_ATTACK):
        return False  # we're a defender, defenders don't run away!

    if not creep.creep.getActiveBodyparts(MOVE) or creep.creep.fatigue >= 0:  # if we can't move, we won't move.
        instinct_do_heal(creep)
        instinct_do_attack(creep)
        return True

    for target, target_range in hostile_path_targets:
        if not movement.squared_distance(target, creep.creep.pos) > target_range * target_range:
            break
    else:
        # No targets in range, no need to do anything
        return False

    path = get_cached_away_path(creep, hostile_path_targets)

    if len(path):
        if creep.creep.getActiveBodyparts(HEAL):
            instinct_do_heal(creep)
        if creep.creep.getActiveBodyparts(ATTACK):
            instinct_do_attack(creep)
        result = creep.creep.moveByPath(path)
        if result == ERR_NO_PATH:
            del creep.memory._away_path
            path = get_cached_away_path(creep, hostile_path_targets)
            result = creep.creep.moveByPath(path)
        if result != OK:
            creep.log("Unknown result from moving when running away: {}".format(result))
        return True
    else:
        # we're a safe distance away from all enemies
        return False


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
