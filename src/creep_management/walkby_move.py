from cache import volatile_cache
from constants import *
from empire import stored_data
from jstools.screeps import *
from utilities import hostile_utils

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

IDLE_ABOUT = 6
MOVE_THEN_WORK = 5
CONSTANT_MOVEMENT = 4
SEMICONSTANT_MOVEMENT = 3
MILITARY = 2
MOVE_THEN_STOP = 1

role_movement_types = {
    role_upgrader: MOVE_THEN_WORK,
    role_spawn_fill: SEMICONSTANT_MOVEMENT,
    "spawn_wait": IDLE_ABOUT,
    role_spawn_fill_backup: SEMICONSTANT_MOVEMENT,
    role_upgrade_fill: IDLE_ABOUT,
    role_link_manager: MOVE_THEN_STOP,
    role_builder: MOVE_THEN_WORK,
    role_tower_fill: SEMICONSTANT_MOVEMENT,
    role_miner: MOVE_THEN_STOP,
    role_hauler: CONSTANT_MOVEMENT,
    role_remote_mining_reserve: MOVE_THEN_STOP,
    role_defender: MILITARY,
    role_wall_defender: MILITARY,
    role_ranged_offense: MILITARY,
    role_cleanup: MOVE_THEN_WORK,
    role_temporary_replacing: MOVE_THEN_WORK,
    role_colonist: MOVE_THEN_WORK,
    role_sacrifice: IDLE_ABOUT,
    role_sacrificial_cleanup: MOVE_THEN_WORK,
    role_simple_claim: MILITARY,
    role_room_reserve: MOVE_THEN_STOP,
    role_mineral_steal: CONSTANT_MOVEMENT,
    role_recycling: CONSTANT_MOVEMENT,
    role_mineral_miner: MOVE_THEN_STOP,
    role_mineral_hauler: IDLE_ABOUT,
    role_td_healer: MILITARY,
    role_td_goad: MILITARY,
    role_simple_dismantle: MILITARY,
    role_scout: MILITARY,
    role_power_attack: MILITARY,
    role_power_cleanup: MILITARY,
    role_energy_grab: MILITARY,
    role_squad_init: IDLE_ABOUT,
    role_squad_final_renew: MOVE_THEN_WORK,
    role_squad_final_boost: MOVE_THEN_WORK,
    role_squad_drone: MILITARY,
    role_squad_kiting_heal: MILITARY,
    role_squad_kiting_attack: MILITARY,
    role_squad_ranged: MILITARY,
    role_squad_all_attack: MILITARY,
    role_squad_dismantle: MILITARY,
    role_squad_heal: MILITARY,
}

move_prototype = __pragma__('js', '{}', """
function move (direction) {
    var result = this.__move(direction);
    if (result != OK) {
        return result;
    }
    var newX, newY;
    switch (direction) {
        case TOP_LEFT:
            newX = this.pos.x - 1;
            newY = this.pos.y - 1;
            break;
        case LEFT:
            newX = this.pos.x - 1;
            newY = this.pos.y;
            break;
        case BOTTOM_LEFT:
            newX = this.pos.x - 1;
            newY = this.pos.y + 1;
            break;
        case TOP:
            newX = this.pos.x;
            newY = this.pos.y - 1;
            break;
        case BOTTOM:
            newX = this.pos.x;
            newY = this.pos.y + 1;
            break;
        case TOP_RIGHT:
            newX = this.pos.x + 1;
            newY = this.pos.y - 1;
            break;
        case RIGHT:
            newX = this.pos.x + 1;
            newY = this.pos.y;
            break;
        case BOTTOM_RIGHT:
            newX = this.pos.x + 1;
            newY = this.pos.y + 1;
            break;
    }
    if (newX > 49 || newY > 49 || newX < 0 || newY < 0) {
        this.__moved = true;
        return result;
    }
    var creeps = this.room.lookForAt(LOOK_CREEPS, newX, newY);
    if (creeps.length) {
        var creep = creeps[0]
        if (creep.my) {
            var myRole = this.memory.running || this.memory.role;
            var myPriority = role_movement_types[myRole] || MOVE_THEN_WORK;
            var otherRole = creep.memory.running || creep.memory.role;
            var otherPriority = role_movement_types[otherRole] || MOVE_THEN_WORK;
            if (myPriority < otherPriority
                || (otherPriority == myPriority
                    && this.ticksToLive < creep.ticksToLive
                    && (!('pt' in creep.memory) || creep.memory.pt >= Game.time))) {
                creep.__move(creep.pos.getDirectionTo(this.pos));
                creep.__moved = true;
            } else if (!creep.__moved) {
                if (otherPriority == myPriority && (!('pt' in creep.memory) || creep.memory.pt >= Game.time)) {
                    if (!('pt' in this.memory) || Game.time - this.memory.pt > 50) {
                        this.memory.pt = Game.time + 5;
                    }
                    if (this.memory.pt >= Game.time) {
                        creep.__move(creep.pos.getDirectionTo(this.pos));
                        creep.__moved = true;
                    } else {
                        delete this.memory._move;
                        return result;
                    }
                } else {
                    delete this.memory._move;
                    return result;
                }
            }
        }
    } else if ('pt' in this.memory && Game.time - this.memory.pt > 50) {
        delete this.memory.pt;
    }
    this.__moved = true;
    return result;
}
""")


def apply_move_prototype():
    Creep.prototype.__move = Creep.prototype.move
    Creep.prototype.move = move_prototype


def _add_only_blocking_creeps_to_matrix(my_priority, room, cost_matrix, same_role_cost, same_role_swamp_cost,
                                        existing_cost_addition):
    for creep in room.find(FIND_MY_CREEPS):
        role = creep.memory.running or creep.memory.role
        priority = role_movement_types[role] or MOVE_THEN_WORK
        # Constant movement creeps constantly move.
        if priority == MOVE_THEN_STOP or (priority < my_priority and priority is not CONSTANT_MOVEMENT):
            cost_matrix.set(creep.pos.x, creep.pos.y, 255)
        elif priority is my_priority \
                or (priority is CONSTANT_MOVEMENT and priority < my_priority):
            x = creep.pos.x
            y = creep.pos.y
            if Game.map.getTerrainAt(x, y, room.name) == 'swamp':
                if cost_matrix.get(x, y) < same_role_swamp_cost:
                    cost_matrix.set(x, y, same_role_swamp_cost)
                else:
                    cost_matrix.set(x, y, cost_matrix.get(x, y) + existing_cost_addition)
            else:
                if cost_matrix.get(x, y) < same_role_cost:
                    cost_matrix.set(x, y, same_role_cost)
                else:
                    cost_matrix.set(x, y, cost_matrix.get(x, y) + existing_cost_addition)


def _create_basic_room_cost_matrix(room_name):
    matrix = __new__(PathFinder.CostMatrix())
    room = Game.rooms[room_name]
    if room:
        any_lairs = False
        for structure in room.find(FIND_STRUCTURES):
            if structure.structureType == STRUCTURE_RAMPART and (structure.my or structure.isPublic):
                continue
            if structure.structureType == STRUCTURE_ROAD:
                if matrix.get(structure.pos.x, structure.pos.y) <= 2:
                    matrix.set(structure.pos.x, structure.pos.y, 1)
                continue
            if structure.structureType == STRUCTURE_CONTAINER:
                continue
            if structure.structureType == STRUCTURE_KEEPER_LAIR:
                any_lairs = True
            matrix.set(structure.pos.x, structure.pos.y, 255)
        for site in room.find(FIND_MY_CONSTRUCTION_SITES):
            if site.structureType == STRUCTURE_RAMPART or site.structureType == STRUCTURE_ROAD \
                    or site.structureType == STRUCTURE_CONTAINER:
                continue
            matrix.set(site.pos.x, site.pos.y, 255)
        # Note: this depends on room being a regular Room, not a RoomMind, since RoomMind.find(FIND_HOSTILE_CREEPS)
        # excludes allies!
        if not room.controller or not room.controller.my or not room.controller.safeMode:
            for creep in room.find(FIND_HOSTILE_CREEPS):
                matrix.set(creep.pos.x, creep.pos.y, 255)
        if any_lairs:
            for source in room.find(FIND_SOURCES):
                for x in range(source.pos.x - 4, source.pos.x + 5):
                    for y in range(source.pos.y - 4, source.pos.y + 5):
                        matrix.set(x, y, 250)
            for mineral in room.find(FIND_MINERALS):
                for x in range(mineral.pos.x - 4, mineral.pos.x + 5):
                    for y in range(mineral.pos.y - 4, mineral.pos.y + 5):
                        matrix.set(x, y, 250)
    else:
        data = stored_data.get_data(room_name)
        if not data:
            return matrix
        for obstacle in data.obstacles:
            if obstacle.type == StoredObstacleType.ROAD:
                if matrix.get(obstacle.x, obstacle.y) == 0:
                    matrix.set(obstacle.x, obstacle.y, 1)
            else:
                if obstacle.type == StoredObstacleType.SOURCE_KEEPER_SOURCE \
                        or obstacle.type == StoredObstacleType.SOURCE_KEEPER_MINERAL:
                    for x in range(obstacle.x - 4, obstacle.x + 5):
                        for y in range(obstacle.y - 4, obstacle.y + 5):
                            matrix.set(x, y, 250)
                matrix.set(obstacle.x, obstacle.y, 255)
    return matrix


def _add_avoid_things_to_cost_matrix(room_name, cost_matrix, roads):
    multiplier = 2 if roads else 1
    # Add a small avoidance for exits
    for x in [0, 49]:
        for y in range(0, 49):
            terrain = Game.map.getTerrainAt(x, y, room_name)
            if terrain != 'wall':
                existing = cost_matrix.get(x, y)
                if existing is 0:
                    if terrain == 'swamp':
                        existing = 5 * multiplier
                    else:  # plains
                        existing = multiplier
                cost_matrix.set(x, y, existing + 2 * multiplier)
    for y in [0, 49]:
        for x in range(1, 48):  # 0, 0 and 49, 49 have already been added above
            terrain = Game.map.getTerrainAt(x, y, room_name)
            if terrain != 'wall':
                existing = cost_matrix.get(x, y)
                if existing is 0:
                    if terrain == 'swamp':
                        existing = 5 * multiplier
                    else:  # plains
                        existing = multiplier
                cost_matrix.set(x, y, existing + 2 * multiplier)


def get_cost_matrix_for_creep(me, room_name, roads, target_room=None):
    if hostile_utils.enemy_using_room(room_name) and room_name != target_room:
        return False
    if room_name not in Game.rooms:
        return __new__(PathFinder.CostMatrix())  # TODO: pull cached data here

    cache = volatile_cache.submem('matrices', room_name)

    my_role = me.memory.running or me.memory.role
    my_priority = role_movement_types[my_role] or MOVE_THEN_WORK

    key = my_priority
    if roads:
        key <<= 5
    if cache.has(key):
        return cache.get(key)
    else:
        if roads:
            basic_key = -2
        else:
            basic_key = -1
        if cache.has(basic_key):
            matrix = cache.get(basic_key).clone()
        else:
            matrix = _create_basic_room_cost_matrix(room_name)
            _add_avoid_things_to_cost_matrix(room_name, matrix, roads)
            cache.set(basic_key, matrix.clone())
        multiplier = 2 if roads else 1
        _add_only_blocking_creeps_to_matrix(my_priority, Game.rooms[room_name], matrix,
                                            5 * multiplier,  # same role cost (1 + 4)
                                            9 * multiplier,  # same role cost in swamp (5 + 4)
                                            4 * multiplier,  # existing cost addition (x + 4)
                                            )
        return matrix


def get_basic_cost_matrix(room_name, roads=False):
    if room_name not in Game.rooms:
        return __new__(PathFinder.CostMatrix())  # TODO: pull cached data here
    cache = volatile_cache.submem('matrices', room_name)
    if roads:
        basic_key = -2
    else:
        basic_key = -1
    if cache.has(basic_key):
        matrix = cache.get(basic_key).clone()
    else:
        matrix = _create_basic_room_cost_matrix(room_name)
        _add_avoid_things_to_cost_matrix(room_name, matrix, roads)
        cache.set(basic_key, matrix.clone())
    return matrix


def create_cost_callback(me, roads, target_room=None):
    return lambda room_name: get_cost_matrix_for_creep(me, room_name, roads, target_room)
