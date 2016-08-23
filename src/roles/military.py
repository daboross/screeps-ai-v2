import math
import random

import autoactions
import context
import flags
from constants import target_single_flag, role_td_healer
from control import pathdef
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
                self.creep.move(random.randint(1, 9))
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


class TowerDrainHealer(RoleBase):
    def run(self):
        target = self.target_mind.get_new_target(self, target_single_flag, flags.TD_H_H_STOP)
        if not target:
            if len(flags.find_flags(self.home, flags.RAID_OVER)):
                self.recycle_me()
            else:
                self.log("TowerDrainHealer has no target!")
                self.go_to_depot()
            return
        if not self.creep.pos.isEqualTo(target.pos):
            self.move_to(target)

        autoactions.instinct_do_heal(self)

    def _calculate_time_to_replace(self):
        target = self.target_mind.get_new_target(self, target_single_flag, flags.TD_H_H_STOP)
        if not target:
            return -1
        target_pos = target.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # TODO: nice module to use pathfinder without exit flags that we can use for this.
        path_len = len(PathFinder.search(spawn_pos, {"pos": target_pos, "range": 1}, {
            "roomCallback": autoactions.simple_cost_matrix
        }).path)
        time = path_len * 2 + RoleBase._calculate_time_to_replace(self)
        return time


class TowerDrainer(RoleBase):
    def run(self):
        if self.memory.goading and self.creep.hits < self.creep.hitsMax / 2:
            self.memory.goading = False
            self.target_mind.untarget_all(self)
        if not self.memory.goading and self.creep.hits >= self.creep.hitsMax:
            self.memory.goading = True
            self.target_mind.untarget_all(self)

        if self.memory.goading:
            target = self.target_mind.get_new_target(self, target_single_flag, flags.TD_D_GOAD)
            if not target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.log("TowerDrainer has no target!")
                    self.recycle_me()
                return
            if not self.creep.pos.isEqualTo(target.pos):
                if self.creep.pos.isNearTo(target.pos):
                    self.creep.move(pathdef.get_direction(target.pos.x - self.creep.pos.x,
                                                          target.pos.y - self.creep.pos.y))
                else:
                    self.creep.moveTo(target.pos)
        else:
            target = self.target_mind.get_new_target(self, target_single_flag, flags.TD_H_D_STOP)
            if not target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.log("TowerDrainer has no healer target!")
                    self.go_to_depot()
                return
            room = context.hive().get_room(target.pos.roomName)
            if room and _.find(room.find(FIND_MY_CREEPS), lambda c: c.memory.role == role_td_healer):
                if not self.creep.pos.isEqualTo(target.pos):
                    self.creep.moveTo(target)
            else:
                self.go_to_depot()

        autoactions.instinct_do_attack(self)

    def _calculate_time_to_replace(self):
        target = self.target_mind.get_new_target(self, target_single_flag, flags.TD_D_GOAD)
        if not target:
            return -1
        target_pos = target.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # TODO: nice module to use pathfinder without exit flags that we can use for this.
        path_len = len(PathFinder.search(spawn_pos, {"pos": target_pos, "range": 1}, {
            "roomCallback": autoactions.simple_cost_matrix
        }).path)
        time = path_len * 2 + RoleBase._calculate_time_to_replace(self)
        return time


class Dismantler(RoleBase):
    def run(self):
        if self.memory.dismantling and self.creep.hits < self.creep.hitsMax / 2:
            self.memory.dismantling = False
            self.target_mind.untarget_all(self)
        if not self.memory.dismantling and self.creep.hits >= self.creep.hitsMax:
            self.memory.dismantling = True
            self.target_mind.untarget_all(self)

        if self.memory.dismantling:
            target = self.target_mind.get_new_target(self, target_single_flag, flags.ATTACK_DISMANTLE)
            if not target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.log("Dismantler has no target!")
                    self.go_to_depot()
                return
            if self.creep.pos.isNearTo(target.pos):
                struct = self.room.room.lookForAt(LOOK_STRUCTURES, target.pos)[0]
                if struct:
                    self.creep.dismantle(struct)
            else:
                result = self.creep.moveTo(target)
                if result != OK and result != ERR_TIRED:
                    self.log("Unknown result from creep.moveByPath(): {}".format(result))
        else:
            target = self.target_mind.get_new_target(self, target_single_flag, flags.TD_H_D_STOP)
            if not target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.log("Dismantler has no healer target!")
                    self.go_to_depot()
                return
            room = context.hive().get_room(target.pos.roomName)
            if room and _.find(room.find(FIND_MY_CREEPS), lambda c: c.memory.role == role_td_healer):
                if not self.creep.pos.isEqualTo(target.pos):
                    self.creep.moveTo(target)
            else:
                self.go_to_depot()

    def _calculate_time_to_replace(self):
        target = self.target_mind.get_new_target(self, target_single_flag, flags.ATTACK_DISMANTLE)
        if not target:
            return -1
        target_pos = target.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # TODO: nice module to use pathfinder without exit flags that we can use for this.
        path_len = len(PathFinder.search(spawn_pos, {"pos": target_pos, "range": 1}, {
            "roomCallback": autoactions.simple_cost_matrix
        }).path)
        time = path_len * 2 + RoleBase._calculate_time_to_replace(self)
        return time
