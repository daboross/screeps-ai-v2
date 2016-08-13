import flags
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

from control.building import _flag_sub_to_structure_type


class CachedTrails:
    def __init__(self, hive):
        self.hive = hive

    def find_path(self, origin, destination):
        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos
        if origin.roomName != destination.roomName:
            return None
        room = self.hive.get_room(origin.roomName)
        if room:
            return room.honey.find_path(origin, destination)
        memory = Memory.rooms[origin.roomName]
        if not memory or not memory.cache:
            return None
        key = "path_{}_{}_{}_{}".format(origin.x, origin.y, destination.x, destination.y)
        if key not in memory.cache:
            return None
        if memory.cache[key].dead_at <= Game.time:
            del memory.cache[key]
            return None
        try:
            return Room.deserializePath(memory.cache[key].value)
        except:
            print("[{}][honey] Serialized path from {},{} to {},{} was invalid.")
            del memory.cache[key]
            return None


class HoneyTrails:
    """
    :type room: control.hivemind.RoomMind
    """

    def __init__(self, room):
        self.room = room
        self.hive = room.hive_mind

    def _modify_cost_matrix(self, room_name, cost_matrix, origin, destination):
        if self.room.room_name != room_name:
            return

        going_to_extension = False
        for s in self.room.room.lookForAt(LOOK_STRUCTURES, destination):
            if s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN:
                going_to_extension = True
        if not going_to_extension:
            for s in self.room.room.lookForAt(LOOK_STRUCTURES, origin):
                if s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN:
                    going_to_extension = True

        def set_matrix(type, pos):
            if type == STRUCTURE_ROAD or type == STRUCTURE_RAMPART:
                return
            if pos.x == destination.x and pos.y == destination.y:
                return
            if pos.x == origin.x and pos.y == origin.y:
                return
            cost_matrix.set(pos.x, pos.y, 255)
            if abs(pos.x - origin.x) <= 3 and abs(pos.y - origin.y) <= 3:
                return
            if abs(pos.x - destination.x) <= 3 and abs(pos.y - destination.y) <= 3:
                return
            if type == STRUCTURE_SPAWN or type == STRUCTURE_EXTENSION:
                if not going_to_extension:
                    for x in range(pos.x - 1, pos.x + 1):
                        for y in range(pos.y - 1, pos.y + 1):
                            cost_matrix.set(x, y, 7)
            elif type == STRUCTURE_CONTROLLER or type == "this_is_a_source":
                for x in range(pos.x - 3, pos.x + 3):
                    for y in range(pos.y - 3, pos.y + 3):
                        cost_matrix.set(x, y, 5)
                for x in range(pos.x - 1, pos.x + 1):
                    for y in range(pos.y - 1, pos.y + 1):
                        cost_matrix.set(x, y, 7)
            cost_matrix.set(pos.x, pos.y, 255)

        for struct in self.room.find(FIND_STRUCTURES):
            set_matrix(struct.structureType, struct.pos)
        for site in self.room.find(FIND_CONSTRUCTION_SITES):
            set_matrix(site.structureType, site.pos)
        for flag, type in flags.find_by_main_with_sub(self.room, flags.MAIN_BUILD):
            set_matrix(_flag_sub_to_structure_type[type], flag.pos)
        for source in self.room.find(FIND_SOURCES):
            set_matrix("this_is_a_source", source.pos)
        for x in [0, 49]:
            for y in range(0, 50):
                if cost_matrix.get(x, y) < 200 and (x != origin.x or y != origin.y) \
                        and (x != destination.x or y != destination.y):
                    cost_matrix.set(x, y, 255)
        for y in [0, 49]:
            for x in range(0, 50):
                if cost_matrix.get(x, y) < 200 and (x != origin.x or y != origin.y) \
                        and (x != destination.x or y != destination.y):
                    cost_matrix.set(x, y, 255)

    def _get_callback(self, origin, destination):
        return lambda room_name, cost_matrix: self._modify_cost_matrix(room_name, cost_matrix, origin, destination)

    def find_path(self, origin, destination):
        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos
        if origin.roomName != self.room.room_name or destination.roomName != self.room.room_name:
            return None
        key = "path_{}_{}_{}_{}".format(origin.x, origin.y, destination.x, destination.y)
        path = self.room.get_cached_property(key)
        if path:
            try:
                return Room.deserializePath(path)
            except:
                print("[{}][honey] Serialized path from {},{} to {},{} was invalid.")
                del self.room.mem.cache[key]  # TODO: util method on room to do this.
        path = self.room.room.findPath(origin, destination, {
            "ignoreCreeps": True,
            "ignoreRoads": True,
            "costCallback": self._get_callback(origin, destination),
            "maxRooms": 1
        })
        # TODO: system to store last accessed time and remove paths which aren't accessed in the last 500 ticks.
        # TODO: longer TTL when we get this perfected
        self.room.store_cached_property(key, Room.serializePath(path), 1000, 100)
        return path

    def map_out_full_path(self, origin, destination):
        """
        :param origin: Starting position
        :param destination: Ending position
        :return: None if any room inbetween isn't viewable, otherwise a list of paths
        :rtype: list[list[object]]
        """
        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos
        if origin == destination:
            return None
        current = __new__(RoomPosition(origin.x, origin.y, origin.roomPosition))
        path_list = []

        target_room_xy = movement.parse_room_to_xy(destination.roomName)

        while current.roomName != destination.roomName:
            room = self.hive.get_room(current.roomName)
            if not room:
                print("[{}][honey] Couldn't find view to room {}.".format(self.room.room_name, current.roomName))
                return None
            current_room_xy = movement.parse_room_to_xy(current.roomName)
            difference = (target_room_xy[0] - current_room_xy[0], target_room_xy[1] - current_room_xy[1])
            exit_pos, exit_direction = movement.get_exit_flag_and_direction(current.roomName, destination.roomName,
                                                                            difference)
            if not exit_pos:
                return None

            path = room.honey.find_path(current, exit_pos)
            if not path:
                print("[{}][honey] Couldn't find path to exit {} in room {}!".format(
                    self.room.room_name, exit_direction, current.roomName))
                return None
            path_list.append(path)

        room = self.hive.get_room(current.roomName)
        if not room:
            print("[{}][honey] Couldn't find view to room {}.".format(self.room.room_name, current.roomName))
            return None

        path = room.honey.find_path(current, destination)
        if not path:
            print("[{}][honey] Couldn't find path from {} to {} in room {}!".format(
                self.room.room_name, current, destination, current.roomName))
            return None
        path_list.append(path)
        return path_list


profiling.profile_whitelist(HoneyTrails, [
    "find_path",
    "map_out_full_path",
])
