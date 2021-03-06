from typing import Dict, Optional, TYPE_CHECKING, cast

from constants import INVADER_USERNAME, rmem_key_stored_hostiles, role_defender, role_miner, role_recycling, \
    target_rampart_defense
from creeps.base import RoleBase
from creeps.behaviors.military import MilitaryBase
from jstools.screeps import *
from utilities import hostile_utils, movement, positions

if TYPE_CHECKING:
    from empire.targets import TargetMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


class RoleDefender(MilitaryBase):
    def should_pickup(self, resource_type = None):
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

        target = cast(Creep, Game.getObjectById(target_id))

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
    def boost(self):
        if not self.room.defense.needs_boosted_defenders():
            self.memory.boosted = 2
            return False

        lab = _.find(self.home.minerals.labs(),
                     lambda l: l.mineralAmount and l.energy and l.mineralType == RESOURCE_CATALYZED_UTRIUM_ACID)
        if lab:
            if self.pos.isNearTo(lab):
                result = lab.boostCreep(self.creep)
                if result == OK or result == ERR_NOT_ENOUGH_RESOURCES or self.creep.hasBoostedBodyparts(ATTACK):
                    self.memory.boosted = 1
                else:
                    self.log("WARNING: Unknown result from {}.boostCreep({}): {}"
                             .format(lab, self.creep, result))
            else:
                self.move_to(lab)
            return True
        else:
            self.memory.boosted = 2
        return False

    def run(self):
        if self.creep.ticksToLive > 1400 and not (self.memory.boosted >= 1):
            if self.boost():
                return False
        target = self.targets.get_new_target(self, target_rampart_defense)
        if not target:
            self.go_to_depot()
            self.log('no new target! target: {}'.format(target))
            return

        nearby_enemies = self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1)

        if len(nearby_enemies):
            biggest_threat = cast(Dict[str, Creep],
                                  _.max(nearby_enemies, lambda x: self.home.defense.danger_level(x.creep)))
            if self.home.defense.danger_level(biggest_threat[LOOK_CREEPS]) > 0:
                result = self.creep.attack(biggest_threat[LOOK_CREEPS])
                if result != OK:
                    self.log("Unknown result from creep.attack({}): {}".format(biggest_threat[LOOK_CREEPS], result))
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


def find_new_target_rampart_defense_spot(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    hot_spots, cold_spots = creep.home.defense.get_current_defender_spots()
    nearest = None
    nearest_distance = Infinity
    for location in hot_spots:
        if not targets.targets[target_rampart_defense][location.name]:
            distance = movement.chebyshev_distance_room_pos(location, creep.pos)
            if distance < nearest_distance:
                nearest = location
                nearest_distance = distance
    if nearest is None:
        for location in cold_spots:
            if not targets.targets[target_rampart_defense][location.name]:
                distance = movement.chebyshev_distance_room_pos(location, creep.pos)
                if distance < nearest_distance:
                    nearest = location
                    nearest_distance = distance
        if nearest is None:
            for location in creep.home.defense.get_old_defender_spots():
                if not targets.targets[target_rampart_defense][location.name]:
                    distance = movement.chebyshev_distance_room_pos(location, creep.pos)
                    if distance < nearest_distance:
                        nearest = location
                        nearest_distance = distance
    if nearest:
        return nearest.name
    else:
        return None
