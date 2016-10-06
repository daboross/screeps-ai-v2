from constants import INVADER_USERNAME
from role_base import RoleBase
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


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
                if Game.cpu.bucket < 6500:
                    self.creep.suicide()
                else:
                    self.basic_move_to(__new__(RoomPosition(25, 25, self.pos.roomName)))
                return False

        hostile_info = Memory.hostiles[target_id]
        if not hostile_info or Game.time >= hostile_info.dead:
            del self.memory.attack_target
            return True

        hostile_room = hostile_info.room

        if self.pos.roomName != hostile_room:
            self.creep.moveTo(__new__(RoomPosition(25, 25, hostile_room)))
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

        self.creep.moveTo(target)

    def _calculate_time_to_replace(self):
        return 0  # never live-replace a defender.


class WallDefender(RoleBase):
    def run(self):
        pass


profiling.profile_whitelist(RoleDefender, ["run"])
