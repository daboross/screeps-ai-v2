from constants import INVADER_USERNAME, target_rampart_defense, role_recycling, role_wall_defender, role_defender
from role_base import RoleBase
from roles.offensive import MilitaryBase
from tools import profiling
from utilities import hostile_utils
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


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
                        self.pos, movement.serialized_pos_to_pos_obj(mem_hostile.room, mem_hostile.pos))
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
        hostile_pos = movement.serialized_pos_to_pos_obj(hostile_room, hostile_info.pos)

        if self.pos.roomName != hostile_room:
            if 'checkpoint' not in self.memory or \
                            movement.chebyshev_distance_room_pos(self.memory.checkpoint, self.pos) > 50:
                self.memory.checkpoint = self.pos
            if hostile_utils.enemy_room(self.memory.checkpoint.roomName):
                self.memory.checkpoint = self.home.spawn or movement.find_an_open_space(self.home.room_name)

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
            room_hostiles = Memory.rooms[hostile_room].danger
            index = _.findIndex(room_hostiles, lambda x: x.id == target_id)
            if index != -1:
                room_hostiles.splice(index, 1)
            return True

        self.creep.moveTo(target, _.create(self._move_options(target.pos.roomName), {'reusePath': 2}))

    def _calculate_time_to_replace(self):
        return 0  # never live-replace a defender.


class WallDefender(RoleBase):
    def run(self):
        target = self.targets.get_new_target(self, target_rampart_defense)
        if not target:
            self.log("WARNING: No wall to defend!")
        if target:
            if not self.creep.pos.isEqualTo(target.pos):
                self.move_to(target)
            elif not _.find(self.room.look_at(LOOK_STRUCTURES, self.pos),
                            lambda s: s.structureType == STRUCTURE_RAMPART):
                self.move_to(self.pos.findClosestByRange(FIND_MY_STRUCTURES,
                                                         {'filter': lambda s: s.structureType == STRUCTURE_RAMPART
                                                                              and not len(s.pos.lookFor(LOOK_CREEPS))}))
                return
        all_hostiles = self.room.defense.all_hostiles()
        highest_priority = _.find(all_hostiles, lambda f: f.pos.isNearTo(self.pos))  # hostiles are already sorted

        if highest_priority:
            self.creep.attack(highest_priority)
        else:
            tcheck = (Game.time * 2 + self.creep.ticksToLive) % 50
            if tcheck <= 5:  # In case the enemies are bouncing in and out - let's give a good window to find a new wall
                if not self.room.mem.attack and not len(all_hostiles):
                    self.memory.role = role_recycling
                    self.memory.last_role = role_wall_defender
                    return False
                elif self.pos.isEqualTo(target.pos) and len(all_hostiles):
                    # TODO: in this case, look for a specific wall which has hostiles next to it! don't just blindly
                    # re-choose
                    self.targets.untarget(self, target_rampart_defense)


profiling.profile_whitelist(RoleDefender, ["run"])
