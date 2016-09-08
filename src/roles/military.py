import math

import random

import autoactions
import flags
from constants import target_single_flag, role_td_healer
from control import pathdef
from role_base import RoleBase
from tools import profiling
from utilities import movement
from utilities.movement import center_pos, room_xy_to_name, parse_room_to_xy
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def delete_target(target_id):
    index = _.findIndex(Memory.hostiles, lambda t: t[0] == target_id)
    if index >= 0:
        Memory.hostiles.splice(index, 1)
    del Memory.hostile_last_rooms[target_id]
    del Memory.hostile_last_positions[target_id]


class RoleDefender(RoleBase):
    def should_pickup(self, resource_type=None):
        return False

    def run(self):
        target_id = self.memory.attack_target
        if not target_id:
            best_id = None
            closest_distance = Infinity
            for target_id, room_name, pos, target_owner in Memory.hostiles:
                distance = movement.distance_squared_room_pos(self.creep.pos, pos)
                if distance < closest_distance:
                    best_id = target_id
                    closest_distance = distance
            if best_id:
                target_id = best_id
                self.memory.attack_target = best_id
            else:
                if Game.cpu.bucket < 6500:
                    self.creep.suicide()
                else:
                    self.creep.move(random.randint(1, 9))
                return False

        hostile_room = Memory.hostile_last_rooms[target_id]
        if self.pos.roomName != hostile_room:
            if hostile_room:
                self.creep.moveTo(__new__(RoomPosition(25, 25, hostile_room)))
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

    def _calculate_time_to_replace(self):
        return 0  # never live-replace a defender.


profiling.profile_whitelist(RoleDefender, ["run"])


class MilitaryBase(RoleBase):
    def _find_nearest_junctions(self):

        room_xy = parse_room_to_xy(self.pos.roomName)
        if room_xy is None:  # we're in sim
            return []
        x, y = room_xy

        if x % 10 == 0:
            if y % 10 == 0:
                return [center_pos(room_xy_to_name(x, y))]
            else:
                return [
                    center_pos(room_xy_to_name(x, math.floor(y / 10) * 10)),
                    center_pos(room_xy_to_name(x, math.ceil(y / 10) * 10)),
                ]
        elif y % 10 == 0:
            return [
                center_pos(room_xy_to_name(math.floor(x / 10) * 10, y)),
                center_pos(room_xy_to_name(math.ceil(x / 10) * 10, y)),
            ]
        else:
            return [
                center_pos(room_xy_to_name(math.floor(x / 10) * 10, math.floor(y / 10) * 10)),
                center_pos(room_xy_to_name(math.floor(x / 10) * 10, math.ceil(y / 10) * 10)),
                center_pos(room_xy_to_name(math.ceil(x / 10) * 10, math.floor(y / 10) * 10)),
                center_pos(room_xy_to_name(math.ceil(x / 10) * 10, math.ceil(y / 10) * 10)),
            ]

    def find_midpoint(self, origin, target):
        # This method calculates the angle at each junction made by drawing lines from the origin and destination to
        # that junction. pi*2/5 is just under 90 degrees, and is our cutoff point for deciding to path through an
        # intersection.
        biggest_midpoint_angle = math.pi * 2 / 5
        best_midpoint = None
        for junction in self._find_nearest_junctions():
            # a^2 = b^2 + c^2  - 2bc * cos(A)
            # cos(A) = (b^2 + c^2 - a^2) / (2bc)
            oj_distance_squared = movement.distance_squared_room_pos(origin, junction)
            jt_distance_squared = movement.distance_squared_room_pos(junction, target)
            ot_distance_squared = movement.distance_squared_room_pos(origin, target)
            junction_angle = math.acos(
                (oj_distance_squared + jt_distance_squared - ot_distance_squared)
                / (2 * math.sqrt(oj_distance_squared) * math.sqrt(jt_distance_squared))
            )
            if junction_angle > biggest_midpoint_angle:
                biggest_midpoint_angle = junction_angle
                best_midpoint = junction
        # if best_midpoint is not None:
        #     self.log("WARNING: Found midpoint {} for path from {} to {}".format(
        #         best_midpoint, origin, target
        #     ))
        return best_midpoint

    # TODO: A lot of this is copied directly (and shared with) transport.TransportPickup
    def follow_military_path(self, origin, target, opts=None):
        if opts and "to_home" in opts:
            to_home = opts["to_home"]
        else:
            to_home = False
        if origin.pos: origin = origin.pos
        if target.pos: target = target.pos
        if self.creep.fatigue > 0:
            return
        if self.pos.getRangeTo(target) < 10 or self.pos.roomName == target.roomName:
            self.move_to(target)
            return
        path_opts = {
            'current_room': self.pos.roomName,
        }
        if opts:
            path_opts = _.create(path_opts, opts)
        # TODO: this is all stupid, PathFinder is stupid for multiple rooms!
        if movement.distance_squared_room_pos(origin, target) > math.pow(200, 2):
            path_opts.max_ops = 30000
            path_opts.max_rooms = 30
            path_opts.use_roads = False
            # TODO: handle this better (this is for not having multiple super-duper-long cached paths)
            if to_home:
                intermediate = __new__(RoomPosition(25, 25, origin.roomName))
                origin = intermediate
            else:
                intermediate = __new__(RoomPosition(25, 25, target.roomName))
                if self.pos.roomName != intermediate.roomName:
                    target = intermediate
                    path_opts.range = 10
                else:
                    # If we're this far away, let's just get to the room using a cached path and then do
                    # basic pathfinding to get to our actual target.
                    self.move_to(target)
                    return
            origin_midpoint = self.find_midpoint(self, origin)
            if origin_midpoint is not None:
                origin = origin_midpoint
            dest_midpoint = self.find_midpoint(origin, target)
            if dest_midpoint is not None:
                if self.pos.roomName == dest_midpoint.roomName:
                    origin = dest_midpoint
                else:
                    target = dest_midpoint
                    path_opts.range = 10

        path = self.room.honey.find_path(origin, target, path_opts)
        # TODO: manually check the next position, and if it's a creep check what direction it's going
        result = self.creep.moveByPath(path)
        if result == ERR_NOT_FOUND:
            if not self.memory.next_ppos:
                all_positions = self.room.honey.list_of_room_positions_in_path(origin, target, path_opts)
                closest = None
                closest_distance = Infinity
                for pos in all_positions:
                    distance = movement.distance_squared_room_pos(self.pos, pos)
                    if distance < closest_distance:
                        closest_distance = distance
                        closest = pos
                if closest:
                    self.memory.next_ppos = closest
                else:
                    self.log("WARNING: Couldn't find closest position on path from {} to {} near {}!"
                             "\nMoving manually... (all pos: {})"
                             .format(origin, target, self.pos, all_positions))
                    self.memory.next_ppos = target
            mtarget = self.memory.next_ppos
            new_target = __new__(RoomPosition(mtarget.x, mtarget.y, mtarget.roomName))
            self.creep.moveTo(new_target)
            if self.pos.isEqualTo(new_target):
                del self.memory.next_ppos
            if not self.memory.off_path_for:
                self.memory.off_path_for = 1
            else:
                self.memory.off_path_for += 1
                if self.memory.off_path_for > 10:
                    self.log("Lost the path from {} to {}! Pos: {}. Retargeting to: {}".format(
                        origin, target, self.pos, new_target))
        elif result != OK:
            self.log("Unknown result from follow_military_path: {}".format(result))
        else:
            # String.fromCodePoint(pos.x | (pos.y << 6));
            # var val = str.charCodeAt(i);
            # var x = (val & 0x3F);
            # var y = ((val >> 6) & 0x3F);
            # return {x: x, y: y};
            if self.memory.off_path_for:
                del self.memory.next_ppos
                del self.memory.off_path_for
        serialized_pos = self.pos.x | (self.pos.y << 6)
        if self.memory.last_pos == serialized_pos:
            self.log("Standstill!")
            if self.memory.standstill_for:
                self.memory.standstill_for += 1
            else:
                self.memory.standstill_for = 1
            if self.memory.standstill_for == 5:
                del self.memory.next_ppos
            if self.memory.standstill_for > 10:
                del self.memory.last_position
                del self.memory.standstill_for
                del self.memory.next_ppos
                self.room.honey.clear_cached_path(origin, target, path_opts)
                self.move_to(target)
        else:
            self.memory.last_pos = serialized_pos
            del self.memory.standstill_for

    def get_military_path(self, spawn, target, opts=None):
        if opts:
            path_opts = opts
        else:
            path_opts = {}
        if movement.distance_squared_room_pos(spawn, target) > math.pow(200, 2):
            # TODO: handle this better (this is for not having multiple super-duper-long cached paths)
            intermediate = __new__(RoomPosition(25, 25, target.roomName))
            target = intermediate
            path_opts.max_ops = 30000
            path_opts.max_rooms = 30
            path_opts.use_roads = False
        else:
            path_opts.max_ops = 9000
            path_opts.max_rooms = 15

        return self.room.honey.find_path(spawn, target, path_opts)


class Scout(MilitaryBase):
    def run(self):
        destination = self.targets.get_new_target(self, target_single_flag, flags.SCOUT)
        if not destination:
            self.log("ERROR: Scout does not have destination set!")
            return
        if self.pos.isNearTo(destination):
            self.basic_move_to(destination)
        else:
            self.follow_military_path(self.home.spawn, destination, {"ignore_swamp": True})


class TowerDrainHealer(RoleBase, MilitaryBase):
    def run(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.TD_H_H_STOP)
        if not target:
            if len(flags.find_flags(self.home, flags.RAID_OVER)):
                self.recycle_me()
            else:
                self.log("TowerDrainHealer has no target!")
                self.go_to_depot()
            return
        if not self.creep.pos.isEqualTo(target.pos):
            self.follow_military_path(self.home.spawn, target)

        autoactions.instinct_do_heal(self)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.TD_H_H_STOP)
        if not target:
            return -1
        path = self.get_military_path(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) / 2:
            path_len = len(path)
        else:
            path_len = len(path) * 2
        return path_len + _.size(self.creep.body) * 3 + 10


class TowerDrainer(RoleBase, MilitaryBase):
    def should_pickup(self, resource_type=None):
        return False

    def run(self):
        if self.memory.goading and self.creep.hits < self.creep.hitsMax / 2:
            self.memory.goading = False
            self.targets.untarget_all(self)
        if not self.memory.goading and self.creep.hits >= self.creep.hitsMax:
            self.memory.goading = True
            self.targets.untarget_all(self)

        if self.memory.goading:
            target = self.targets.get_new_target(self, target_single_flag, flags.TD_D_GOAD)
            if not target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.log("TowerDrainer has no target!")
                    self.recycle_me()
                return
            if not self.creep.pos.isEqualTo(target.pos):
                if self.creep.pos.isNearTo(target.pos):
                    direction = pathdef.get_direction(target.pos.x - self.creep.pos.x,
                                                      target.pos.y - self.creep.pos.y)
                    if direction is None:
                        self.log("Unknown result from pathdef.get_direction({} - {}, {} - {})".format(
                            target.pos.x, self.creep.pos.x, target.pos.y, self.creep.pos.y
                        ))
                    self.creep.move(direction)
                else:
                    self.follow_military_path(self.home.spawn, target)
        else:
            target = self.targets.get_new_target(self, target_single_flag, flags.TD_H_D_STOP)
            if not target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.log("TowerDrainer has no healer target!")
                    self.go_to_depot()
                return
            if self.pos.roomName != target.pos.roomName:
                self.moveTo(target)
            else:
                room = self.hive.get_room(target.pos.roomName)
                if room and _.find(room.find(FIND_MY_CREEPS), lambda c: c.memory.role == role_td_healer):
                    if not self.creep.pos.isEqualTo(target.pos):
                        self.creep.moveTo(target)
                else:
                    self.go_to_depot()

        autoactions.instinct_do_attack(self)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.TD_D_GOAD)
        if not target:
            return -1
        path = self.get_military_path(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) / 2:
            path_len = len(path)
        else:
            path_len = len(path) * 2
        return path_len + _.size(self.creep.body) * 3 + 10


class Dismantler(MilitaryBase):
    def run(self):
        if self.memory.dismantling and self.creep.hits < self.creep.hitsMax / 2:
            self.memory.dismantling = False
            self.targets.untarget_all(self)
        if not self.memory.dismantling and self.creep.hits >= self.creep.hitsMax:
            self.memory.dismantling = True
            self.targets.untarget_all(self)

        if self.memory.dismantling:
            target = self.targets.get_new_target(self, target_single_flag, flags.ATTACK_DISMANTLE)
            if not target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.log("Dismantler has no target!")
                    self.go_to_depot()
                return
            if self.creep.pos.isNearTo(target.pos):
                struct = self.room.find_at(FIND_STRUCTURES, target.pos)[0]
                if struct:
                    self.creep.dismantle(struct)
                else:
                    target.remove()
            else:
                if self.pos.roomName == target.pos.roomName:
                    result = self.creep.moveTo(target, {"ignoreDestructibleStructures": True})
                    if result != OK and result != ERR_TIRED:
                        self.log("Unknown result from creep.moveTo({}): {}".format(target, result))
                else:
                    self.follow_military_path(self.home.spawn, target)
        else:
            target = self.targets.get_new_target(self, target_single_flag, flags.TD_H_D_STOP)
            if not target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.log("Dismantler has no healer target!")
                    self.go_to_depot()
                return
            if self.pos.roomName != target.pos.roomName:
                self.creep.moveTo(target)
            else:
                room = self.hive.get_room(target.pos.roomName)
                if room and _.find(room.find(FIND_MY_CREEPS), lambda c: c.memory.role == role_td_healer):
                    if not self.creep.pos.isEqualTo(target.pos):
                        self.creep.moveTo(target)
                        self.follow_military_path(self.home.spawn, target)
                else:
                    self.go_to_depot()

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.ATTACK_DISMANTLE)
        if not target:
            return -1
        path = self.get_military_path(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) / 2:
            path_len = len(path)
        else:
            path_len = len(path) * 2
        return path_len + _.size(self.creep.body) * 3 + 10
