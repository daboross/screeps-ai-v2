import random

import context
import flags
import role_base
from constants import INVADER_USERNAME, role_simple_dismantle, role_miner
from control import defense
from control import pathdef
from tools import profiling
from utilities import volatile_cache, movement, hostile_utils
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def is_room_mostly_safe(room_name):
    room = context.hive().get_room(room_name)
    if not room or not room.my:
        return False
    if room.defense.broken_walls or room.being_bootstrapped():
        return False
    return True


def pathfinder_enemy_array_for_room(room_name):
    cache = volatile_cache.mem("enemy_lists")
    if cache.has(room_name):
        return cache.get(room_name)
    my = is_room_mostly_safe(room_name)
    enemy_positions = []
    for h in defense.stored_hostiles_near(room_name):
        if not is_room_mostly_safe(room_name):
            if h.user == INVADER_USERNAME:
                if my:
                    enemy_range = 2
                else:
                    enemy_range = 5
            elif h.ranged or h.attack:
                enemy_range = 10
            else:
                continue
        elif h.user == INVADER_USERNAME:
            enemy_range = 5
        elif h.ranged:
            enemy_range = 7
        elif h.attack:
            enemy_range = 5
        else:
            continue

        pos = __new__(RoomPosition(h.pos & 0x3F, h.pos >> 6 & 0x3F, h.room))
        # NOTE: here we multiply by two, so that when we pass this array to the PathFinder we'll get a better path.
        enemy_positions.append({"pos": pos, "range": enemy_range * 4})

    cache.set(room_name, enemy_positions)
    return enemy_positions


def room_hostile(room_name):
    cache = volatile_cache.mem("rua")
    if cache.has(room_name):
        return cache.get(room_name)

    # This will only get "active" hostiles, which doesn't count source keepers, or non-ATTACK/RANGED_ATTACK creeps in
    # owned rooms.
    room_under_attack = len(defense.stored_hostiles_in(room_name))

    cache.set(room_name, room_under_attack)
    return room_under_attack


def enemy_purposes_cost_matrix(room_name):
    cache = volatile_cache.mem("super_simple_cost_matrix")
    if cache.has(room_name):
        return cache.get(room_name)

    room = context.hive().get_room(room_name)
    if not room:
        return __new__(PathFinder.CostMatrix())

    cost_matrix = __new__(PathFinder.CostMatrix())

    def wall_at(x, y):
        return Game.map.getTerrainAt(x, y, room_name) == 'wall'

    for struct in room.find(FIND_STRUCTURES):
        if struct.structureType != STRUCTURE_ROAD and struct.structureType != STRUCTURE_CONTAINER \
                and (struct.structureType != STRUCTURE_RAMPART or struct.my):
            cost_matrix.set(struct.pos.x, struct.pos.y, 255)

    cache.set(room_name, cost_matrix)
    return cost_matrix


def simple_cost_matrix(room_name, new_to_use_as_base=False):
    cache = volatile_cache.mem("enemy_cost_matrix")
    if not new_to_use_as_base and cache.has(room_name):
        return cache.get(room_name)
    # TODO: some of this is duplicated in pathdef.HoneyTrails

    room = context.hive().get_room(room_name)
    if not room:
        if room_hostile(room_name) or hostile_utils.enemy_room(room_name):
            return False
        else:
            return __new__(PathFinder.CostMatrix())

    cost_matrix = __new__(PathFinder.CostMatrix())

    def wall_at(x, y):
        return Game.map.getTerrainAt(x, y, room_name) == 'wall'

    def set_in_range(pos, drange, value, increase_by_center):
        for x in range(pos.x - drange, pos.x + drange + 1):
            for y in range(pos.y - drange, pos.y + drange + 1):
                if not wall_at(x, y) and cost_matrix.get(x, y) < value:
                    cost_matrix.set(x, y, value)
        if increase_by_center > 0 and drange > 0:
            set_in_range(pos, drange - 1, value + increase_by_center, increase_by_center)

    for struct in room.find(FIND_STRUCTURES):
        if struct.structureType == STRUCTURE_ROAD:
            cost_matrix.set(struct.pos.x, struct.pos.y, 1)
        elif struct.structureType != STRUCTURE_CONTAINER and (struct.structureType != STRUCTURE_RAMPART
                                                              or not struct.my):
            cost_matrix.set(struct.pos.x, struct.pos.y, 255)
    for creep in room.find(FIND_CREEPS):
        set_in_range(creep.pos, 1, 5, 0)
        cost_matrix.set(creep.pos.x, creep.pos.y, 255)
    for creep in room.find(FIND_HOSTILE_CREEPS):
        set_in_range(creep.pos, 7, 2, 7)
        cost_matrix.set(creep.pos.x, creep.pos.y, 255)
    for flag in flags.find_flags(room_name, flags.SK_LAIR_SOURCE_NOTED):
        set_in_range(flag.pos, 4, 255, 0)

    if not new_to_use_as_base:
        cache.set(room_name, cost_matrix)
    role_base.add_exits(room_name, cost_matrix)
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
    for pos in result.path:
        dx = pos.x - last_x
        dy = pos.y - last_y
        last_x = pos.x
        last_y = pos.y
        direction = pathdef.get_direction(dx, dy)
        if direction is None:
            print("[autoactions][get_path_away] Unknown direction for pos: {},{}, last: {},{}".format(
                pos.x, pos.y, last_x, last_y))
            return None
        path.append({
            'x': pos.x,
            'y': pos.y,
            'dx': dx,
            'dy': dy,
            'direction': direction
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
        path = get_path_away(creep.pos, targets)
        creep.memory._away_path = {"reset": Game.time + 10, "path": Room.serializePath(path)}
        return path


def instinct_do_heal(creep):
    """
    :type creep: role_base.RoleBase
    """
    if not creep.creep.hasActiveBodyparts(HEAL):
        return
    damaged = None
    most_damage = 0
    for ally_obj in creep.room.look_for_in_area_around(LOOK_CREEPS, creep.pos, 1):
        ally = ally_obj.creep
        if not ally.my and not Memory.meta.friends.includes(ally.owner.username):
            continue
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
    if not creep.creep.hasActiveBodyparts(ATTACK):
        return
    best = None
    best_priority = -Infinity
    for enemy in creep.room.find_in_range(FIND_HOSTILE_CREEPS, 1, creep.creep.pos):
        priority = enemy.hitsMax - enemy.hits
        if enemy.hasActiveBodyparts(RANGED_ATTACK):
            priority += 3000
        elif enemy.hasActiveBodyparts(ATTACK):
            priority += 2000
        elif enemy.hasActiveBodyparts(WORK):
            priority += 1000
        if priority > best_priority:
            best_priority = priority
            best = enemy
    if best:
        creep.creep.attack(best)


def run_away_check(creep, hostile_path_targets):
    """
    :type creep: Creep
    """

    check_path = is_room_mostly_safe(creep.pos.roomName)

    if check_path and not creep.memory._safe or not creep.memory._safe_from \
            or movement.chebyshev_distance_room_pos(creep.memory._safe_from, creep.pos) > 2:
        creep.memory._safe = []
        creep.memory._safe_from = creep.pos

    any_unsafe = False
    for obj in hostile_path_targets:
        target = obj.pos
        target_range = obj.range
        # NOTE: target_range here is twice what we actually want, so that when passing to PathFinder we get a better
        # path. See NOTE above.
        distance = movement.chebyshev_distance_room_pos(target, creep.pos)
        if distance > target_range * 0.25 + 1:
            continue
        if check_path:
            safe = False
            for safe_pos in creep.memory._safe:
                if movement.chebyshev_distance_room_pos(safe_pos, target) < 2:
                    safe = True
                    break
            if safe:
                continue
            enemy_path = PathFinder.search(target, {"pos": creep.pos, "range": 1}, {
                "roomCallback": enemy_purposes_cost_matrix,
                "maxRooms": 5,
                "plainCost": 1,
                "swampCost": 1,  # for speed purposes
                "maxCost": 10,
            })
            if enemy_path.incomplete:
                creep.memory._safe.push(target)
                continue

        distance = movement.chebyshev_distance_room_pos(target, creep.pos)
        if distance <= target_range * 0.25:
            break
        else:
            # elif distance <= target_range * 0.25 + 1: # We check this above
            any_unsafe = True
    else:
        return any_unsafe and random.randint(0, 3) < 3  # if we're between target_range and target_range + 1, just pause

    path = get_cached_away_path(creep, hostile_path_targets)

    if len(path):
        del creep.last_checkpoint
        del creep.last_target
        del creep.memory.was_on_the_path
        result = creep.moveByPath(path)
        if result == ERR_NO_PATH or result == ERR_NOT_FOUND:
            # del creep.memory._away_path
            # path = get_cached_away_path(creep, hostile_path_targets)
            # result = creep.creep.moveByPath(path)
            # I had the above enabled previously, and I don't think it really helped any... the ERR_NOT_FOUND would just
            # happen with the newly-generated path too.
            return True
        if result != OK:
            print("[{}][{}] Unknown result from moving when running away: {}".format(creep.memory.home,
                                                                                     creep.name, result))
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
    if creep.creep.spawning:
        return False
    if run_away_check(creep):
        return True
    return False


instinct_check = profiling.profiled(instinct_check, "autoactions.instinct_check")


def running_check_room(room):
    """
    :type room: control.hivemind.RoomMind
    """
    if room.my and room.room.controller.safeMode:
        return
    my_creeps = room.find(FIND_MY_CREEPS)
    if not len(my_creeps):
        return
    if not len(room.defense.dangerous_hostiles()):
        return

    hostile_path_targets = pathfinder_enemy_array_for_room(room.room_name)

    for creep in my_creeps:
        if creep.fatigue > 0 or len(creep.body) <= 1 \
                or _.find(creep.body, lambda p: p.type == ATTACK or p.type == RANGED_ATTACK or p.type == HEAL) \
                or (creep.memory.role == role_simple_dismantle
                    and creep.memory.home in Game.rooms
                    and room.hive_mind.get_room(creep.memory.home).conducting_siege()) \
                or not creep.hasActiveBodyparts(MOVE) \
                or (creep.memory.role == role_miner and _.find(creep.pos.lookFor(LOOK_STRUCTURES),
                                                               {'structureType': STRUCTURE_RAMPART})):
            continue
        overridden = run_away_check(creep, hostile_path_targets)
        if overridden:
            creep.defense_override = True


def cleanup_running_memory():
    for creep in _.values(Game.creeps):
        if not creep.defense_override and '_away_path' in creep.memory or '_safe' in creep.memory:
            del creep.memory._away_path
            del creep.memory._safe
            del creep.memory._safe_from


def pickup_check_room(room):
    """
    :type room: control.hivemind.RoomMind
    """
    energy = room.find(FIND_DROPPED_ENERGY)
    if not len(energy):
        return
    creeps = room.find(FIND_MY_CREEPS)
    if not len(creeps):
        return
    for pile in energy:
        if 'picked_up' in pile:
            continue
        left = pile.amount
        for creep in creeps:
            if creep.carryCapacity != 0 and creep.pos.isNearTo(pile.pos) \
                    and 'wrapped' in creep and creep.wrapped.should_pickup(pile.resourceType):
                if 'picked_up' not in creep:
                    empty = creep.carryCapacity - _.sum(creep.carry)
                    result = creep.pickup(pile)
                    if result == OK:
                        creep.cancelOrder('withdraw')
                        creep.picked_up = True
                        left -= empty
                        if left <= 0:
                            break
