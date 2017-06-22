from constants import INVADER_USERNAME, rmem_key_stored_hostiles, role_defender, role_miner, role_recycling, \
    target_rampart_defense
from creeps.base import RoleBase
from creeps.behaviors.military import MilitaryBase
from jstools.screeps import *
from utilities import hostile_utils, movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


class RoleDefender(MilitaryBase):
    def should_pickup(self, resource_type=None):
        return False

    def run(self):
        target_id = self.memory.attack_target
        if not target_id:
            best_id = None
            closest_distance = Infinity
            for hostile in self.room.defense.dangerous_hostiles():
                distance = movement.chebyshev_distance_room_pos(self.pos, hostile.pos)
                if distance < closest_distance:
                    best_id = hostile.id
                    closest_distance = distance
            if not best_id:
                for mem_hostile in self.home.defense.remote_hostiles():
                    distance = movement.chebyshev_distance_room_pos(
                        self.pos, positions.deserialize_xy_to_pos(mem_hostile.pos, mem_hostile.room))
                    if mem_hostile.ranged and not mem_hostile.attack:
                        distance += 1000  # Don't go after kiting attackers
                    if distance < closest_distance:
                        best_id = mem_hostile.id
                        closest_distance = distance
            if best_id:
                target_id = best_id
                self.memory.attack_target = best_id
            else:
                self.memory.role = role_recycling
                self.memory.last_role = role_defender
                return False

        hostile_info = Memory.hostiles[target_id]
        if not hostile_info or Game.time >= hostile_info.dead:
            del self.memory.attack_target
            return True

        hostile_room = hostile_info.room
        hostile_pos = positions.deserialize_xy_to_pos(hostile_info.pos, hostile_room)

        if self.pos.roomName != hostile_room:
            if 'checkpoint' not in self.memory or \
                            movement.chebyshev_distance_room_pos(self.memory.checkpoint, self.pos) > 50:
                self.memory.checkpoint = self.pos
            if hostile_utils.enemy_owns_room(self.memory.checkpoint.roomName):
                self.memory.checkpoint = self.home.spawn or movement.find_an_open_space(self.home.name)

            if 'enemy_checkpoint' in self.memory:
                enemy_checkpoint = self.memory.enemy_checkpoint
                if movement.chebyshev_distance_room_pos(enemy_checkpoint, hostile_pos) > 10:
                    enemy_checkpoint = self.memory.enemy_checkpoint = hostile_pos
            else:
                enemy_checkpoint = self.memory.enemy_checkpoint = hostile_pos

            self.follow_military_path(_.create(RoomPosition.prototype, self.memory.checkpoint),
                                      _.create(RoomPosition.prototype, enemy_checkpoint), {'range': 1})
            return False

        target = Game.getObjectById(target_id)

        if target is None or (self.room.hostile and target.owner.username != INVADER_USERNAME):
            del self.memory.attack_target
            del Memory.hostiles[target_id]
            if hostile_room in Memory.rooms:
                room_hostiles = Memory.rooms[hostile_room][rmem_key_stored_hostiles]
                index = _.findIndex(room_hostiles, lambda x: x.id == target_id)
                if index != -1:
                    room_hostiles.splice(index, 1)
            return True

        if self.pos.isNearTo(target):
            self.creep.attack(target)
        else:
            self.move_to(target, {'reusePath': 2})

    def _calculate_time_to_replace(self):
        return 0  # never live-replace a defender.


class WallDefender(RoleBase):
    def run(self):
        target = self.targets.get_new_target(self, target_rampart_defense)
        if not target:
            self.go_to_depot()
            self.log('no new target! target: {}'.format(target))
            return

        nearby_enemies = self.room.look_for_in_area_around(LOOK_CREEPS, self, 1)

        if len(nearby_enemies):
            biggest_threat = _.max(nearby_enemies, lambda x: self.home.defense.danger_level(x.creep))
            if self.home.defense.danger_level(biggest_threat.creep) > 0:
                result = self.creep.attack(biggest_threat.creep)
                if result != OK:
                    self.log("Unknown result from creep.attack({}): {}".format(biggest_threat.creep, result))
        else:
            if self.pos.isEqualTo(target) and len(self.home.defense.dangerous_hostiles()):
                if _.some(self.home.defense.get_current_defender_spots()[0],
                          lambda loc: not self.targets.targets[target_rampart_defense][loc.name]):
                    self.log("Found a new hot spot: untargeting.")
                    self.targets.untarget(self, target_rampart_defense)

        if not self.pos.isEqualTo(target):
            self.move_to(target)
        else:
            at_target = self.room.look_at(LOOK_CREEPS, target)
            if _.some(at_target, lambda c: c.memory.role == role_miner):
                self.log("Hot spot has miner: untargeting.")
                self.targets.untarget(self, target_rampart_defense)
