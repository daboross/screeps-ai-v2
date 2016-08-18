import flags
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

# # TODO: function to use pathfinder to search and cache results
# if self.memory.path_cached and self.memory.path_reset > Game.time:
#     path = Room.deserializePath(self.memory.path_cached)
# else:
#     result = PathFinder.search(self.creep.pos, {"pos": target.pos, "range": 1}, {
#         "roomCallback": autoactions.simple_cost_matrix,
#         "maxOps": 1000,
#     })
#     path = pathdef.pathfinder_to_regular_path(self.creep.pos, result.path)
#     self.memory.path_cached = Room.serializePath(path)
#     self.memory.path_reset = Game.time + 10
# result = self.creep.moveTo(target)
# if result != OK:
#     self.log("Unknown result from creep.moveByPath(): {}".format(result))

def get_direction(dx, dy):
    """
    Gets the screeps direction constant from a given dx and dy.
    :type dx: int
    :type dy: int
    :rtype: int
    """
    direction = None
    if dx < 0:
        if dy < 0:
            direction = TOP_LEFT
        elif dy == 0:
            direction = LEFT
        elif dy > 0:
            direction = BOTTOM_LEFT
    elif dx == 0:
        if dy < 0:
            direction = TOP
        elif dy > 0:
            direction = BOTTOM
    elif dx > 0:
        if dy < 0:
            direction = TOP_RIGHT
        elif dy == 0:
            direction = RIGHT
        elif dy > 0:
            direction = BOTTOM_RIGHT
    if direction is None:
        print("[honey][direction] ERROR: Unknown dx/dy: {},{}!".format(dx, dy))
        return None
    else:
        return direction


def reverse_path(input_path, new_origin):
    """
    :type input_path: list[Any]
    :type new_origin: RoomPosition
    """
    output_path = []
    last_x, last_y = new_origin.x, new_origin.y
    for pos in reversed(input_path):
        dx = pos.x - last_x
        dy = pos.y - last_y
        direction = get_direction(dx, dy)
        if direction is None:
            return None
        last_x = pos.x
        last_y = pos.y
        output_path.append({
            'x': pos.x,
            'y': pos.y,
            'dx': dx,
            'dy': dy,
            'direction': direction
        })
    return output_path


def pathfinder_to_regular_path(origin, input):
    path = []
    last_x, last_y = origin.x, origin.y
    for pos in input:
        dx = pos.x - last_x
        dy = pos.y - last_y
        last_x = pos.x
        last_y = pos.y
        path.append({
            'x': pos.x,
            'y': pos.y,
            'dx': dx,
            'dy': dy,
            'direction': get_direction(dx, dy)
        })
    return path


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

    def _new_cost_matrix(self, room_name, origin, destination, opts):
        use_roads = opts['roads']
        if_roads_mutiplier = 2 if use_roads else 1
        if self.room.room_name != room_name:
            return

        structures_ignore = [s.structureType for s in self.room.find_at(FIND_STRUCTURES, origin)] + \
                            [s.structureType for s in self.room.find_at(FIND_STRUCTURES, destination)]
        going_to_extension = STRUCTURE_EXTENSION in structures_ignore or STRUCTURE_SPAWN in structures_ignore
        going_to_storage = STRUCTURE_STORAGE in structures_ignore or STRUCTURE_LINK in structures_ignore
        going_to_controller = STRUCTURE_CONTROLLER in structures_ignore
        going_to_source = len(self.room.find_at(FIND_SOURCES, origin)) or len(
            self.room.find_at(FIND_SOURCES, destination))

        cost_matrix = __new__(PathFinder.CostMatrix())

        def wall_at(x, y):
            for t in self.room.room.lookForAt(LOOK_TERRAIN, x, y):
                # TODO: there are no constants for this value, and TERRAIN_MASK_* constants seem to be useless...
                if t == 'wall':
                    return True
            return False

        def set_matrix(stype, pos):
            if stype == STRUCTURE_ROAD or stype == STRUCTURE_RAMPART:
                if stype == STRUCTURE_ROAD and use_roads:
                    cost_matrix.set(pos.x, pos.y, 1)
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
            if ((stype == STRUCTURE_SPAWN or stype == STRUCTURE_EXTENSION) and not going_to_extension) \
                    or ((stype == STRUCTURE_STORAGE or stype == STRUCTURE_LINK) and not going_to_storage):
                if not going_to_extension:
                    for x in range(pos.x - 1, pos.x + 2):
                        for y in range(pos.y - 1, pos.y + 2):
                            if not wall_at(x, y) and cost_matrix.get(x, y) < 20 * if_roads_mutiplier:
                                cost_matrix.set(x, y, 20 * if_roads_mutiplier)
            elif (stype == STRUCTURE_CONTROLLER and not going_to_controller) or \
                    (stype == "this_is_a_source" and not going_to_source):
                for x in range(pos.x - 3, pos.x + 4):
                    for y in range(pos.y - 3, pos.y + 4):
                        if not wall_at(x, y) and cost_matrix.get(x, y) < 5 * if_roads_mutiplier:
                            cost_matrix.set(x, y, 5 * if_roads_mutiplier)
                for x in range(pos.x - 1, pos.x + 2):
                    for y in range(pos.y - 1, pos.y + 2):
                        if not wall_at(x, y) and cost_matrix.get(x, y) < 20 * if_roads_mutiplier:
                            cost_matrix.set(x, y, 20 * if_roads_mutiplier)
            cost_matrix.set(pos.x, pos.y, 255)

        for struct in self.room.find(FIND_STRUCTURES):
            set_matrix(struct.structureType, struct.pos)
        for site in self.room.find(FIND_CONSTRUCTION_SITES):
            set_matrix(site.structureType, site.pos)
        for flag, stype in flags.find_by_main_with_sub(self.room, flags.MAIN_BUILD):
            set_matrix(flags.flag_sub_to_structure_type[stype], flag.pos)
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

        return cost_matrix

    def _get_callback(self, origin, destination, opts):
        return lambda room_name: self._new_cost_matrix(room_name, origin, destination, opts)

    def find_path(self, origin, destination, opts=None):
        if opts:
            roads_better = opts["use_roads"] if "use_roads" in opts else False
            range = opts["range"] if "range" in opts else 1
        else:
            roads_better = False
            range = 1
        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos
        if origin.roomName != self.room.room_name or destination.roomName != self.room.room_name:
            return None
        key = "path_{}_{}_{}_{}".format(origin.x, origin.y, destination.x, destination.y)
        serialized_path = self.room.get_cached_property(key)
        if serialized_path is not None:
            try:
                return Room.deserializePath(serialized_path)
            except:
                print("[{}][honey] Serialized path from {},{} to {},{} was invalid.".format(
                    self.room.room_name, origin.x, origin.y, destination.x, destination.y))
                del self.room.mem.cache[key]  # TODO: util method on room to do this.

        from_dest_path_serialized = self.room.get_cached_property("path_{}_{}_{}_{}".format(
            destination.x, destination.y, origin.x, origin.y))
        if from_dest_path_serialized is not None:
            from_dest_path = None
            try:
                from_dest_path = Room.deserializePath(from_dest_path_serialized)
            except:
                print("[{}][honey] Serialized path (retrieved reverse) from {},{} to {},{} was invalid.".format(
                    self.room.room_name, destination.x, destination.y, origin.x, origin.y))
            # TODO: replace this check with a "try..except..else" clause when it starts working in Transcrypt.
            if from_dest_path is not None:
                path = reverse_path(from_dest_path, origin)
                if path is not None:
                    if self.room.my:
                        self.room.store_cached_property(key, Room.serializePath(path), 3000, 500)
                    else:
                        self.room.store_cached_property(key, Room.serializePath(path), 10000, 1000)
                    return path

        result = PathFinder.search(origin, {"pos": destination, "range": range}, {
            "plainCost": 2 if roads_better else 1,
            "swampCost": 10 if roads_better else 5,
            "roomCallback": self._get_callback(origin, destination, {"roads": roads_better}),
            "maxRooms": 1
        })
        # TODO: make our own serialization format. This wouldn't be too much of a stretch, since we already have to do
        # all of this to convert PathFinder results into a Room-compatible format.
        path = pathfinder_to_regular_path(origin, result.path)
        if self.room.my:
            self.room.store_cached_property(key, Room.serializePath(path), 3000, 500)
        else:
            self.room.store_cached_property(key, Room.serializePath(path), 10000, 1000)
        return path

    def map_out_full_path(self, origin, destination):
        """
        :param origin: Starting position
        :param destination: Ending position
        :return: None if any room in between isn't viewable, otherwise a list of paths
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
