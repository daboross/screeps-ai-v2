import flags
from tools import profiling
from utilities import global_cache
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def pathfinder_to_regular_path(origin, input):
    path = []
    room_start_positions = []
    last_room = None
    last_x, last_y = origin.x, origin.y
    for pos in input:
        if last_room != pos.roomName:
            room_start_positions.append([pos.roomName, len(path)])
            last_room = pos.roomName
        dx = pos.x - last_x
        dy = pos.y - last_y
        if dx == -49:
            dx = 1
        elif dx == 49:
            dx = -1
        if dy == -49:
            dy = 1
        elif dy == 49:
            dy = -1
        if dx < -1 or dx > 1:
            print("[honey][pathfinder_to_regular_path] dx found from {} to {}: {}".format(
                last_x, pos.x, dx
            ))
        if dy < -1 or dy > 1:
            print("[honey][pathfinder_to_regular_path] dy found from {} to {}: {}".format(
                last_y, pos.y, dy
            ))
        last_x = pos.x
        last_y = pos.y
        direction = get_direction(dx, dy)
        if direction is None:
            print("[honey][pathfinder_to_regular_path] Unknown direction for pos: {},{}, last: {},{}".format(
                pos.x, pos.y, last_x, last_y))
            return None
        path.append({
            'x': pos.x,
            'y': pos.y,
            'dx': dx,
            'dy': dy,
            'direction': direction
        })
    return path, room_start_positions


# def serialize_pathfinder_path(path):
#     codepoints = []
#     for pos in path:
#         codepoints.append(pos.x | (pos.y << 6))
#         codepoints.append()
#     # String.fromCodePoint(x | (y << 6));
#     # 2:09 decode like this:
#     # var char = str.charCodeAt(index);
#     #    var x = (char &  0x3F);
#     #    var y = ((char >> 6) & 0x3F);
#     #    return {x: x, y:y};
#     pass


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


def direction_to(origin, destination):
    if origin.pos: origin = origin.pos
    if destination.pos: destination = destination.pos
    direction = get_direction(destination.x - origin.x, destination.y - origin.y)
    if direction is None:
        print("[honey][direction_to] No direction found for get_direction({} - {}, {} - {})."
              .format(destination.x, origin.x, destination.y, origin.y))
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
        if dx == -49:
            dx = 1
        elif dx == 49:
            dx = -1
        if dy == -49:
            dy = 1
        elif dy == 49:
            dy = -1
        direction = get_direction(dx, dy)
        if direction is None:
            print("[honey][reverse_path] Unknown direction for pos: {},{}, last: {},{}".format(
                pos.x, pos.y, last_x, last_y))
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
    # This function takes in a freshly-deserialized path, so we do need to do normalizing
    # TODO: do our own serialization format so this isn't neccessary
    for pos in output_path:
        while pos.x < 0:
            pos.x += 50
        pos.x %= 50
        while pos.y < 0:
            pos.y += 50
        pos.y %= 50
    return output_path


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
        self.used_basic_matrix = False

    def mark_exit_tiles(self, room_name, matrix, opts):
        use_roads = opts['roads']
        if_roads_mutiplier = 2 if use_roads else 1
        room_x, room_y = movement.parse_room_to_xy(room_name)
        if room_x % 10 == 0 or room_y % 10 == 0:
            for x in [0, 49]:
                for y in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 1 * if_roads_mutiplier)
            for y in [0, 49]:
                for x in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 1 * if_roads_mutiplier)
        else:
            for x in [0, 49]:
                for y in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 2 * if_roads_mutiplier)
            for y in [0, 49]:
                for x in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 2 * if_roads_mutiplier)

    def _new_cost_matrix(self, room_name, origin, destination, opts):
        use_roads = opts['roads']
        if_roads_mutiplier = 2 if use_roads else 1
        if self.room.room_name != room_name:

            room = self.hive.get_room(room_name)
            if room:
                print("[honey] Redelegating matrix for room {}.".format(room_name))
                return room.honey._new_cost_matrix(room_name, origin, destination, opts)
            else:
                if Memory.enemy_rooms and room_name in Memory.enemy_rooms \
                        and room_name != origin.roomName and room_name != destination.roomName:
                    print("[honey] Avoiding room {}.".format(room_name))
                    return False
                print("[honey] Using basic matrix for room {}.".format(room_name))
                self.used_basic_matrix = True
                matrix = __new__(PathFinder.CostMatrix())
                # Avoid stepping on exit tiles unnecessarily
                self.mark_exit_tiles(room_name, matrix, opts)
                return matrix
        print("[honey] Calculating matrix for room {}.".format(room_name))

        # Python way doesn't work in JS :(
        # structures_ignore = [s.structureType for s in self.room.find_at(FIND_STRUCTURES, origin)] + \
        #                     [s.structureType for s in self.room.find_at(FIND_STRUCTURES, destination)]
        structures_ignore = []
        if origin.roomName == room_name:
            for s in self.room.find_at(FIND_STRUCTURES, origin):
                structures_ignore.append(s.structureType)
        if destination.roomName == room_name:
            for s in self.room.find_at(FIND_STRUCTURES, destination):
                structures_ignore.append(s.structureType)
        going_to_extension = STRUCTURE_EXTENSION in structures_ignore or STRUCTURE_SPAWN in structures_ignore
        going_to_storage = STRUCTURE_STORAGE in structures_ignore or STRUCTURE_LINK in structures_ignore
        going_to_controller = STRUCTURE_CONTROLLER in structures_ignore
        # Note: RoomMind.find_at() checks if pos.roomName == self.room_name, and if not, re-delegates to the actual room.
        # that allows this to work correctly for multi-room paths.
        going_to_source = len(self.room.find_at(FIND_SOURCES, origin)) or len(
            self.room.find_at(FIND_SOURCES, destination))

        cost_matrix = __new__(PathFinder.CostMatrix())
        self.mark_exit_tiles(room_name, cost_matrix, opts)

        def wall_at(x, y):
            return Game.map.getTerrainAt(x, y, room_name) == 'wall'

        def road_at(x, y):
            for s in self.room.room.lookForAt(LOOK_STRUCTURES, x, y):
                if s.structureType == STRUCTURE_ROAD:
                    return True
            return False

        def set_matrix(stype, pos):
            if stype == STRUCTURE_ROAD or stype == STRUCTURE_RAMPART:
                if stype == STRUCTURE_ROAD and use_roads \
                        and not flags.look_for(self.room, pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD):
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
                for x in range(pos.x - 1, pos.x + 2):
                    for y in range(pos.y - 1, pos.y + 2):
                        if not road_at(x, y) and not wall_at(x, y) and cost_matrix.get(x, y) < 10 * if_roads_mutiplier:
                            cost_matrix.set(x, y, 10 * if_roads_mutiplier)
            elif (stype == STRUCTURE_CONTROLLER and not going_to_controller) or \
                    (stype == "this_is_a_source" and not going_to_source):
                for x in range(pos.x - 3, pos.x + 4):
                    for y in range(pos.y - 3, pos.y + 4):
                        if not road_at(x, y) and not wall_at(x, y) and cost_matrix.get(x, y) < 5 * if_roads_mutiplier:
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

        # Make room for the link manager creep! This can cause problems if not included.
        if self.room.my and self.room.room.storage and self.room.links.main_link:
            ml = self.room.links.main_link
            storage = self.room.room.storage
            for x in range(ml.pos.x - 1, ml.pos.x + 2):
                for y in range(ml.pos.y - 1, ml.pos.y + 2):
                    if abs(storage.pos.x - x) == 1 and abs(storage.pos.y - y) == 1:
                        cost_matrix.set(x, y, 255)

        return cost_matrix

    def _get_callback(self, origin, destination, opts):
        return lambda room_name: self._new_cost_matrix(room_name, origin, destination, opts)

    def find_path(self, origin, destination, opts=None):
        if opts:
            if "current_room" in opts:
                current_room = opts["current_room"]
                if current_room:
                    if current_room.room: current_room = current_room.room
                    if current_room.name: current_room = current_room.name
            else:
                current_room = None
            roads_better = opts["use_roads"] if "use_roads" in opts else True
            range = opts["range"] if "range" in opts else 1
            max_ops = opts["max_ops"] if "max_ops" in opts else 2000
            max_rooms = opts["max_rooms"] if "max_rooms" in opts else 16
        else:
            roads_better = True
            range = 1
            max_ops = 2000
            max_rooms = 16
            current_room = None

        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos
        key = "path_{}_{}_{}_{}_{}_{}".format(origin.roomName, origin.x, origin.y,
                                              destination.roomName, destination.x, destination.y)
        serialized_path = global_cache.get(key)
        if serialized_path is not None:
            path = None
            try:
                path = Room.deserializePath(serialized_path)
            except:
                print("[{}][honey] Serialized path from {} to {} was invalid.".format(
                    self.room.room_name, origin, destination))
                global_cache.rem(key)
            if path:
                # TODO: do our own serialization format so this isn't neccessary
                for pos in path:
                    while pos.x < 0:
                        pos.x += 50
                    pos.x %= 50
                    while pos.y < 0:
                        pos.y += 50
                    pos.y %= 50
                # TODO: this is another hack-y workaround for not having our own multi-room serialization format!
                if current_room is not None and origin.roomName != destination.roomName:
                    # TODO: list() here is needed since the array returned by Room.deserializePath() isn't
                    # instanceof Array. Our own serialization would fix this!
                    room_start_pos = global_cache.get("{}_rsp".format(key))
                    # The old format was an object! Let's recalculate if that's the case!
                    if room_start_pos is not None and room_start_pos.length != undefined:
                        room_start_pos = list(room_start_pos)
                        for rsp_index, (room_name, path_index) in enumerate(room_start_pos):
                            if room_name == current_room:
                                if rsp_index + 1 < len(room_start_pos):
                                    end_index = room_start_pos[rsp_index + 1][1]
                                    path = list(path)[path_index:end_index]
                                else:
                                    end_index = "none"
                                    path = list(path)[path_index:]
                                if not len(path):
                                    print("WARNING: Current room {} on path from {} to {} produced empty path!"
                                          " start index: {}, end index: {}".format(current_room, origin, destination,
                                                                                   path_index, end_index))
                                break
                        else:
                            print("WARNING: current room {} wasn't found on path from {} to {}!".format(
                                current_room, origin, destination))
                            return []  # No rooms matched, we don't have a valid path!
                        # do an extra return here so we can calculate a path as normal if roomstartpos.length is undef.
                        if Memory.path_debug:
                            print("Used section {} to {} of path from {} to {} (length: {})".format(
                                path_index, end_index, origin, destination, len(path)
                            ))
                        return path
                else:
                    return path

        # reverse_key = "path_{}_{}_{}_{}_{}_{}".format(destination.roomName, destination.x, destination.y,
        #                                               origin.roomName, origin.x, origin.y)
        # from_dest_path_serialized = global_cache.get(reverse_key)
        # if from_dest_path_serialized is not None:
        #     from_dest_path = None
        #     try:
        #         from_dest_path = Room.deserializePath(from_dest_path_serialized)
        #     except:
        #         print("[{}][honey] Serialized path (retrieved reverse) from {},{} to {},{} was invalid.".format(
        #             self.room.room_name, destination.x, destination.y, origin.x, origin.y))
        #     # TODO: replace this check with a "try..except..else" clause when it starts working in Transcrypt.
        #     if from_dest_path is not None:
        #         path = reverse_path(from_dest_path, origin)
        #         if path is not None:
        #             global_cache.set(key, Room.serializePath(path), Memory.cache.reverse_key.d - Game.time)
        #             return path

        self.used_basic_matrix = False
        result = PathFinder.search(origin, {"pos": destination, "range": range}, {
            "plainCost": 2 if roads_better else 1,
            "swampCost": 10 if roads_better else 5,
            "roomCallback": self._get_callback(origin, destination, {"roads": roads_better}),
            "maxRooms": max_rooms,
            "maxOps": max_ops,
        })
        print("[honey] Calculated new path from {} to {} in {} ops.".format(
            origin, destination, result.ops))
        # TODO: make our own serialization format. This wouldn't be too much of a stretch, since we already have to do
        # all of this to convert PathFinder results into a Room-compatible format.
        rpresult = pathfinder_to_regular_path(origin, result.path)
        if rpresult is None:
            return None
        path, room_start_pos = rpresult
        all_paved = True
        for pos in path:
            if not _.find(self.room.find_at(FIND_STRUCTURES, pos.x, pos.y),
                          lambda s: s.structureType == STRUCTURE_ROAD) \
                    and not _.find(self.room.find_at(FIND_MY_CONSTRUCTION_SITES, pos.x, pos.y),
                                   lambda s: s.structureType == STRUCTURE_ROAD):
                all_paved = False

                break

        expire_in = 20000
        if all_paved:
            expire_in *= 4
        if not self.room.my:
            expire_in *= 2
        if self.used_basic_matrix:
            # Don't constantly re-calculate super-long paths that we can't view the rooms for.
            if len(room_start_pos) < 4:
                expire_in /= 10
        global_cache.set(key, Room.serializePath(path), expire_in)
        global_cache.set("{}_rsp".format(key), room_start_pos, expire_in)

        if current_room and origin.roomName != destination.roomName:
            # TODO: this little snippet is duplicated in the deserialization section above
            for rsp_index, (room_name, path_index) in enumerate(room_start_pos):
                if room_name == current_room:
                    if rsp_index + 1 < len(room_start_pos):
                        end_index = room_start_pos[rsp_index + 1][1]
                        path = path[path_index:end_index]
                    else:
                        end_index = "none"
                        path = path[path_index:]
                    if not len(path):
                        print("Current room {} on path from {} to {} produced empty path!"
                              " start index: {}, end index: {}".format(current_room, origin, destination,
                                                                       path_index, end_index))
                    break
            else:
                print("Huh, current room {} wasn't found on path from {} to {}!".format(current_room, origin,
                                                                                        destination))
                return []  # No rooms match, we don't have a valid path!
        return path

    def list_of_room_positions_in_path(self, origin, destination, opts=None):
        if opts and "current_room" in opts:
            opts = Object.create(opts)
            opts["current_room"] = None

        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos

        path_list = self.find_path(origin, destination, opts)

        rsp_key = "path_{}_{}_{}_{}_{}_{}_rsp".format(origin.roomName, origin.x, origin.y,
                                                      destination.roomName, destination.x, destination.y)
        rsp = global_cache.get(rsp_key)
        if not rsp or not rsp.length:
            # The old format was an object! Let's recalculate if that's the case!
            global_cache.rem("path_{}_{}_{}_{}_{}_{}".format(origin.roomName, origin.x, origin.y,
                                                             destination.roomName, destination.x, destination.y))
            path_list = self.find_path(origin, destination, opts)
            rsp = global_cache.get(rsp_key)

        if not len(rsp):
            rsp = {origin.roomName: 0}

        final_list = []

        for rsp_index, (room_name, path_index) in enumerate(list(rsp)):
            if rsp_index + 1 >= len(rsp):
                this_room_path_list = path_list
            else:
                next_index = rsp[rsp_index + 1][1]
                new_path_list = path_list.splice(next_index, Infinity)
                this_room_path_list = path_list
                path_list = new_path_list
            for pos in this_room_path_list:
                final_list.append(__new__(RoomPosition(pos.x, pos.y, room_name)))
        return final_list


profiling.profile_whitelist(HoneyTrails, [
    "find_path",
])
