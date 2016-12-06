from constants import *
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

MOVE_THEN_WORK = 4
CONSTANT_MOVEMENT = 3
MILITARY = 2
MOVE_THEN_STOP = 1

spawn_fill_running_memory = __pragma__('js', '{}', """
function runningMemory (creep) {
    if (creep.memory.running && creep.memory.running != role_spawn_fill) {
        return MOVE_THEN_WORK;
    } else {
        return CONSTANT_MOVEMENT;
    }
}
""")

role_movement_types = {
    role_upgrader: MOVE_THEN_WORK,
    role_spawn_fill: CONSTANT_MOVEMENT,
    role_spawn_fill_backup: CONSTANT_MOVEMENT,
    role_upgrade_fill: MOVE_THEN_WORK,
    role_link_manager: MOVE_THEN_STOP,
    role_builder: MOVE_THEN_WORK,
    role_tower_fill: CONSTANT_MOVEMENT,
    role_miner: MOVE_THEN_STOP,
    role_hauler: CONSTANT_MOVEMENT,
    role_remote_mining_reserve: MOVE_THEN_STOP,
    role_defender: MILITARY,
    role_wall_defender: MILITARY,
    role_ranged_offense: MILITARY,
    role_cleanup: MOVE_THEN_WORK,
    role_temporary_replacing: MOVE_THEN_WORK,
    role_colonist: MOVE_THEN_WORK,
    role_simple_claim: MOVE_THEN_WORK,
    role_room_reserve: MOVE_THEN_STOP,
    role_mineral_steal: CONSTANT_MOVEMENT,
    role_recycling: CONSTANT_MOVEMENT,
    role_mineral_miner: MOVE_THEN_STOP,
    role_mineral_hauler: CONSTANT_MOVEMENT,
    role_td_healer: MILITARY,
    role_td_goad: MILITARY,
    role_simple_dismantle: MILITARY,
    role_scout: MILITARY,
    role_power_attack: MILITARY,
    role_power_cleanup: MILITARY,
    role_energy_grab: MILITARY,
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
                    && !('pt' in creep.memory && creep.memory.pt < Game.time))) {
                creep.__move(creep.pos.getDirectionTo(this.pos));
                creep.__moved = true;
            } else if (otherPriority == myPriority && (!('pt' in creep.memory) || creep.memory.pt < Game.time)) {
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
    this.__moved = true;
    return result;
}
""")


def apply_move_prototype():
    Creep.prototype.__move = Creep.prototype.move
    Creep.prototype.move = move_prototype


def mod_cost_matrix(me, room_name, cost_matrix):
    my_role = me.memory.running or me.memory.role
    my_priority = role_movement_types[my_role] or MOVE_THEN_WORK
    if room_name in Game.rooms:
        for creep in Game.rooms[room_name].find(FIND_MY_CREEPS):
            role = creep.memory.running or creep.memory.role
            priority = role_movement_types[role] or MOVE_THEN_WORK
            if priority > my_priority:
                x = creep.pos.x
                y = creep.pos.y
                if Game.map.getTerrainAt(x, y, room_name) == 'swamp':
                    cost_matrix.set(creep.pos.x, creep.pos.y, 10)
                else:
                    cost_matrix.set(creep.pos.x, creep.pos.y, 2)
            elif priority == my_priority:
                x = creep.pos.x
                y = creep.pos.y
                if Game.map.getTerrainAt(x, y, room_name) == 'swamp':
                    cost_matrix.set(creep.pos.x, creep.pos.y, 10 + 3)
                else:
                    cost_matrix.set(creep.pos.x, creep.pos.y, 2 + 3)
