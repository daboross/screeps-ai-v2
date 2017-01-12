from cache import global_cache
from constants import SK_LAIR_SOURCE_NOTED, SLIGHTLY_AVOID, SPAWN_FILL_WAIT, UPGRADER_SPOT, \
    global_cache_mining_roads_suffix
from creep_management import mining_paths
from jstools.screeps_constants import *
from position_management import flags
from utilities import hostile_utils, movement
from utilities.movement import dxdy_to_direction

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_path_cached_data_key_full_path = 'full'
_path_cached_data_key_room_order = 'o'
_path_cached_data_key_length = 'l'


def pathfinder_path_to_room_to_path_obj(origin, input_path):
    result_obj = {}
    result_obj[_path_cached_data_key_room_order] = list_of_rooms = []
    last_room = None
    current_path = None
    last_x, last_y = origin.x, origin.y
    reroute_end_dx, reroute_end_dy = None, None
    for pos in input_path:
        if last_room != pos.roomName:
            if pos.roomName in result_obj:
                # we're visiting the same room twice!
                msg = (
                    '[honey] WARNING: Visiting same room ({}) twice in path from {} to {}!'
                    ' This is not fully supported, please be advised!'.format(
                        pos.roomName, origin, input_path[len(input_path) - 1]
                    )
                )
                console.log(msg)
                Game.notify(msg)
                # still, let's try to support it the best we can
                current_path = result_obj[pos.roomName]
                # due to the game's serialization method, positions further than 1 distance apart aren't supported.
                # let's fill that in the best we can - not that well tested, and is only as a last resort.
                while True:
                    last_pos = current_path[len(current_path) - 1]
                    x_diff = last_pos.x - pos.x
                    y_diff = last_pos.y - pos.y
                    if x_diff < -1:
                        dx = 1
                        if y_diff < -1:
                            dy = 1
                        elif y_diff > 1:
                            dy = -1
                        else:
                            dy = 1
                    elif x_diff > 1:
                        dx = -1
                        if y_diff < -1:
                            dy = 1
                        elif y_diff > 1:
                            dy = -1
                        else:
                            dy = 0
                    else:
                        dx = 0
                        if y_diff < -1:
                            dy = 1
                        elif y_diff > 1:
                            dy = -1
                        else:
                            break
                    current_path.push({
                        'x': last_pos.x + dx,
                        'y': last_pos.y + dy,
                        'dx': dx,
                        'dy': dy,
                        'direction': dxdy_to_direction(dx, dy)
                    })
            else:
                current_path = []
                # this is passed by reference, so we just set it here
                result_obj[pos.roomName] = current_path
                last_room = pos.roomName
                list_of_rooms.push(pos.roomName)
        if reroute_end_dx is not None:
            dx = reroute_end_dx
            dy = reroute_end_dy
            reroute_end_dx, reroute_end_dy = None, None
        else:
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
            if pos.endOfReroute:
                reroute_end_dx = dx
                reroute_end_dy = dy
        if dx < -1 or dx > 1:
            print("[honey][pathfinder_to_regular_path] dx found from {} to {}: {}".format(
                last_x, pos.x, dx
            ))
        if dy < -1 or dy > 1:
            print("[honey][pathfinder_to_regular_path] dy found from {} to {}: {}".format(
                last_y, pos.y, dy
            ))
        direction = dxdy_to_direction(dx, dy)
        if direction is None:
            print("[honey][pathfinder_to_regular_path] Unknown direction for pos: {},{}, last: {},{}".format(
                pos.x, pos.y, last_x, last_y))
            return None
        last_x = pos.x
        last_y = pos.y
        item = {
            'x': pos.x,
            'y': pos.y,
            'dx': dx,
            'dy': dy,
            'direction': direction
        }
        current_path.append(item)
    result_obj[_path_cached_data_key_length] = len(input_path) - len(list_of_rooms) + 1
    return result_obj


def clear_serialized_cost_matrix(room_name):
    for i in range(0, 10):
        key = "{}_cost_matrix_{}".format(room_name, i)
        if global_cache.has(key):
            global_cache.rem(key)


def get_global_cache_key(origin, destination, opts):
    if opts:
        if opts['ignore_swamp']:  # Default false
            return '_'.join([
                'path',
                origin.roomName,
                origin.x,
                origin.y,
                destination.roomName,
                destination.x,
                destination.y,
                'swl'
            ])
        elif opts['paved_for']:  # Default false
            return '_'.join([
                'path',
                origin.roomName,
                origin.x,
                origin.y,
                destination.roomName,
                destination.x,
                destination.y,
                global_cache_mining_roads_suffix
            ])

    return '_'.join([
        'path',
        origin.roomName,
        origin.x,
        origin.y,
        destination.roomName,
        destination.x,
        destination.y,
    ])


__pragma__('fcall')


class HoneyTrails:
    """
    :type hive: empire.hive.HiveMind
    """

    def __init__(self, hive):
        self.hive = hive

    def mark_exit_tiles(self, room_name, matrix, opts):
        plain_cost = opts['plain_cost']

        room_x, room_y = movement.parse_room_to_xy(room_name)
        rrx = (-room_x - 1 if room_x < 0 else room_x) % 10
        rry = (-room_y - 1 if room_y < 0 else room_y) % 10
        if rrx == 0 or rry == 0:
            for x in [0, 49]:
                for y in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 1 * plain_cost)
            for y in [0, 49]:
                for x in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 1 * plain_cost)
        else:
            for x in [0, 49]:
                for y in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 2 * plain_cost)
            for y in [0, 49]:
                for x in range(0, 50):
                    if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                        matrix.set(x, y, 2 * plain_cost)

    def mark_flags(self, room_name, matrix, opts):
        for flag in flags.find_flags(room_name, SK_LAIR_SOURCE_NOTED):
            for x in range(flag.pos.x - 4, flag.pos.x + 5):
                for y in range(flag.pos.y - 4, flag.pos.y + 5):
                    matrix.set(x, y, 255)

        slightly_avoid = flags.find_flags(room_name, SLIGHTLY_AVOID) \
            .concat(flags.find_flags(room_name, UPGRADER_SPOT))
        if len(slightly_avoid):
            cost = 2 * opts['plain_cost']
            for flag in slightly_avoid:
                if Game.map.getTerrainAt(flag.pos.x, flag.pos.y, room_name) != 'wall' \
                        and matrix.get(flag.pos.x, flag.pos.y) < cost:
                    matrix.set(flag.pos.x, flag.pos.y, cost)

    def set_max_avoid(self, room_name, matrix, opts):
        if opts['max_avoid']:
            plain_cost = opts['plain_cost']
            if room_name in opts['max_avoid']:
                print("Setting max_avoid in room {}".format(room_name))
                for x in range(0, 49):
                    for y in range(0, 49):
                        if Game.map.getTerrainAt(x, y, room_name) != 'wall':
                            matrix.set(x, y, plain_cost * 20)
                return True
            for direction, other_room in _.pairs(Game.map.describeExits(room_name)):
                if other_room in opts['max_avoid']:
                    print("Setting max_avoid on the {} of room {}".format(
                        {TOP: "top", BOTTOM: "bottom", LEFT: "left", RIGHT: "right"}[direction], room_name))
                    if direction == TOP:
                        for x in range(0, 49):
                            if Game.map.getTerrainAt(x, 0, room_name) != 'wall':
                                matrix.set(x, 0, 20 * plain_cost)
                    elif direction == BOTTOM:
                        for x in range(0, 49):
                            if Game.map.getTerrainAt(x, 49, room_name) != 'wall':
                                matrix.set(x, 49, 20 * plain_cost)
                    elif direction == LEFT:
                        for y in range(0, 49):
                            if Game.map.getTerrainAt(0, y, room_name) != 'wall':
                                matrix.set(0, y, 20 * plain_cost)
                    elif direction == RIGHT:
                        for y in range(0, 49):
                            if Game.map.getTerrainAt(49, y, room_name) != 'wall':
                                matrix.set(49, y, 20 * plain_cost)

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
        plain_cost = opts['plain_cost']
        swamp_cost = opts['swamp_cost']

        serialization_key = "{}_cost_matrix_{}".format(room_name, plain_cost)
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

        def increase_by(x, y, added):
            existing = cost_matrix.get(x, y)
            if existing == 0:
                terrain = Game.map.getTerrainAt(x, y, room_name)
                if terrain[0] is 'p':
                    existing = plain_cost
                elif terrain[0] is 's':
                    existing = swamp_cost
                else:
                    return
            cost_matrix.set(x, y, existing + added)

        if room.my:
            spawn_fill_wait_flags = flags.find_flags(room, SPAWN_FILL_WAIT)
            if len(spawn_fill_wait_flags):
                avoid_extensions = False
            else:
                avoid_extensions = True
        else:
            avoid_extensions = False
            spawn_fill_wait_flags = []

        if room.my:
            upgrader_wait_flags = flags.find_flags(room, UPGRADER_SPOT)
            if len(upgrader_wait_flags):
                avoid_controller = False
            else:
                avoid_controller = True
        else:
            avoid_controller = False
            upgrader_wait_flags = []

        cost_matrix = __new__(PathFinder.CostMatrix())

        self.mark_exit_tiles(room_name, cost_matrix, opts)
        self.mark_flags(room_name, cost_matrix, opts)

        def set_matrix(stype, pos, my):
            if stype == STRUCTURE_ROAD or (stype == STRUCTURE_RAMPART and my) or stype == STRUCTURE_CONTAINER:
                if stype == STRUCTURE_ROAD:
                    existing = cost_matrix.get(pos.x, pos.y)
                    if existing < 255 and not wall_at(pos.x, pos.y):
                        if existing != 0 and existing > plain_cost:  # manually set
                            cost_matrix.set(pos.x, pos.y, existing - 2)
                        else:
                            cost_matrix.set(pos.x, pos.y, 1)
                return
            cost_matrix.set(pos.x, pos.y, 255)
            if my:
                if avoid_extensions and (stype == STRUCTURE_SPAWN or stype == STRUCTURE_EXTENSION):
                    for x in range(pos.x - 1, pos.x + 2):
                        for y in range(pos.y - 1, pos.y + 2):
                            increase_by(x, y, 9 * plain_cost)
                elif stype == STRUCTURE_STORAGE or stype == STRUCTURE_LINK:
                    for x in range(pos.x - 1, pos.x + 2):
                        for y in range(pos.y - 1, pos.y + 2):
                            increase_by(x, y, 6 * plain_cost)
                elif avoid_controller and stype == STRUCTURE_CONTROLLER:
                    for x in range(pos.x - 3, pos.x + 4):
                        for y in range(pos.y - 3, pos.y + 4):
                            increase_by(x, y, 4 * plain_cost)
                    for x in range(pos.x - 2, pos.x + 3):
                        for y in range(pos.y - 2, pos.y + 3):
                            increase_by(x, y, 2 * plain_cost)
                    for x in range(pos.x - 1, pos.x + 2):
                        for y in range(pos.y - 1, pos.y + 2):
                            increase_by(x, y, 13 * plain_cost)
                elif stype == '--source':
                    for x in range(pos.x - 3, pos.x + 4):
                        for y in range(pos.y - 3, pos.y + 4):
                            increase_by(x, y, 4 * plain_cost)
                    for x in range(pos.x - 2, pos.x + 3):
                        for y in range(pos.y - 2, pos.y + 3):
                            increase_by(x, y, 2 * plain_cost)
                    for x in range(pos.x - 1, pos.x + 2):
                        for y in range(pos.y - 1, pos.y + 2):
                            increase_by(x, y, 11 * plain_cost)
            cost_matrix.set(pos.x, pos.y, 255)

        for struct in room.find(FIND_STRUCTURES):
            set_matrix(struct.structureType, struct.pos, struct.my or (not struct.owner))
        for site in room.find(FIND_CONSTRUCTION_SITES):
            set_matrix(site.structureType, site.pos, site.my)
        for flag, stype in flags.find_by_main_with_sub(room, flags.MAIN_BUILD):
            set_matrix(flags.flag_sub_to_structure_type[stype], flag.pos, True)
        for source in room.find(FIND_SOURCES):
            set_matrix("--source", source.pos, True)
        for flag in spawn_fill_wait_flags:
            cost_matrix.set(flag.pos.x, flag.pos.y, 255)
        for flag in upgrader_wait_flags:
            cost_matrix.set(flag.pos.x, flag.pos.y, 255)

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
        paved_for = opts['paved_for']

        if hostile_utils.enemy_room(room_name):
            if room_name != origin.roomName and room_name != destination.roomName:
                # print("[honey] Avoiding room {}.".format(room_name))
                return False
            else:
                print("[honey] Warning: path {}-{} ends up in an enemy room ({})!"
                      .format(origin, destination, room_name))

        if_roads_multiplier = opts['plain_cost']
        plain_cost = opts['plain_cost']
        swamp_cost = opts['swamp_cost']
        room = self.hive.get_room(room_name)
        if (room_name != origin.roomName and room_name != destination.roomName and not paved_for) or not room:
            if paved_for:
                serialized = global_cache.get("{}_cost_matrix_{}".format(room_name, if_roads_multiplier))
                if serialized:
                    matrix = PathFinder.CostMatrix.deserialize(JSON.parse(serialized))
                    self.set_max_avoid(room_name, matrix, opts)
                    mining_paths.set_decreasing_cost_matrix_costs(
                        room_name,
                        paved_for,
                        matrix,
                        opts['plain_cost'],
                        opts['swamp_cost'],
                        3,
                    )
            else:
                matrix = self.get_generic_cost_matrix(room_name, opts)
                if matrix:
                    return matrix

            matrix = __new__(PathFinder.CostMatrix())
            # Avoid stepping on exit tiles unnecessarily
            self.mark_exit_tiles(room_name, matrix, opts)
            self.mark_flags(room_name, matrix, opts)
            self.set_max_avoid(room_name, matrix, opts)
            return matrix

        if room.my:
            spawn_fill_wait_flags = flags.find_flags(room, SPAWN_FILL_WAIT)
            if len(spawn_fill_wait_flags):
                avoid_extensions = False
            else:
                avoid_extensions = True
                if destination.roomName == room_name:
                    for s in room.look_at(LOOK_STRUCTURES, destination):
                        if s.structureType == STRUCTURE_SPAWN or s.structureType == STRUCTURE_EXTENSION:
                            avoid_extensions = False
        else:
            avoid_extensions = False
            spawn_fill_wait_flags = []

        if room.my:
            upgrader_wait_flags = flags.find_flags(room, UPGRADER_SPOT)
            if len(upgrader_wait_flags):
                avoid_controller = False
            else:
                avoid_controller = True
        else:
            avoid_controller = False
            upgrader_wait_flags = []

        cost_matrix = __new__(PathFinder.CostMatrix())

        self.mark_exit_tiles(room_name, cost_matrix, opts)
        self.mark_flags(room_name, cost_matrix, opts)

        if self.set_max_avoid(room_name, cost_matrix, opts):
            return cost_matrix

        def increase_by(x, y, added):
            existing = cost_matrix.get(x, y)
            if existing == 0:
                terrain = Game.map.getTerrainAt(x, y, room_name)
                if terrain[0] is 'p':
                    existing = plain_cost
                elif terrain[0] is 's':
                    existing = swamp_cost
                else:
                    return
            cost_matrix.set(x, y, existing + added)

        def set_matrix(stype, pos, planned, my):
            if stype == STRUCTURE_ROAD or (stype == STRUCTURE_RAMPART and my) or stype == STRUCTURE_CONTAINER:
                if stype == STRUCTURE_ROAD:
                    # TODO: this should really just be a method on top of this method to do this
                    if paved_for and not planned:
                        existing = cost_matrix.get(pos.x, pos.y)
                        if existing == 0:
                            terrain = Game.map.getTerrainAt(pos.x, pos.y, room_name)
                            if terrain[0] is 'p':
                                existing = plain_cost
                            elif terrain[0] is 's':
                                existing = swamp_cost
                            else:
                                return  # wall
                        if 1 < existing < 255:
                            cost_matrix.set(pos.x, pos.y, existing - 1)
                    else:
                        existing = cost_matrix.get(pos.x, pos.y)
                        if existing != 0 and existing > plain_cost:  # manually set
                            cost_matrix.set(pos.x, pos.y, existing - 2)
                        else:
                            cost_matrix.set(pos.x, pos.y, 1)
                return
            if pos.x == destination.x and pos.y == destination.y:
                return
            if pos.x == origin.x and pos.y == origin.y:
                return
            cost_matrix.set(pos.x, pos.y, 255)
            if abs(pos.x - origin.x) <= 1 and abs(pos.y - origin.y) <= 1:
                return
            if abs(pos.x - destination.x) <= 1 and abs(pos.y - destination.y) <= 1:
                return
            if my:
                if avoid_extensions and (stype == STRUCTURE_SPAWN or stype == STRUCTURE_EXTENSION):
                    for x in range(pos.x - 1, pos.x + 2):
                        for y in range(pos.y - 1, pos.y + 2):
                            increase_by(x, y, 9 * plain_cost)
                elif stype == STRUCTURE_STORAGE or stype == STRUCTURE_LINK:
                    for x in range(pos.x - 1, pos.x + 2):
                        for y in range(pos.y - 1, pos.y + 2):
                            increase_by(x, y, 6 * plain_cost)
                elif avoid_controller and stype == STRUCTURE_CONTROLLER:
                    for x in range(pos.x - 3, pos.x + 4):
                        for y in range(pos.y - 3, pos.y + 4):
                            increase_by(x, y, 4 * plain_cost)
                    for x in range(pos.x - 2, pos.x + 3):
                        for y in range(pos.y - 2, pos.y + 3):
                            increase_by(x, y, 2 * plain_cost)
                    for x in range(pos.x - 1, pos.x + 2):
                        for y in range(pos.y - 1, pos.y + 2):
                            increase_by(x, y, 13 * plain_cost)
                elif stype == '--source':
                    if paved_for:
                        if room.my:
                            for x in range(pos.x - 2, pos.x + 3):
                                for y in range(pos.y - 2, pos.y + 3):
                                    increase_by(x, y, 3 * plain_cost)
                            for x in range(pos.x - 1, pos.x + 2):
                                for y in range(pos.y - 1, pos.y + 2):
                                    increase_by(x, y, 11 * plain_cost)
                        else:
                            for x in range(pos.x - 3, pos.x + 4):
                                for y in range(pos.y - 3, pos.y + 4):
                                    increase_by(x, y, 6 * plain_cost)
                            for x in range(pos.x - 1, pos.x + 2):
                                for y in range(pos.y - 1, pos.y + 2):
                                    increase_by(x, y, 6 * plain_cost)
                    else:
                        for x in range(pos.x - 3, pos.x + 4):
                            for y in range(pos.y - 3, pos.y + 4):
                                increase_by(x, y, 4 * plain_cost)
                        for x in range(pos.x - 2, pos.x + 3):
                            for y in range(pos.y - 2, pos.y + 3):
                                increase_by(x, y, 2 * plain_cost)
                        for x in range(pos.x - 1, pos.x + 2):
                            for y in range(pos.y - 1, pos.y + 2):
                                increase_by(x, y, 11 * plain_cost)
            cost_matrix.set(pos.x, pos.y, 255)

        for struct in room.find(FIND_STRUCTURES):
            if struct.structureType != STRUCTURE_CONTROLLER or struct.my:
                set_matrix(struct.structureType, struct.pos, False, struct.my or (not struct.owner))
        for site in room.find(FIND_CONSTRUCTION_SITES):
            set_matrix(site.structureType, site.pos, True, site.my)
        for flag, stype in flags.find_by_main_with_sub(room, flags.MAIN_BUILD):
            set_matrix(flags.flag_sub_to_structure_type[stype], flag.pos, True, True)
        for source in room.find(FIND_SOURCES):
            set_matrix("--source", source.pos, False, True)
        for flag in spawn_fill_wait_flags:
            cost_matrix.set(flag.pos.x, flag.pos.y, 255)
        for flag in upgrader_wait_flags:
            cost_matrix.set(flag.pos.x, flag.pos.y, 255)

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

        if paved_for:
            mining_paths.set_decreasing_cost_matrix_costs(
                room_name,
                paved_for,
                cost_matrix,
                plain_cost,
                swamp_cost,
                2,
            )
        return cost_matrix

    def _get_callback(self, origin, destination, opts):
        return lambda room_name: self._new_cost_matrix(room_name, origin, destination, opts)

    def get_default_max_ops(self, origin, destination, opts):
        linear_distance = movement.chebyshev_distance_room_pos(origin, destination)
        ops = linear_distance * 200
        if opts['paved_for']:
            ops *= 5
        elif 'use_roads' not in opts or opts['use_roads']:
            ops *= 2
        return ops

    def _get_raw_path(self, origin, destination, opts=None):
        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos

        if opts:
            roads_better = opts["use_roads"] if "use_roads" in opts else True
            ignore_swamp = opts["ignore_swamp"] if "ignore_swamp" in opts else False
            pf_range = opts["range"] if "range" in opts else 1
            paved_for = opts['paved_for'] if 'paved_for' in opts else None
            max_ops = opts["max_ops"] if "max_ops" in opts else self.get_default_max_ops(origin, destination, opts)
            max_rooms = opts["max_rooms"] if "max_rooms" in opts else 16
            max_avoid = opts["avoid_rooms"] if "avoid_rooms" in opts else None
        else:
            roads_better = True
            ignore_swamp = False
            pf_range = 1
            max_rooms = 16
            paved_for = None
            max_ops = self.get_default_max_ops(origin, destination, {'use_roads': roads_better})
            max_avoid = None

        if 'reroute' in Game.flags and 'reroute_destination' in Game.flags:
            reroute_start = Game.flags['reroute']
            reroute_destination = Game.flags['reroute_destination']
            if movement.chebyshev_distance_room_pos(origin, reroute_start) \
                    + movement.chebyshev_distance_room_pos(reroute_destination, destination) \
                    < movement.chebyshev_distance_room_pos(origin, destination):
                # Let's path through the portal!
                path1 = self._get_raw_path(origin, reroute_start)
                if not len(path1) or (path1[len(path1) - 1].isNearTo(reroute_start.pos)
                                      and not path1[len(path1) - 1].isEqualTo(reroute_start.pos)):
                    pos = __new__(RoomPosition(reroute_start.pos.x, reroute_start.pos.y, reroute_start.pos.roomName))
                    pos.endOfReroute = True
                    path1.push(pos)
                path2 = self._get_raw_path(reroute_destination, destination)
                return path1.concat(path2)

        if paved_for:
            plain_cost = 5
            swamp_cost = 10
        elif ignore_swamp:
            plain_cost = 1
            swamp_cost = 1
        elif roads_better:
            plain_cost = 2
            swamp_cost = 10
        else:
            plain_cost = 1
            swamp_cost = 5

        result = PathFinder.search(origin, {"pos": destination, "range": pf_range}, {
            "plainCost": plain_cost,
            "swampCost": swamp_cost,
            "roomCallback": self._get_callback(origin, destination, {
                "roads": roads_better,
                "paved_for": paved_for,
                "max_avoid": max_avoid,
                "plain_cost": plain_cost,
                "swamp_cost": swamp_cost,
            }),
            "maxRooms": max_rooms,
            "maxOps": max_ops,
        })

        print("[honey] Calculated new path from {} to {} in {} ops.".format(
            origin, destination, result.ops))
        path = result.path
        if result.incomplete:
            print(
                "[honey] WARNING: Calculated incomplete path."
                " Chebyshev distance: {}."
                " Path distance found: {}."
                " Ops used: {}."
                " Max ops: {}."
                " Max rooms: {}.".format(
                    movement.chebyshev_distance_room_pos(origin, destination),
                    len(result.path), result.ops, max_ops, max_rooms,
                )
            )
            if roads_better:
                print("[honey] Trying recalculation without preferring roads.")
                return self._get_raw_path(origin, destination, _.create(opts, {'use_roads': False}))
            if len(result.path) > 15:
                path_start = path.slice(0, -10)
                midpoint = path_start[len(path_start) - 1]

                print("[honey] OK, trying to build the rest of the path from {} to {}, starting at {}"
                      .format(origin, destination, midpoint))
                second_path_result = PathFinder.search(midpoint, {"pos": destination, "range": pf_range}, {
                    "plainCost": plain_cost,
                    "swampCost": swamp_cost,
                    "roomCallback": self._get_callback(origin, destination, {
                        "roads": roads_better,
                        "paved_for": paved_for,
                        "max_avoid": max_avoid,
                        "plain_cost": plain_cost,
                        "swamp_cost": swamp_cost,
                    }),
                    "maxRooms": max_rooms,
                    "maxOps": max_ops,
                })
                if second_path_result.incomplete:
                    print("[honey] Second path result incomplete, not appending.")
                else:
                    print("[honey] Second path result complete! Concatenating paths!")
                    path = path_start.concat(second_path_result.path)
        if paved_for:
            if paved_for.name:
                mine_name = paved_for.name
                spawn_id = 'none'
            else:
                mine_name = paved_for[0].name
                spawn_id = paved_for[1].id
            print("[honey] Registering new paved path for mine {}, spawn {}.".format(mine_name, spawn_id))
            mining_paths.register_new_mining_path(paved_for, path)
        return path

    def get_serialized_path_obj(self, origin, destination, opts=None):
        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos

        if opts and 'keep_for' in opts:
            keep_for = opts["keep_for"]
        else:
            keep_for = 0

        cache_key = get_global_cache_key(origin, destination, opts)

        serialized_path_obj = global_cache.get(cache_key)
        if serialized_path_obj is not None:
            return serialized_path_obj

        path = self._get_raw_path(origin, destination, opts)
        # TODO: make our own serialization format. This wouldn't be too much of a stretch, since we already have to do
        # all of this to convert PathFinder results into a Room-compatible format.
        room_to_path_obj = pathfinder_path_to_room_to_path_obj(origin, path)
        if room_to_path_obj is None:
            return None
        if not (keep_for > 0):
            all_viewed = True
            all_owned = True
            for pos in path:
                room = self.hive.get_room(pos.roomName)
                if not room:
                    all_owned = False
                    all_viewed = False
                    break
                if not room.my:
                    all_owned = False

            if all_viewed:
                keep_for = 80 * 1000
                if all_owned:
                    keep_for *= 2
            else:
                # Don't constantly re-calculate super-long paths that we can't view the rooms for.
                if len(Object.keys(room_to_path_obj)) < 3:
                    keep_for = 4 * 1000
                elif len(Object.keys(room_to_path_obj)) < 4:
                    keep_for = 10 * 1000
                else:
                    keep_for = 40 * 1000
        serialized_path_obj = {}
        for room_name in Object.keys(room_to_path_obj):
            if room_name == _path_cached_data_key_room_order or room_name == _path_cached_data_key_length:
                serialized_path_obj[room_name] = room_to_path_obj[room_name]
            else:
                serialized_path_obj[room_name] = Room.serializePath(room_to_path_obj[room_name])
        global_cache.set(cache_key, serialized_path_obj, keep_for)
        return serialized_path_obj

    def completely_repath_and_get_raw_path(self, origin, destination, opts):
        if origin.pos:
            origin = origin.pos
        if destination.pos:
            destination = destination.pos
        if "keep_for" in opts:
            keep_for = opts["keep_for"]
        else:
            raise ValueError("force_complete_repath_and_get_raw_path requires an options object with a"
                             " keep_for property")

        cache_key = get_global_cache_key(origin, destination, opts)

        path = self._get_raw_path(origin, destination, opts)
        room_to_path_obj = pathfinder_path_to_room_to_path_obj(origin, path)
        if room_to_path_obj is not None:
            serialized_path_obj = {}
            for room_name in Object.keys(room_to_path_obj):
                if room_name == _path_cached_data_key_room_order or room_name == _path_cached_data_key_length:
                    serialized_path_obj[room_name] = room_to_path_obj[room_name]
                else:
                    serialized_path_obj[room_name] = Room.serializePath(room_to_path_obj[room_name])
            global_cache.set(cache_key, serialized_path_obj, keep_for)
        return path

    def find_serialized_path(self, origin, destination, opts):
        if opts and "current_room" in opts:
            current_room = opts["current_room"]
            if current_room:
                current_room = current_room.name or current_room
            else:
                raise ValueError("find_serialized_path requires a current_room argument.")
        else:
            raise ValueError("find_serialized_path requires a current_room argument.")

        serialized_path_obj = self.get_serialized_path_obj(origin, destination, opts)

        if current_room in serialized_path_obj:
            return serialized_path_obj[current_room]
        else:
            return ''

    def find_path(self, origin, destination, opts):
        if opts and "current_room" in opts:
            current_room = opts["current_room"]
            if current_room:
                current_room = current_room.name or current_room
            else:
                raise ValueError("find_path requires a current_room argument.")
        else:
            raise ValueError("find_path requires a current_room argument.")

        serialized_path_obj = self.get_serialized_path_obj(origin, destination, opts)

        if serialized_path_obj is None or current_room not in serialized_path_obj:
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

        if _path_cached_data_key_room_order in path_obj:
            list_of_names = path_obj[_path_cached_data_key_room_order]
        else:
            list_of_names = Object.keys(path_obj)

        for room_name in list_of_names:
            if not movement.is_valid_room_name(room_name):  # special key
                continue
            path = Room.deserializePath(path_obj[room_name])
            for pos in path:
                if 0 < pos.x < 50 and 0 < pos.y < 50:
                    final_list.append(__new__(RoomPosition(pos.x, pos.y, room_name)))
        return final_list

    def find_path_length(self, origin, destination, opts=None):
        serialized_path_obj = self.get_serialized_path_obj(origin, destination, opts)
        # TODO: should be we accounting for the path containing two position in the case of edge positions? yes!

        # return len(serialized_path_obj['full'])   # The length of the path
        #  - 4 + 1                                  # The first four characters only represent one position
        #  - (
        # len(Object.keys(serialized_path_obj))     # On each room edge, creeps moving along the path skip one square
        # - 1)                                      # -1 because we want the count of room _exits_, which is one less
        #                                           #  than the room count.
        if _path_cached_data_key_full_path in serialized_path_obj:  # Version 1 stored path
            return len(serialized_path_obj[_path_cached_data_key_full_path]) \
                   - _.sum(Object.keys(serialized_path_obj), lambda n: movement.is_valid_room_name(n)) - 2
        elif _path_cached_data_key_length in serialized_path_obj:  # Version two stored path
            return serialized_path_obj[_path_cached_data_key_length]
        else:  # Unknown format, let's just guesstimate
            total = 1
            for room_name in Object.keys(serialized_path_obj):
                if movement.is_valid_room_name(room_name):
                    # first 4 characters represent 1 position, but also each exit position is doubled per-room
                    # -4 + 1 - 1
                    total += len(serialized_path_obj[room_name]) - 4
            return total


__pragma__('nofcall')
