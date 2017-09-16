"""
Portals: useful functions.
"""
from typing import Dict, List, Optional, Tuple, Union

from constants.memkeys import portal_segment_data_key_destination_room_name, portal_segment_data_key_xy_pairs
from empire import stored_data
from jstools.screeps import *
from utilities import movement, positions, robjs

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def portals_near(room_name: str) -> List[Tuple[str, Dict[str, Union[str, int]]]]:
    portal_data = stored_data.portal_info()
    result = []
    for center in movement.sector_centers_near(room_name):
        if center in portal_data:
            result.append((center, portal_data[center]))
    for odd_name in stored_data.odd_portal_rooms():
        if odd_name in portal_data and movement.room_chebyshev_distance(room_name, odd_name) < 10:
            result.append((odd_name, portal_data[odd_name]))
    return result


def recommended_reroute(origin: RoomPosition, destination: RoomPosition) -> Optional[Tuple[RoomPosition, RoomPosition]]:
    path_len = movement.room_chebyshev_distance(origin.roomName, destination.roomName)
    if path_len < 5:
        return None

    reroute = None  # type: Optional[Tuple[str, Dict[str, Union[str, int]]]]
    for origin_portal_room, portal_data in portals_near(origin.roomName):
        destination_portal_room = portal_data[portal_segment_data_key_destination_room_name]
        trying_len = (
            movement.room_chebyshev_distance(origin.roomName, origin_portal_room)
            + movement.room_chebyshev_distance(destination_portal_room, destination.roomName)
        )
        if trying_len < path_len:
            path_len = trying_len
            reroute = (origin_portal_room, portal_data)
    if reroute is None:
        return None
    origin_portal_room, portal_data = reroute
    destination_portal_room = portal_data[portal_segment_data_key_destination_room_name]
    xys_encoded = portal_data[portal_segment_data_key_xy_pairs]
    origin_x, origin_y = positions.deserialize_xy(int(robjs.get_str_codepoint(xys_encoded, 0)))
    destination_x, destination_y = positions.deserialize_xy(int(robjs.get_str_codepoint(xys_encoded, 1)))
    reroute_start = __new__(RoomPosition(origin_x, origin_y, origin_portal_room))
    reroute_end = __new__(RoomPosition(destination_x, destination_y, destination_portal_room))
    return reroute_start, reroute_end
