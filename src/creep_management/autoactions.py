from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union, cast

import random

from cache import context, volatile_cache
from constants import INVADER_USERNAME, role_miner, role_simple_dismantle, role_squad_dismantle
from creep_management import walkby_move
from jstools.screeps import *
from rooms import defense
from utilities import hostile_utils, movement

if TYPE_CHECKING:
    from rooms.room_mind import RoomMind
    from creeps.base import RoleBase

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def is_room_mostly_safe(room_name):
    # type: (str) -> bool
    room = context.hive().get_room(room_name)
    if not room or not room.my:
        return False
    # right now, broken walls returns True even when the walls that are broken are non-essential.
    # not a very useful metric.
    # if room.defense.broken_walls or room.being_bootstrapped():
    if room.being_bootstrapped():
        return False
    return True


def pathfinder_enemy_array_for_room(room_name):
    # type: (str) -> List[Dict[str, Any]]
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
    # type: (str) -> bool
    cache = volatile_cache.mem("rua")
    if cache.has(room_name):
        return cache.get(room_name)

    # This will only get "active" hostiles, which doesn't count source keepers, or non-ATTACK/RANGED_ATTACK creeps in
    # owned rooms.
    room_under_attack = not not len(defense.stored_hostiles_in(room_name))

    cache.set(room_name, room_under_attack)
    return room_under_attack


def enemy_purposes_cost_matrix(room_name):
    # type: (str) -> PathFinder.CostMatrix
    cache = volatile_cache.mem("super_simple_cost_matrix")
    if cache.has(room_name):
        return cache.get(room_name)

    room = context.hive().get_room(room_name)
    if not room:
        return __new__(PathFinder.CostMatrix())

    cost_matrix = __new__(PathFinder.CostMatrix())

    for struct in cast(List[Structure], room.find(FIND_STRUCTURES)):
        if struct.structureType != STRUCTURE_ROAD and struct.structureType != STRUCTURE_CONTAINER \
                and (struct.structureType != STRUCTURE_RAMPART or cast(StructureRampart, struct).my):
            cost_matrix.set(struct.pos.x, struct.pos.y, 255)

    cache.set(room_name, cost_matrix)
    return cost_matrix


def simple_cost_matrix(room_name):
    # type: (str) -> Union[PathFinder.CostMatrix, bool]
    cache = volatile_cache.mem("enemy_cost_matrix")
    # TODO: some of this is duplicated in honey.HoneyTrails

    room = context.hive().get_room(room_name)
    if not room:
        if room_hostile(room_name) or hostile_utils.enemy_using_room(room_name):
            return False
        else:
            return __new__(PathFinder.CostMatrix())

    # The basic cost matrix already has impassable things on it, and already has SK lairs avoided, but does not
    # have any non-hostile creeps. It also already has exits marked.
    cost_matrix = walkby_move.get_basic_cost_matrix(room_name, False)

    def wall_at(x, y):
        return Game.map.getTerrainAt(x, y, room_name) == 'wall'

    def set_in_range(pos, drange, value, increase_by_center):
        for x in range(pos.x - drange, pos.x + drange + 1):
            for y in range(pos.y - drange, pos.y + drange + 1):
                if not wall_at(x, y) and cost_matrix.get(x, y) < value:
                    cost_matrix.set(x, y, value)
        if increase_by_center > 0 and drange > 0:
            set_in_range(pos, drange - 1, value + increase_by_center, increase_by_center)

    for creep in room.find(FIND_CREEPS):
        set_in_range(creep.pos, 1, 5, 0)
        cost_matrix.set(creep.pos.x, creep.pos.y, 255)
    for creep in room.find(FIND_HOSTILE_CREEPS):
        set_in_range(creep.pos, 7, 2, 7)
        cost_matrix.set(creep.pos.x, creep.pos.y, 255)

    cache.set(room_name, cost_matrix)
    return cost_matrix


def get_path_away(origin, targets):
    # type: (RoomPosition, List[Dict[str, Any]]) -> Optional[List[RoomPosition]]
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
        direction = movement.dxdy_to_direction(dx, dy)
        if direction is None:
            print("[autoactions][get_path_away] error! dx/dy pair {},{} is unknown. pos: {},{}, last: {},{}"
                  .format(dx, dy, pos.x, pos.y, last_x, last_y))
            return None
        path.append({
            'x': pos.x,
            'y': pos.y,
            'dx': dx,
            'dy': dy,
            'direction': direction
        })

    return path


def get_cached_away_path(creep, targets):
    # type: (Creep, List[Dict[str, Any]]) -> List[Union[_PathPos, RoomPosition]]

    if '_away_path' in creep.memory and creep.memory._away_path['reset'] > Game.time:
        return Room.deserializePath(creep.memory._away_path['path'])
    else:
        path = get_path_away(creep.pos, targets)
        creep.memory._away_path = {"reset": Game.time + 10, "path": Room.serializePath(path)}
        return path


def instinct_do_heal(creep):
    # type: (RoleBase) -> None
    if not creep.creep.hasActiveBodyparts(HEAL):
        return
    damaged = None
    most_damage = 0
    for ally_obj in cast(List[Dict[str, Creep]], creep.room.look_for_in_area_around(LOOK_CREEPS, creep.pos, 1)):
        ally = ally_obj[LOOK_CREEPS]
        if not ally.my and not Memory.meta.friends.includes(ally.owner.username.lower()):
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
    # type: (RoleBase) -> None
    """
    :type creep: creeps.base.RoleBase
    """
    if not creep.creep.hasActiveBodyparts(ATTACK):
        return
    best = None
    best_priority = -Infinity
    for enemy in cast(List[Creep], creep.room.find_in_range(FIND_HOSTILE_CREEPS, 1, creep.pos)):
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
    # type: (Creep, List[Dict[str, Any]]) -> bool

    check_path = is_room_mostly_safe(creep.pos.roomName)

    if check_path and not creep.memory._safe or not creep.memory._safe_from \
            or movement.chebyshev_distance_room_pos(creep.memory._safe_from, creep.pos) > 2:
        creep.memory._safe = []
        creep.memory._safe_from = creep.pos

    any_unsafe = False
    for obj in hostile_path_targets:
        target = obj['pos']
        target_range = obj['range']
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


def running_check_room(room):
    # type: (RoomMind) -> None
    """
    :type room: rooms.room_mind.RoomMind
    """
    if room.my and room.room.controller.safeMode:
        return
    my_creeps = cast(List[Creep], room.find(FIND_MY_CREEPS))
    if not len(my_creeps):
        return
    if not len(room.defense.dangerous_hostiles()):
        return

    hostile_path_targets = pathfinder_enemy_array_for_room(room.name)

    for creep in my_creeps:
        if creep.fatigue > 0 or len(creep.body) <= 1 \
                or _.find(creep.body, lambda p: p.type == ATTACK or p.type == RANGED_ATTACK or p.type == HEAL) \
                or (creep.memory.role == role_simple_dismantle
                    and creep.memory.home in Game.rooms
                    and room.hive.get_room(creep.memory.home).conducting_siege()) \
                or not creep.hasActiveBodyparts(MOVE) \
                or (creep.memory.role == role_miner and _.find(creep.pos.lookFor(LOOK_STRUCTURES),
                                                               {'structureType': STRUCTURE_RAMPART})) \
                or (creep.memory.role == role_squad_dismantle):
            continue
        overridden = run_away_check(creep, hostile_path_targets)
        if overridden:
            volatile_cache.setmem("creep_defense_override").add(creep.name)


def cleanup_running_memory():
    # type: () -> None
    creep_defense_override = volatile_cache.setmem("creep_defense_override")
    for creep in _.values(Game.creeps):
        if not creep_defense_override.has(creep.name) and ('_away_path' in creep.memory or '_safe' in creep.memory):
            del creep.memory._away_path
            del creep.memory._safe
            del creep.memory._safe_from


def pickup_check_room(room):
    # type: (RoomMind) -> None
    energy = cast(List[Resource], room.find(FIND_DROPPED_RESOURCES))
    if not len(energy):
        return
    creeps = cast(List[Creep], room.find(FIND_MY_CREEPS))
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
                        creep.picked_up = pile
                        left -= empty
                        if left <= 0:
                            break
