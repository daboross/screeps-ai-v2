import math
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Tuple, Union, cast

from cache import global_cache
from constants import SLIGHTLY_AVOID, SPAWN_FILL_WAIT, UPGRADER_SPOT, global_cache_mining_paths_suffix, \
    global_cache_roadless_paths_suffix, global_cache_swamp_paths_suffix, global_cache_warpath_suffix, role_miner
from creep_management import mining_paths
from empire import stored_data
from jstools.screeps import *
from position_management import flags
from utilities import movement, positions, robjs
from utilities.movement import dxdy_to_direction

if TYPE_CHECKING:
    from empire.hive import HiveMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

_path_cached_data_key_metadata = 'm'
_path_cached_data_key_full_path = 'full'
_path_cached_data_key_room_order = 'o'
_path_cached_data_key_length = 'l'


def pathfinder_path_to_room_to_path_obj(origin, input_path):
    # type: (RoomPosition, List[RoomPosition]) -> Optional[Dict[str, List[Dict[str, Any]]]]
    result_obj = {}
    list_of_rooms = []
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
                print(msg)
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
                last_room = pos.roomName
            else:
                current_path = []
                # this is passed by reference, so we just set it here
                result_obj[pos.roomName] = current_path
                last_room = pos.roomName
                list_of_rooms.push(pos.roomName)
        if reroute_end_dx is not None:
            # Skip the first position past the reroute end.
            reroute_end_dx, reroute_end_dy = None, None
            last_x = pos.x
            last_y = pos.y
            continue
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
            if pos.end_of_reroute:
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
            if dx == 0 and dy == 0:
                continue
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
    total_length = len(input_path) - len(list_of_rooms) + 1
    result_obj[_path_cached_data_key_metadata] = ','.join([total_length].concat(list_of_rooms))
    return result_obj


def get_global_cache_key(origin, destination, opts):
    # type: (RoomPosition, RoomPosition, Optional[Dict[str, Any]]) -> str
    parts = [
        'path',
        origin.roomName,
        str(origin.x),
        str(origin.y),
        destination.roomName,
        str(destination.x),
        str(destination.y),
    ]

    if opts:
        if opts['ignore_swamp']:  # Default false
            parts.append(global_cache_swamp_paths_suffix)
        elif opts['paved_for']:  # Default false
            parts.append(global_cache_mining_paths_suffix)
        elif 'use_roads' in opts and not opts['use_roads']:  # Default true
            parts.append(global_cache_roadless_paths_suffix)

        if opts['sk_ok']:  # Default false
            parts.append(global_cache_warpath_suffix)

    return '_'.join(parts)


__pragma__('skip')  # Real class defined below


class CustomCostMatrix:
    """
    :type room_name: str
    :type plain_cost: int
    :type swamp_cost: int
    :type cost_matrix: PathFinder.CostMatrix
    """

    def __init__(self, room_name: str, plain_cost: int, swamp_cost: int, debug: bool = False):
        """
        :type room_name: str
        :type plain_cost: int
        :type swamp_cost: int
        """
        self.room_name = room_name
        self.plain_cost = plain_cost
        self.swamp_cost = swamp_cost
        self.cost_matrix = PathFinder.CostMatrix()
        self.debug = not not debug
        raise NotImplementedError

    def get(self, x: int, y: int) -> int:
        pass

    def get_existing(self, x: int, y: int) -> int:
        pass

    def set(self, x: int, y: int, value: int):
        pass

    def set_impassable(self, x: int, y: int):
        pass

    def increase_at(self, x: int, y: int, cost_type: Optional[int], added: int):
        pass

    def visual(self) -> str:
        pass


__pragma__('noskip')


# noinspection PyPep8Naming
def _create_custom_cost_matrix(room_name, plain_cost, swamp_cost, min_cost, debug):  # actual version of the above
    this.cost_matrix = __new__(PathFinder.CostMatrix())
    this.room_name = room_name
    this.plain_cost = plain_cost
    this.swamp_cost = swamp_cost
    this.min_cost = min_cost
    this.added_at = {}
    if debug:
        this.debug = True


def create_custom_cost_matrix(room_name, plain_cost, swamp_cost, min_cost, debug):
    """
    :rtype: CustomCostMatrix
    :param room_name: The room name
    :param plain_cost: The plain cost
    :param swamp_cost: The swamp cost
    :param min_cost: The minimum cost
    :return: The custom cost matrix
    """
    return __new__(_create_custom_cost_matrix(room_name, plain_cost, swamp_cost, min_cost, debug))


def _cma_get(x, y):
    return this.cost_matrix.get(x, y)


def _cma_set(x, y, value):
    if value < this.min_cost:
        value = this.min_cost
    if this.debug:
        print('[DEBUG][ccm][{}] Setting {},{} as {}.'.format(this.room_name, x, y, value))
    return this.cost_matrix.set(x, y, value)


def _cma_set_impassable(x, y):
    if this.debug:
        print('[DEBUG][ccm][{}] Setting {},{} as impassable.'.format(this.room_name, x, y))
    return this.cost_matrix.set(x, y, 255)


def _cma_get_existing(x, y):
    existing = this.cost_matrix.get(x, y)
    if existing == 0:
        terrain = Game.map.getTerrainAt(x, y, this.room_name)
        if terrain[0] is 'p':
            return this.plain_cost
        elif terrain[0] is 's':
            return this.swamp_cost
        else:
            return 255
    return existing


def _cma_increase_at(x, y, cost_type, added):
    if added <= 0:
        return
    existing = this.get_existing(x, y)
    if existing >= 255:
        return

    ser = positions.serialize_xy(x, y)
    if cost_type is not None:
        if cost_type in this.added_at:
            cost_map = this.added_at[cost_type]
        else:
            # noinspection PyUnresolvedReferences
            cost_map = this.added_at[cost_type] = __new__(Set())
        if cost_map.has(ser):
            return
        cost_map.add(ser)

    if this.debug:
        print('[DEBUG][ccm][{}] Increasing {},{} from {} to {}.'
              .format(this.room_name, x, y, existing, existing + added))

    this.cost_matrix.set(x, y, existing + added)


def _cma_visual():
    rows = []
    for y in range(0, 50):
        row = []
        for x in range(0, 50):
            value = this.get(x, y)
            if value == 0:
                terrain = Game.map.getTerrainAt(x, y, this.room_name)
                if terrain[0] is 'p':
                    row.push('  ')
                elif terrain[0] is 's':
                    row.push('SS')
                else:
                    row.push('WW')
            elif value < this.swamp_cost:
                if this.swamp_cost < 10:
                    row.push('R' + str(value))
                else:
                    row.push('R+')
            elif value < 255:
                row.push('X' + str(math.floor(value / 255 * 10)))
            else:
                row.push('XX')
        rows.push(' '.join(row))
    return '\n'.join(rows)


# noinspection PyUnresolvedReferences
_create_custom_cost_matrix.prototype.get = _cma_get
# noinspection PyUnresolvedReferences
_create_custom_cost_matrix.prototype.set = _cma_set
# noinspection PyUnresolvedReferences
_create_custom_cost_matrix.prototype.get_existing = _cma_get_existing
# noinspection PyUnresolvedReferences
_create_custom_cost_matrix.prototype.set_impassable = _cma_set_impassable
# noinspection PyUnresolvedReferences
_create_custom_cost_matrix.prototype.increase_at = _cma_increase_at
# noinspection PyUnresolvedReferences
_create_custom_cost_matrix.prototype.visual = _cma_visual

_COST_TYPE_EXIT_TILES = 0
_COST_TYPE_SLIGHTLY_AVOID = 1
_COST_TYPE_MAX_AVOID = 2
_COST_TYPE_AVOID_SOURCE = 4
_COST_TYPE_AVOID_CONTROLLER = 5
_COST_TYPE_AVOID_STORAGE = 6
_COST_TYPE_AVOID_EXTENSIONS = 7
COST_TYPE_CUSTOM_1 = 8
COST_TYPE_CUSTOM_2 = 9
_LINKED_SOURCE_CONSTANT_STRUCTURE_TYPE = '--linked--'


def mark_exit_tiles(matrix: CustomCostMatrix):
    plain_cost = matrix.plain_cost
    room_name = matrix.room_name

    room_x, room_y = movement.parse_room_to_xy(room_name)
    rrx = (-room_x - 1 if room_x < 0 else room_x) % 10
    rry = (-room_y - 1 if room_y < 0 else room_y) % 10
    if rrx == 0 or rry == 0:
        for x in [0, 49]:
            for y in range(0, 50):
                matrix.increase_at(x, y, _COST_TYPE_EXIT_TILES, 1 * plain_cost)
        for y in [0, 49]:
            for x in range(0, 50):
                matrix.increase_at(x, y, _COST_TYPE_EXIT_TILES, 1 * plain_cost)
    else:
        for x in [0, 49]:
            for y in range(0, 50):
                matrix.increase_at(x, y, _COST_TYPE_EXIT_TILES, 2 * plain_cost)
        for y in [0, 49]:
            for x in range(0, 50):
                matrix.increase_at(x, y, _COST_TYPE_EXIT_TILES, 2 * plain_cost)


def mark_flags(matrix: CustomCostMatrix):
    slightly_avoid = flags.find_flags(matrix.room_name, SLIGHTLY_AVOID) \
        .concat(flags.find_flags(matrix.room_name, UPGRADER_SPOT))
    if len(slightly_avoid):
        for flag in slightly_avoid:
            matrix.increase_at(flag.pos.x, flag.pos.y, _COST_TYPE_SLIGHTLY_AVOID, 2 * matrix.plain_cost)


def set_max_avoid(matrix: CustomCostMatrix, opts: Dict[str, Any]):
    if opts['max_avoid']:
        room_name = matrix.room_name
        plain_cost = matrix.plain_cost
        if matrix.room_name in opts['max_avoid']:
            print("Setting max_avoid in room {}".format(room_name))
            for x in range(0, 49):
                for y in range(0, 49):
                    matrix.increase_at(x, y, _COST_TYPE_MAX_AVOID, 20 * plain_cost)
            return True
        else:
            for direction, other_room in _.pairs(Game.map.describeExits(room_name)):
                if other_room in opts['max_avoid']:
                    print("Setting max_avoid on the {} of room {}".format(
                        {TOP: "top", BOTTOM: "bottom", LEFT: "left", RIGHT: "right"}[direction], room_name))
                    if direction == TOP:
                        for x in range(0, 49):
                            matrix.increase_at(x, 0, _COST_TYPE_MAX_AVOID, 20 * plain_cost)
                    elif direction == BOTTOM:
                        for x in range(0, 49):
                            matrix.increase_at(x, 49, _COST_TYPE_MAX_AVOID, 20 * plain_cost)
                    elif direction == LEFT:
                        for y in range(0, 49):
                            matrix.increase_at(0, y, _COST_TYPE_MAX_AVOID, 20 * plain_cost)
                    elif direction == RIGHT:
                        for y in range(0, 49):
                            matrix.increase_at(49, y, _COST_TYPE_MAX_AVOID, 20 * plain_cost)


__pragma__('fcall')


def get_default_max_ops(origin, destination, opts):
    # type: (RoomPosition, RoomPosition, Dict[str, Any]) -> int
    linear_distance = movement.chebyshev_distance_room_pos(origin, destination)
    ops = linear_distance * 200
    if opts['paved_for']:
        ops *= 5
    elif 'use_roads' not in opts or opts['use_roads']:
        ops *= 2
    return ops


def clear_cached_path(origin, destination, opts=None):
    # type: (RoomPosition, RoomPosition, Optional[Dict[str, Any]]) -> None
    key = get_global_cache_key(origin, destination, opts)
    global_cache.rem(key)


def get_room_list_from_serialized_obj(path_obj):
    # type: (Dict[str, Any]) -> List[str]
    if _path_cached_data_key_room_order in path_obj:
        return path_obj[_path_cached_data_key_room_order]
    elif _path_cached_data_key_metadata in path_obj:
        return path_obj[_path_cached_data_key_metadata].js_split(',').slice(1)
    else:
        return Object.keys(path_obj)


class HoneyTrails:
    """
    :type hive: empire.hive.HiveMind
    """

    def __init__(self, hive: HiveMind):
        self.hive = hive

    def _new_cost_matrix(self, room_name, origin, destination, opts):
        # type: (str, RoomPosition, RoomPosition, Dict[str, Any]) -> Union[PathFinder.CostMatrix, bool]
        paved_for = opts['paved_for']

        room_data = stored_data.get_data(room_name)
        room = self.hive.get_room(room_name)

        sk_ok = not not opts['sk_ok']

        if room_data and room_data.owner:
            if room_data.owner.state is StoredEnemyRoomState.FULLY_FUNCTIONAL:
                if room_name != origin.roomName and room_name != destination.roomName:
                    if opts['enemy_ok']:
                        print('[honey] Avoiding fully functional enemy room {}!'
                              .format(room_name))
                    # print("[honey] Avoiding room {}.".format(room_name))
                    return False
                else:
                    print("[honey] Warning: path {}-{} ends up in an enemy room ({}, {})!"
                          .format(origin, destination, room_data.owner.name, room_name))
            elif not opts['enemy_ok'] and room_data.owner.state is StoredEnemyRoomState.RESERVED \
                    and not Memory.meta.friends.includes(room_data.owner.name.lower()):
                if room_name != origin.roomName and room_name != destination.roomName:
                    # print("[honey] Avoiding room {}.".format(room_name))
                    return False
                else:
                    print("[honey] Warning: path {}-{} ends up in a friendly mining room ({})!"
                          .format(origin, destination, room_name))
            elif not opts['enemy_ok'] and room_data.owner.state is StoredEnemyRoomState.JUST_MINING:
                print("[honey] Warning: path {}-{} may pass through {}'s mining room, {}"
                      .format(origin, destination, room_data.owner.name, room_name))
            if room_data.owner and room_data.owner.state is StoredEnemyRoomState.JUST_MINING \
                    and Memory.meta.friends.includes(room_data.owner.name.lower()):
                print("[honey] Enabling moving close to SK mines in {} (mining room of {})"
                      .format(room_name, room_data.owner.name))
                sk_ok = True
        elif room and room.enemy:
            # TODO: add the granularity we have above down here.
            if room_name != origin.roomName and room_name != destination.roomName:
                if opts['enemy_ok']:
                    print('[honey] Avoiding fully functional enemy room {}!'
                          .format(room_name))
                # print("[honey] Avoiding room {}.".format(room_name))
                return False
            else:
                print("[honey] Warning: path {}-{} ends up in an enemy room ({})!"
                      .format(origin, destination, room_name))
        if room_data and room_data.avoid_always:
            print("[honey] Manually avoiding room {} marked as always avoid.".format(room_name))
            return False

        plain_cost = opts['plain_cost'] or 1
        swamp_cost = opts['swamp_cost'] or 5
        min_cost = opts['min_cost'] or 1

        matrix = create_custom_cost_matrix(room_name, plain_cost, swamp_cost, min_cost, opts.debug_output)

        if not room and not room_data:
            mark_exit_tiles(matrix)
            mark_flags(matrix)
            set_max_avoid(matrix, opts)
            return matrix.cost_matrix

        if room and room.my:
            spawn_fill_wait_flags = flags.find_flags(room, SPAWN_FILL_WAIT)
            if len(spawn_fill_wait_flags):
                avoid_extensions = False
            else:
                avoid_extensions = True
                if destination.roomName == room_name:
                    for s in cast(List[Structure], room.look_at(LOOK_STRUCTURES, destination)):
                        if s.structureType == STRUCTURE_SPAWN or s.structureType == STRUCTURE_EXTENSION:
                            avoid_extensions = False
            upgrader_wait_flags = flags.find_flags(room, UPGRADER_SPOT)
            if len(upgrader_wait_flags):
                avoid_controller = False
            else:
                avoid_controller = True
            avoid_controller_slightly = False
            probably_mining = True
        else:
            avoid_extensions = False
            spawn_fill_wait_flags = []
            avoid_controller = False
            upgrader_wait_flags = []
            if room_data and room_data.reservation_end > Game.time:
                avoid_controller_slightly = True
            else:
                avoid_controller_slightly = False
            if room and _.some(room.find(FIND_MY_CREEPS), lambda c: c.memory.role == role_miner):
                probably_mining = True
            else:
                probably_mining = False

        mark_exit_tiles(matrix)
        mark_flags(matrix)

        if set_max_avoid(matrix, opts):
            return matrix.cost_matrix

        is_origin_room = room_name == origin.roomName
        is_dest_room = room_name == destination.roomName

        # IGNORE: Rampart that's mine, container
        def set_matrix(x, y, stored_type, planned, structure_type):
            if stored_type == StoredObstacleType.ROAD:
                if paved_for:
                    if not planned:
                        existing = matrix.get_existing(x, y)
                        if 1 < existing < 255:
                            matrix.set(x, y, existing - 1)
                else:
                    existing = matrix.get(x, y)
                    if existing != 0 and existing > plain_cost:
                        # manually set
                        matrix.set(x, y, existing - plain_cost)
                    else:
                        matrix.set(x, y, 1)
                return

            if is_dest_room and x == destination.x and y == destination.y:
                return
            if is_origin_room and x == origin.x and y == origin.y:
                return
            matrix.set_impassable(x, y)
            if stored_type == StoredObstacleType.CONTROLLER:
                if avoid_controller:
                    for xx in range(x - 1, x + 1):
                        for yy in range(y - 1, y + 1):
                            matrix.increase_at(xx, yy, _COST_TYPE_AVOID_CONTROLLER, 10 * plain_cost)
                    for xx in range(x - 3, x + 4):
                        for yy in range(y - 3, y + 4):
                            matrix.increase_at(xx, yy, _COST_TYPE_AVOID_CONTROLLER, 8 * plain_cost)
                elif avoid_controller_slightly:
                    for xx in range(x - 1, x + 1):
                        for yy in range(y - 1, y + 1):
                            matrix.increase_at(xx, yy, _COST_TYPE_AVOID_CONTROLLER, 10 * plain_cost)
                return
            if stored_type == StoredObstacleType.SOURCE:
                if probably_mining:
                    for xx in range(x - 1, x + 2):
                        for yy in range(y - 1, y + 2):
                            matrix.increase_at(xx, yy, _COST_TYPE_AVOID_SOURCE, 10 * plain_cost)
                    if paved_for and structure_type != _LINKED_SOURCE_CONSTANT_STRUCTURE_TYPE:
                        if room and room.my:
                            for xx in range(x - 2, x + 3):
                                for yy in range(y - 2, y + 3):
                                    matrix.increase_at(xx, yy, _COST_TYPE_AVOID_SOURCE, 6 * plain_cost)
                        else:
                            for xx in range(x - 3, x + 4):
                                for yy in range(y - 3, y + 4):
                                    matrix.increase_at(xx, yy, _COST_TYPE_AVOID_SOURCE, 6 * plain_cost)
                return

            if not sk_ok and (stored_type == StoredObstacleType.SOURCE_KEEPER_SOURCE
                              or stored_type == StoredObstacleType.SOURCE_KEEPER_MINERAL
                              or stored_type == StoredObstacleType.SOURCE_KEEPER_LAIR):
                for xx in range(x - 4, x + 5):
                    for yy in range(y - 4, y + 5):
                        matrix.set_impassable(xx, yy)
                return

            if structure_type:
                if (structure_type == STRUCTURE_STORAGE or structure_type == STRUCTURE_LINK
                    or structure_type == STRUCTURE_LAB or structure_type == STRUCTURE_TERMINAL) \
                        and not paved_for:
                    if (not is_dest_room or abs(x - destination.x) > 3 or abs(y - destination.y) > 3) \
                            and (not is_origin_room or abs(x - origin.x) > 3 or abs(y - origin.y) > 3):
                        for xx in range(x - 1, x + 2):
                            for yy in range(y - 1, y + 2):
                                matrix.increase_at(xx, yy, _COST_TYPE_AVOID_STORAGE, 2 * plain_cost)
                elif avoid_extensions and (stored_type == STRUCTURE_SPAWN or stored_type == STRUCTURE_EXTENSION):
                    for xx in range(x - 1, x + 2):
                        for yy in range(y - 1, y + 2):
                            matrix.increase_at(xx, yy, _COST_TYPE_AVOID_EXTENSIONS, 6 * plain_cost)

        # Use data even if we have vision, to avoid extra find calls
        if room and (room.my or probably_mining or paved_for or not room_data):
            any_lairs = False
            for struct in cast(List[Structure], room.find(FIND_STRUCTURES)):
                structure_type = struct.structureType
                if structure_type == STRUCTURE_CONTAINER or (structure_type == STRUCTURE_RAMPART
                                                             and cast(StructureRampart, struct).my):
                    continue
                elif structure_type == STRUCTURE_ROAD:
                    sstype = StoredObstacleType.ROAD
                elif structure_type == STRUCTURE_CONTROLLER:
                    sstype = StoredObstacleType.CONTROLLER
                elif structure_type == STRUCTURE_KEEPER_LAIR:
                    sstype = StoredObstacleType.SOURCE_KEEPER_LAIR
                    any_lairs = True
                else:
                    sstype = StoredObstacleType.OTHER_IMPASSABLE
                set_matrix(struct.pos.x, struct.pos.y, sstype, False, structure_type)
            for site in cast(List[ConstructionSite], room.find(FIND_MY_CONSTRUCTION_SITES)):
                structure_type = site.structureType
                if structure_type == STRUCTURE_CONTAINER or structure_type == STRUCTURE_RAMPART:
                    continue
                elif structure_type == STRUCTURE_ROAD:
                    sstype = StoredObstacleType.ROAD
                else:
                    sstype = StoredObstacleType.OTHER_IMPASSABLE
                set_matrix(site.pos.x, site.pos.y, sstype, True, structure_type)
            if room.my:
                for flag, flag_type in flags.find_by_main_with_sub(room, flags.MAIN_BUILD):
                    structure_type = flags.flag_sub_to_structure_type[flag_type]
                    if structure_type == STRUCTURE_CONTAINER or structure_type == STRUCTURE_RAMPART \
                            or structure_type == STRUCTURE_ROAD:
                        continue
                    set_matrix(struct.pos.x, struct.pos.y, StoredObstacleType.OTHER_IMPASSABLE, True, structure_type)
            for source in room.find(FIND_SOURCES):
                if any_lairs:
                    set_matrix(source.pos.x, source.pos.y, StoredObstacleType.SOURCE_KEEPER_SOURCE, False, None)
                elif room.my and room.mining.is_mine_linked(source):
                    set_matrix(source.pos.x, source.pos.y, StoredObstacleType.SOURCE, False,
                               _LINKED_SOURCE_CONSTANT_STRUCTURE_TYPE)
                else:
                    set_matrix(source.pos.x, source.pos.y, StoredObstacleType.SOURCE, False, None)
            for mineral in room.find(FIND_MINERALS):
                if any_lairs:
                    set_matrix(mineral.pos.x, mineral.pos.y, StoredObstacleType.SOURCE_KEEPER_MINERAL, False, None)
                else:
                    set_matrix(mineral.pos.x, mineral.pos.y, StoredObstacleType.MINERAL, False, None)
            for flag in spawn_fill_wait_flags:
                matrix.set_impassable(flag.pos.x, flag.pos.y)
            controller = room.room.controller
            if not controller or destination.roomName != room_name \
                    or destination.x != controller.pos.x or destination.y != controller.pos.y:
                for flag in upgrader_wait_flags:
                    matrix.set_impassable(flag.pos.x, flag.pos.y)
            # Link manager creep position
            if room.my and room.room.storage and room.links.main_link:
                ml = room.links.main_link
                storage = room.room.storage
                if ml.pos.x == storage.pos.x and abs(ml.pos.y - storage.pos.y) == 2 \
                        and movement.is_block_empty(room, ml.pos.x, int((ml.pos.y + storage.pos.y) / 2)):
                    matrix.set_impassable(ml.pos.x, int((ml.pos.y + storage.pos.y) / 2))
                elif ml.pos.y == storage.pos.y and abs(ml.pos.x - storage.pos.x) == 2 \
                        and movement.is_block_empty(room, int((ml.pos.x + storage.pos.x) / 2), ml.pos.y):
                    matrix.set_impassable(int((ml.pos.x + storage.pos.x) / 2), ml.pos.y)
                else:
                    for sxx in range(ml.pos.x - 1, ml.pos.x + 2):
                        for syy in range(ml.pos.y - 1, ml.pos.y + 2):
                            if abs(storage.pos.x - sxx) <= 1 and abs(storage.pos.y - syy) <= 1:
                                matrix.set_impassable(sxx, syy)

        else:
            for stored_struct in room_data.obstacles:
                set_matrix(stored_struct.x, stored_struct.y, stored_struct.type, False, None)

        if paved_for:
            mining_paths.set_decreasing_cost_matrix_costs(
                room_name,
                paved_for,
                matrix.cost_matrix,
                plain_cost,
                swamp_cost,
                min_cost,
            )
        if opts.debug_visual:
            print('visual debug\n\n' + matrix.visual())
        return matrix.cost_matrix

    def _get_callback(self, origin, destination, opts):
        # type: (RoomPosition, RoomPosition, Dict[str, Any]) -> Callable[[str], Union[PathFinder.CostMatrix, bool]]
        return lambda room_name: self._new_cost_matrix(room_name, origin, destination, opts)

    def _get_raw_path(self, origin, destination, opts=None):
        # type: (RoomPosition, RoomPosition, Optional[Dict[str, Any]]) -> List[RoomPosition]

        if opts:
            roads_better = opts["use_roads"] if "use_roads" in opts else True
            ignore_swamp = opts["ignore_swamp"] if "ignore_swamp" in opts else False
            pf_range = opts["range"] if "range" in opts else 1
            paved_for = opts['paved_for'] if 'paved_for' in opts else None
            max_ops = opts["max_ops"] if "max_ops" in opts else get_default_max_ops(origin, destination, opts)
            max_rooms = opts["max_rooms"] if "max_rooms" in opts else 16
            max_avoid = opts["avoid_rooms"] if "avoid_rooms" in opts else None
            heuristic_attempt_num = opts["heuristic_attempt_num"] if "heuristic_attempt_num" in opts else 0
            sk_ok = opts["sk_ok"] if "sk_ok" in opts else False
        else:
            roads_better = True
            ignore_swamp = False
            pf_range = 1
            max_rooms = 16
            paved_for = None
            max_ops = get_default_max_ops(origin, destination, {'use_roads': roads_better})
            max_avoid = None
            heuristic_attempt_num = 0
            sk_ok = False

        if 'reroute' in Game.flags and 'reroute_destination' in Game.flags:
            reroute_start = Game.flags['reroute'].pos
            reroute_destination = Game.flags['reroute_destination'].pos
            if movement.chebyshev_distance_room_pos(origin, reroute_start) \
                    + movement.chebyshev_distance_room_pos(reroute_destination, destination) \
                    < movement.chebyshev_distance_room_pos(origin, destination):
                # Let's path through the portal!
                origin_opts = Object.create(opts)
                origin_opts.range = 1
                path1 = self._get_raw_path(origin, reroute_start, origin_opts)
                if not len(path1) or (not path1[len(path1) - 1].isEqualTo(reroute_start)):
                    pos = __new__(RoomPosition(reroute_start.x, reroute_start.y, reroute_start.roomName))
                    pos.end_of_reroute = True
                    path1.push(pos)
                else:
                    path1[len(path1) - 1].end_of_reroute = True
                path1.push(reroute_destination)
                path2 = self._get_raw_path(reroute_destination, destination, opts)
                return path1.concat(path2)

        if paved_for:
            plain_cost = 20
            swamp_cost = 40
            heuristic = 18
            min_cost = 15
        elif ignore_swamp:
            plain_cost = 1
            swamp_cost = 1
            heuristic = 1.2
            min_cost = 1
        elif roads_better:
            plain_cost = 2
            swamp_cost = 10
            heuristic = 1.2
            min_cost = 1
        else:
            plain_cost = 1
            swamp_cost = 5
            heuristic = 1.2
            min_cost = 1

        if heuristic_attempt_num == 1:
            heuristic *= 3
        elif heuristic_attempt_num == 2:
            heuristic /= 3

        destination_data = stored_data.get_data(destination.roomName)
        if destination_data and destination_data.owner \
                and destination_data.owner.state != StoredEnemyRoomState.JUST_MINING:
            enemy_ok = True
            print("[honey] Calculating path assuming traversing enemy rooms is OK, as {} is an enemy room."
                  .format(destination.roomName))
        else:
            enemy_ok = False

        if not isinstance(origin, RoomPosition):
            try:
                to_str = str(origin)
            except:
                to_str = "<non-displayable>"
            raise AssertionError("Struct {} is not a room position! ({})".format(to_str, JSON.stringify(origin)))
        if not isinstance(destination, RoomPosition):
            try:
                to_str = str(destination)
            except:
                to_str = "<non-displayable>"
            raise AssertionError("Struct {} is not a room position! ({})".format(to_str, JSON.stringify(destination)))

        result = PathFinder.search(origin, {"pos": destination, "range": pf_range}, {
            "plainCost": plain_cost,
            "swampCost": swamp_cost,
            "roomCallback": self._get_callback(origin, destination, {
                "roads": roads_better,
                "paved_for": paved_for,
                "max_avoid": max_avoid,
                "plain_cost": plain_cost,
                "swamp_cost": swamp_cost,
                "min_cost": min_cost,
                "enemy_ok": enemy_ok,
                "sk_ok": sk_ok,
            }),
            "maxRooms": max_rooms,
            "maxOps": max_ops,
            "heuristicWeight": heuristic,
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
                path = path_start.concat(second_path_result.path)
                if second_path_result.incomplete:
                    second_midpoint = path[len(path) - 1]
                    print("[honey] Second path result incomplete, trying third from {} to {}, starting at {}."
                          .format(origin, destination, midpoint))

                    third_path_result = PathFinder.search(second_midpoint, {"pos": destination, "range": pf_range}, {
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
                    path = path.concat(third_path_result.path)
                    if third_path_result.incomplete:
                        if heuristic_attempt_num < 3:
                            print("[honey] Third path still incomplete! Trying next heuristic attempt ({})."
                                  .format(heuristic_attempt_num + 1))
                            return self._get_raw_path(origin, destination, _.create(opts, {
                                'heuristic_attempt_num': heuristic_attempt_num + 1
                            }))
                        else:
                            print("[honey] Third path still incomplete! Still concatenating.")
                else:
                    print("[honey] Second path result complete! Concatenating paths!")
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
        # type: (RoomPosition, RoomPosition, Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]

        origin = robjs.pos(origin)
        destination = robjs.pos(destination)

        if opts and 'keep_for' in opts:
            keep_for = opts["keep_for"]
        else:
            keep_for = 0

        cache_key = get_global_cache_key(origin, destination, opts)

        serialized_path_obj = global_cache.get(cache_key)
        if serialized_path_obj is not None:
            return serialized_path_obj

        if Game.cpu.getUsed() > 300:
            serialized_path_obj = global_cache.get_100_slack(cache_key)
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
            if room_name == _path_cached_data_key_metadata:
                serialized_path_obj[room_name] = room_to_path_obj[room_name]
            else:
                serialized_path_obj[room_name] = Room.serializePath(room_to_path_obj[room_name])
        global_cache.set(cache_key, serialized_path_obj, keep_for)
        return serialized_path_obj

    def completely_repath_and_get_raw_path(self, origin, destination, opts):
        # type: (RoomPosition, RoomPosition, Dict[str, Any]) -> List[RoomPosition]
        origin = robjs.pos(origin)
        destination = robjs.pos(destination)

        if "keep_for" in opts:
            keep_for = opts["keep_for"]
        else:
            raise AssertionError("force_complete_repath_and_get_raw_path requires an options object with a"
                                 " keep_for property")

        cache_key = get_global_cache_key(origin, destination, opts)

        path = self._get_raw_path(origin, destination, opts)
        room_to_path_obj = pathfinder_path_to_room_to_path_obj(origin, path)
        if room_to_path_obj is not None:
            serialized_path_obj = {}
            for room_name in Object.keys(room_to_path_obj):
                if room_name == _path_cached_data_key_metadata:
                    serialized_path_obj[room_name] = room_to_path_obj[room_name]
                else:
                    serialized_path_obj[room_name] = Room.serializePath(room_to_path_obj[room_name])
            global_cache.set(cache_key, serialized_path_obj, keep_for)
        return path

    def find_serialized_path(self, origin, destination, opts):
        # type: (RoomPosition, RoomPosition, Dict[str, Any]) -> Optional[str]
        origin = robjs.pos(origin)
        destination = robjs.pos(destination)

        if opts and "current_room" in opts:
            current_room = opts["current_room"]
            if current_room:
                current_room = current_room.name or current_room
            else:
                raise AssertionError("find_serialized_path requires a current_room argument.")
        else:
            raise AssertionError("find_serialized_path requires a current_room argument.")

        serialized_path_obj = self.get_serialized_path_obj(origin, destination, opts)

        if serialized_path_obj is not None and current_room in serialized_path_obj:
            return serialized_path_obj[current_room]
        else:
            return ''

    def find_path(self, origin, destination, opts):
        # type: (RoomPosition, RoomPosition, Dict[str, Any]) -> List[_PathPos]
        origin = robjs.pos(origin)
        destination = robjs.pos(destination)

        if "current_room" in opts:
            current_room = opts["current_room"]
            if current_room:
                current_room = current_room.name or current_room
            else:
                raise AssertionError("find_path requires a current_room argument.")
        else:
            raise AssertionError("find_path requires a current_room argument.")

        serialized_path_obj = self.get_serialized_path_obj(origin, destination, opts)

        if serialized_path_obj is None or current_room not in serialized_path_obj:
            return []
        try:
            path = Room.deserializePath(serialized_path_obj[current_room])
        except:
            print("[honey] Serialized path from {} to {} with current-room {} was invalid.".format(
                origin, destination, current_room))
            clear_cached_path(origin, destination, opts)
            new_path_obj = self.get_serialized_path_obj(origin, destination, opts)
            if current_room in new_path_obj:
                path = Room.deserializePath(new_path_obj[current_room])
            else:
                return []

        return path

    def list_of_room_positions_in_path(self, origin, destination, opts=None):
        # type: (RoomPosition, RoomPosition, Optional[Dict[str, Any]]) -> List[RoomPosition]
        """
        Gets a list of room positions in the path, with guaranteed order. This is retrieved from cached memory, but a
        new list to return is created each call, and each RoomPosition is created fresh each call.
        """
        origin = robjs.pos(origin)
        destination = robjs.pos(destination)

        path_obj = self.get_serialized_path_obj(origin, destination, opts)

        final_list = []

        list_of_names = get_room_list_from_serialized_obj(path_obj)

        for room_name in list_of_names:
            if not movement.is_valid_room_name(room_name):  # special key
                continue
            path = Room.deserializePath(path_obj[room_name])
            for pos in path:
                if 0 < pos.x < 50 and 0 < pos.y < 50:
                    final_list.append(__new__(RoomPosition(pos.x, pos.y, room_name)))
        return final_list

    def get_ordered_list_of_serialized_path_segments(self, origin, destination, opts=None):
        # type: (RoomPosition, RoomPosition, Optional[Dict[str, Any]]) -> List[Tuple[str, str]]
        """
        Gets a list of serialized path segments in order for the path from origin to destination.
        :rtype: list[(str, str)]
        """
        origin = robjs.pos(origin)
        destination = robjs.pos(destination)

        path_obj = self.get_serialized_path_obj(origin, destination, opts)

        result = []

        list_of_names = get_room_list_from_serialized_obj(path_obj)

        for room_name in list_of_names:
            if not movement.is_valid_room_name(room_name):  # special key
                continue
            result.append((room_name, path_obj[room_name]))
        return result

    def find_path_length(self, origin, destination, opts=None):
        # type: (RoomPosition, RoomPosition, Optional[Dict[str, Any]]) -> int
        origin = robjs.pos(origin)
        destination = robjs.pos(destination)

        serialized_path_obj = self.get_serialized_path_obj(origin, destination, opts)
        # TODO: should be we accounting for the path containing two position in the case of edge positions? yes!

        if not serialized_path_obj:
            return 1
        if _path_cached_data_key_metadata in serialized_path_obj:  # Version 3 stored path
            return int(serialized_path_obj[_path_cached_data_key_metadata].js_split(',')[0])
        if _path_cached_data_key_full_path in serialized_path_obj:  # Version 1 stored path
            # return len(serialized_path_obj['full'])   # The length of the path
            #  - 4 + 1                                  # The first four characters only represent one position
            #  - (
            # len(Object.keys(serialized_path_obj))     # On each room edge, creeps moving along the path skip one
            #                                           # square
            # - 1)                                      # -1 because we want the count of room _exits_, which is one
            #                                           # less than the room count.
            return len(serialized_path_obj[_path_cached_data_key_full_path]) \
                   - _.sum(Object.keys(serialized_path_obj), lambda n: movement.is_valid_room_name(n)) - 2
        elif _path_cached_data_key_length in serialized_path_obj:  # Version two stored path
            return cast(int, serialized_path_obj[_path_cached_data_key_length])
        else:  # Unknown format, let's just guesstimate
            total = 1
            for room_name in Object.keys(serialized_path_obj):
                if movement.is_valid_room_name(room_name):
                    # first 4 characters represent 1 position, but also each exit position is doubled per-room
                    # -4 + 1 - 1
                    total += len(serialized_path_obj[room_name]) - 4
            return total


__pragma__('nofcall')
