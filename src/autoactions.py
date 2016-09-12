import context
import flags
from constants import role_scout, INVADER_USERNAME
from control import pathdef
from tools import profiling
from utilities import volatile_cache, movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def pathfinder_enemy_array_for_room(room_name):
    cache = volatile_cache.mem("enemy_lists")
    if cache.has(room_name):
        return cache.get(room_name)

    enemy_positions = []

    if Memory.hostiles and len(Memory.hostiles):
        for hostile, hostile_room, pos, owner in Memory.hostiles:
            dx, dy = movement.inter_room_difference(hostile_room, room_name)
            if abs(dx) <= 1 and abs(dy) <= 1:
                if owner == "Source Keeper":
                    enemy_range = 5
                elif owner == INVADER_USERNAME:
                    enemy_range = 20
                else:
                    enemy_range = 60
                pos = __new__(RoomPosition(pos.x, pos.y, pos.roomName))
                enemy_positions.append({"pos": pos, "range": enemy_range})

    cache.set(room_name, enemy_positions)
    return enemy_positions


def room_hostile(room_name):
    cache = volatile_cache.mem("rua")
    if cache.has(room_name):
        return cache.get(room_name)

    room_under_attack = False

    for hostile, hostile_room, pos, owner in Memory.hostiles:
        if hostile_room == room_name and owner != "Source Keeper":
            room_under_attack = True
            break

    cache.set(room_name, room_under_attack)
    return room_under_attack


def simple_cost_matrix(room_name, new_to_use_as_base=False):
    cache = volatile_cache.mem("enemy_cost_matrix")
    if not new_to_use_as_base and cache.has(room_name):
        return cache.get(room_name)
    # TODO: some of this is duplicated in pathdef.HoneyTrails

    room = context.hive().get_room(room_name)
    if not room:
        if room_hostile(room_name) or (Memory.enemy_rooms and room_name in Memory.enemy_rooms):
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
    for flag in flags.find_flags(room_name, flags.SK_LAIR_SOURCE_NOTED):
        set_in_range(flag.pos, 4, 255, 0)

    if not new_to_use_as_base:
        cache.set(room_name, cost_matrix)
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
        path = get_path_away(creep.creep.pos, targets)
        creep.memory._away_path = {"reset": Game.time + 10, "path": Room.serializePath(path)}
        return path


def instinct_do_heal(creep):
    """
    :type creep: role_base.RoleBase
    """
    if not creep.creep.getActiveBodyparts(HEAL):
        return
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
    if not creep.creep.getActiveBodyparts(ATTACK):
        return
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
        del creep.memory.running_now
        return False
    if creep.creep.getActiveBodyparts(ATTACK) or creep.creep.getActiveBodyparts(RANGED_ATTACK):
        return False  # we're a defender, defenders don't run away!

    if not creep.creep.getActiveBodyparts(MOVE) or creep.creep.fatigue > 0:  # if we can't move, we won't move.
        instinct_do_heal(creep)
        instinct_do_attack(creep)
        return False

    for obj in hostile_path_targets:
        target = obj.pos
        target_range = obj.range
        if not movement.distance_squared_room_pos(target, creep.creep.pos) > target_range * target_range:
            break
    else:
        # No targets in range, no need to do anything
        for obj in hostile_path_targets:
            target = obj.pos
            target_range = obj.range
            if creep.memory.running_now:
                target_range *= 1.2
            if not movement.distance_squared_room_pos(target, creep.creep.pos) > (target_range) * (target_range):
                return True  # Still cancel creep actions if we're semi-close, so as not to do back-and-forth.
        return False

    creep.memory.running_now = True
    path = get_cached_away_path(creep, hostile_path_targets)

    if len(path):
        if creep.creep.getActiveBodyparts(HEAL):
            instinct_do_heal(creep)
        if creep.creep.getActiveBodyparts(ATTACK):
            instinct_do_attack(creep)
        creep.last_checkpoint = None  # we're moving manually here
        del creep.memory.was_on_the_path
        result = creep.creep.moveByPath(path)
        if result == ERR_NO_PATH or result == ERR_NOT_FOUND:
            # del creep.memory._away_path
            # path = get_cached_away_path(creep, hostile_path_targets)
            # result = creep.creep.moveByPath(path)
            # I had the above enabled previously, and I don't think it really helped any... the ERR_NOT_FOUND would just
            # happen with the newly-generated path too.
            return True
        if result != OK:
            creep.log("Unknown result from moving when running away: {}".format(result))
        return True
    else:
        # we're a safe distance away from all enemies
        return False


run_away_check = profiling.profiled(run_away_check, "autoactions.run_away_check")


def pickup_check(creep):
    """
    :type creep: role_base.RoleBase
    """
    if creep.should_pickup() and _.sum(creep.creep.carry) < creep.creep.carryCapacity:
        energy = creep.room.find_in_range(FIND_DROPPED_RESOURCES, 1, creep.creep.pos)
        if len(energy) > 0:
            if len(energy) > 1:
                energy = _.sortBy(energy, lambda e: e.amount)
            for e in energy:
                if creep.should_pickup(e.resourceType):
                    creep.creep.pickup(e)
                    break


def mercy_check(creep):
    """
    :type creep: role_base.RoleBase
    """
    if creep.memory.role != role_scout and len(creep.creep.body) <= 1:
        creep.creep.suicide()
        return True


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
    if mercy_check(creep):
        return True
    pickup_check(creep)
    # transfer_check(creep)
    return False


instinct_check = profiling.profiled(instinct_check, "autoactions.instinct_check")
