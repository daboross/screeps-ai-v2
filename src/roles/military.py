import math

from role_base import RoleBase
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def delete_target(target_id):
    index = _.findIndex(Memory.hostiles, lambda t: t[0] == target_id)
    if index >= 0:
        Memory.hostiles.splice(index, 1)
    del Memory.hostile_last_rooms[target_id]
    del Memory.hostile_last_positions[target_id]


class RoleDefender(RoleBase):
    def run(self):
        target_id = self.memory.attack_target
        if not target_id:
            best_id = None
            closest_distance = math.pow(2, 30)
            for target_id, room_name, pos, target_owner in Memory.hostiles:
                distance = movement.distance_squared_room_pos(self.creep.pos, pos)
                if distance < closest_distance:
                    best_id = target_id
                    closest_distance = distance
            if best_id:
                target_id = best_id
                self.memory.attack_target = best_id
            else:
                self.recycle_me()
                return False

        hostile_room = Memory.hostile_last_rooms[target_id]
        if self.creep.pos.roomName != hostile_room:
            if hostile_room:
                self.move_to(__new__(RoomPosition(25, 25, hostile_room)))
                return False
            else:
                self.memory.attack_target = None
                delete_target(target_id)
                return True

        target = Game.getObjectById(target_id)

        if target is None or self.room.hostile:
            self.memory.attack_target = None
            delete_target(target_id)
            return True

        self.move_to(target)


profiling.profile_whitelist(RoleDefender, ["run"])
