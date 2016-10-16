import math

import autoactions
import flags
from constants import target_single_flag, role_td_healer, target_single_flag2
from role_base import RoleBase
from utilities import movement
from utilities.movement import center_pos, room_xy_to_name, parse_room_to_xy
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


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

    def recalc_military_path(self, origin, target, opts=None):
        # TODO: separate the majority of the code this shares with follow_military_path into a new module
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
        self.hive.honey.clear_cached_path(origin, target, path_opts)

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
            pass
            # origin_midpoint = self.find_midpoint(self, origin)
            # if origin_midpoint is not None:
            #     origin = origin_midpoint
            # dest_midpoint = self.find_midpoint(origin, target)
            # if dest_midpoint is not None:
            #     if self.pos.roomName == dest_midpoint.roomName:
            #         origin = dest_midpoint
            #     else:
            #         target = dest_midpoint
            #         path_opts.range = 10

        path = self.hive.honey.find_path(origin, target, path_opts)
        # TODO: manually check the next position, and if it's a creep check what direction it's going
        result = self.creep.moveByPath(path)
        if result == ERR_NOT_FOUND:
            if not self.memory.next_ppos:
                all_positions = self.hive.honey.list_of_room_positions_in_path(origin, target, path_opts)
                closest = None
                closest_distance = Infinity
                for pos in all_positions:
                    distance = movement.chebyshev_distance_room_pos(self.pos, pos)
                    if distance < closest_distance:
                        closest_distance = distance
                        closest = pos
                if closest:
                    self.memory.next_ppos = closest
                    if closest.isEqualTo(self.pos):
                        self.log("WARNING: ERR_NOT_FOUND when actually still on military path! Path retrieved:\n{}"
                                 "\nPos: {}.".format(path, self.pos))
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
                self.memory.lost_path_at = self.pos
            else:
                if not self.memory.lost_path_at:
                    self.memory.lost_path_at = self.pos
                self.memory.off_path_for += 1
                if self.memory.off_path_for > 10:
                    self.log("Lost the path from {} to {}! Pos: {}. Retargeting to: {}".format(
                        origin, target, self.pos, new_target))
                    if movement.chebyshev_distance_room_pos(self.memory.lost_path_at, self.pos) < 5 \
                            and not self.pos.isEqualTo(new_target) \
                            and not self.pos.isEqualTo(movement.get_entrance_for_exit_pos(new_target)):
                        self.hive.honey.clear_cached_path(origin, target, path_opts)
                        del self.memory.off_path_for
                        del self.memory.lost_path_at
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
                del self.memory.lost_path_at
        serialized_pos = self.pos.x | (self.pos.y << 6)
        if self.memory.last_pos == serialized_pos:
            self.log("Standstill!")
            if self.memory.standstill_for:
                self.memory.standstill_for += 1
            else:
                self.memory.standstill_for = 1
            if self.memory.standstill_for == 5:
                del self.memory.next_ppos
                found_mine = False
                for pos in self.hive.honey.find_path(origin, target, path_opts):
                    if pos.x == self.pos.x and pos.y == self.pos.y:
                        found_mine = True
                    elif found_mine:
                        if movement.is_block_clear(self.room, pos.x, pos.y):
                            self.memory.next_ppos = {"x": pos.x, "y": pos.y, "roomName": self.pos.roomName}
                            self.creep.moveTo(__new__(RoomPosition(pos.x, pos.y, self.pos.roomName)))
                            break
            if self.memory.standstill_for > 10:
                del self.memory.last_position
                del self.memory.standstill_for
                del self.memory.next_ppos
                self.hive.honey.clear_cached_path(origin, target, path_opts)
                self.move_to(target)
        else:
            self.memory.last_pos = serialized_pos
            del self.memory.standstill_for

    def get_military_path_length(self, spawn, target, opts=None):
        if spawn.pos:
            spawn = spawn.pos
        if target.pos:
            target = target.pos
        if opts:
            path_opts = opts
        else:
            path_opts = {}
        # if movement.distance_squared_room_pos(spawn, target) > math.pow(200, 2):
        #     # TODO: handle this better (this is for not having multiple super-duper-long cached paths)
        #     intermediate = __new__(RoomPosition(25, 25, target.roomName))
        #     path_opts.max_ops = 30000
        #     path_opts.max_rooms = 30
        #     path_opts.use_roads = False
        #     path1 = self.hive.honey.find_path(spawn, intermediate, path_opts)
        #     path2 = self.hive.honey.find_path(intermediate, target, path_opts)
        #     return len(path1) + 20 + len(path2)
        # else:
        path_opts.max_ops = 9000
        path_opts.max_rooms = 15
        path1 = self.hive.honey.find_path(spawn, target, path_opts)
        return len(path1)


class TowerDrainHealer(MilitaryBase):
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
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


class TowerDrainer(MilitaryBase):
    def should_pickup(self, resource_type=None):
        return False

    def run(self):
        if 'goading' not in self.memory:
            self.memory.goading = False
        if self.memory.goading and self.creep.hits < self.creep.hitsMax / 2:
            self.memory.goading = False
            self.targets.untarget_all(self)
        if not self.memory.goading and self.creep.hits >= self.creep.hitsMax:
            self.memory.goading = True
            self.targets.untarget_all(self)
        goad_target = self.targets.get_new_target(self, target_single_flag, flags.TD_D_GOAD)
        if not goad_target:
            if len(flags.find_flags(self.home, flags.RAID_OVER)):
                self.recycle_me()
            else:
                self.log("TowerDrainer has no target!")
                self.recycle_me()
            return
        if self.memory.goading:
            if self.creep.pos.isEqualTo(goad_target.pos):
                pass
            elif movement.chebyshev_distance_room_pos(self.pos, goad_target) < 50:
                self.creep.moveTo(goad_target, {
                    "costCallback": lambda room_name, matrix: self.hive.honey.set_max_avoid(
                        room_name, matrix, {'max_avoid': [goad_target.pos.roomName]}
                    )
                })
            else:
                self.follow_military_path(self.home.spawn, goad_target, {'avoid_rooms': [goad_target.pos.roomName]})
        else:
            heal_target = self.targets.get_new_target(self, target_single_flag2, flags.TD_H_D_STOP)
            if not heal_target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    self.recycle_me()
                else:
                    self.go_to_depot()
                return
            if self.creep.pos.isEqualTo(heal_target.pos):
                pass
            elif movement.chebyshev_distance_room_pos(self.pos, heal_target) < 50:
                self.creep.moveTo(heal_target, {  # TODO: make a military moveTo method like this
                    "costCallback": lambda room_name, matrix: self.hive.honey.set_max_avoid(
                        room_name, matrix, {'max_avoid': [goad_target.pos.roomName]}
                    )
                })
            else:
                self.follow_military_path(self.home.spawn, heal_target, {'avoid_rooms': [goad_target.pos.roomName]})

        autoactions.instinct_do_attack(self)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.TD_D_GOAD)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target, {'avoid_rooms': [target.pos.roomName]})
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
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
                    if self.creep.ticksToLive < 300:
                        self.creep.suicide()
                    else:
                        self.recycle_me()
                else:
                    self.log("Dismantler has no target!")
                    self.go_to_depot()
                return
            if self.creep.pos.isNearTo(target.pos):
                struct = self.room.look_at(LOOK_STRUCTURES, target.pos)[0]
                if struct:
                    self.creep.dismantle(struct)
                else:
                    site = self.room.look_at(LOOK_CONSTRUCTION_SITES, target.pos)[0]
                    if site:
                        self.basic_move_to(site)
                    elif target.memory.dismantle_all:
                        new_target_site = self.room.find_closest_by_range(FIND_HOSTILE_CONSTRUCTION_SITES, target.pos)
                        new_structure = self.room.find_closest_by_range(
                            FIND_STRUCTURES, target.pos, lambda s: s.structureType != STRUCTURE_ROAD
                                                                   and s.structureType != STRUCTURE_CONTAINER
                                                                   and s.structureType != STRUCTURE_CONTROLLER
                                                                   and s.structureType != STRUCTURE_EXTRACTOR
                                                                   and s.structureType != STRUCTURE_STORAGE
                                                                   and s.structureType != STRUCTURE_TERMINAL)
                        if new_structure and (not new_target_site or
                                                      movement.distance_squared_room_pos(target, new_target_site)
                                                      > movement.distance_squared_room_pos(target, new_structure)):
                            new_pos = new_structure.pos
                        elif new_target_site:
                            new_pos = new_target_site.pos
                        else:
                            target.remove()
                            return
                        target.setPosition(new_pos)
                        self.move_to(new_pos)
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
                    if self.creep.ticksToLive < 300:
                        self.creep.suicide()
                    else:
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
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


class PowerAttack(MilitaryBase):
    def run(self):
        if not self.memory.healing and self.creep.hits < \
                max(ATTACK_POWER * self.creep.getActiveBodyparts(ATTACK), self.creep.hitsMax / 2):
            self.memory.healing = True
            self.targets.untarget_all(self)
        if self.memory.healing and self.creep.hits >= self.creep.hitsMax:
            self.memory.healing = False
            self.targets.untarget_all(self)

        target = self.targets.get_new_target(self, target_single_flag, flags.ATTACK_POWER_BANK)
        if not target:
            if len(flags.find_flags(self.home, flags.RAID_OVER)):
                if self.creep.ticksToLive < 300:
                    self.creep.suicide()
                else:
                    self.recycle_me()
            else:
                self.log("PowerAttack has no target!")
                self.go_to_depot()
            return
        heal_target = self.targets.get_new_target(self, target_single_flag2, flags.TD_H_D_STOP, target.pos)
        if self.memory.healing:
            if not heal_target:
                if len(flags.find_flags(self.home, flags.RAID_OVER)):
                    if self.creep.ticksToLive < 300:
                        self.creep.suicide()
                    else:
                        self.recycle_me()
                else:
                    self.log("PowerAttack has no healer target!")
                    self.go_to_depot()
                return
            if self.pos.roomName != heal_target.pos.roomName:
                self.creep.moveTo(heal_target)
            else:
                room = self.hive.get_room(heal_target.pos.roomName)
                if room and _.find(room.find(FIND_MY_CREEPS), lambda c: c.memory.role == role_td_healer):
                    if not self.creep.pos.isEqualTo(heal_target.pos):
                        self.creep.moveTo(heal_target)
                        self.follow_military_path(self.home.spawn, heal_target)
                else:
                    self.go_to_depot()
        else:
            if self.creep.pos.isNearTo(target.pos):
                struct = self.room.look_at(LOOK_STRUCTURES, target.pos)[0]
                if struct:
                    self.creep.attack(struct)
                else:
                    for flag in flags.find_flags(self.room, flags.TD_H_H_STOP):
                        flag.remove()
                    for flag in flags.find_flags(self.room, flags.TD_H_D_STOP):
                        flag.remove()
                    target.remove()
            if not self.creep.pos.isEqualTo(heal_target.pos):
                if self.pos.roomName == target.pos.roomName:
                    result = self.creep.moveTo(heal_target)
                    if result != OK and result != ERR_TIRED:
                        self.log("Unknown result from creep.moveTo({}): {}".format(target, result))
                else:
                    self.follow_military_path(self.home.spawn, heal_target)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.ATTACK_POWER_BANK)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


# TODO: Change the speech on this to something unique.
class PowerCleanup(MilitaryBase):
    def should_pickup(self, resource_type=None):
        return resource_type is None or resource_type == RESOURCE_POWER

    def run(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.REAP_POWER_BANK)
        if not target:
            if len(flags.find_flags(self.home, flags.RAID_OVER)) or self.creep.ticksToLive < 100:
                self.recycle_me()
            else:
                self.log("PowerAttack has no target!")
                self.go_to_depot()
            return
        if self.memory.filling and self.carry_sum() >= self.creep.carryCapacity:
            self.memory.filling = False

        if not self.memory.filling and self.carry_sum() <= 0:
            self.memory.filling = True

        storage = self.home.room.storage
        if self.memory.filling:
            if self.pos.roomName != target.pos.roomName:
                self.follow_military_path(self.home.spawn, target)
                return

            # TODO: Make some cached memory map of all hostile creeps, and use it to avoid.
            resources = self.room.find(FIND_DROPPED_RESOURCES)
            if len(resources):
                closest = None
                closest_distance = Infinity
                for resource in resources:
                    if len(self.room.find_in_range(FIND_HOSTILE_CREEPS, 3, resource.pos)) == 0:

                        if self.memory.last_energy_target:
                            compressed_pos = resource.pos.x | (resource.pos.y << 6)
                            if compressed_pos == self.memory.last_energy_target:
                                closest = resource
                                break
                        if (resource.amount > 50 or
                                    len(self.room.find_in_range(FIND_SOURCES, 1, resource.pos)) == 0):

                            # we've confirmed now that this is a valid target! congrats.
                            distance = movement.distance_squared_room_pos(self.creep.pos, resource.pos)
                            if distance < closest_distance:
                                closest = resource
                                closest_distance = distance
                pile = closest
            else:
                pile = None

            if not pile:
                del self.memory.last_energy_target
                if not _.find(self.room.find(FIND_STRUCTURES), {"structureType": STRUCTURE_POWER_BANK}):
                    if self.carry_sum() >= 0:
                        self.memory.filling = False
                    else:
                        target.remove()
                else:
                    if self.pos.inRangeTo(target, 7):
                        self.move_around(target)
                    else:
                        self.move_to(target)
                return

            self.memory.last_energy_target = pile.pos.x | (pile.pos.y << 6)

            if not self.creep.pos.isNearTo(pile.pos):
                self.move_to(pile)
                return False

            result = self.creep.pickup(pile)

            if result == OK:
                pass
            elif result == ERR_FULL:
                self.memory.filling = False
                return True
            else:
                self.log("Unknown result from cleanup-creep.pickup({}): {}", pile, result)
        else:
            if not storage:
                self.go_to_depot()
                return

            if self.creep.pos.roomName != storage.pos.roomName:
                self.follow_military_path(target, storage)
                return False

            target = storage
            if not self.creep.pos.isNearTo(target.pos):
                self.move_to(target)
                return False

            resource_type = _.find(Object.keys(self.creep.carry), lambda r: self.creep.carry[r] > 0)
            result = self.creep.transfer(target, resource_type)
            if result == OK:
                pass
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.filling = True
                return True
            elif result == ERR_FULL:
                if target == storage:
                    self.log("Storage in room {} full!", storage.room.name)
            else:
                self.log("Unknown result from cleanup-creep.transfer({}, {}): {}", target, resource_type, result)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.REAP_POWER_BANK)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10
