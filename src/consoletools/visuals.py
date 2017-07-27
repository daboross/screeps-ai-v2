from typing import TYPE_CHECKING

from constants import rmem_key_currently_under_siege
from creep_management import mining_paths
from jstools import js_visuals
from jstools.screeps import *
from utilities import positions

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


def visualize_room(hive, room_name):
    # type: (HiveMind, str) -> None
    """
    :type hive: empire.hive.HiveMind
    :type room_name: str
    """
    js_visuals.clear(room_name)
    path_colors = ['#6AB4FF', '#A4B227', '#EDFF51', '#CC362C', '#B2615B']
    next_color = 0
    path_list = mining_paths.list_of_paths_with_metadata(room_name)
    for path in _.sortBy(path_list):
        points = []
        path = path[path.codePointAt(0):]
        for i in range(0, len(path)):
            xy = path.codePointAt(i)
            x, y = positions.deserialize_xy(xy)
            points.append([x, y])
        color = path_colors[next_color]
        next_color = (next_color + 1) % len(path_colors)
        js_visuals.poly(room_name, points, {
            'stroke': color,
            'opacity': 0.3,
            'strokeWidth': 0.2,
        })

    room = hive.get_room(room_name)
    if room and room.my and room.mem[rmem_key_currently_under_siege]:
        js_visuals.text(room_name, 5, 45, "under attack", {
            'color': '#AA0114',
            'size': 1.0,
            'opacity': 0.8,
        })
        hot, cold = room.defense.get_current_defender_spots()
        for spot in hot:
            js_visuals.circle(room_name, spot.x, spot.y, {
                'radius': 2.0,
                'fill': '#AA0114',
                'opacity': 0.2,
            })
            js_visuals.circle(room_name, spot.x, spot.y, {
                'radius': 4.0,
                'fill': '#AA0114',
                'opacity': 0.2,
            })
        for spot in cold:
            js_visuals.circle(room_name, spot.x, spot.y, {
                'radius': 2.0,
                'fill': '00B7EB',
                'opacity': 0.2,
            })
            js_visuals.circle(room_name, spot.x, spot.y, {
                'radius': 4.0,
                'fill': '#00B7EB',
                'opacity': 0.2,
            })
