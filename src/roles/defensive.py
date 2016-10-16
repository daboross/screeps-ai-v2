import role_base
from constants import INVADER_USERNAME, target_rampart_defense, role_recycling, role_wall_defender
from role_base import RoleBase
from tools import profiling
from utilities import hostile_utils
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def avoid_hostile_rooms_costmatrix(room_name, cost_matrix):
    if hostile_utils.enemy_room(room_name):
        for x in range(0, 49):
            for y in range(0, 49):
                cost_matrix.set(x, y, 150)
        return False
    else:
        role_base.add_roads(room_name, cost_matrix)
    return cost_matrix


class RoleDefender(RoleBase):
    def should_pickup(self, resource_type=None):
        return False

    def run(self):
        target_id = self.memory.attack_target
        if not target_id:
            best_id = None
            closest_distance = Infinity
            for hostile in self.room.defense.dangerous_hostiles():
                distance = movement.distance_room_pos(self.pos, hostile.pos)
                if distance < closest_distance:
                    best_id = hostile.id
                    closest_distance = distance
            if not best_id:
                for mem_hostile in self.home.defense.remote_hostiles():
                    distance = movement.distance_squared_room_pos(self.pos, {
                        'x': mem_hostile.pos & 0x3F, 'y': mem_hostile.pos >> 6 & 0x3F, 'roomName': mem_hostile.room,
                    })
                    if distance < closest_distance:
                        best_id = mem_hostile.id
                        closest_distance = distance
            if best_id:
                target_id = best_id
                self.memory.attack_target = best_id
            else:
                self.creep.suicide()
                return False

        hostile_info = Memory.hostiles[target_id]
        if not hostile_info or Game.time >= hostile_info.dead:
            del self.memory.attack_target
            return True

        hostile_room = hostile_info.room

        if self.pos.roomName != hostile_room:
            self.creep.moveTo(__new__(RoomPosition(25, 25, hostile_room)), {
                'ignoreRoads': True,
                'costCallback': avoid_hostile_rooms_costmatrix,
            })
            return False

        target = Game.getObjectById(target_id)

        if target is None or (self.room.hostile and target.owner.username != INVADER_USERNAME):
            del self.memory.attack_target
            del Memory.hostiles[target_id]
            room_hostiles = Memory.rooms[hostile_room].danger
            index = _.findIndex(room_hostiles, lambda x: x.id == target_id)
            if index != -1:
                room_hostiles.splice(index, 1)
            return True

        self.creep.moveTo(target, {'reusePath': 2, 'ignoreRoads': True,
                                   "costCallback": role_base.def_cost_callback})

    def _calculate_time_to_replace(self):
        return 0  # never live-replace a defender.


class WallDefender(RoleBase):
    def run(self):
        target = self.targets.get_new_target(self, target_rampart_defense)
        if not target:
            target = self.home.find_closest_by_range(FIND_HOSTILE_CREEPS, self)
        if not self.creep.pos.isEqualTo(target.pos):
            self.creep.moveTo(target)
        all_hostiles = self.room.defense.all_hostiles()
        highest_priority = _.find(all_hostiles, lambda f: f.pos.isNearTo(self.pos))  # hostiles are already sorted

        if highest_priority:
            self.creep.attack(highest_priority)
        elif not len(all_hostiles):
            if (Game.time * 2 + self.creep.ticksToLive) % 50 == 0:
                self.targets.untarget(self, target_rampart_defense)
                if not self.room.mem.attack:
                    self.memory.role = role_recycling
                    self.memory.last_role = role_wall_defender
                    return False


profiling.profile_whitelist(RoleDefender, ["run"])
