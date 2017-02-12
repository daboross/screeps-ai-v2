from creep_management import mining_paths
from jstools import js_visuals
from jstools.screeps import *
from utilities import positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def visualize_room(room_name):
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
