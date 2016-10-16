import flags
from tools import profiling
from utilities import global_cache
from utilities import hostile_utils
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def pathfinder_path_to_room_to_path_obj(origin, input):
    result_obj = {}
    full_path = []
    result_obj["full"] = full_path
    last_room = None
    current_path = None
    last_x, last_y = origin.x, origin.y
    for pos in input:
        if last_room != pos.roomName:
            current_path = []
            # this is passed by reference, so we just set it here
            result_obj[pos.roomName] = current_path
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
        item = {
            'x': pos.x,
            'y': pos.y,
            'dx': dx,
            'dy': dy,
            'direction': direction
        }
        current_path.append(item)
        full_path.append(item)
    return result_obj


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


class HoneyTrails:
    """
    :type hive: control.hivemind.HiveMind
    """

    def __init__(self, hive_mind):
        self.hive = hive_mind

    def mark_exit_tiles(self, room_name, matrix, opts):
        use_roads = opts['roads']
        future_chosen = opts['future_chosen']
        if future_chosen:
            if_roads_multiplier = 5
        else:
            if_roads_multiplier = 2 if use_roads else 1

        room_x, room_y = movement.parse_room_to_xy(room_name)
        if room_x % 10 == 0 or room_y % 10 == 0:
            for x in [0, 49]:
                for y in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 1 * if_roads_multiplier)
            for y in [0, 49]:
                for x in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 1 * if_roads_multiplier)
        else:
            for x in [0, 49]:
                for y in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 2 * if_roads_multiplier)
            for y in [0, 49]:
                for x in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 2 * if_roads_multiplier)

    def mark_flags(self, room_name, matrix, opts):
        for flag in flags.find_flags(room_name, flags.SK_LAIR_SOURCE_NOTED):
            for x in range(flag.pos.x - 4, flag.pos.x + 5):
                for y in range(flag.pos.y - 4, flag.pos.y + 5):
                    matrix.set(x, y, 255)

        slightly_avoid = flags.find_flags(room_name, flags.SLIGHTLY_AVOID)
        if len(slightly_avoid):
            cost = 10 if opts['future_chosen'] else (4 if opts['roads'] else 2)
            for flag in slightly_avoid:
                if Game.map.getTerrainAt(flag.pos.x, flag.pos.y, room_name) != 'wall' \
                        and matrix.get(flag.pos.x, flag.pos.y) < cost:
                    matrix.set(flag.pos.x, flag.pos.y, cost)

    def set_max_avoid(self, room_name, matrix, opts):
        if opts['max_avoid']:
            if opts['future_chosen']:
                if_roads_multiplier = 5
            elif opts['roads']:
                if_roads_multiplier = 2
            else:
                if_roads_multiplier = 1
            if room_name in opts['max_avoid']:
                # print("Setting max_avoid in room {}".format(room_name))
                for x in range(0, 49):
                    for y in range(0, 49):
                        if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                            matrix.set(x, y, if_roads_multiplier * 20)
                return True
            for direction, other_room in _.pairs(Game.map.describeExits(room_name)):
                if other_room in opts['max_avoid']:
                    # print("Setting max_avoid on the {} of room {}".format(
                    #     "top" if direction == TOP
                    #     else ("bottom" if direction == BOTTOM
                    #           else "left" if direction == LEFT else (
                    #         "right" if direction == RIGHT else direction
                    #     )), room_name))
                    if direction == TOP:
                        for x in range(0, 49):
                            if Game.map.getTerrainAt(x, 0, room_name) != 'wall':
                                matrix.set(x, 0, 20 * if_roads_multiplier)
                    elif direction == BOTTOM:
                        for x in range(0, 49):
                            if Game.map.getTerrainAt(x, 49, room_name) != 'wall':
                                matrix.set(x, 49, 20 * if_roads_multiplier)
                    elif direction == LEFT:
                        for y in range(0, 49):
                            if Game.map.getTerrainAt(0, y, room_name) != 'wall':
                                matrix.set(0, y, 20 * if_roads_multiplier)
                    elif direction == RIGHT:
                        for y in range(0, 49):
                            if Game.map.getTerrainAt(49, y, room_name) != 'wall':
                                matrix.set(49, y, 20 * if_roads_multiplier)

    def generate_serialized_cost_matrix(self, room_name):
        if not global_cache.has("{}_cost_matrix_{}".format(room_name, 1)):
            self.get_generic_cost_matrix(room_name, {'roads': False})
        if not global_cache.has("{}_cost_matrix_{}".format(room_name, 2)):
            self.get_generic_cost_matrix(room_name, {'roads': True})

    def get_generic_cost_matrix(self, room_name, opts):
        """
        Gets a generic cost matrix, accepting slightly different options from find_path() methods
        :param room_name: Room name to get the cost matrix for
        :param opts: {'roads': True|False}
        :return: A cost matrix
        """
        use_roads = opts['roads']
        if_roads_multiplier = 2 if use_roads else 1

        serialization_key = "{}_cost_matrix_{}".format(room_name, if_roads_multiplier)
        serialized = global_cache.get(serialization_key)
        if serialized:
            cost_matrix = PathFinder.CostMatrix.deserialize(JSON.parse(serialized))
            self.set_max_avoid(room_name, cost_matrix, opts)
            return cost_matrix

        room = self.hive.get_room(room_name)
        if not room:
            return None

        def wall_at(x, y):
            return Game.map.getTerrainAt(x, y, room_name) == 'wall'

        def road_at(x, y):
            for s in room.look_at(LOOK_STRUCTURES, x, y):
                if s.structureType == STRUCTURE_ROAD:
                    return True
            for s in room.look_at(LOOK_CONSTRUCTION_SITES, x, y):
                if s.structureType == STRUCTURE_ROAD:
                    return True
            return False

        cost_matrix = __new__(PathFinder.CostMatrix())

        self.mark_exit_tiles(room_name, cost_matrix, opts)
        self.mark_flags(room_name, cost_matrix, opts)

        def set_matrix(stype, pos, planned):
            if stype == STRUCTURE_ROAD or stype == STRUCTURE_RAMPART or stype == STRUCTURE_CONTAINER:
                if stype == STRUCTURE_ROAD and use_roads \
                        and not flags.look_for(room, pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD):
                    # TODO: this should really just be a method on top of this method to do this
                    if cost_matrix.get(pos.x, pos.y) > 2:
                        cost_matrix.set(pos.x, pos.y, cost_matrix.get(pos.x, pos.y) / 2)

                        return  # Don't set roads to low-cost if they're already set to high-cost
                    cost_matrix.set(pos.x, pos.y, 1)
                return
            cost_matrix.set(pos.x, pos.y, 255)
            if (stype == STRUCTURE_SPAWN or stype == STRUCTURE_EXTENSION or
                        stype == STRUCTURE_STORAGE or stype == STRUCTURE_LINK):
                for x in range(pos.x - 1, pos.x + 2):
                    for y in range(pos.y - 1, pos.y + 2):
                        if not road_at(x, y) and not wall_at(x, y) and cost_matrix.get(x, y) < 10 * if_roads_multiplier:
                            cost_matrix.set(x, y, 10 * if_roads_multiplier)
            elif stype == STRUCTURE_CONTROLLER or stype == "this_is_a_source":
                for x in range(pos.x - 3, pos.x + 4):
                    for y in range(pos.y - 3, pos.y + 4):
                        if not road_at(x, y) and not wall_at(x, y) and cost_matrix.get(x, y) < 5 * if_roads_multiplier:
                            cost_matrix.set(x, y, 5 * if_roads_multiplier)
                for x in range(pos.x - 2, pos.x + 3):
                    for y in range(pos.y - 2, pos.y + 3):
                        if not wall_at(x, y) and cost_matrix.get(x, y) < 7 * if_roads_multiplier:
                            cost_matrix.set(x, y, 7 * if_roads_multiplier)
                for x in range(pos.x - 1, pos.x + 2):
                    for y in range(pos.y - 1, pos.y + 2):
                        if not wall_at(x, y) and cost_matrix.get(x, y) < 20 * if_roads_multiplier:
                            cost_matrix.set(x, y, 20 * if_roads_multiplier)
            cost_matrix.set(pos.x, pos.y, 255)

        for struct in room.find(FIND_STRUCTURES):
            set_matrix(struct.structureType, struct.pos, False)
        for site in room.find(FIND_CONSTRUCTION_SITES):
            set_matrix(site.structureType, site.pos, True)
        for flag, stype in flags.find_by_main_with_sub(room, flags.MAIN_BUILD):
            set_matrix(flags.flag_sub_to_structure_type[stype], flag.pos, True)
        for source in room.find(FIND_SOURCES):
            set_matrix("this_is_a_source", source.pos, False)

        # Make room for the link manager creep! This can cause problems if not included.
        if room.my and room.room.storage and room.links.main_link:
            ml = room.links.main_link
            storage = room.room.storage
            if ml.pos.x == storage.pos.x and abs(ml.pos.y - storage.pos.y) == 2 \
                    and movement.is_block_empty(room, ml.pos.x, (ml.pos.y + storage.pos.y) / 2):
                cost_matrix.set(ml.pos.x, (ml.pos.y + storage.pos.y) / 2, 255)
            elif ml.pos.y == storage.pos.y and abs(ml.pos.x - storage.pos.x) == 2 \
                    and movement.is_block_empty(room, (ml.pos.x + storage.pos.x) / 2, ml.pos.y):
                cost_matrix.set((ml.pos.x + storage.pos.x) / 2, ml.pos.y, 255)
            else:
                for x in range(ml.pos.x - 1, ml.pos.x + 2):
                    for y in range(ml.pos.y - 1, ml.pos.y + 2):
                        if abs(storage.pos.x - x) <= 1 and abs(storage.pos.y - y) <= 1:
                            cost_matrix.set(x, y, 255)

        serialized = JSON.stringify(cost_matrix.serialize())
        cache_for = 100 if room.my else 10000
        global_cache.set(serialization_key, serialized, cache_for)

        self.set_max_avoid(room_name, cost_matrix, opts)

        return cost_matrix

    def _new_cost_matrix(self, room_name, origin, destination, opts):
        use_roads = opts['roads']
        future_chosen = opts['future_chosen']

        if hostile_utils.enemy_room(room_name):
            if room_name != origin.roomName and room_name != destination.roomName:
                return False
            else:
                print("[honey] Warning: path {}-{} ends up in an enemy room ({})!"
                      .format(origin, destination, room_name))

        if future_chosen:
            if_roads_multiplier = 5
            this_room_future_roads = future_chosen[room_name] or []
        else:
            if_roads_multiplier = 2 if use_roads else 1
            this_room_future_roads = None
        room = self.hive.get_room(room_name)
        if (room_name != origin.roomName and room_name != destination.roomName and not future_chosen) or not room:
            if this_room_future_roads:
                serialized = global_cache.get("{}_cost_matrix_{}".format(room_name, if_roads_multiplier))
                if serialized:
                    print("[honey] Using serialized matrix for room {}.".format(room_name))
                    matrix = PathFinder.CostMatrix.deserialize(JSON.parse(serialized))
                    self.set_max_avoid(room_name, matrix, opts)
                    if this_room_future_roads:
                        for pos in this_room_future_roads:
                            matrix.set(pos.x, pos.y, 2)
            else:
                matrix = self.get_generic_cost_matrix(room_name, opts)
                if matrix:
                    print("[honey] Using generic matrix for room {}.".format(room_name))
                    return matrix

            print("[honey] Using basic matrix for room {}.".format(room_name))
            matrix = __new__(PathFinder.CostMatrix())
            # Avoid stepping on exit tiles unnecessarily
            self.mark_exit_tiles(room_name, matrix, opts)
            self.mark_flags(room_name, matrix, opts)
            self.set_max_avoid(room_name, matrix, opts)
            return matrix
        print("[honey] Calculating intricate matrix for room {}.".format(room_name))

        structures_ignore = []
        if origin.roomName == room_name:
            for s in room.look_at(LOOK_STRUCTURES, origin):
                structures_ignore.append(s.structureType)
        if destination.roomName == room_name:
            for s in room.look_at(LOOK_STRUCTURES, destination):
                structures_ignore.append(s.structureType)
        going_to_extension = structures_ignore.includes(STRUCTURE_EXTENSION) or structures_ignore.includes(
            STRUCTURE_SPAWN)
        going_to_storage = structures_ignore.includes(STRUCTURE_STORAGE) or structures_ignore.includes(STRUCTURE_LINK)
        going_to_controller = structures_ignore.includes(STRUCTURE_CONTROLLER)
        # Note: RoomMind.find_at() checks if pos.roomName == self.room_name, and if not, re-delegates to the actual
        # room. that allows this to work correctly for multi-room paths.
        going_to_source = (
            (origin.roomName == room_name and len(room.look_at(LOOK_SOURCES, origin)))
            or (destination.roomName == room_name and len(room.look_at(LOOK_SOURCES, destination)))
        )

        cost_matrix = __new__(PathFinder.CostMatrix())
        self.mark_exit_tiles(room_name, cost_matrix, opts)
        self.mark_flags(room_name, cost_matrix, opts)
        if self.set_max_avoid(room_name, cost_matrix, opts):
            return cost_matrix

        def wall_at(x, y):
            return Game.map.getTerrainAt(x, y, room_name) == 'wall'

        def road_at(x, y):
            for s in room.look_at(LOOK_STRUCTURES, x, y):
                if s.structureType == STRUCTURE_ROAD:
                    return True
            for s in room.look_at(LOOK_CONSTRUCTION_SITES, x, y):
                if s.structureType == STRUCTURE_ROAD:
                    return True
            return False

        def set_matrix(stype, pos, planned):
            if stype == STRUCTURE_ROAD or stype == STRUCTURE_RAMPART or stype == STRUCTURE_CONTAINER:
                if stype == STRUCTURE_ROAD and use_roads \
                        and not flags.look_for(room, pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD):
                    # TODO: this should really just be a method on top of this method to do this
                    if cost_matrix.get(pos.x, pos.y) > 2:
                        if this_room_future_roads:
                            # Plains cost is 4 for when planning with future road places
                            if planned:
                                cost_matrix.set(pos.x, pos.y, cost_matrix.get(pos.x, pos.y) - 1)
                            else:
                                cost_matrix.set(pos.x, pos.y, cost_matrix.get(pos.x, pos.y) - 2)
                        else:
                            cost_matrix.set(pos.x, pos.y, cost_matrix.get(pos.x, pos.y) - 2)

                        return  # Don't set roads to low-cost if they're already set to high-cost
                    if this_room_future_roads:
                        # Base is 4 for when planning with future road places
                        if planned:
                            cost_matrix.set(pos.x, pos.y, 4)
                        else:
                            cost_matrix.set(pos.x, pos.y, 3)
                    else:
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
                        if not road_at(x, y) and not wall_at(x, y) and cost_matrix.get(x, y) < 10 * if_roads_multiplier:
                            cost_matrix.set(x, y, 10 * if_roads_multiplier)
            elif (stype == STRUCTURE_CONTROLLER and not going_to_controller) or \
                    (stype == "this_is_a_source" and not going_to_source):
                for x in range(pos.x - 3, pos.x + 4):
                    for y in range(pos.y - 3, pos.y + 4):
                        if not road_at(x, y) and not wall_at(x, y) and cost_matrix.get(x, y) < 5 * if_roads_multiplier:
                            cost_matrix.set(x, y, 5 * if_roads_multiplier)
                for x in range(pos.x - 2, pos.x + 3):
                    for y in range(pos.y - 2, pos.y + 3):
                        if not wall_at(x, y) and cost_matrix.get(x, y) < 7 * if_roads_multiplier:
                            cost_matrix.set(x, y, 7 * if_roads_multiplier)
                for x in range(pos.x - 1, pos.x + 2):
                    for y in range(pos.y - 1, pos.y + 2):
                        if not wall_at(x, y) and cost_matrix.get(x, y) < 20 * if_roads_multiplier:
                            cost_matrix.set(x, y, 20 * if_roads_multiplier)
            elif stype == "this_is_a_source":  # and going to source:
                if this_room_future_roads:
                    if room.my:
                        for x in range(pos.x - 2, pos.x + 3):
                            for y in range(pos.y - 2, pos.y + 3):
                                if not wall_at(x, y) and cost_matrix.get(x, y) < 9 * if_roads_multiplier:
                                    cost_matrix.set(x, y, 9 * if_roads_multiplier)
                    else:
                        for x in range(pos.x - 5, pos.x + 6):
                            for y in range(pos.y - 5, pos.y + 6):
                                if not wall_at(x, y) and cost_matrix.get(x, y) < 6 * if_roads_multiplier:
                                    cost_matrix.set(x, y, 6 * if_roads_multiplier)
                        for x in range(pos.x - 3, pos.x + 4):
                            for y in range(pos.y - 3, pos.y + 4):
                                if not wall_at(x, y) and cost_matrix.get(x, y) < 8 * if_roads_multiplier:
                                    cost_matrix.set(x, y, 8 * if_roads_multiplier)
                for x in range(pos.x - 1, pos.x + 2):
                    for y in range(pos.y - 1, pos.y + 2):
                        if not wall_at(x, y) and cost_matrix.get(x, y) < 13 * if_roads_multiplier:
                            cost_matrix.set(x, y, 13 * if_roads_multiplier)
            cost_matrix.set(pos.x, pos.y, 255)

        for struct in room.find(FIND_STRUCTURES):
            set_matrix(struct.structureType, struct.pos, False)
        for site in room.find(FIND_CONSTRUCTION_SITES):
            set_matrix(site.structureType, site.pos, True)
        for flag, stype in flags.find_by_main_with_sub(room, flags.MAIN_BUILD):
            set_matrix(flags.flag_sub_to_structure_type[stype], flag.pos, True)
        for source in room.find(FIND_SOURCES):
            set_matrix("this_is_a_source", source.pos, False)

        # Make room for the link manager creep! This can cause problems if not included.
        if room.my and room.room.storage and room.links.main_link:
            ml = room.links.main_link
            storage = room.room.storage
            if ml.pos.x == storage.pos.x and abs(ml.pos.y - storage.pos.y) == 2 \
                    and movement.is_block_empty(room, ml.pos.x, (ml.pos.y + storage.pos.y) / 2):
                cost_matrix.set(ml.pos.x, (ml.pos.y + storage.pos.y) / 2, 255)
            elif ml.pos.y == storage.pos.y and abs(ml.pos.x - storage.pos.x) == 2 \
                    and movement.is_block_empty(room, (ml.pos.x + storage.pos.x) / 2, ml.pos.y):
                cost_matrix.set((ml.pos.x + storage.pos.x) / 2, ml.pos.y, 255)
            else:
                for x in range(ml.pos.x - 1, ml.pos.x + 2):
                    for y in range(ml.pos.y - 1, ml.pos.y + 2):
                        if abs(storage.pos.x - x) <= 1 and abs(storage.pos.y - y) <= 1:
                            cost_matrix.set(x, y, 255)

        if not room.my and future_chosen:  # Cache before adding this_room_future_roads costs
            serialized = JSON.stringify(cost_matrix.serialize())
            global_cache.set("{}_cost_matrix_{}".format(room_name, if_roads_multiplier), serialized, 10000)

        if this_room_future_roads:
            for pos in this_room_future_roads:
                now = cost_matrix.get(pos.x, pos.y)
                if now <= 4:
                    cost_matrix.set(pos.x, pos.y, 2)
                else:
                    cost_matrix.set(pos.x, pos.y, now - 2)
        return cost_matrix

    def _get_callback(self, origin, destination, opts):
        return lambda room_name: self._new_cost_matrix(room_name, origin, destination, opts)

    def get_default_max_ops(self, origin, destination, opts):
        linear_distance = movement.chebyshev_distance_room_pos(origin, destination)
        ops = linear_distance * 200
        if opts["dfr"]:
            ops *= 5
        elif opts["use_roads"]:
            ops *= 2
        return ops

    def get_serialized_path_obj(self, origin, destination, opts=None):
        if opts:
            roads_better = opts["use_roads"] if "use_roads" in opts else True
            ignore_swamp = opts["ignore_swamp"] if "ignore_swamp" in opts else False
            range = opts["range"] if "range" in opts else 1
            decided_future_roads = opts["decided_future_roads"] if "decided_future_roads" in opts else None
            max_ops = opts["max_ops"] if "max_ops" in opts else self.get_default_max_ops(origin, destination,
                                                                                         {"use_roads": roads_better,
                                                                                          "dfr": decided_future_roads})
            max_rooms = opts["max_rooms"] if "max_rooms" in opts else 16
            keep_for = opts["keep_for"] if "keep_for" in opts else 0
            max_avoid = opts["avoid_rooms"] if "avoid_rooms" in opts else None
        else:
            roads_better = True
            ignore_swamp = False
            range = 1
            max_rooms = 16
            decided_future_roads = None
            max_ops = self.get_default_max_ops(origin, destination, {"use_roads": roads_better,
                                                                     "dfr": decided_future_roads})
            keep_for = 0
            max_avoid = None

        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos
        if ignore_swamp:
            key = "path_{}_{}_{}_{}_{}_{}_swl".format(origin.roomName, origin.x, origin.y,
                                                      destination.roomName, destination.x, destination.y)
        else:
            key = "path_{}_{}_{}_{}_{}_{}".format(origin.roomName, origin.x, origin.y,
                                                  destination.roomName, destination.x, destination.y)

        serialized_path_obj = global_cache.get(key)
        if serialized_path_obj is not None:
            return serialized_path_obj

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

        result = PathFinder.search(origin, {"pos": destination, "range": range}, {
            "plainCost": 5 if decided_future_roads else (2 if roads_better else 1),
            "swampCost": (2 if roads_better else 1) if ignore_swamp else (10 if roads_better else 5),
            "roomCallback": self._get_callback(origin, destination, {
                "roads": roads_better,
                "future_chosen": decided_future_roads,
                "max_avoid": max_avoid,
            }),
            "maxRooms": max_rooms,
            "maxOps": max_ops,
        })

        print("[honey] Calculated new path from {} to {} in {} ops.".format(
            origin, destination, result.ops))
        if result.incomplete:
            print("[honey] WARNING: Calculated incomplete path.")
            if roads_better:
                print("[honey] Trying recalculation without prefering roads.")
                return self.get_serialized_path_obj(origin, destination, _.create(opts, {'use_roads': False}))
        # TODO: make our own serialization format. This wouldn't be too much of a stretch, since we already have to do
        # all of this to convert PathFinder results into a Room-compatible format.
        room_to_path_obj = pathfinder_path_to_room_to_path_obj(origin, result.path)
        if room_to_path_obj is None:
            return None
        if not (keep_for > 0):
            all_viewed = True
            all_owned = True
            all_paved = True
            for pos in result.path:
                room = self.hive.get_room(pos.roomName)
                if not room:
                    all_owned = False
                    all_viewed = False
                    all_paved = False
                    break
                if not room.my:
                    all_owned = False
                if (not _.find(room.look_at(LOOK_STRUCTURES, pos.x, pos.y),
                               lambda s: s.structureType == STRUCTURE_ROAD)
                    and not _.find(room.look_at(LOOK_CONSTRUCTION_SITES, pos.x, pos.y)),
                    lambda s: s.structureType == STRUCTURE_ROAD):
                    all_paved = False

            keep_for = 20000
            if all_paved:
                keep_for *= 4
            if all_owned:
                keep_for *= 2
            if not all_viewed:
                # Don't constantly re-calculate super-long paths that we can't view the rooms for.
                if len(Object.keys(room_to_path_obj)) < 4:
                    keep_for /= 4
        serialized_path_obj = {key: Room.serializePath(value) for key, value in room_to_path_obj.items()}
        global_cache.set(key, serialized_path_obj, keep_for)
        return serialized_path_obj

    def find_path(self, origin, destination, opts=None):
        if opts and "current_room" in opts:
            current_room = opts["current_room"]
            if current_room:
                if current_room.room: current_room = current_room.room
                if current_room.name: current_room = current_room.name
        else:
            current_room = "full"

        serialized_path_obj = self.get_serialized_path_obj(origin, destination, opts)

        if current_room not in serialized_path_obj:
            return []
        try:
            path = Room.deserializePath(serialized_path_obj[current_room])
        except:
            print("[honey] Serialized path from {} to {} with current-room {} was invalid.".format(
                origin, destination, current_room))
            self.clear_cached_path(origin, destination, opts)
            new_path_obj = self.get_serialized_path_obj(origin, destination, opts)
            if current_room in new_path_obj:
                path = Room.deserializePath(new_path_obj[current_room])
            else:
                return []

        # TODO: do our own serialization format so this isn't neccessary
        for pos in path:
            # while pos.x < 0:
            #     pos.x += 50
            # pos.x %= 50
            # while pos.y < 0:
            #     pos.y += 50
            # pos.y %= 50
            # TODO: use in-place %= operator after https://github.com/QQuick/Transcrypt/issues/134 is fixed.
            # noinspection PyAugmentAssignment
            pos.x = pos.x % 50
            # noinspection PyAugmentAssignment
            pos.y = pos.y % 50
        return path

    def clear_cached_path(self, origin, destination, opts=None):
        if opts:
            ignore_swamp = opts["ignore_swamp"] if "ignore_swamp" in opts else False
        else:
            ignore_swamp = False

        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos
        if ignore_swamp:
            key = "path_{}_{}_{}_{}_{}_{}_swl".format(origin.roomName, origin.x, origin.y,
                                                      destination.roomName, destination.x, destination.y)
        else:
            key = "path_{}_{}_{}_{}_{}_{}".format(origin.roomName, origin.x, origin.y,
                                                  destination.roomName, destination.x, destination.y)
        global_cache.rem(key)

    def list_of_room_positions_in_path(self, origin, destination, opts=None):
        """
        Gets a list of room positions in the path. The positions are guaranteed to be in order for each room, but it is
        not guaranteed that the rooms will be in order. This is retrieved from cached memory, but a new list to return
        is created each call, and each RoomPosition is created fresh each call.
        """
        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos

        path_obj = self.get_serialized_path_obj(origin, destination, opts)

        final_list = []

        for room_name, serialized_path in _.pairs(path_obj):
            if room_name == "full":
                continue
            path = Room.deserializePath(serialized_path)
            for pos in path:
                if 0 < pos.x < 50 and 0 < pos.y < 50:
                    final_list.append(__new__(RoomPosition(pos.x, pos.y, room_name)))
        return final_list


profiling.profile_whitelist(HoneyTrails, [
    "find_path",
])
