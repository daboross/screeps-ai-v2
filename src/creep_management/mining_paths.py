from typing import List, Optional, TYPE_CHECKING, Tuple, Union, cast

from constants import gmem_key_room_mining_paths
from jstools.js_set_map import new_map, new_set
from jstools.screeps import *

if TYPE_CHECKING:
    from empire.hive import HiveMind
    from jstools.js_set_map import JSSet, JSMap

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

no_spawn_name_name = 'none'


def _get_mem():
    # type: () -> _Memory
    """
    Gets the mining_paths globally stored memory.

    The memory format is an object of room name -> stored paths/data points.

    For each room name, there is a list of 'paths' that go through it. Each 'path' is a string which is encoded using
    String.fromCodePoint and string.codePointAt. At the start of the path are 2 code points indicating the total
    key length of the mine name / spawn name + 2, and the second indicating just the length of the mine name.

    This is optimized so that in order to 'just' get the path values, you can do data = data[data.codePointAt(0):].

    To get the mine name and spawn id, you can do name_data = data[2:data(0)];
        mine_name = name_data[:data.codePointAt(1)];
        spawn_id = name_data[data.codePointAt(1):];

    After the mine/spawn name, the rest of the data is individual room positions encoded as (pos.x | pos.y << 6).

    To decode, simply do xy = data.codePointAt(index); x = xy & 0x3F; y = xy >> 6 & 0x3F.
    :return:
    """
    if gmem_key_room_mining_paths in Memory:
        return Memory[gmem_key_room_mining_paths]
    else:
        mem = Memory[gmem_key_room_mining_paths] = {}
        return cast(_Memory, mem)


_MineData = Union[Flag, Tuple[Flag, StructureSpawn]]


def _parse_mine_data(mine_data):
    # type: (_MineData) -> Tuple[Optional[str], Optional[str]]
    """
    Gets a mine_name and spawn_id from a mine_data array or object. mine_data may either be a Flag with a name property,
    or an array containing a Flag and a StructureSpawn.

    If no spawn is passed in, spawn_id will be equal to the `no_spawn_name_name` constant.
    :return: [mine_name, spawn_id] or [None, None] if an error has occurred.
    """
    if _.isArray(mine_data):
        if len(mine_data) > 2 or len(mine_data) < 1 \
                or not mine_data[0].name or (mine_data[1] and not mine_data[1].id):
            msg = (
                "[mining_paths] WARNING: Unknown kind of mine data: {} ({}, {})"
                    .format(JSON.stringify(mine_data), mine_data[0], mine_data[1])
            )
            print(msg)
            Game.notify(msg)
            return None, None
        mine_data = cast(Tuple[Flag, StructureSpawn], mine_data)
        mine_name = mine_data[0].name
        spawn_id = mine_data[1].id if mine_data[1] else no_spawn_name_name
    else:
        mine_data = cast(Flag, mine_data)
        if not mine_data.name:
            msg = ("[mining_paths] WARNING: Unknown kind of mine data: {} ({})"
                   .format(JSON.stringify(mine_data), mine_data))
            print(msg)
            Game.notify(msg)
            return None, None
        mine_name = mine_data.name
        spawn_id = no_spawn_name_name
    return mine_name, spawn_id


def register_new_mining_path(mine_data, raw_path):
    # type: (_MineData, List[RoomPosition]) -> None
    mine_name, spawn_id = _parse_mine_data(mine_data)
    if mine_name is None or spawn_id is None:
        raise ValueError("Invalid mine data ({}): no name/id".format(mine_data))
    serialized_string = []
    if len(raw_path):
        last_room = raw_path[0].roomName
        room_pos_points = {last_room: serialized_string}
        for pos in raw_path:
            if pos.roomName != last_room:
                if pos.roomName in room_pos_points:
                    serialized_string = room_pos_points[pos.roomName]
                else:
                    serialized_string = room_pos_points[pos.roomName] = []
                last_room = pos.roomName
            serialized_string.push(String.fromCodePoint(pos.x | pos.y << 6))
    else:
        room_pos_points = {}

    our_key_start = (
        String.fromCodePoint(len(mine_name) + len(spawn_id) + 2)
        + String.fromCodePoint(len(mine_name))
        + mine_name
        + spawn_id
    )
    gmem = _get_mem()
    rooms_this_is_in = Object.keys(room_pos_points)
    for room_name in rooms_this_is_in:
        our_data = our_key_start + ''.join(room_pos_points[room_name])
        if room_name in gmem:
            data_array = gmem[room_name]
            _.remove(data_array, lambda x: x.startsWith(our_key_start))
            data_array.push(our_data)
        else:
            gmem[room_name] = [our_data]
    # Remove old parts of the path from rooms that we're not in
    #  (we've already updated all the ones the new path is in above)
    for room_name in Object.keys(gmem):
        if not rooms_this_is_in.includes(room_name):
            data_list = gmem[room_name]
            _.remove(data_list, lambda x: x.startsWith(our_key_start))
            if not len(data_list):
                del gmem[room_name]


def get_set_of_all_serialized_positions_in(room_name):
    # type: (str) -> JSSet[int]
    """
    Gets a set containing the serialized (xy) integers for each position with a planned road.

    :param room_name: The room name
    :return: The set
    :type room_name: str
    :rtype: jstools.js_set_map.JSSet
    """
    the_set = new_set()

    gmem = _get_mem()
    if room_name not in gmem:
        return the_set
    for data_string in gmem[room_name]:
        points = data_string[data_string.codePointAt(0):]
        for i in range(0, len(points)):
            xy = points.codePointAt(i)
            the_set.add(xy)
    return the_set


def usage_map_of(room_name):
    # type: (str) -> JSMap[int, int]
    """
    :type room_name: str
    :rtype: jstools.js_set_map.JSMap
    """
    map_of_values = new_map()

    gmem = _get_mem()
    if room_name not in gmem:
        return map_of_values
    for data_string in gmem[room_name]:
        points = data_string[data_string.codePointAt(0):]
        for i in range(0, len(points)):
            xy = points.codePointAt(i)
            if map_of_values.has(xy):
                map_of_values.set(xy, map_of_values.get(xy) + 1)
            else:
                map_of_values.set(xy, 1)
    return map_of_values


def list_of_paths_with_metadata(room_name):
    # type: (str) -> _MemoryValue
    gmem = _get_mem()
    if room_name not in gmem:
        return []
    return gmem[room_name]


def debug_str(room_name):
    # type: (str) -> str
    """
    :type room_name: str
    :rtype: str
    """

    gmem = _get_mem()
    if room_name not in gmem:
        return 'no paths through {}'.format(room_name)
    map_of_values = usage_map_of(room_name)
    output = []
    for y in range(0, 50):
        output.push('\n')
        for x in range(0, 50):
            xy = x | y << 6
            value = map_of_values.get(xy)
            if value:
                output.push(value)
            else:
                output.push(' ')
            output.push(' ')
        output.pop()  # remove the last space from each row
    return ''.join(output)


def set_decreasing_cost_matrix_costs(room_name, mine_path_data, cost_matrix, base_plains, base_swamp, lowest_possible):
    # type: (str, _MineData, PathFinder.CostMatrix, int, int, int) -> None
    """
    :type room_name: str
    :type mine_path_data: list[Any] | Any
    :type cost_matrix: CostMatrix
    :type base_plains: int
    :type base_swamp: int
    :type lowest_possible: int
    """
    lowest_possible = max(lowest_possible, 1)

    mine_name, spawn_id = _parse_mine_data(mine_path_data)
    if mine_name is None or spawn_id is None:
        return

    key_to_avoid = (
        String.fromCodePoint(len(mine_name) + len(spawn_id) + 2)
        + String.fromCodePoint(len(mine_name))
        + mine_name
        + spawn_id
    )

    gmem = _get_mem()
    if room_name not in gmem:
        return
    avoid_points = new_set()
    already_set_once = new_set()

    for data_string in gmem[room_name]:
        if data_string.startsWith(key_to_avoid):
            points = data_string[data_string.codePointAt(0):]
            for i in range(0, len(points)):
                xy = points.codePointAt(i)
                avoid_points.add(xy)

    for data_string in gmem[room_name]:
        if data_string.startsWith(key_to_avoid):
            continue
        points = data_string[data_string.codePointAt(0):]
        for i in range(0, len(points)):
            xy = points.codePointAt(i)
            if already_set_once.has(xy):
                continue
            elif avoid_points.has(xy):
                # Only decrease roads where we're already doing it by a maximum of 1 point
                already_set_once.add(xy)
            x = xy & 0x3F
            y = xy >> 6 & 0x3F
            existing = cost_matrix.get(x, y)
            if existing == 0:
                terrain = Game.map.getTerrainAt(x, y, room_name)
                if terrain[0] == 'p':
                    existing = base_plains
                elif terrain[0] == 's':
                    existing = base_swamp
                else:
                    continue
            if existing > lowest_possible:
                cost_matrix.set(x, y, existing - 1)


def set_slightly_increased_cost(room_name, cost_matrix, base_plains, base_swamp, increase_by):
    # type: (str, PathFinder.CostMatrix, int, int, int) -> None
    """
    Slightly increase the cost in the cost matrix for planned roads.
    :param room_name: The room
    :param cost_matrix: The cost matrix
    :param base_plains: Base plains cost
    :param base_swamp: Base swamp cost
    :param increase_by: How much to increase each by
    """
    gmem = _get_mem()
    if room_name not in gmem:
        return
    roads_added = new_set()
    for data_string in gmem[room_name]:
        points = data_string[data_string.codePointAt(0):]
        for i in range(0, len(points)):
            xy = points.codePointAt(i)
            if roads_added.has(xy):
                continue
            roads_added.add(xy)
            x = xy & 0x3F
            y = xy >> 6 & 0x3F
            existing = cost_matrix.get(x, y)
            if existing == 0:
                terrain = Game.map.getTerrainAt(x, y, room_name)
                if terrain[0] == 'p':
                    existing = base_plains
                elif terrain[0] == 's':
                    existing = base_swamp
                else:
                    continue
            cost_matrix.set(x, y, existing + increase_by)


def cleanup_old_values(hive):
    # type: (HiveMind) -> None
    """
    Fairly expensive method, as it requires calculating active mines for every owned room, and checking every room's
    stored paths.
    :type hive: empire.hive.HiveMind
    """
    active_mines = new_set()
    for room in hive.my_rooms:
        for mine in room.mining.active_mines:
            active_mines.add(mine.name)

    path_mem = _get_mem()
    for room_name in Object.keys(path_mem):
        data_list = path_mem[room_name]
        to_remove_indices = []
        for index, data_string in enumerate(data_list):
            end_of_name_data = data_string.codePointAt(0)
            mine_name_length = data_string.codePointAt(1)
            mine_name = data_string[2:2 + mine_name_length]
            spawn_id = data_string[2 + mine_name_length:end_of_name_data]
            if not active_mines.has(mine_name) or (spawn_id != no_spawn_name_name
                                                   and Game.getObjectById(spawn_id) is None):
                to_remove_indices.push(index)
                print('[mining_paths] Removing path in {} for mine: {}, spawn: {}.'
                      .format(room_name, mine_name, spawn_id))
        _.pullAt(data_list, to_remove_indices)
        if not len(data_list):
            del path_mem[room_name]
