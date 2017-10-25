from typing import Callable, List, TYPE_CHECKING, cast

from empire import stored_data
from jstools.js_set_map import new_map
from jstools.screeps import *
from utilities import movement

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


def visit_room_graph(center_room: str, max_distance: int, visitor: Callable[[str], bool]):
    """
    Visits each room from the center room outwards by calling the visitor function.

    Will end exploring from a given room if visitor returns false - but will continue to explore other paths until
    all paths end with visitor returning false.
    """
    visited = new_map()

    def visit_with_neighbors(room_name: str, time_left_now: int):
        already_visited_here = False
        if visited.has(room_name):
            already_visited_here = True
            last_time_left = visited.get(room_name)
            if last_time_left < 0 or last_time_left >= time_left_now:
                return

        visited.set(room_name, time_left_now)

        if not already_visited_here:
            continuing = visitor(room_name)
            if not continuing:
                visited.set(room_name, -1)
                return

        time_left_after_this_room = time_left_now - 50
        if time_left_after_this_room > 0:
            exits = Game.map.describeExits(room_name)
            for room_key in _.shuffle(Object.keys(exits)):
                next_room = exits[room_key]
                visit_with_neighbors(next_room, time_left_after_this_room)

    visit_with_neighbors(center_room, max_distance)


def hostiles() -> List[str]:
    """
    Finds hostile rooms
    :return:
    """
    hive = cast(HiveMind, js_global.py.hive())

    result = []

    def visitor(room_name: str) -> bool:
        data = stored_data.get_data(room_name)
        if not data:
            return False
        if data.owner and data.owner.state == StoredEnemyRoomState.FULLY_FUNCTIONAL \
                and not Memory.meta.friends.includes(data.owner.name) \
                and data.owner.name != stored_data.get_my_username():
            result.append(room_name)
        return True

    for room in hive.my_rooms:
        visit_room_graph(room.name, CREEP_LIFE_TIME, visitor)

    return result


def leftovers() -> str:
    """
    Finds rooms with leftover structures
    """
    hive = cast(HiveMind, js_global.py.hive())

    result_str = []
    result_here = []

    def visitor(room_name: str) -> bool:
        data = stored_data.get_data(room_name)
        room = hive.get_room(room_name)
        if not data:
            return False
        if data.owner and data.owner.state != StoredEnemyRoomState.OWNED_DEAD \
                and data.owner.name != stored_data.get_my_username():
            return False
        if movement.is_room_exact_center_of_sector(room_name) or movement.is_room_inner_circle_of_sector(room_name)\
                or movement.is_room_highway(room_name):
            return False
        if (not data.owner or data.owner.state == StoredEnemyRoomState.OWNED_DEAD) \
                and (not room or not room.my):
            any_structures = False
            for obstacle in data.obstacles:
                if obstacle.type == StoredObstacleType.OTHER_IMPASSABLE:
                    any_structures = True
            if any_structures:
                result_here.append(room_name)
        return True

    for room in hive.my_rooms:
        visit_room_graph(room.name, CREEP_CLAIM_LIFE_TIME, visitor)
        result_str.append("{}:\n\t{}"
                          .format(room.name, ' '.join(result_here)))
        result_here = []

    return '\n'.join(result_str)
