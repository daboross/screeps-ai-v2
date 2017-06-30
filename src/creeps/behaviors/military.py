import math

from creeps.base import RoleBase
from empire import honey
from jstools.screeps import *
from utilities import movement
from utilities.movement import center_pos, chebyshev_distance_room_pos, distance_squared_room_pos, find_an_open_space, \
    get_entrance_for_exit_pos, is_block_clear, parse_room_to_xy, room_xy_to_name

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def _find_nearest_junctions(pos):
    """
    :type pos: RoomPosition
    """
    if pos.pos:
        pos = pos.pos
    x, y = parse_room_to_xy(pos.roomName)
    if x == 0 and y == 0 and pos.roomName == 'sim':
        return []  # we're in sim

    rrx = (-x - 1 if x < 0 else x) % 10
    rry = (-y - 1 if y < 0 else y) % 10

    def floor_thing(coord):
        if coord < 0:
            return math.floor((coord + 1) / 10) * 10 - 1
        else:
            return math.floor(coord / 10) * 10

    def ceil_thing(coord):
        if coord < 0:
            return math.ceil((coord + 1) / 10) * 10 - 1
        else:
            return math.ceil(coord / 10) * 10

    if rrx == 0:
        if rry == 0:
            return [center_pos(room_xy_to_name(x, y))]
        else:
            return [
                center_pos(room_xy_to_name(x, floor_thing(y))),
                center_pos(room_xy_to_name(x, ceil_thing(y))),
            ]
    elif rry == 0:
        return [
            center_pos(room_xy_to_name(floor_thing(x), y)),
            center_pos(room_xy_to_name(ceil_thing(x), y)),
        ]
    else:
        return [
            center_pos(room_xy_to_name(floor_thing(x), floor_thing(y))),
            center_pos(room_xy_to_name(floor_thing(x), ceil_thing(y))),
            center_pos(room_xy_to_name(ceil_thing(x), floor_thing(y))),
            center_pos(room_xy_to_name(ceil_thing(x), ceil_thing(y))),
        ]


def find_midpoint(pos, origin, target):
    # This method calculates the angle at each junction made by drawing lines from the origin and destination to
    # that junction. pi*2/5 is just under 90 degrees, and is our cutoff point for deciding to path through an
    # intersection.
    if pos.pos:
        pos = pos.pos
    biggest_midpoint_angle = math.pi * 2 / 5
    best_midpoint = None
    for junction in _find_nearest_junctions(pos):
        # a^2 = b^2 + c^2  - 2bc * cos(A)
        # cos(A) = (b^2 + c^2 - a^2) / (2bc)
        oj_distance_squared = distance_squared_room_pos(origin, junction)
        jt_distance_squared = distance_squared_room_pos(junction, target)
        ot_distance_squared = distance_squared_room_pos(origin, target)
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


def is_path_portal(origin, target):
    if 'reroute' in Game.flags and 'reroute_destination' in Game.flags:
        reroute_start = Game.flags['reroute']
        reroute_destination = Game.flags['reroute_destination']
        if chebyshev_distance_room_pos(origin, reroute_start) \
                + chebyshev_distance_room_pos(reroute_destination, target) \
                < chebyshev_distance_room_pos(origin, target):
            return True
    return False


class MilitaryBase(RoleBase):
    def recalc_military_path(self, origin, target, opts=None):
        # TODO: separate the majority of the code this shares with follow_military_path into a new module
        if opts and "to_home" in opts:
            to_home = opts["to_home"]
        else:
            to_home = False
        if not origin:
            origin = movement.find_an_open_space(self.memory.home)
        if origin.pos:
            origin = origin.pos
        if target.pos:
            target = target.pos
        if self.creep.fatigue > 0:
            return
        if self.pos.getRangeTo(target) < 10 or self.pos.roomName == target.roomName:
            self.move_to(target)
            return
        path_opts = {
            'current_room': self.pos.roomName,
        }
        if opts:
            path_opts = _.merge(path_opts, opts)
        # TODO: this is all stupid, PathFinder is stupid for multiple rooms!
        if chebyshev_distance_room_pos(origin, target) > 900 \
                and not is_path_portal(origin, target):
            path_opts.max_ops = chebyshev_distance_room_pos(origin, target) * 150
            path_opts.max_rooms = math.ceil(chebyshev_distance_room_pos(origin, target) / 5)
            path_opts.use_roads = False
            # TODO: handle this better (this is for not having multiple super-duper-long cached paths)
            if to_home:
                intermediate = find_an_open_space(origin.roomName)
                origin = intermediate
            else:
                intermediate = center_pos(target.roomName)
                if self.pos.roomName != intermediate.roomName:
                    target = intermediate
                    path_opts.range = 10
                else:
                    # If we're this far away, let's just get to the room using a cached path and then do
                    # basic pathfinding to get to our actual target.
                    self.move_to(target)
                    return
            if not is_path_portal(origin, target):
                origin_midpoint = find_midpoint(self, self, origin)
                if origin_midpoint is not None:
                    origin = origin_midpoint
                dest_midpoint = find_midpoint(self, origin, target)
                if dest_midpoint is not None:
                    if self.pos.roomName == dest_midpoint.roomName:
                        origin = dest_midpoint
                    else:
                        target = dest_midpoint
                        path_opts.range = 10
        honey.clear_cached_path(origin, target, path_opts)

    # TODO: A lot of this is copied directly (and shared with) transport.TransportPickup
    def follow_military_path(self, origin, target, opts=None):
        if opts and "to_home" in opts:
            to_home = opts["to_home"]
        else:
            to_home = False
        if not origin:
            origin = movement.find_an_open_space(self.memory.home)
        if origin.pos:
            origin = origin.pos
        if target.pos:
            target = target.pos
        if self.creep.fatigue > 0:
            return
        if self.pos.getRangeTo(target) < 10 or self.pos.roomName == target.roomName:
            self.move_to(target)
            return
        path_opts = {
            'current_room': self.pos.roomName,
        }
        if opts:
            path_opts = _.merge(path_opts, opts)
        # TODO: this is all stupid, PathFinder is stupid for multiple rooms!
        if chebyshev_distance_room_pos(origin, target) > 900 \
                and not is_path_portal(origin, target):
            path_opts.max_ops = chebyshev_distance_room_pos(origin, target) * 150
            path_opts.max_rooms = math.ceil(chebyshev_distance_room_pos(origin, target) / 5)

            # TODO: handle this better (this is for not having multiple super-duper-long cached paths)
            if to_home:
                intermediate = find_an_open_space(origin.roomName)
                origin = intermediate
            else:
                intermediate = center_pos(target.roomName)
                if self.pos.roomName != intermediate.roomName:
                    target = intermediate
                    path_opts.range = max(path_opts.range or 0, 10)
                else:
                    # If we're this far away, let's just get to the room using a cached path and then do
                    # basic pathfinding to get to our actual target.
                    self.move_to(target)
                    return
            pass
            origin_midpoint = find_midpoint(self, self, origin)
            if origin_midpoint is not None:
                origin = origin_midpoint
            dest_midpoint = find_midpoint(self, origin, target)
            if dest_midpoint is not None:
                if self.pos.roomName == dest_midpoint.roomName:
                    origin = dest_midpoint
                else:
                    target = dest_midpoint
                    path_opts.range = max(path_opts.range or 0, 10)

        path = self.hive.honey.find_serialized_path(origin, target, path_opts)
        # TODO: manually check the next position, and if it's a creep check what direction it's going
        result = self.creep.moveByPath(path)
        if result == ERR_NOT_FOUND:
            if self.memory.manual:
                self.move_to(target)
            elif not self.memory.next_ppos or movement.chebyshev_distance_room_pos(
                    self, self.memory.next_ppos) > CREEP_LIFE_TIME:
                all_positions = self.hive.honey.list_of_room_positions_in_path(origin, target, path_opts)
                closest = None
                closest_distance = Infinity
                for pos in all_positions:
                    distance = chebyshev_distance_room_pos(self.pos, pos)
                    if distance < closest_distance:
                        closest_distance = distance
                        closest = pos
                if closest and closest_distance < CREEP_LIFE_TIME:
                    self.memory.next_ppos = closest
                    if closest.isEqualTo(self.pos):
                        self.log("WARNING: ERR_NOT_FOUND when actually still on military path! Path retrieved:\n{}"
                                 "\nPos: {}.".format(path, self.pos))
                        if chebyshev_distance_room_pos(self.pos, target) <= 50:
                            self.memory.manual = True
                            self.move_to(target)
                            return
                else:
                    portals = _.filter(self.room.find(FIND_STRUCTURES), {'structureType': STRUCTURE_PORTAL})
                    if len(portals) and movement.chebyshev_distance_room_pos(self.pos, portals[0].pos) \
                            + movement.chebyshev_distance_room_pos(portals[0].destination, target) \
                            < movement.chebyshev_distance_room_pos(self.pos, target):
                        self.memory.next_ppos = self.pos.findClosestByRange(portals).pos
                    else:
                        self.log("WARNING: Couldn't find closest position on path from {} to {} near {}!"
                                 "\nMoving manually... (all pos: {})"
                                 .format(origin, target, self.pos, all_positions))
                        self.memory.next_ppos = target
            mtarget = self.memory.next_ppos
            if mtarget:
                new_target = __new__(RoomPosition(mtarget.x, mtarget.y, mtarget.roomName))
                if self.pos.isNearTo(new_target):
                    self.creep.move(self.pos.getDirectionTo(new_target))
                else:
                    self.move_to(new_target)
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
                        if chebyshev_distance_room_pos(self.memory.lost_path_at, self.pos) < 5 \
                                and not self.pos.isEqualTo(new_target) \
                                and not self.pos.isEqualTo(get_entrance_for_exit_pos(new_target)):
                            honey.clear_cached_path(origin, target, path_opts)
                            del self.memory.off_path_for
                            del self.memory.lost_path_at
                            del self.memory.next_ppos

                        self.log("Lost the path from {} to {}! Pos: {}. Retargeting to: {} (path: {})".format(
                            origin, target, self.pos, new_target, [
                                "({},{})".format(p.x, p.y) for p in Room.deserializePath(
                                    _.get(self.memory, ['_move', 'path'], ''))
                            ].join(', ')))
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
                        if is_block_clear(self.room, pos.x, pos.y):
                            self.memory.next_ppos = {"x": pos.x, "y": pos.y, "roomName": self.pos.roomName}
                            self.move_to(__new__(RoomPosition(pos.x, pos.y, self.pos.roomName)))
                            break
            if self.memory.standstill_for > 10:
                del self.memory.last_position
                del self.memory.standstill_for
                del self.memory.next_ppos
                honey.clear_cached_path(origin, target, path_opts)
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
        # if distance_squared_room_pos(spawn, target) > math.pow(200, 2):
        #     # TODO: handle this better (this is for not having multiple super-duper-long cached paths)
        #     intermediate = __new__(RoomPosition(25, 25, target.roomName))
        #     path_opts.max_ops = 30000
        #     path_opts.max_rooms = 30
        #     path_opts.use_roads = False
        #     path1 = self.hive.honey.find_path(spawn, intermediate, path_opts)
        #     path2 = self.hive.honey.find_path(intermediate, target, path_opts)
        #     return len(path1) + 20 + len(path2)
        # else:
        path_opts.max_ops = chebyshev_distance_room_pos(spawn, target) * 150
        path_opts.max_rooms = math.ceil(chebyshev_distance_room_pos(spawn, target) / 5)
        return self.hive.honey.find_path_length(spawn, target, path_opts)
